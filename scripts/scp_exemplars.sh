#!/usr/bin/env bash
# Sync dogfood/exemplars/ to /tmp/dogfood_exemplars on the deployed
# host so scripts/seed_dogfood_exemplars.py (run via smoke.sh) can
# read from there. Mirrors scp_tasks.sh / smoke.sh pattern.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY="$REPO_ROOT/deploy_key"

# shellcheck source=/dev/null
source "$REPO_ROOT/.env"

HOST="${DEPLOY_USER:-root}@${DEPLOY_HOST:?DEPLOY_HOST not set in .env}"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=no -o LogLevel=ERROR)

ssh "${SSH_OPTS[@]}" "$HOST" "rm -rf /tmp/dogfood_exemplars"
scp "${SSH_OPTS[@]}" -q -r "$REPO_ROOT/dogfood/exemplars" "$HOST:/tmp/dogfood_exemplars"
echo "OK — scp'd $REPO_ROOT/dogfood/exemplars → $HOST:/tmp/dogfood_exemplars"
