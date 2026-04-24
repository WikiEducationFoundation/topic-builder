---
task_id: crispr-gene-editing-thin
variant: thin
benchmark_slug: crispr-gene-editing
run_topic_name_template: crispr-gene-editing-thin {ts}
---

# Benchmark run: CRISPR gene editing

You're executing a competitive benchmark against the Topic Builder MCP server. Build the best topic you can for the scope below, then submit feedback. Your final corpus will be scored against a frozen audit.

**Mode:** deep consultative, completeness-seeking — not speed. An honest 0.6 coverage estimate is more useful than an inflated 0.9. No human operator will steer you mid-session.

## Scope statement

> Wikipedia articles about CRISPR as a gene-editing system — its biology, mechanisms, associated techniques and tools, pioneering scientists, CRISPR-focused companies, applications (therapies and projects), and the central bioethical episode (He Jiankui affair).

That paragraph is the whole scope you're given. Flesh out the rubric from it yourself per the server's SCOPE RUBRIC guidance.

## Protocol

1. `start_topic(name="crispr-gene-editing-thin {ts}", wiki="en", fresh=False)`. The name above is pre-rendered with a fresh timestamp every time this brief is fetched — use it verbatim. A separate frozen baseline topic exists with a related name; do NOT overwrite it.
2. Draft a rubric from the scope statement and persist it via `set_topic_rubric(rubric=...)`. Follow the SCOPE RUBRIC framework in the server's instructions.
3. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). Follow the server's PIPELINE, NOISE TAXONOMY, KNOWN SHARP EDGES, and WRAP-UP guidance.
4. Do SPOT CHECK and GAP CHECK before wrap-up per the server instructions. No user is here to propose probe titles — fabricate them yourself.
5. Call `submit_feedback(...)` with honest values for the structured fields. See the tool's docstring for the schema; at minimum populate `coverage_estimate`, `strategies_used`, `spot_check`, `sharp_edges_hit`, and `tool_friction` alongside the prose fields. Don't call `export_csv` — the scoring script pulls the corpus directly from the server.
6. Reply with a short summary: final article count, coverage_estimate.confidence, notable friction.
