#!/bin/bash
# Creates seyalrun_identity / seyalrun_inventory on the bare-metal
# Postgres or MySQL configured in .env, and imports the matching
# schema/<engine>/schema.sql into both (idempotent — CREATE TABLE IF NOT
# EXISTS, safe to re-run).
#
# Usage:
#   ops/init-db.sh
#
# Requires .env (DB_ENGINE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
# IDENTITY_DB_NAME, INVENTORY_DB_NAME) — see .env.example. DB_USER must be
# able to create databases on DB_HOST.

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

case "$DB_ENGINE" in
  postgres)
    export PGPASSWORD="$DB_PASSWORD"
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      echo "[*] Ensuring database '$db' exists on ${DB_HOST}:${DB_PORT}..."
      exists=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '$db'")
      if [[ "$exists" != "1" ]]; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$db\""
      fi
    done
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      echo "[*] Importing schema/postgres/schema.sql into '$db'..."
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$db" -v ON_ERROR_STOP=1 -f schema/postgres/schema.sql
    done
    ;;
  mysql)
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      echo "[*] Ensuring database '$db' exists on ${DB_HOST}:${DB_PORT}..."
      mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" \
        -e "CREATE DATABASE IF NOT EXISTS \`$db\`"
    done
    for db in "$IDENTITY_DB_NAME" "$INVENTORY_DB_NAME"; do
      echo "[*] Importing schema/mysql/schema.sql into '$db'..."
      mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$db" < schema/mysql/schema.sql
    done
    ;;
  *)
    echo "Unsupported DB_ENGINE: '$DB_ENGINE' (expected postgres|mysql)" >&2
    exit 1
    ;;
esac

echo "[✓] Database initialization complete (${IDENTITY_DB_NAME}, ${INVENTORY_DB_NAME} on ${DB_ENGINE})."
