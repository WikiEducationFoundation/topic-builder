# african-american-stem

Benchmark topic: Wikipedia biographies of African American people in
STEM research, with US affiliation. One of five benchmarks — represents
the "intersectional biography" shape that Wiki Education specifically
prioritizes ratcheting completeness for.

See `../README.md` for the umbrella; sister benchmark is
`benchmarks/hispanic-latino-stem-us/`.

## Why this topic

- **WikiEd priority.** Intersectional biography is the most important
  shape for Wiki Education's impact goals — coverage gaps here are the
  primary reason the Topic Builder exists.
- **Moderate size** (832 articles) + **existing medicine blocklist**
  (topic id 8, 807 articles) — gives us an external signal for the
  clinical-medicine exclusion rule.
- **Category-heavy triangulation** (61.8% multi-sourced in the arc
  run) — very different signal shape from CRISPR (0% multi) and
  Apollo 11 (30%).

## Status

| Artifact | Status |
|---|---|
| `scope.md` | First draft 2026-04-23, modeled on hispanic-latino-stem-us. |
| `rubric.txt` | First draft 2026-04-23. |
| `baseline.json` | Computed from pre-logging-backfill run (API-call counts not captured). |
| `gold.csv` | Audited 2026-04-23. on_topic ∈ {in, peripheral, out, uncertain}. |
| `audit_notes.md` | Classification summary + 20 uncertain cases for Sage review. |
| `calls.jsonl` | **Pending** — written after first ratchet run. |
| `runs/` | (empty) |

## Origin

Topic 7 "African American people in STEM" was built 2026-04-17 as a
sister to hispanic-latino-stem-us. Sources were predominantly
`category:African-American scientists` + `category:African-American engineers`
+ targeted search. No `submit_feedback` was called on this topic, so
`ai_self_rating` in baseline.json is null.

The arc run predates the Stage 1.1 logging backfill, so
`total_api_calls` in baseline.json is 0 (the field wasn't populated
for these historical calls). `wall_time_s` and `tool_call_count` are
accurate. Future benchmark runs against the patched server will
produce fully-instrumented baselines.

## Known gaps the baseline left on the table

- **Medicine-blocklist articles still in corpus.** The "AA STEM
  medicine blocklist" topic identified clinical-physician bios as
  candidates for exclusion but the blocklist was never applied to
  topic 7. A future run should produce a tighter corpus by default.
- **Wikidata P106 (occupation)** — e.g. `occupation = physicist` AND
  `ethnic group = African American` would surface additional bios
  the category-based sweep missed.
- **Cross-wiki for African-diaspora researchers** — e.g. frwiki for
  Francophone African researchers with US postdocs. Non-zero reach.

## How a future run competes

1. Establish topic, persist a rubric via `set_topic_rubric` (or lift
   from `rubric.txt`).
2. Run the build end-to-end.
3. Compare vs. `baseline.json` + `gold.csv`:
   - Precision vs. gold — must not regress.
   - Recall vs. gold — must not regress.
   - At least one cost metric (`wall_time_s`, `total_api_calls`,
     `tool_call_count`) improves.
   - Reach (audited on-topic additions beyond current gold) is the
     aspirational win; this is Wiki Education's primary interest for
     this shape.
