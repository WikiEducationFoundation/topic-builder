# Dogfood / benchmark task briefs

Markdown source files for the `dogfood_tasks` database table that backs
the `fetch_task_brief` MCP tool. Each file is one task, with YAML-lite
frontmatter describing its metadata and a markdown body that is the
literal text served to the AI on `fetch_task_brief(task_id=...)`.

## File format

```
---
task_id: <unique-id>
variant: <thin|fat|...>
benchmark_slug: <slug-from-benchmarks-dir-or-empty>
run_topic_name: <exact topic name the AI should start_topic with>
---

# <brief body starts here — pure markdown, served verbatim>
```

Frontmatter keys (all required except `benchmark_slug`):
- `task_id` — the lookup key. `<slug>-<variant>` is the convention (`apollo-11-thin`, `apollo-11-fat`).
- `variant` — distinguishes prompt shapes. Canonical: `thin` (minimal — one-paragraph scope + session instructions), `fat` (scope + rubric + reach targets + guardrails inlined).
- `benchmark_slug` — matches a `benchmarks/<slug>/` directory for scoring-linkage. Omit for ad-hoc dogfood tasks not tied to a benchmark.
- `run_topic_name` — the exact topic name the AI should pass to `start_topic`. Distinct from the baseline topic name so the baseline stays frozen.

## Loading into the DB

```
bash scripts/smoke.sh scripts/seed_dogfood_tasks.py
```

The seed script reads every `.md` file in `dogfood/tasks/`, parses the
frontmatter, and upserts to the `dogfood_tasks` table. Idempotent — safe
to re-run after editing any brief.

## Authoring a new variant

1. Copy an existing `<slug>-thin.md` → `<slug>-fat.md` (or whatever).
2. Edit the frontmatter (`task_id`, `variant`).
3. Edit the body.
4. `bash scripts/smoke.sh scripts/seed_dogfood_tasks.py`.
5. Verify with `fetch_task_brief(task_id="<new-id>")` via an MCP client.
