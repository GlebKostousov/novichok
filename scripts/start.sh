#!/bin/sh
set -eu

alembic upgrade head
exec uvicorn app.app_factory:create_app --factory --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips=127.0.0.1,172.16.0.0/12
