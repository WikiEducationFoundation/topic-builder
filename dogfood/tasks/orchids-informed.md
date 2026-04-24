---
task_id: orchids-informed
variant: informed
benchmark_slug: orchids
run_topic_name_template: orchids-informed {ts}
---

# Benchmark run: orchids (informed variant)

You're executing a benchmark run against the Topic Builder MCP server. This is the **informed** variant — the baseline's quality numbers + current gold-set size are visible to you. The goal isn't to rediscover what the baseline already captured; it's to **grow gold**: find on-topic articles the audited gold set doesn't yet contain. Audited reach additions become part of the next baseline.

**Mode:** deep consultative, completeness-seeking. No human operator will steer you mid-session.

## Scope statement

> Wikipedia articles about members of the Orchidaceae family (orchids) and their immediate biology, taxonomy, cultivation, pollination, phytochemistry, and cultural role. Includes orchid-focused people and institutions; includes orchid cultural works; excludes non-Orchidaceae plants and general botany unless orchid-specific.

That paragraph is the whole scope you're given. Flesh out the rubric from it yourself per the server's SCOPE RUBRIC guidance.

## Baseline + gold snapshot

- **Current audited gold set**: 7,354 on-topic articles (classified CENTRAL or PERIPHERAL).
- **Prior baseline run**: 18,122-article corpus, precision 1.0, recall 1.0 against gold at bootstrap. Read: the baseline captured everything audited in — large corpus, clean within its scope — but gold has contracted since baseline as redlinks and non-article titles were excluded from scoring. Real-article reach opportunities concentrate in cross-wiki sitelink walks, Wikidata parent-taxon probes, and cultural-tail coverage.
- **What "beat the baseline" means here**: reach against the current gold is the win. The baseline's approach — deep category crawl + list-page harvest — saturated the enwiki-native orchid structure. New reach comes from structural sources the baseline didn't exercise.

These numbers are visible so you can pace your session. This is the largest benchmark — follow COST AWARENESS guidance and prefer `preview_*` variants before committing to heavy pulls.

## Protocol

1. `start_topic(name="orchids-informed {ts}", wiki="en", fresh=False)`. The name above is pre-rendered with a fresh timestamp at fetch time — use it verbatim. A separate frozen baseline topic exists with a related name; do NOT overwrite it.
2. Draft a rubric from the scope statement and persist it via `set_topic_rubric(rubric=...)`. Follow the SCOPE RUBRIC framework in the server's instructions.
3. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). Follow the server's PIPELINE, COST AWARENESS, NOISE TAXONOMY, KNOWN SHARP EDGES, and WRAP-UP guidance. Since the goal is reach, bias toward strategies that surface articles the baseline's approach would have missed.
4. Do SPOT CHECK and GAP CHECK before wrap-up per the server instructions. Fabricate probes targeting under-covered subdomains of the scope.
5. Call `submit_feedback(...)` with honest values for the structured fields. See the tool's docstring for the schema; at minimum populate `coverage_estimate`, `strategies_used`, `spot_check`, `sharp_edges_hit`, and `tool_friction` alongside the prose fields. Note your estimated reach count in the feedback so we can correlate with the scoreboard when the run is audited. Don't call `export_csv` — the scoring script pulls the corpus directly from the server.
6. Reply with a short summary: final article count, coverage_estimate.confidence, your estimate of the reach count (articles you believe are not already in gold), and notable friction.
