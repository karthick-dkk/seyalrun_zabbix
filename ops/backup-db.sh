#!/bin/bash
# Dumps seyalrun_identity and seyalrun_inventory using pg_dump or
# mysqldump (per DB_ENGINE in .env) to timestamped files under
# the given output directory.
#
# Usage:
#   ops/backup-db.sh [OUTPUT_DIR]     # OUTPUT_DIR defaults to ./backups

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

: "${DB_ENGINE:?DB_ENGINE must be set in .env (postgres|mysql)}"
: "${DB_HOST:?DB_HOST must be set in .env}"
: "${DB_PORT:?DB_PORT must be set in .env}"
: "${DB_USER:?DB_USER must be set in .env}"
: "${DB_PASSWORD:?DB_PASSWORD must be set in .env}"
: "${IDENTITY_DB_NAME:?IDENTITY_DB_NAME must be set in .env}"
: "${INVENTORY_DB_NAME:?INVENTORY_DB_NAME must be set in .env}"

OUT_DIR="${1:-$REPO_ROOT/backups}"
mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d-%H%M%S)"

case "$DB_ENGINE" in
  postgres)
    export PGPASSWORD="$DB_PASSWORD"
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      OUT_FILE="$OUT_DIR/${db}-${TS}.sql.gz"
      echo "[*] Dumping '$db' -> $OUT_FILE"
      pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" | gzip > "$OUT_FILE"
    done
    ;;
  mysql)
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      OUT_FILE="$OUT_DIR/${db}-${TS}.sql.gz"
      echo "[*] Dumping '$db' -> $OUT_FILE"
      mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" \
        --single-transaction --routines --triggers "$db" | gzip > "$OUT_FILE"
    done
    ;;
  *)
    echo "Unsupported DB_ENGINE: '$DB_ENGINE' (expected postgres|mysql)" >&2
    exit 1
    ;;
esac

echo "[✓] Backups written to $OUT_DIR"
