"""Проверь размещённое демо через HTTP в новых изолированных учебных сессиях."""

import argparse
import json
from http.cookiejar import CookieJar
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener
from uuid import uuid4

MAX_RESPONSE_BYTES = 512 * 1024


def require(condition: bool, message: str) -> None:
    """Останови проверку при нарушении ожидаемого контракта."""
    if not condition:
        raise ValueError(message)


def validate_origin(value: str) -> str:
    """Разреши только HTTP-адрес сервиса без учётных данных и пути."""
    parsed = urlsplit(value)
    require(parsed.scheme in {"http", "https"}, "Нужен адрес http:// или https://.")
    require(bool(parsed.hostname), "В адресе отсутствует имя сервера.")
    require(not (parsed.username or parsed.password), "Не передавайте пароль в URL.")
    require(parsed.path in {"", "/"}, "Укажите адрес сервиса без пути к странице.")
    require(not (parsed.query or parsed.fragment), "В адресе не нужны параметры.")
    return value.rstrip("/")


def object_value(value: object, name: str) -> dict[str, object]:
    """Потребуй объект JSON вместо непроверенного приведения типа."""
    require(isinstance(value, dict), f"Поле {name} должно быть объектом JSON.")
    return cast(dict[str, object], value)


def array_value(value: object, name: str) -> list[object]:
    """Потребуй массив JSON на границе ответа сервера."""
    require(isinstance(value, list), f"Поле {name} должно быть массивом JSON.")
    return cast(list[object], value)


def employee_ids(state: dict[str, object]) -> set[str]:
    """Получи идентификаторы сотрудников из проверенного массива."""
    values = array_value(state.get("employees"), "employees")
    result = {str(object_value(item, "employee")["id"]) for item in values}
    require(len(result) == len(values), "В ответе повторяется ID сотрудника.")
    return result


class DemoClient:
    """Храни отдельный cookie jar; не затрагивай сессию посетителя."""

    def __init__(self, origin: str) -> None:
        """Подготовь клиент со своей новой демонстрационной сессией."""
        self.origin = origin
        self.cookies = CookieJar()
        self._opener: OpenerDirector = build_opener(HTTPCookieProcessor(self.cookies))

    def read(self, path: str, payload: dict[str, object] | None = None) -> bytes:
        """Получи ограниченный ответ без вывода cookie или содержимого БД."""
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers.update(
                {
                    "Content-Type": "application/json",
                    "X-Demo-Action": "1",
                    "X-Demo-Role": "manager",
                }
            )
        request = Request(self.origin + path, data=data, headers=headers)
        with self._opener.open(request, timeout=15) as response:
            body = cast(bytes, response.read(MAX_RESPONSE_BYTES + 1))
        require(len(body) <= MAX_RESPONSE_BYTES, "Ответ превышает ограничение проверки.")
        return body

    def json(
        self, path: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        """Проверь JSON-объект успешного HTTP-ответа."""
        return object_value(json.loads(self.read(path, payload)), path)


def check_hire(client: DemoClient, state: dict[str, object]) -> dict[str, object]:
    """Создай одного вымышленного сотрудника и проверь точный повтор события."""
    departments = array_value(state.get("departments"), "departments")
    require(bool(departments), "В демо нет подразделений.")
    payload = {
        "expected_revision": state["revision"],
        "external_id": f"smoke-{uuid4().hex}",
        "full_name": "Сотрудник Проверочный",
        "department_id": object_value(departments[0], "department")["id"],
        "start_date": state["today"],
    }
    created = client.json("/api/demo/hire", payload)
    require(
        len(employee_ids(created)) == len(employee_ids(state)) + 1,
        "Выход не создал ровно одного сотрудника.",
    )
    repeated = client.json("/api/demo/hire", payload)
    require(
        employee_ids(created) == employee_ids(repeated),
        "Повтор события изменил набор сотрудников.",
    )
    require(
        created["revision"] == repeated["revision"],
        "Повтор события изменил версию.",
    )
    require(
        object_value(repeated.get("last_event"), "last_event").get("outcome")
        == "already_processed",
        "Повтор не распознан как уже обработанный.",
    )
    return repeated


def check_demo(origin: str) -> None:
    """Проверь HTML, БД, cookie, повтор события, сохранение и изоляцию."""
    client = DemoClient(origin)
    require(b'<div id="app"' in client.read("/"), "Не получен собранный интерфейс.")
    require(
        client.json("/api/health").get("status") == "ok",
        "База не прошла healthcheck.",
    )
    initial = client.json("/api/demo")
    require(bool(list(client.cookies)), "Сервер не установил cookie демосессии.")
    current = check_hire(client, initial)
    saved = client.json("/api/demo")
    require(employee_ids(saved) == employee_ids(current), "Изменение не сохранилось.")
    require(saved["revision"] == current["revision"], "Версия после чтения изменилась.")
    other = DemoClient(origin).json("/api/demo")
    require(
        employee_ids(saved).isdisjoint(employee_ids(other)),
        "Две сессии получили общих сотрудников.",
    )
    print("Пройдено: интерфейс, БД, cookie, повтор события, сохранение, изоляция.")
    print("Созданы только отдельные учебные сессии; чужие данные не изменялись.")


def main() -> int:
    """Прими адрес стенда и верни ненулевой код при любой ошибке проверки."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Адрес демо, например http://127.0.0.1:8080")
    try:
        check_demo(validate_origin(parser.parse_args().url))
    except HTTPError as error:
        print(f"Проверка не пройдена: сервер вернул HTTP {error.code}.")
        return 1
    except (URLError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Проверка не пройдена: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
