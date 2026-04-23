#!/usr/bin/env bash
# Run a local Python smoke test against the deployed Topic Builder host.
#
# Usage:
#   smoke.sh <local.py> [args passed to the script on the host]
#
# Copies <local.py> to /tmp/ on the host and runs it with the deployed
# venv's python (so `import server`, `import wikipedia_api`, etc. work).
# Handy for verifying a fresh deploy without touching MCP client state.
#
# Reads DEPLOY_HOST / DEPLOY_USER from ../.env relative to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEY="$REPO_ROOT/deploy_key"

# shellcheck source=/dev/null
source "$REPO_ROOT/.env"

HOST="${DEPLOY_USER:-root}@${DEPLOY_HOST:?DEPLOY_HOST not set in .env}"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=no -o LogLevel=ERROR)

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <local.py> [args...]" >&2
  exit 2
fi

local_script="$1"
shift

if [[ ! -f "$local_script" ]]; then
  echo "Not found: $local_script" >&2
  exit 2
fi

# Stable remote filename keyed on the basename keeps the host path
# predictable across runs; new content overwrites old.
remote_name="smoke_$(basename "$local_script")"
remote_path="/tmp/$remote_name"

scp "${SSH_OPTS[@]}" -q "$local_script" "$HOST:$remote_path"

# Requote each passed arg so embedded spaces survive the ssh round-trip.
quoted=""
for a in "$@"; do
  quoted+=" $(printf '%q' "$a")"
done

ssh "${SSH_OPTS[@]}" "$HOST" "/opt/topic-builder/venv/bin/python $remote_path$quoted"
