# Dogfood / benchmark task briefs

Markdown source files for the `dogfood_tasks` database table that backs
the `fetch_task_brief` MCP tool. Each file is one task. Both the
frontmatter `run_topic_name_template` and the markdown body are
**templates** — the server renders `{ts}` (minute-UTC) at call time so
each fetch produces a fresh, unique run-topic name without anyone
editing the source.

## Why this exists

- **Operator simplicity.** Kickoff becomes one line: _"Call
  `fetch_task_brief(task_id='X')`, follow its instructions."_ No
  copy-pasting long markdown files into the chat.
- **Frozen prompts, evolving substrate.** The briefs are the
  measurement contract. Changes to the tool surface / instructions /
  feedback schema can move the metrics; changes to the briefs would
  reset the comparison. Keep briefs static; iterate on the substrate.
- **Repeat-run friendly.** Each fetch produces a fresh
  `{ts}`-stamped run-topic name, so running the same task five days
  apart doesn't collide on the server.
- **Path to guided-mode skill.** The eventual claude.ai skill can call
  the same tool — the skill becomes a thin wrapper.

## File format

```
---
task_id: <unique-id>
variant: <thin|informed|...>
benchmark_slug: <slug-from-benchmarks-dir-or-empty>
run_topic_name_template: <slug>-<variant> {ts}
---

# <brief body starts here — pure markdown, served verbatim after {ts} render>
```

Frontmatter keys (all required except `benchmark_slug`):

- `task_id` — the lookup key. Convention: `<slug>-<variant>` (e.g.
  `apollo-11-thin`).
- `variant` — distinguishes prompt shapes. Canonical:
  - `thin` — one-paragraph scope + session protocol; no rubric framework
    details, no probe counts, no topic-specific guardrails. Tests the
    tool surface under realistic-user guidance. This is the default
    measurement mode for the ratchet.
  - `informed` — thin brief body + "the gold set has ≥N articles; the
    prior thin baseline hit precision P, recall R." Gold-farming
    variant; AI knows the bar.
  (File-based `fat` variants from the 2026-04-23 cycle still live under
  `dogfood/kickoffs/` as historical artifacts. They are not loaded into
  the DB; the ratchet measures thin now.)
- `benchmark_slug` — matches `benchmarks/<slug>/` for scoring-linkage.
  Omit for ad-hoc dogfood tasks.
- `run_topic_name_template` — string that becomes the run-topic name
  after `{ts}` is rendered at fetch time. Convention:
  `<slug>-<variant> {ts}` → e.g. `apollo-11-thin 20260425T0013`. Must
  NOT collide with the baseline topic's name.

## Template rendering

The server's `fetch_task_brief` runs one substitution pass at call time:

- `{ts}` → current minute-UTC in `YYYYMMDDTHHMM` format.
- (Future placeholders like `{task_id}` can share the same pass; `{ts}`
  is the only one currently supported.)

Both `run_topic_name_template` AND the brief body are rendered. The
brief's step-1 `start_topic(name="...")` example uses the same
`{ts}` placeholder so the concrete name in the returned brief matches
the returned `run_topic_name` field. No manual coordination required.

## Loading into the DB

```
# Pre-scp the tasks dir to the host:
source .env && scp -i deploy_key -r dogfood/tasks \
  "$DEPLOY_USER@$DEPLOY_HOST:/tmp/dogfood_tasks"

# Then run the seed:
bash scripts/smoke.sh scripts/seed_dogfood_tasks.py
```

Idempotent — safe to re-run after editing any brief.

## Authoring a new variant

1. Copy an existing `<slug>-thin.md` → `<slug>-informed.md` (or
   whatever).
2. Edit the frontmatter (`task_id`, `variant`, `run_topic_name_template`).
3. Edit the body — keep it operational (scope statement + protocol
   references to server instructions). Anything that might evolve
   (probe counts, rubric tier details, topic-specific guardrails)
   belongs in `server_instructions.md`, not in the brief.
4. Reseed via the command above.
5. Verify with `fetch_task_brief(task_id="<new-id>")` through any MCP
   client — the returned `run_topic_name` and `brief` should contain
   the rendered timestamp.

## Running a task

```
# From an MCP client (Claude, Codex, etc.):
Call fetch_task_brief(task_id="<task-id>"), then follow its instructions.
```

## Scoring a run

The `--task` mode on the scoring script auto-resolves the most recent
matching run:

```
python3 scripts/benchmark_score.py --task <task-id>
python3 scripts/benchmark_score.py --task <task-id> --nth 1   # second-most-recent
```

The direct `<slug> <run-topic-name>` form still works if you want to
score a specific run name:

```
python3 scripts/benchmark_score.py <slug> "<exact run-topic name>"
```
