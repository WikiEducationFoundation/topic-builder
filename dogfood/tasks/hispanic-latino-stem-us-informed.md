---
task_id: hispanic-latino-stem-us-informed
variant: informed
benchmark_slug: hispanic-latino-stem-us
run_topic_name_template: hispanic-latino-stem-us-informed {ts}
---

# Benchmark run: Hispanic and Latino people in STEM in the United States (informed variant)

You're executing a benchmark run against the Topic Builder MCP server. This is the **informed** variant — the baseline's quality numbers + current gold-set size are visible to you. The goal isn't to rediscover what the baseline already captured; it's to **grow gold**: find on-topic articles the audited gold set doesn't yet contain. Audited reach additions become part of the next baseline.

**Mode:** deep consultative, completeness-seeking. No human operator will steer you mid-session.

## Scope statement

> Wikipedia biographies of people of Hispanic and Latino heritage, working in STEM fields, with a meaningful affiliation to the United States.

That paragraph is the whole scope you're given. Flesh out the rubric from it yourself per the server's SCOPE RUBRIC guidance.

## Baseline + gold snapshot

- **Current audited gold set**: 314 on-topic articles.
- **Prior baseline run**: 1,936-article corpus, precision 0.448, recall 0.984 against gold at bootstrap. Read: the baseline was very broad — the majority of its corpus was audited OUT — and captured nearly all audited in-scope articles. A scope-tightened run should ship with far fewer false positives while preserving recall.
- **What "beat the baseline" means here**: substantial precision improvement is the primary win (baseline 45% on-topic means there's a lot of clinical-medicine / social-science / non-STEM noise to cut). Reach is secondary — find intersectional biographies the baseline's PetScan-style category-sweep missed.

These numbers are visible so you can pace your session. You don't need to race; precision and reach both matter on this shape.

## Protocol

1. `start_topic(name="hispanic-latino-stem-us-informed {ts}", wiki="en", fresh=False)`. The name above is pre-rendered with a fresh timestamp at fetch time — use it verbatim. A separate frozen baseline topic exists with a related name; do NOT overwrite it.
2. Draft a rubric from the scope statement and persist it via `set_topic_rubric(rubric=...)`. Follow the SCOPE RUBRIC framework in the server's instructions.
3. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). Follow the server's PIPELINE, NOISE TAXONOMY, KNOWN SHARP EDGES, INTERSECTIONAL TOPICS, and WRAP-UP guidance. Since the goal is reach and precision, bias toward strategies that surface articles the baseline's approach would have missed AND be aggressive about cutting off-scope noise.
4. Do SPOT CHECK and GAP CHECK before wrap-up per the server instructions. Fabricate probes targeting under-covered subdomains of the scope.
5. Call `submit_feedback(...)` with honest values for the structured fields. See the tool's docstring for the schema; at minimum populate `coverage_estimate`, `strategies_used`, `spot_check`, `sharp_edges_hit`, and `tool_friction` alongside the prose fields. Note your estimated reach count in the feedback so we can correlate with the scoreboard when the run is audited. Don't call `export_csv` — the scoring script pulls the corpus directly from the server.
6. Reply with a short summary: final article count, coverage_estimate.confidence, your estimate of the reach count (articles you believe are not already in gold), and notable friction.
