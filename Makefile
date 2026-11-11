.PHONY: install check test build run e2e smoke verify-container test-delivery

install:
	cd backend && uv sync --frozen
	cd frontend && npm ci

check:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run mypy app tests
	cd backend && uv run lint-imports
	cd frontend && npm run check

test:
	cd backend && uv run pytest

build:
	cd frontend && npm run build

run: build
	cd backend && uv run alembic upgrade head
	cd backend && NOVICHOK_STATIC_DIR=../frontend/dist uv run uvicorn app.app_factory:create_app --factory --host 127.0.0.1 --port 8000

e2e:
	cd frontend && npm run test:e2e

# Эти команды не требуют Python-зависимостей приложения.
URL ?= http://127.0.0.1:8080

smoke:
	python3 scripts/check_http.py "$(URL)"

verify-container:
	bash scripts/verify_container.sh

test-delivery:
	python3 -m unittest discover -s scripts/tests -v
