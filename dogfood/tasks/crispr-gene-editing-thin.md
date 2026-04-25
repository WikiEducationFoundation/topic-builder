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

## Protocol — phase 1 (thin build, measured)

1. `start_topic(name="crispr-gene-editing-thin {ts}", wiki="en", fresh=False)`. The name above is pre-rendered with a fresh timestamp every time this brief is fetched — use it verbatim. A separate frozen baseline topic exists with a related name; do NOT overwrite it.

2. Draft a rubric from the scope statement and persist it via `set_topic_rubric(rubric=...)`. Follow the SCOPE RUBRIC framework in the server's instructions.

3. **PREPARATORY PHASE** (free-tools-only, before any Wikipedia/Wikidata-hitting tool call):
   - Read your rubric in full via `get_topic_rubric()`. Confirm it captures the scope edges your topic actually has — biographies in/out, lists in/out, "in popular culture" in/out, etc.
   - Sketch a 3–5-step gather strategy. Name the *first* metered tool you'll call and *why* (which axis it covers, what it'll surface).
   - No user is here to confirm; talk it through to yourself, then proceed.

4. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). Follow the server's PIPELINE, COST AWARENESS, NOISE TAXONOMY, KNOWN SHARP EDGES, and WRAP-UP guidance.

5. Do SPOT CHECK and GAP CHECK before phase-1 wrap-up per the server instructions. No user is here to propose probe titles — fabricate them yourself.

6. Call `submit_feedback(phase=1, ...)` with honest values for the structured fields. At minimum populate `coverage_estimate`, `strategies_used`, `spot_check`, `sharp_edges_hit`, `tool_friction`, and `prep_calls_made` (which prep-checklist items you actually completed). Don't call `export_csv` — the scoring script pulls the corpus directly from the server.

## Protocol — phase 2 (reach extension + reflection)

After phase-1 `submit_feedback` lands, you continue on the same topic for a focused reach-extension round. Phase 2's metric is *audited reach beyond gold*; phase 1's metrics are what we actually optimize for.

1. Inspect your phase-1 corpus via `describe_topic` and `get_articles_by_source`. Identify articles or *classes of articles* you may have missed.

2. Extend reach using the REACH EXTENSION meta-tactics in `server_instructions.md` (cross-language sweeps, eponym chains, niche-example probes, additional Wikidata-property probes). Apply tactics you didn't try in phase 1.

3. Phase-2 budget (autonomous-only):
   - Ceiling ~30 metered tool calls.
   - Early exit when the last 10 metered calls yield fewer than 2 on-topic finds.
   - Soft headroom to ~60 if mid-strategy with high expected yield on the next call.

4. Submit a second `submit_feedback(phase=2, ...)`. Required structured fields:
   - `phase_1_misses`: list of `{pattern: ..., guidance_that_would_help: ...}` dicts. Class-level patterns ("missed all eponymous taxonomy genera", "missed Spanish-language biographies") — NOT literal article titles. Gold article lists never appear in your reflections (privacy invariant).
   - `phase_1_confidence_recalibration`: float — delta between your phase-1 confidence and what you'd rate it now after seeing what phase 2 surfaced. Negative = phase-1 was overconfident.
   - `prep_calls_skipped`: list of prep-checklist steps you didn't take in phase 1 but, looking back, would have helped.

5. Reply with a short summary: phase-1 final count, phase-2 reach finds, calibration delta, key reflection points.
