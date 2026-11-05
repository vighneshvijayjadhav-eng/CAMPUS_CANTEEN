#!/usr/bin/env sh
# Back up the staging/production database and review photos together.
#   infra/scripts/backup.sh [compose-file] [env-file]
# Writes backups/<timestamp>/{canteen.dump,media.tar.gz,SHA256SUMS}. Copy that folder off
# the server (encrypted) according to the retention policy.
set -eu
COMPOSE_FILE=${1:-infra/compose.staging.yml}
ENV_FILE=${2:-.env.staging}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=backups/$STAMP
mkdir -p "$OUT"
dc() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

# Custom-format dump: consistent snapshot, restorable table by table.
dc exec -T db pg_dump -U canteen -d canteen -Fc --no-owner > "$OUT/canteen.dump"
dc run --rm --no-deps -T --entrypoint tar api -czf - -C /data media > "$OUT/media.tar.gz"
( cd "$OUT" && sha256sum canteen.dump media.tar.gz > SHA256SUMS )
echo "Backup written to $OUT"
