#!/usr/bin/env bash
# Sync dogfood/tasks/ to /tmp/dogfood_tasks on the deployed host so
# scripts/seed_dogfood_tasks.py (run via smoke.sh) can read from there.
#
# Usage: bash scripts/scp_tasks.sh
#
# Reads DEPLOY_HOST / DEPLOY_USER from ../.env relative to this script.
# Mirrors smoke.sh's pattern.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY="$REPO_ROOT/deploy_key"

# shellcheck source=/dev/null
source "$REPO_ROOT/.env"

HOST="${DEPLOY_USER:-root}@${DEPLOY_HOST:?DEPLOY_HOST not set in .env}"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=no -o LogLevel=ERROR)

# Remove any prior /tmp/dogfood_tasks before copying so retired briefs
# don't linger as zombie files on the host.
ssh "${SSH_OPTS[@]}" "$HOST" "rm -rf /tmp/dogfood_tasks"
scp "${SSH_OPTS[@]}" -q -r "$REPO_ROOT/dogfood/tasks" "$HOST:/tmp/dogfood_tasks"
echo "OK — scp'd $REPO_ROOT/dogfood/tasks → $HOST:/tmp/dogfood_tasks"
