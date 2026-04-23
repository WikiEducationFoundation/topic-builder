# crispr-gene-editing

Benchmark topic: CRISPR gene editing. One of five benchmarks — represents
the "scientific discipline with distinctive vocabulary" shape. See
`../README.md` for the umbrella.

## Why this topic

- **Shape:** search-native (distinctive lexical stem "CRISPR" / "Cas"),
  weak category / list structure, single-source-heavy. The Codex arc
  reached rating 8 here with only 14 tool calls and 46 API calls —
  tight baseline to beat.
- **Small + clean** (99 articles). Easy to audit exhaustively, easy
  to iterate against.
- **Documented noise class:** lexical search pulled in ~15 obvious
  unrelated articles (Cement, Plastic, Submarine, Umeå, etc.) — a
  ratchet target for smarter filtering.

## Status

| Artifact | Status |
|---|---|
| `scope.md` | First draft 2026-04-23, from arc-run corpus + Codex feedback. |
| `rubric.txt` | First draft 2026-04-23 (CENTRAL/PERIPHERAL/OUT). |
| `baseline.json` | Computed from arc run (2026-04-23T18:21 → T18:27 UTC). |
| `gold.csv` | Audited 2026-04-23. on_topic ∈ {in, peripheral, out}. |
| `audit_notes.md` | Audit rationale + judgment calls. |
| `calls.jsonl` | **Pending** — exemplar script written after first ratchet run. |
| `runs/` | (empty) |

## Origin

Bootstrapped from the 2026-04-23 CRISPR dogfood session (Codex, rating 8).
That run went single-search → preview_similar → auto_score_by_keyword →
export in ~5 min, under 50 API calls. Represents an efficient baseline
on a search-native shape; the ratchet asks whether we can do as well or
better while ALSO catching reach articles (things-named-after, Wikidata-
property members) that the arc run didn't probe for.

## Known gaps the baseline left on the table

- **No Wikidata probe.** P101 (field of work) = Q42240 (CRISPR) would
  likely surface additional pioneer biographies.
- **No navbox harvest.** If Wikipedia maintains a CRISPR-related navbox
  template, `harvest_navbox` would surface related articles the single-
  search missed.
- **Search noise was cleaned manually.** Codex removed 13 articles via
  `remove_articles`; a stronger relevance filter (centrality scoring,
  description-match rejection) would cut this overhead.
- **No cross-wiki probe.** He Jiankui has substantial coverage on
  zhwiki / jawiki that may not sitelink to enwiki.

## How a future run competes

1. Establish the topic, persist a rubric via `set_topic_rubric`.
2. Run the build end-to-end.
3. Compare final state to `baseline.json`:
   - Precision vs. `gold.csv` must not drop below the baseline run's
     audited precision.
   - Recall vs. `gold.csv` must not drop.
   - At least one of `wall_time_s`, `total_api_calls`, or
     `tool_call_count` must improve.
   - Reach (on-topic additions beyond `gold.csv`) is the aspirational
     win — CRISPR's baseline is search-heavy, so Wikidata- or
     navbox-driven reach is where the upside lives.
