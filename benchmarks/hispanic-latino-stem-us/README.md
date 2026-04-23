# hispanic-latino-stem-us

First Topic Builder benchmark. Scope frozen 2026-04-17 (see `scope.md`).
Integrated into the 5-benchmark ratchet 2026-04-23 alongside apollo-11,
crispr-gene-editing, african-american-stem, and orchids.

## Origin

Bootstrapped from a dogfood session run on 2026-04-17 where the user
built a 440-article list for this topic and submitted feedback rating it
7/10. The audit found the list had ~334 likely under-scores (Hispanic
scientists cut by binary scoring) and ~6 meta pages that slipped through
cleanup, so the user-scored set is not authoritative as-is.

## Status (2026-04-23)

| Artifact | Status |
|---|---|
| `scope.md` | Frozen 2026-04-17 (user-directed scope decisions) |
| `petscan.md` | **Pending** — PetScan query attached in README section below (psid=32906566); formal .md file not written |
| `gold.csv` | **Audited** — 701 rows: 314 positive, 387 negative (binary on_topic=true/false from 2026-04-17) |
| `audit_notes.md` | From original audit — documents classifier passes and edge cases |
| `baseline.md` | From original audit — precision/recall report format |
| `baseline.json` | **Added 2026-04-23** — standardized metrics matching the 5-benchmark suite |
| `rubric.txt` | **Added 2026-04-23** — three-tier rubric aligned with other benchmarks; notes binary → in/out mapping |
| `calls.jsonl` | 28 lines — exemplar session script |
| `review_queue.json` / `review_cursor.txt` | Audit state tracking from original pass |

## Current baseline vs. existing gold (2026-04-23)

Topic 6 on the server has **1,936 articles** (grew since the original
2026-04-17 build). Measured against the existing audited `gold.csv`:

| Metric | Value |
|---|---:|
| Gold positives total | 314 |
| Gold positives in current corpus (recall) | 309 / 314 = **98.4%** |
| Gold positives NOT in corpus (reach candidates) | 5 |
| Gold negatives in current corpus (false positives → remove) | 381 |
| Corpus articles NOT in gold (unaudited — need classification) | 1,246 |
| Precision vs. audited subset of corpus | 309 / 690 = **44.8%** |

The 1,246 unaudited articles are the biggest open question — they
include both legitimate gold-candidate biographies that should extend
the gold, and search-noise articles that should be OUT. Running the
3-tier rubric (`rubric.txt`) against them would produce a full
classification; deferred pending future audit time.

## Ratchet targets for this benchmark

- **Reduce false positives.** 381 corpus articles are confirmed OUT
  per gold; a future run with better scope-filtering should ship
  without them.
- **Recover the 5 missing gold positives** (Alba Colón, Annie Antón,
  Carmen Cid, Cecilia R. Aragon, Celso-Ramón García, Craig Henriquez
  — per baseline.md).
- **Audit the 1,246 unaudited.** Classify via the rubric; grow gold
  as audited-positives are confirmed; reduce precision denominator
  bias.
- **Cross-wiki reach.** Spanish-language Wikipedia likely has
  Latino STEM biographies not sitelinked to enwiki. High-priority
  reach target for this topic shape (the PetScan query is en-only).

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
