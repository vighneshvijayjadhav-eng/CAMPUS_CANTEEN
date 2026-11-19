#!/bin/sh
# Container entrypoint. Optional start-up steps for single-service hosts (e.g. Render free):
#   RUN_MIGRATIONS=1  apply database migrations (additive only)
#   SEED_MENU=1       insert-only menu seed from the bundled workbook
#   DEMO_MODE=1       demo canteens, counters, logins and labelled sample data (never production)
set -e
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  alembic upgrade head
fi
if [ "${SEED_MENU:-0}" = "1" ]; then
  # A changed workbook stops the seed on purpose (source ids must be reviewed); keep serving.
  python -m app.modules.menu.seed /seed/AISSMS_Canteen_Menu.xlsx || echo "WARNING: menu seed skipped"
fi
if [ "${DEMO_MODE:-0}" = "1" ]; then
  python -m app.ops.demo
fi
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS" \
  --workers "$WEB_CONCURRENCY" --no-server-header --no-access-log
