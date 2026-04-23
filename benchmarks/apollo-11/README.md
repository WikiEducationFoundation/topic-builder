# apollo-11

Benchmark topic: the Apollo 11 crewed lunar-landing mission. One of five
benchmarks in the ratchet — representing the "single historical event
with cultural tail" shape. See `../README.md` for the umbrella.

## Why this topic

- **Shape:** rich cross-linking, moderate triangulation (~30% multi-
  sourced in the initial run), substantive cultural tail, Wikidata-
  property potential across P361 / P793 / P138 / P17.
- **Documented gap dynamics:** the original arc run missed Kennedy Space
  Center (rescued only via `browse_edges`), never used `harvest_navbox`,
  and skipped the Wikidata things-named-after probe — concrete reach
  targets for future runs.
- **Moderate size:** 699 articles — small enough to audit by eye if
  we want to, large enough to stress the cost metrics.

## Status

| Artifact | Status |
|---|---|
| `scope.md` | First draft 2026-04-23, from the arc run's observed scope. |
| `rubric.txt` | First draft 2026-04-23 (CENTRAL/PERIPHERAL/OUT, three-part). |
| `baseline.json` | Computed from arc run (2026-04-23T15:37 → T15:58 UTC). |
| `gold.csv` | **Pending audit** — 699 rows all marked `pending_audit`. |
| `calls.jsonl` | **Pending** — exemplar script written after gold is audited. |
| `runs/` | (empty) Per-run artifacts land here as future benchmark runs land. |

## Origin

Bootstrapped from the 2026-04-23 Apollo 11 dogfood session (Claude Code,
rating 7). That run was the first dogfood session after the `note=`
parameter and the autonomous-spot-check task.md update landed, but ran
*before* the Chunks 1–6 tool improvements. So the baseline represents a
mid-upgrade state; a fresh run on the current server should already beat
it on most cost axes thanks to the post-arc fixes.

## Known gaps the baseline run left on the table

- **Kennedy Space Center** was only rescued via `browse_edges` from
  peripheral seeds; direct `Template:Apollo program` harvest (via
  the newer `harvest_navbox`) would have caught it in one call.
- **No Wikidata things-named-after probe.** P138=Q43653 would surface
  schools, streets, vessels, craters. Reach candidate.
- **No cross-wiki walk.** Low-priority for this topic (enwiki-dominant)
  but non-zero reach target.
- **`intitle:"A" OR intitle:"B"` compound OR bug** bit the AI at least
  4 times per its feedback; Chunk 2 fixed this, so future runs should
  save ~8 redundant calls.

## How a future run should compete against this baseline

1. On topic creation, write and persist a rubric via `set_topic_rubric`.
   Reference `rubric.txt` if you want to match the benchmark scope; adapt
   if the run has a narrower interest.
2. Run the build end-to-end. At export, pull the final corpus + usage
   log and compute the metrics.
3. Compare against `baseline.json`:
   - Precision (gold ∩ corpus / corpus) must not drop below the baseline.
   - Recall (gold ∩ corpus / gold) must not drop below the baseline.
   - At least one of `wall_time_s`, `total_api_calls`, `tool_call_count`
     must improve.
   - Reach (audited on-topic additions beyond `gold.csv`) is the
     aspirational win.
4. If precision/recall hold and at least one cost metric improves, the
   run passes; its metrics become the new baseline (and any reach
   additions that pass audit grow `gold.csv`).
