#!/usr/bin/env bash
# Собери и проверь демо в отдельном Compose-проекте, затем удали только его.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v docker >/dev/null || { echo 'Нужны Docker Engine и Compose v2.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Нужен Python 3.' >&2; exit 1; }
docker compose version >/dev/null

project="novichok-check-$(date +%s)-$$"
export POSTGRES_PASSWORD
POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
export APP_PORT=0
export NOVICHOK_COOKIE_SECURE=false
export NOVICHOK_ALLOWED_HOSTS='["localhost","127.0.0.1"]'
export NOVICHOK_MAX_WORKSPACES=20

compose() {
    docker compose --env-file /dev/null --project-name "$project" -f "$root/compose.yaml" "$@"
}

cleanup() {
    result=$?
    trap - EXIT
    if (( result != 0 )); then
        compose logs --no-color --tail=80 app >&2 || true
    fi
    if ! compose down --volumes --remove-orphans --rmi local >/dev/null; then
        echo "Не удалось удалить тестовый Compose-проект: $project" >&2
        echo 'Проверьте его контейнеры и volume перед повторным запуском.' >&2
        if (( result == 0 )); then
            result=1
        fi
    fi
    exit "$result"
}
trap cleanup EXIT

compose up --build --detach --wait --wait-timeout 180
endpoint="$(compose port app 8000)"
python3 "$root/scripts/check_http.py" "http://$endpoint"
echo 'Контейнерный запуск проверен. Временные контейнеры и volume будут удалены.'
