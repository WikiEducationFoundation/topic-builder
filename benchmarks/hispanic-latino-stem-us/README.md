# hispanic-latino-stem-us

First Topic Builder benchmark. Scope frozen 2026-04-17 (see `scope.md`).

## Origin

Bootstrapped from a dogfood session run on 2026-04-17 where the user
built a 440-article list for this topic and submitted feedback rating it
7/10. The audit found the list had ~334 likely under-scores (Hispanic
scientists cut by binary scoring) and ~6 meta pages that slipped through
cleanup, so the user-scored set is not authoritative as-is.

This benchmark is being built as the first "gold-standard" topic for the
Topic Builder tool-change regression harness.

## Status

| Artifact | Status |
|---|---|
| `scope.md` | Filled in 2026-04-17 (user-directed scope decisions) |
| `petscan.md` | **Pending** — user has a PetScan query they use as the non-AI baseline; to be attached in a future session |
| `gold.csv` | **Pending** — audit starts once PetScan query is attached |
| `calls.jsonl` | **Pending** — exemplar session script written after gold exists |

## Pending work

1. User attaches the PetScan query → this file gets filled as
   `petscan.md` with the raw query, run timestamp, and result count.
2. Merge candidate pool: PetScan results ∪ user's 2026-04-17 score=1
   articles ∪ anything else we surface during audit.
3. Audit each candidate against `scope.md`. Three buckets:
   - Both methods agree + on-topic → high-confidence gold positive
   - Both agree + off-topic → gold negative (useful for testing
     noise-removal tools)
   - One-method-only → investigate each; promotes to positive or
     negative based on scope.md
4. Write `gold.csv` with a row per audited article:
   `title, on_topic, best_source_strategy, justification, notes`.
5. Write `calls.jsonl` — an idealized tool-call sequence that a good AI
   run would make to try to hit the gold set. Used by
   `scripts/benchmark.py` to produce precision/recall reports.
6. Run `scripts/benchmark.py hispanic-latino-stem-us` to establish the
   baseline report.

## How gold will be validated

- Each positive must be justified against the `scope.md` rulings. If
  the justification would require relaxing or extending a scope rule,
  the scope is the thing that gets updated (deliberately, with a note).
- Edge cases (Brazilian-American scientists, physician-scientists,
  scientists who visited the US briefly) get explicit notes in `gold.csv`
  and default to OUT per scope.md.
- Articles scored inconsistently across methods (PetScan IN but user OUT,
  or vice versa) get the deepest scrutiny.

## Refresh cadence

Quarterly at minimum. Record the last-audited date at the top of
`scope.md` and bump it on every audit pass. Wikipedia renames, merges,
and creates articles continuously.

## What lives here locally (NOT in git)

Per the `benchmarks/README.md` norm: `gold.csv`, any audit-notes files,
and raw PetScan result snapshots are gitignored because they pair real
people's names with possibly-incorrect judgments. Keep them on your
machine; share via private channels if ever needed.

## PetScan baseline

The org's non-AI baseline for this topic is a PetScan saved query:
[psid=32906566](https://petscan.wmcloud.org/?psid=32906566). Categories
input: `Hispanic_and_Latino_American_scientists` (deep category tree
search, single root category). Result count on 2026-04-17: 284 articles.

Known scope mismatch: the PetScan query's root category pulls in many
clinical physicians because Wikipedia's category tree nests medical
specialties under "scientists." Our frozen scope excludes clinical
medicine (see `scope.md`), so PetScan will have false positives we'll
need to audit out. Despite the mismatch, it's the best available
mechanical comparison set for this topic.

Populate `petscan.md` with the committed query summary; do not commit
the raw results.
