# Dogfood session notes — 2026-04-28 (crispr-gene-editing-thin, Claude Code Opus 4.7, medium effort)

> **What this is.** First ratchet run after the 2026-04-28 ship of three
> Tier 1 items from the strategy brainstorm: `get_article_see_also` tool,
> `hastemplate-typed-probe` + `articletopic-classifier-probe` strategy
> moves, and `llm-fabricate-and-verify` move. Run was a fresh-terminal
> autonomous kickoff (`fetch_task_brief()` round-robin → CRISPR), then
> two-phase build with `submit_feedback` per phase. Ratchet-scored
> against the 2026-04-25 baseline.
>
> Per-run substrate: topic id 69, run-topic
> `crispr-gene-editing-thin 20260428T1401`, 292 articles final.
> Two phases. Both feedback records + tool-call log on host.

## Gate verdict: ❌ FAIL — recall regressed despite cost win

| Metric | Run | Baseline | Δ | In gate? |
|---|---:|---:|---|---|
| Corpus size | 292 | 354 | ↓62 | informational |
| Precision vs gold | 100% | 91% | ↑9pp | yes |
| Recall vs gold | **82.5%** | **92.5%** | **↓10pp** | yes (regressed) |
| Reach (beyond gold) | 124 | — | new audit candidates | informational |
| API calls | 129 | 268 | ↓139 | yes (improved) |
| Tool calls | 61 | 70 | ↓9 | yes (improved) |
| Wall time (s) | 710 | 1581 | ↓871 | informational |

99 / 99 audited gold hits in corpus → precision 100%. 21 of 120
audited-gold articles missed → recall 82.5%. Reach added 124
candidates for audit. Cost down ~50%. Net: failed gate on recall
regression.

## Did the new tools / moves fire?

**No.** None of the three Tier 1 ships from earlier today were
exercised in this run.

| Tool / move | Fired? | Notes |
|---|---|---|
| `get_article_see_also` | ❌ | Never called. The `seed-anchored-mining-from-canonical-article` move was partial — `get_article_templates(CRISPR gene editing)` fired once but no `get_article_content`, `get_article_links`, `get_article_categories`, or the new `get_article_see_also`. |
| `hastemplate-typed-probe` | ❌ | No `hastemplate:` queries in the search log. |
| `articletopic-classifier-probe` | ❌ | No `articletopic:` queries. |
| `llm-fabricate-and-verify` | ⚠ partial | Name-OR'd searches ("Pardis Sabeti" OR "George Church" OR "Kevin Esvelt" OR ...) were thematically similar but not invoked as the named move. No `source="llm-fabricate:..."` provenance. |

## Missed-gold pattern is See-also-shaped

21 articles in audited gold weren't reached. Notable cluster:

- **Cas proteins** — Cas1, Cas2. Should have been caught by the
  `intitle:Cas9 OR Cas12 OR Cas13 OR ...` search but the compound-OR
  query returned 0 (the documented sharp edge — same shape as
  compound `incategory:` and `hastemplate:`). The AI flagged this in
  WHAT_DIDNT but didn't recover.
- **Technique-adjacent articles**: Gene delivery, Homology directed
  repair, Non-homologous end joining, Recombinant DNA, Gene knock-in.
  These are textbook sister-articles and exactly the kind of
  curated semantic-neighbor link that lives in
  `==See also==` on the canonical CRISPR articles.
- **Major figure**: George Church (geneticist) — covered by an OR'd
  name search that pulled noise instead.
- **Subjects/tools**: Streptococcus pyogenes, PCSK9, Perturb-seq,
  Lovotibeglogene autotemcel, Colossal Biosciences (and dire wolf
  project), Genetically modified crops, Timeline of biotechnology,
  Kim Jin-soo (biologist), Kira Makarova, Sean Parker, University of
  California Berkeley.

The missed-gold list is suggestive: a substantial fraction would
plausibly appear in a See-also harvest of "CRISPR gene editing" or
"CRISPR" — specifically the technique-adjacent cluster. Not yet
verified empirically against the actual See also section content;
worth a one-off check next session.

## Other observations

- **PREP checklist short-circuited.** The AI claimed
  `prep_calls_made=['list_exemplars']` in phase-1 feedback, but the
  usage log shows zero `list_exemplars` calls and zero `get_exemplar`
  calls. WHAT_WORKED text invokes "Apollo concentric-rings + climate-
  change WikiProject framing" — apparently AI training-data recall of
  exemplars rather than the live tool. The confabulation crosscheck
  caught this (`claimed_prep_call_no_evidence:list_exemplars`).
