#!/usr/bin/env sh
# Restore a backup into a THROWAWAY database and verify it. Never targets the live database.
#   infra/scripts/restore-drill.sh backups/<timestamp>
set -eu
DIR=${1:?usage: restore-drill.sh backups/<timestamp>}
( cd "$DIR" && sha256sum -c SHA256SUMS )
NAME=canteen-restore-drill-$$
PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$NAME" -e POSTGRES_USER=canteen -e POSTGRES_PASSWORD="$PASSWORD" \
  -e POSTGRES_DB=canteen postgres:18 >/dev/null
until docker exec "$NAME" pg_isready -U canteen -d canteen >/dev/null 2>&1; do sleep 1; done
docker exec -i "$NAME" pg_restore -U canteen -d canteen --no-owner --exit-on-error < "$DIR/canteen.dump"

# Schema at head, totals, collection state, codes, payments and refunds must all agree.
docker run --rm --network "container:$NAME" \
  -e DATABASE_URL="postgresql+psycopg://canteen:$PASSWORD@127.0.0.1:5432/canteen" \
  canteen-api:staging python -m app.ops.verify
tar -tzf "$DIR/media.tar.gz" >/dev/null
echo "Restore drill passed for $DIR"
