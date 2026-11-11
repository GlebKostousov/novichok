"""Создание локальной конфигурации без перезаписи существующего файла."""

from pathlib import Path
from secrets import token_hex


def main() -> None:
    """Сохранить настройки Compose и случайный пароль с правами владельца."""
    destination = Path(__file__).resolve().parents[1] / ".env"
    content = (
        f"POSTGRES_PASSWORD={token_hex(24)}\n"
        "APP_PORT=8080\n"
        "NOVICHOK_COOKIE_SECURE=false\n"
        'NOVICHOK_ALLOWED_HOSTS=["localhost","127.0.0.1"]\n'
        "NOVICHOK_MAX_WORKSPACES=500\n"
    )
    try:
        with destination.open("x", encoding="utf-8") as output:
            destination.chmod(0o600)
            output.write(content)
    except FileExistsError:
        print("Файл .env уже существует. Его настройки сохранены.")
        return
    print("Файл .env создан. Для HTTPS задайте домен и COOKIE_SECURE=true.")


if __name__ == "__main__":
    main()