- **`audit_progress` not consulted.** No call. The mid-build pivot
  signal (yield_trajectory, applicable-but-unattempted moves) was
  available but unused.
- **11 confabulation flags on `strategies_used`.** All of the form
  `(unmapped family — add to _STRATEGY_FAMILY_EVIDENCE if this is a
  real category)`. The AI populated `strategies_used` with canonical
  move names from `strategy_moves.md` (`category-shape-survey-with-
  branch-identification`, `wikiproject-recon`, etc.) instead of the
  family tags `_STRATEGY_FAMILY_EVIDENCE` expects (`category_crawl`,
  `wikiproject`, etc.). Reproduces the existing Tier 1 backlog item
  "Widen confabulation crosscheck coverage" from a fresh run.
- **Auth save-to-memory prompt did not fire.** AI authenticated on
  first `start_topic` but never asked the user whether to save the
  token. Already drafted as a Tier 1 backlog entry; this run is the
  motivating evidence.
- **Compound `intitle:OR` returned 0** even though `search_articles`
  is supposed to auto-split. Server logged "compound intitle-OR split
  into 4 separate queries" — the workaround fired but the merged
  result was still 0, suggesting a deeper issue. Worth investigating
  if a second session reproduces.

## Coverage band derivation

- Phase 1 band: **high** — triangulation 43.9% (>40%), 9/12
  applicable moves attempted (75%), yield trajectory 'plateau'.
  Phase 1 rating 7/10.
- Phase 2 band: **moderate** — triangulation 42.5%, 11/12 applicable
  moves attempted, yield rising. No phase-2 rating supplied.

The "high" verdict for phase 1 sits alongside 82.5% actual recall —
band-vs-recall calibration is a live datapoint for
`scripts/analyze_calibration.py`.

## Open observations / pending pattern-tracking

These are *not* yet promoted to backlog. Per Sage 2026-04-28: hold
for multi-session evidence before deciding action.

Annotation update after the second 2026-04-28 run (HL-STEM, see
`session-2026-04-28-hl-stem-thin-claude-code.md`): items 1, 2, 4
now reproduce. 2/2.

1. **Catalog-vs-reach gap.** New tools/moves landed in catalog but AI
   didn't reach for them. Cause unclear: prep checklist short-circuit?
   Move-catalog discoverability? Topic shape didn't naturally invite
   them? Want to see whether next 2-3 dogfood runs exercise any of
   the new tools/moves. **(Reproduced 2026-04-28 HL-STEM — 2/2 runs no new tools fired.)**
2. **PREP checklist effectiveness.** `list_exemplars` claimed but not
   called this run. Reproduces? Or one-off? **(Reproduced 2026-04-28 HL-STEM. Notable: phase-2 prep — `get_exemplar(allow_own=True)` — DID fire when the brief explicitly names the call; phase-1 prep — "use the checklist which includes `list_exemplars`" — short-circuits. Imperative > checklist.)**
3. **Seed-anchored-mining-from-canonical-article move partial-fire.**
   Only `get_article_templates` step ran — none of the other 7 steps.
   Move catalog says "RTFA → categories → navboxes → wikiproject →
   wikidata → see-also (new) → links → backlinks." Worth checking
   whether other shapes get a more complete sweep. **(HL-STEM didn't run any of the seed-anchored steps either — but HL-STEM doesn't have a single canonical article in the same way, so the move's preconditions might not match. Still inconclusive.)**
4. **Phase-2 reach extension underused the new moves.** Phase 2 ran
   `harvest_navbox` (existing) + `wikidata_entities_by_property`
   (existing) + `morelike:` (existing). The new `articletopic:` /
   `hastemplate:` / `get_article_see_also` were natural phase-2 fits
   that didn't surface. **(Reproduced 2026-04-28 HL-STEM — phase 2 added 5 manually-seeded articles, no new-tool use.)**
5. **Compound `intitle:OR` auto-split followed by 0 results.** Either
   the workaround broke or the OR'd alternations matched nothing
   (hostile spelling, page-namespace issue, etc.). Worth a 5-minute
   smoke if it recurs.

## Run artifacts

- Scoreboard: `benchmarks/crispr-gene-editing/runs/20260428T141720_crispr-gene-editing-thin_20260428t1401.{md,json}`
- Two `submit_feedback` records on host: `/opt/topic-builder/logs/feedback.jsonl`
- Tool-call log: `/opt/topic-builder/logs/usage.jsonl`
- Review one-shot: `bash scripts/smoke.sh scripts/review_run.py -- 69`
