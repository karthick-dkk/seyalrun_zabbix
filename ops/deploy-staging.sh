#!/bin/bash
# Deploys SeyalRun v2.0 Phase 1 to a staging host: rsyncs the repo to
# /opt/seyalrun-v2, runs ops/_staging-bootstrap.sh there (generates .env +
# a self-signed TLS cert if missing, brings up the stack with Docker
# Compose — falling back to docker-compose.db.yml's Dockerized Postgres if
# no bare-metal Postgres is reachable, runs Alembic migrations + the
# superadmin seed), then runs ops/verify-staging.sh.
#
# Usage:
#   ops/deploy-staging.sh <HOST>
#
# Environment:
#   SSH_USER       - remote SSH user (default: test)
#   SUDO_PASSWORD  - remote sudo password, sent only over the SSH stdin
#                     channel to `sudo -S` (docker requires root on this
#                     host). If unset, an interactive `-tt` sudo prompt is
#                     used instead.
#
# Idempotent / safe to re-run: reuses the existing remote .env/TLS cert and
# `docker compose up -d` only (re)creates changed containers.

set -euo pipefail

HOST="${1:-}"
if [[ -z "$HOST" ]]; then
  echo "Usage: $0 <HOST>  — e.g. $0 192.168.64.2" >&2
  exit 1
fi
SSH_USER="${SSH_USER:-test}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)
REMOTE_DIR="/opt/seyalrun-v2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[->]${NC} $*"; }
fail() { echo -e "${RED}[X]${NC} $*"; exit 1; }

# Runs "$1" as root on the remote host.
remote_sudo() {
  if [[ -n "${SUDO_PASSWORD:-}" ]]; then
    ssh "${SSH_OPTS[@]}" "${SSH_USER}@${HOST}" "sudo -S bash -c '$1'" <<< "$SUDO_PASSWORD"
  else
    ssh -tt "${SSH_OPTS[@]}" "${SSH_USER}@${HOST}" "sudo bash -c '$1'"
  fi
}

echo "=== SeyalRun v2.0 deploy -> ${SSH_USER}@${HOST}:${REMOTE_DIR} ==="

info "[1/5] Ensuring ${REMOTE_DIR} exists and is owned by ${SSH_USER}..."
remote_sudo "mkdir -p '${REMOTE_DIR}' && chown ${SSH_USER}:${SSH_USER} '${REMOTE_DIR}'"
log "${REMOTE_DIR} ready"

info "[2/5] Syncing repo to ${REMOTE_DIR} (test-owned — no sudo needed)..."
rsync -az --delete \
  --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='dist' --exclude='.env' --exclude='tls' --exclude='seed-output.txt' \
  --exclude='.compose-flags' --exclude='backups' \
  "${REPO_ROOT}/" "${SSH_USER}@${HOST}:${REMOTE_DIR}/"
log "repo synced"

info "[3/5] Running bootstrap (build + up -d + migrations + seed) — this can take several minutes..."
remote_sudo "cd '${REMOTE_DIR}' && EDGE_HOST='${HOST}' bash ops/_staging-bootstrap.sh"
log "bootstrap complete"

info "[4/5] Superadmin seed output (shown once, then removed from the host):"
SEED_OUTPUT=$(ssh "${SSH_OPTS[@]}" "${SSH_USER}@${HOST}" "cat '${REMOTE_DIR}/seed-output.txt' 2>/dev/null && rm -f '${REMOTE_DIR}/seed-output.txt'" || true)
echo "$SEED_OUTPUT"
SEED_PASSWORD=$(echo "$SEED_OUTPUT" | sed -n 's/.*will not be shown again): //p')

info "[5/5] Running verification..."
SEYALRUN_ADMIN_PASSWORD="${SEYALRUN_ADMIN_PASSWORD:-$SEED_PASSWORD}" "${REPO_ROOT}/ops/verify-staging.sh" "${HOST}"
