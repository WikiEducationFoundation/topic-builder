#!/usr/bin/env bash
# Poll the Topic Builder host for dogfood-session state.
#
# Usage:
#   monitor_dogfood.sh                     # overview (all topics + usage tail)
#   monitor_dogfood.sh <topic>             # drill into a topic (id or substring)
#   monitor_dogfood.sh <topic> --recent N
#   monitor_dogfood.sh tail-usage [N]      # tail usage.jsonl (default 40 lines)
#   monitor_dogfood.sh tail-feedback [N]   # tail feedback.jsonl (default 20 lines)
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

# Make sure the status script is on the host. Copy once per invocation; it's tiny.
scp "${SSH_OPTS[@]}" -q "$SCRIPT_DIR/session_status.py" "$HOST:/tmp/status.py"

cmd="${1:-}"
case "$cmd" in
  tail-usage)
    n="${2:-40}"
    ssh "${SSH_OPTS[@]}" "$HOST" "tail -n $n /opt/topic-builder/logs/usage.jsonl"
    ;;
  tail-feedback)
    n="${2:-20}"
    ssh "${SSH_OPTS[@]}" "$HOST" "tail -n $n /opt/topic-builder/logs/feedback.jsonl 2>/dev/null || echo '(no feedback log yet)'"
    ;;
  "")
    ssh "${SSH_OPTS[@]}" "$HOST" "/opt/topic-builder/venv/bin/python /tmp/status.py"
    ;;
  *)
    # Pass all args through to status.py (topic id/name + optional --recent N).
    # Requote each arg so embedded spaces survive the ssh round-trip.
    quoted=""
    for a in "$@"; do
      quoted+=" $(printf '%q' "$a")"
    done
    ssh "${SSH_OPTS[@]}" "$HOST" "/opt/topic-builder/venv/bin/python /tmp/status.py$quoted"
    ;;
esac
