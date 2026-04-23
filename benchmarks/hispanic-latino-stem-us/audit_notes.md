# Audit notes — hispanic-latino-stem-us (2026-04-17)

First-pass gold set built via iterative automated classification + targeted
human review. Local-only (gitignored).

## Inputs

- PetScan query psid=32906566 returned **284** articles
  (Hispanic_and_Latino_American_scientists category, deep tree)
- User 2026-04-17 `score=1` set: **440** articles
- Union candidate pool: **550** unique titles
- Enriched each with Wikidata shortdesc, categories, and lead extract via
  Wikipedia API (batch-fetched in groups of 20 with continuation handling;
  initial batch-50 attempt silently truncated categories because `cllimit`
  is query-total, not per-page — documented gotcha for future topics)

## Final gold.csv

| Verdict | Count |
|---|---:|
| IN (`on_topic=true`) | 296 |
| OUT (`on_topic=false`) | 254 |
| REVIEW (`on_topic=''`) | 0 |

## Classifier passes

The classifier ran in several refinement passes, each resolving a different
REVIEW sub-bucket:

1. **v1 (initial):** substring-match heritage + profession in cats/desc.
   Caught obvious IN (category:Hispanic and Latino American scientists +
   STEM) and obvious OUT (Brazilian/Portuguese/peninsular Spanish, clear
   non-STEM occupations). Result: 282 IN / 107 OUT / 161 REVIEW.
2. **v2 (extract-aware):** looked inside 600-char lead for heritage signals
   that shortdescs omit. Moved ~50 REVIEW to definite buckets. Result: 285
   IN / 155 OUT / 110 REVIEW.
3. **v2.5 (non-STEM description override):** caught 22 rows where the
   description led with a non-STEM profession (economist, politician,
   psychologist) despite cats containing generic "scientists." Flipped
   them IN → OUT.
4. **v3 (broader heritage patterns):** matched "X of <country> descent"
   forms beyond "people of X descent", and "Latin American X" in prose,
   catching articles like "American academics of Mexican descent." Also
   matched non-Hispanic identity markers (African-American, Jewish-American,
   German-born) to cut false positives. 20 flips.
5. **v4 (nationality-adjective word-boundary + country-name match):**
   caught "Venezuelan hydrologist," "Mexican mathematician," "grew up in
   Colima, Mexico" style signals. 12 flips (all IN).
6. **v5 (PetScan membership + Hispanic-surname heuristic):** for residual
   REVIEW, promoted IN when article is in PetScan (which by definition
   claims Hispanic heritage via category structure) or when the last name
   is in an expanded Hispanic-surname list (accent-normalized, hyphen-
   aware). Default OUT for user-only adds with no Hispanic signal — the
   audit on the original session showed search-driven noise is ~85%.
   62 flips.
