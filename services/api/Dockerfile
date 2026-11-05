# API image. Build from the repository root:
#   docker build -f services/api/Dockerfile -t canteen-api .
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.11.33 /uv /usr/local/bin/uv

WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY services/api/alembic.ini ./
COPY services/api/migrations ./migrations
COPY services/api/app ./app
# Authoritative menu workbook for the one-time seed job.
COPY data/AISSMS_Canteen_Menu.xlsx data/menu_seed_draft.json /seed/

RUN useradd --uid 10001 --no-create-home canteen && mkdir -p /data/media && chown canteen /data/media
USER canteen
ENV PATH=/app/.venv/bin:$PATH \
    MEDIA_DIR=/data/media \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    WEB_CONCURRENCY=2
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# --proxy-headers + FORWARDED_ALLOW_IPS: trust X-Forwarded-For only from the reverse proxy, so
# rate limits see real client addresses instead of the proxy's.
CMD ["sh", "-c", "exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\" --workers \"$WEB_CONCURRENCY\" --no-server-header --no-access-log"]
