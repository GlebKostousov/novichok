"""Проверь помощники поставки без внешней сети и зависимостей приложения."""

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_http", SCRIPTS / "check_http.py")
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class OriginTests(unittest.TestCase):
    """Отклони неоднозначный адрес перед отправкой запросов."""

    def test_valid_origin(self) -> None:
        """Сохрани схему, сервер и порт без завершающего слеша."""
        self.assertEqual(
            checker.validate_origin("http://127.0.0.1:8080/"),
            "http://127.0.0.1:8080",
        )

    def test_reject_invalid_origins(self) -> None:
        """Не допускай пароль, другой протокол и путь страницы."""
        for value in (
            "file:///tmp/file",
            "http:///",
            "https://a:b@example.com",
            "https://example.com/api",
            "https://example.com?q=1",
            "https://example.com/#part",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                checker.validate_origin(value)

    def test_duplicate_employee_ids(self) -> None:
        """Заметь повтор сотрудника внутри снимка."""
        with self.assertRaises(ValueError):
            checker.employee_ids({"employees": [{"id": "a"}, {"id": "a"}]})

    def test_wrong_response_shape(self) -> None:
        """Не принимай массив вместо объекта ответа."""
        with self.assertRaises(ValueError):
            checker.object_value([], "state")


class SmokeTests(unittest.TestCase):
    """Проверь логику помощника на контролируемых ответах, не само приложение."""

    def test_idempotent_hire(self) -> None:
        """Прими неизменившуюся версию точного повтора."""
        initial = {
            "revision": 1,
            "today": "2026-11-11",
            "departments": [{"id": "north"}],
            "employees": [{"id": "a"}],
        }
        created = {
            "revision": 2,
            "employees": [{"id": "a"}, {"id": "b"}],
            "last_event": {"outcome": "created"},
        }
        repeated = {**created, "last_event": {"outcome": "already_processed"}}
        client = checker.DemoClient("http://127.0.0.1")
        with patch.object(client, "json", side_effect=[created, repeated]):
            self.assertEqual(checker.check_hire(client, initial), repeated)

    def test_hire_duplicate_is_rejected(self) -> None:
        """Остановись, если повтор события создал лишнего сотрудника."""
        initial = {
            "revision": 1,
            "today": "2026-11-11",
            "departments": [{"id": "north"}],
            "employees": [{"id": "a"}],
        }
        created = {"revision": 2, "employees": [{"id": "a"}, {"id": "b"}]}
        repeated = {
            "revision": 3,
            "employees": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        }
        client = checker.DemoClient("http://127.0.0.1")
        with (
            patch.object(client, "json", side_effect=[created, repeated]),
            self.assertRaises(ValueError),
        ):
            checker.check_hire(client, initial)


class ConfigureTests(unittest.TestCase):
    """Проверь настоящий запуск генератора .env в отдельном каталоге."""

    def test_creates_private_env_and_preserves_existing(self) -> None:
        """Не перезаписывай пароль при повторной настройке."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            script = scripts / "configure.py"
            script.write_bytes((SCRIPTS / "configure.py").read_bytes())
            subprocess.run(
                [sys.executable, str(script)], check=True, capture_output=True
            )
            env = root / ".env"
            original = env.read_bytes()
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o600)
            else:
                self.assertTrue(os.access(env, os.R_OK | os.W_OK))
            self.assertIn(b"POSTGRES_PASSWORD=", original)
            subprocess.run(
                [sys.executable, str(script)], check=True, capture_output=True
            )
            self.assertEqual(env.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
