#!/usr/bin/env bash
# scripts/agent_matrix.sh
#
# Run a single dogfood task across multiple (agent, model, effort) cells
# serially. Each cell launches a fresh headless `claude -p` or `codex exec`
# session, pre-assigns a unique topic name, and captures stdout+stderr.
#
# Outputs (under dogfood/matrix-runs/<date>-<task>/):
#   <label>.log     — full transcript (stdout+stderr)
#   <label>.topic   — the topic name used by that cell
#   cells.tsv       — append-only ledger (label, agent, model, effort, topic, timing, status)
#
# Score a finished cell with the explicit topic-name form (since the topic
# name has a label suffix, `--task` auto-resolution won't match):
#   python3 scripts/benchmark_score.py <slug> "<topic name from .topic file>"
#
# Edit CELLS below to change the matrix. Assumes the topic-builder MCP
# server is already registered for both claude and codex (one-time setup
# per dogfood/README.md).

set -euo pipefail

TASK_ID="${TASK_ID:-climate-change-thin}"
SLUG="${SLUG:-climate-change}"

# AUTH_ENFORCEMENT=writes is on in production, so each cell needs a Topic
# Builder bearer token (tb_<hex>). Obtain one from the OAuth flow on
# https://topic-builder.wikiedu.org/ and export TB_AUTH_TOKEN before
# running. The token is passed into the agent's prompt so it can call
# authenticate(token=...) at session start; it will appear in the per-cell
# .log file, which is why dogfood/matrix-runs/ is gitignored.
if [ -z "${TB_AUTH_TOKEN:-}" ]; then
  echo "error: TB_AUTH_TOKEN not set." >&2
  echo "       Get a token at https://topic-builder.wikiedu.org/ then:" >&2
  echo "         export TB_AUTH_TOKEN=tb_..." >&2
  exit 2
fi

# Cell format: agent|model|effort|label
# - claude effort: low | medium | high | xhigh | max     (passes --effort)
# - claude model:  opus | sonnet | haiku | <full id>     (passes --model; empty = default)
# - codex  effort: minimal | low | medium | high         (passes -c model_reasoning_effort=...)
# - codex  model:  empty for the default, or e.g. gpt-5  (passes -m)
CELLS=(
  "claude|sonnet|low|claude-sonnet-low"
  "claude|sonnet|medium|claude-sonnet-medium"
  "claude|sonnet|high|claude-sonnet-high"
  "codex||low|codex-low"
  "codex||medium|codex-medium"
  "codex||high|codex-high"
)

DATE=$(date -u +%Y-%m-%d)
RUN_DIR="dogfood/matrix-runs/${DATE}-${TASK_ID}"
mkdir -p "$RUN_DIR"

LEDGER="$RUN_DIR/cells.tsv"
[ -f "$LEDGER" ] || printf "label\tagent\tmodel\teffort\ttopic_name\tstarted_at\tended_at\tstatus\tlog\n" > "$LEDGER"

# Optional: CELL_FILTER=<substring> runs only cells whose label contains it.
#           CELL_EXCLUDE=<substring> skips cells whose label contains it.
# Useful for smoke-testing or re-running a subset.
FILTER="${CELL_FILTER:-}"
EXCLUDE="${CELL_EXCLUDE:-}"

if [ -n "$FILTER" ] || [ -n "$EXCLUDE" ]; then
  filtered=()
  for cell in "${CELLS[@]}"; do
    IFS='|' read -r _ _ _ label <<< "$cell"
    [ -n "$FILTER" ] && [[ "$label" != *"$FILTER"* ]] && continue
    [ -n "$EXCLUDE" ] && [[ "$label" == *"$EXCLUDE"* ]] && continue
    filtered+=("$cell")
  done
  CELLS=("${filtered[@]}")
fi

echo "Run dir: $RUN_DIR"
echo "Cells:   ${#CELLS[@]}${FILTER:+ (filtered by '$FILTER')}"
echo ""

for cell in "${CELLS[@]}"; do
  IFS='|' read -r agent model effort label <<< "$cell"

  ts=$(date -u +%Y%m%dT%H%M)
  topic_name="${TASK_ID} ${ts} ${label}"
  log_file="$RUN_DIR/${label}.log"
  echo "$topic_name" > "$RUN_DIR/${label}.topic"

  model_label="${model:-default}"
  prompt=$(cat <<EOF
You are running a benchmark against the Topic Builder MCP server.

STEP 0 — AUTHENTICATE BEFORE ANY OTHER TOPIC BUILDER CALL:
Call authenticate(token="${TB_AUTH_TOKEN}"). The server has
AUTH_ENFORCEMENT=writes, so every mutation will fail without this. Do
NOT prompt the operator about saving the token to memory — there is no
operator in the loop, and the token is already managed externally.

CRITICAL TOPIC NAME OVERRIDE — read this twice:
When you call \`start_topic\`, use this exact name verbatim:
    ${topic_name}
Ignore the rendered topic name in the task brief; use the name above
instead. Use it in every subsequent tool call that takes \`topic=\`.

When you eventually call \`submit_feedback\`, set the \`runtime\` field to:
    {"agent": "${agent}", "model": "${model_label}", "effort": "${effort}"}

Now: call fetch_task_brief(task_id="${TASK_ID}") and follow its protocol
exactly, except substitute the topic name above for the {ts}-rendered name
in the brief.
EOF
)

  echo "=== $label  →  \"$topic_name\" ==="
  start_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  set +e
  case "$agent" in
    claude)
      args=(-p "$prompt" --dangerously-skip-permissions)
      [ -n "$model" ] && args+=(--model "$model")
      [ -n "$effort" ] && args+=(--effort "$effort")
      claude "${args[@]}" > "$log_file" 2>&1
      rc=$?
      ;;
    codex)
      args=(exec --dangerously-bypass-approvals-and-sandbox)
      [ -n "$model" ] && args+=(-m "$model")
      [ -n "$effort" ] && args+=(-c "model_reasoning_effort=\"$effort\"")
      args+=("$prompt")
      codex "${args[@]}" > "$log_file" 2>&1
      rc=$?
      ;;
    *)
      echo "  ! unknown agent: $agent" >&2
      rc=99
      ;;
  esac
  set -e
  end_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if [ $rc -eq 0 ]; then status="ok"; else status="exit_$rc"; fi
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$agent" "$model" "$effort" "$topic_name" \
    "$start_iso" "$end_iso" "$status" "$log_file" >> "$LEDGER"
  echo "  $status  log=$log_file"
  echo ""
done

echo "=== matrix complete ==="
echo "Ledger:  $LEDGER"
echo ""
echo "Score each cell:"
for cell in "${CELLS[@]}"; do
  IFS='|' read -r _ _ _ label <<< "$cell"
  topic=$(cat "$RUN_DIR/${label}.topic")
  echo "  python3 scripts/benchmark_score.py $SLUG \"$topic\"   # $label"
done
echo ""
echo "Or sweep all cells:"
echo "  for f in $RUN_DIR/*.topic; do python3 scripts/benchmark_score.py $SLUG \"\$(cat \"\$f\")\"; done"