7. **v6 (cleanup):** fixed a bug where the surname heuristic matched first
   names (e.g. "Vera Kistiakowsky" wrongly flipped because "Vera" is a
   Hispanic surname when it's a surname). Also applied explicit hand-
   decisions for the final 10 residuals and a few late-surfacing edge
   cases (Frances Colón as science-diplomat → OUT; Natalie Batalha as
   Portuguese heritage → OUT; Tomás Lozano-Pérez as Cuban-descent
   roboticist → IN, etc).

## Known gold-set limitations

- **"User-only noise default = OUT"** is a lossy call. If the dogfood user
  added an article via a broad search but the target really is a Hispanic
  STEM person whose Wikipedia article never explicitly says so, we likely
  cut them. Examples that might be wrong-to-OUT: articles with very
  common Anglicized names of Latin-American-descent scientists.
- **Hispanic surname heuristic** is best-effort. It relies on a hand-
  curated list; rare surnames won't match; surnames from other Romance
  languages (Portuguese, Italian) could false-positive if not in the
  explicit-Portuguese-OUT list.
- **US affiliation** was checked via text signals (universities, NASA,
  "American X"). Subtle cases where a scientist did a brief US postdoc
  and returned home may have been wrongly cut as "no US affiliation" or
  wrongly kept.
- **Physician-scientist research/clinical line** was drawn on surface
  textual signals (research-phrases in lead). Some clinical-leaning
  researchers may be misclassified.

A quarterly refresh pass should revisit these with human review.

## Benchmark baseline (baseline.md, gitignored)

Current state after the unknowns audit + initial human-verification pass:

- Gold set: **314 IN / 387 OUT / 0 REVIEW** (701 total)
- Recall: **83.8%** (264 / 315 pre-Cumpiano-fix; recompute after verified pass)
- Working-list noise: 257
- Unknown-in-working: 0 (audited)
- Gold positives missed: 51 (candidates for next-iteration calls.jsonl)

These numbers are the baseline to beat: any tool or prompt change should
re-run the benchmark and either improve recall, reduce noise, or both.

## Human-verification progress

Added a `human_verified` column to `gold.csv`. Value `true` means a human
read the Wikipedia article and the current `on_topic` is their confirmed
call. Workflow:

- Build a sampled queue: `python3 /tmp/build_review_queue.py` (samples 10
  from each low-confidence bucket — surname-heuristic IN, user-only-noise
  OUT, search-surfaced OUT, refined-heritage IN/OUT — shuffles them).
  Queue is cached in `benchmarks/<slug>/review_queue.json` +
  `review_cursor.txt` (both gitignored).
- Walk through one at a time. For each, fetch the Wikipedia URL, eyeball,
  then `python3 /tmp/verify_one.py "<title>" <IN|OUT|KEEP> [reason]` which
  updates `gold.csv` (sets `human_verified=true` + updates `on_topic` if
  flipped) and shows the next item.

### Session log

- **2026-04-17 (first pass):** verified 10 rows, skipped 1.
  - **OUT confirmed** (8): William R. Cumpiano (luthier, pre-queue), Jack
    Dongarra (Italian-American), Jennifer Widom, Mónica Fonseca (Colombian
    but journalist), Jeff Morales (public servant), Claudia Alexander
    (African-American), Ibrahim Cissé (Nigerien-American), Deborah
    McGuinness.
  - **IN confirmed** (2): Mónica Medina (Colombian-American scientist),
    E.J. Chichilnisky (Argentine-born neurobiologist, Stanford).
  - **Skipped** (unresolved, worth deeper review): Kerstin Perez —
    surname + "swexicana" self-ID strongly hint Mexican-American but no
    definitive external confirmation.
  - Queue paused at index 10 (Walter Alvarez, who has "American people
    of Asturian descent" — peninsular Spanish, leans OUT per scope).
  - **29 remaining in the queue.** To resume: copy saved state back to
    /tmp if missing, then run `python3 /tmp/verify_one.py` with the next
    title.

### Lessons-to-fold-back observations

During the verification pass, I noticed the classifier missed some clear
heritage signals that should have been caught automatically:

- **Italian-American** heritage (Dongarra) — not in `NON_HISPANIC` list;
  should trigger OUT by matching "italian american" / "italian-american"
  in cats.
- **Colombian descent in cats** (Mónica Fonseca) — category includes
  "American people of Colombian descent" but the unknowns-audit classifier
  didn't surface heritage; the verdict stayed OUT for the right reason
  (non-STEM profession) but the reason string was misleading.
- **Asturian** (Walter Alvarez) — peninsular Spanish region, not caught
  by my SPANISH_PENINSULAR list. Add "asturian", "galician", "catalan",
  "basque" as peninsular-Spanish indicators.

These are small refinements for a future classifier iteration.

## Files in this directory

| File | In git? | Purpose |
|---|---|---|
| `scope.md` | yes | Frozen scope rules |
| `README.md` | yes | Per-topic workflow |
| `calls.jsonl` | yes | Exemplar tool-call sequence |
| `gold.csv` | **no** | Authoritative per-article verdicts (real names) |
| `gold-readable.csv` | **no** | Spreadsheet-friendly view (URL column, Yes/No, ✓) |
| `audit_notes.md` | **no** | This file |
| `baseline.md` | **no** | Detailed benchmark report with sample lists |
| `review_queue.json` | **no** | Persisted review queue for hand-verification |
| `review_cursor.txt` | **no** | Current position in review queue |
