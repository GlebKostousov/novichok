# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run check && npm run build

FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72 AS backend
RUN python -m pip install --no-cache-dir uv==0.13.6
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    NOVICHOK_STATIC_DIR=/app/static \
    NOVICHOK_LOG_JSON=true
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=backend /app/.venv /app/.venv
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/migrations ./migrations
COPY --chown=app:app backend/alembic.ini ./alembic.ini
COPY --from=frontend --chown=app:app /build/dist ./static
COPY --chown=app:app scripts/start.sh /app/start.sh
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
ENTRYPOINT ["/bin/sh", "/app/start.sh"]
