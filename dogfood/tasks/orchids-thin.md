---
task_id: orchids-thin
variant: thin
benchmark_slug: orchids
run_topic_name_template: orchids-thin {ts}
---

# Benchmark run: orchids

You're executing a competitive benchmark against the Topic Builder MCP server. Build the best topic you can for the scope below, then submit feedback. Your final corpus will be scored against a frozen audit.

**Mode:** deep consultative, completeness-seeking — not speed. An honest 0.6 coverage estimate is more useful than an inflated 0.9. No human operator will steer you mid-session.

## Scope statement

> Wikipedia articles about members of the Orchidaceae family (orchids) and their immediate biology, taxonomy, cultivation, pollination, phytochemistry, and cultural role. Includes orchid-focused people and institutions; includes orchid cultural works; excludes non-Orchidaceae plants and general botany unless orchid-specific.

That paragraph is the whole scope you're given. Flesh out the rubric from it yourself per the server's SCOPE RUBRIC guidance.

## Protocol

1. `start_topic(name="orchids-thin {ts}", wiki="en", fresh=False)`. The name above is pre-rendered with a fresh timestamp every time this brief is fetched — use it verbatim. A separate frozen baseline topic exists with a related name; do NOT overwrite it.
2. Draft a rubric from the scope statement and persist it via `set_topic_rubric(rubric=...)`. Follow the SCOPE RUBRIC framework in the server's instructions.
3. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). This topic is large — follow the server's COST AWARENESS guidance and prefer `preview_*` variants before committing.
4. Do SPOT CHECK and GAP CHECK before wrap-up per the server instructions. No user is here to propose probe titles — fabricate them yourself.
5. Call `submit_feedback(...)` with honest values for the structured fields. See the tool's docstring for the schema; at minimum populate `coverage_estimate`, `strategies_used`, `spot_check`, `sharp_edges_hit`, and `tool_friction` alongside the prose fields. Don't call `export_csv` — the scoring script pulls the corpus directly from the server.
6. Reply with a short summary: final article count, coverage_estimate.confidence, notable friction.
