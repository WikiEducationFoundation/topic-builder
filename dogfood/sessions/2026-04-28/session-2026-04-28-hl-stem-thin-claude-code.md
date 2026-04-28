# Dogfood session notes — 2026-04-28 (hispanic-latino-stem-us-thin, Claude Code Opus 4.7)

> **What this is.** Second ratchet run of the day after the
> 2026-04-28 ship of three Tier 1 items
> (`get_article_see_also` tool, `hastemplate-typed-probe` +
> `articletopic-classifier-probe` strategy moves,
> `llm-fabricate-and-verify` move). Companion to the earlier
> CRISPR run — see `session-2026-04-28-crispr-thin-claude-code-medium.md`.
> Same pattern (autonomous kickoff, two-phase build), different
> topic shape: demographic × discipline intersection.
>
> Substrate: topic id 70, run-topic
> `hispanic-latino-stem-us-thin 20260428T1416`, 681 articles final.
> claude-code/opus-4.7 (no `effort` param recorded this run).

## Gate verdict: ❌ FAIL — precision regressed; recall up but precision sank

| Metric | Run | Baseline | Δ | In gate? |
|---|---:|---:|---|---|
| Corpus size | 681 | 199 | ↑482 | informational |
| Precision vs gold | **77.6%** | **95.4%** | **↓17.8pp** | yes (regressed) |
| Recall vs gold | 67.6% | 58.9% | ↑8.7pp | yes (improved) |
| Reach (beyond gold) | 403 | — | new audit candidates | informational |
| Hit OUT (false-positive) | 62 | — | gold says off-topic | informational |
| Missed gold | 103 | — | recall-loss candidates | informational |
| API calls | 1425 | 480 | ↑945 | yes (worse) |
| Tool calls | 65 | 59 | ↑6 | yes (worse) |
| Wall time (s) | 1038 | 1165 | ↓127 | informational |

215/318 gold covered (recall 67.6% vs 58.9%). 62 OUT-classified
hits in corpus — false-positive rate 9.1% vs baseline 4.6%. Cast a
wider net, kept the looser end. Net: opposite failure mode from the
CRISPR run earlier today.

## Comparison to the morning CRISPR run

| Axis | CRISPR (id=69) | HL-STEM (id=70) |
|---|---|---|
| Gate | FAIL | FAIL |
| Failure axis | recall ↓10pp | precision ↓17.8pp |
| Corpus | 292 (vs 354 baseline) | 681 (vs 199 baseline) |
| Cost | ~50% cheaper | ~3× more expensive |
| New tools fired? | none | none |
| PREP short-circuit | yes (`list_exemplars` claimed, not called) | yes (same) |
| Confab flags | 11 | 15 |

The two runs cast in **opposite directions** but neither hit the
gate. Strategy-shape mattered: CRISPR got vocabulary-anchored
searches; HL-STEM got a giant WikiProject pull plus aggressive
shortdesc filtering. Each failure mode is shape-coherent.

## Did the new tools / moves fire?

**No — second run in a row.**

| Tool / move | Fired? | Notes |
|---|---|---|
| `get_article_see_also` | ❌ | Never called. Seed-anchored mining sequence did not run. |
| `hastemplate-typed-probe` | ❌ | No `hastemplate:` queries, despite the topic being a typed-thing biography shape where `hastemplate:"Infobox scientist"` would have been a precision filter for the WP backbone. |
| `articletopic-classifier-probe` | ❌ | No `articletopic:` queries. STEM is a top-level ORES category — would have been a coarse filter on top of the noisy 14K WP pull. |
| `llm-fabricate-and-verify` | ❌ | Phase-2 added 5 manually-seeded canonical figures (Severo Ochoa, Helen Rodríguez Trías, France A. Córdova, José Hernández astronaut, Carlos Bustamante) — same shape as fabrication but not invoked as the named move. |

## What the AI did instead

- WikiProject "Latino and Hispanic heritage" pull (14,510 articles, the demographic backbone).
- `auto_score_by_description` with STEM-occupation marker axis to cut the non-STEM 95%. Triangulation rose 1.9% → 26%.
- Two list-page harvests (Puerto Rican scientists/inventors, Puerto Ricans in NASA).
- Targeted searches.
- `morelike:` probes from canonical figures (Ellen Ochoa, Mario Molina, France Córdova, Albert Baez) — turned out to be noise traps; the AI removed ~190 noise articles via `remove_by_source` after.
- `wikidata_query` with `wdt:P172=Q581921` (Mexican Americans, 83 enwiki rows) — sparse, mostly entertainers.
- Phase 2: `get_exemplar(allow_own=True)` was called this time (unlike CRISPR), and surfaced 5 silently-rejected canonical figures whose shortdescs failed the marker filter.

## Sharp edges hit (rich crop)

The AI's own surfacing in `sharp_edges_hit`:

- **`wdt:P172` (ethnic group) is sparsely populated for STEM biographies** — 83 enwiki rows total, mostly entertainers. The demographic Wikidata property is not a useful additive layer for this intersection.
- **`morelike:` from biographies of demographic-intersection topics returns the discipline neighbors not the demographic neighbors.** Ellen Ochoa morelike → American astronauts (Sally Ride, Robert Crippen). France Córdova → non-Hispanic astrophysicists. Mario Molina → CFC chemistry concept articles, not collaborators. Coherent and damning observation.
- **`auto_score_by_description` marker matching needs exact word-form, not prefix.** Adding `'hematolog'` did not catch `'hematologist'` — had to expand the marker list.
- **Wikidata SPARQL with `wdt:P106/wdt:P279*` + multi-country `VALUES`** times out at the public endpoint.
- **`fetch_descriptions` 60s default budget too short on 15K-article topics** (had to call 3 times).

The morelike-shape-noise observation is fresh and worth surfacing.
It generalizes: morelike-from-pure-topic-seed works on bounded
typed concepts, but on demographic-intersection biographies, BM25
can only follow ONE axis of similarity at a time, and discipline
overpowers demographic.

## Tool friction observations

- `search_similar` yields are unaudited until you preview them. **`preview_similar` would have saved 4 morelike pulls and ~190 wasted noise articles.** This run committed first then cleaned up — exactly the failure pattern `preview_*` was supposed to prevent.
- `auto_score_by_description`'s "axes doing most of the cutting" warning fired but was correct (the cut was intended). Could distinguish between intended vs accidental over-cutting.
- No native gather-time set-intersect between two source labels — `sources_all` on `get_articles` works but isn't a gather-time tool. Echoes the at-pull-time intersection backlog Tier 1 item.

## Missed-strategies (the AI's own list)

- A `wikiproject ∩ category` intersection tool (matches existing Tier 1 backlog).
- PetScan-style compound query (matches existing Tier 3).
- **Cross-language sweep on Spanish Wikipedia** for Hispanic-American STEM bios who lack rich enwiki tagging. The AI did try `survey_categories(category="Científicos hispano estadounidenses", wiki=es)` — returned 1 cat. Then tried "Científicos de Estados Unidos" (46 sub-disciplines) — too broad without a Hispanic intersection.
- Wikidata-aware "country of birth in Latin America + citizen of US + occupation subclass-of scientist" — known to time out without further constraints.
- **Eponym-chain probes** — Severo Ochoa was missing from the corpus, but eponyms (Severo Ochoa Award, Severo Ochoa Center for Molecular Biology) might have surfaced him. The `eponym-namesake-chain-walk` move exists in the catalog but didn't fire.

## PREP-checklist signals — second reproduction

- **Phase 1: `list_exemplars` claimed in `prep_calls_made`, log shows zero calls.** Confab crosscheck caught it: `claimed_prep_call_no_evidence:list_exemplars`. Identical to CRISPR run. **Two-for-two now.**
- **Phase 2 DID call `get_exemplar(allow_own=True)`** explicitly per the brief — and the AI's WHAT_WORKED text shows it was useful (surfaced 5 silently-rejected canonical figures, motivated investigating the marker-matching strictness issue). **Phase 2 PREP works; Phase 1 doesn't.**

This is interesting: the brief's phase-2 instructions explicitly
say "use `get_exemplar(slug=<own>, allow_own=True)`" and the AI
followed. The phase-1 instructions say "use the prep checklist
which includes `list_exemplars`" and the AI doesn't follow. Soft
checklist phrasing → skip. Explicit imperative → execute. Same
pattern as the auth save-to-memory observation.

## Confabulation crosscheck — second reproduction

15 flags this run. 14 of them: `strategies_used` populated with
canonical move names from `strategy_moves.md`
(`category-shape-survey-with-branch-identification`,
`wikiproject-recon`, `wikiproject-pull-as-backbone`,
`list-page-discovery-and-triage`, etc.) instead of the family tags
`_STRATEGY_FAMILY_EVIDENCE` expects. **Same shape as CRISPR (11
flags, same root cause).** This is now multi-session evidence for
the existing Tier 1 "Widen confabulation crosscheck coverage"
backlog item.

15th flag: `claimed_prep_call_no_evidence:list_exemplars` — see
PREP-checklist signals above.

## Coverage band derivation

- Phase 1 band: **moderate** — triangulation 25.9%, 12/11
  applicable moves attempted, yield trajectory 'declining'. Phase-1
  rating 7/10.
- Phase 2 band: **moderate** — triangulation 25.7%, 13/11
  applicable moves attempted, yield 'declining'. No phase-2 rating.

`band=moderate` against actual recall 67.6% — not the
overconfident "high" that CRISPR phase-1 surfaced. The phase-1
rating 7/10 IS overconfident relative to actual recall, though.

## Open observations / pending pattern-tracking

Now considering signals across both 2026-04-28 runs:

1. **Catalog-vs-reach gap** (CRISPR + HL-STEM, 2/2). New tools/moves landed in catalog but neither run reached for them. Topic shapes were different (technical-discipline vs intersectional-biography); both should have plausibly invoked at least `get_article_see_also` and `hastemplate:`. Not a one-off.
2. **PREP short-circuit on phase 1, executed on phase 2** (CRISPR + HL-STEM, 2/2). Phase-2 `get_exemplar(allow_own=True)` works because the brief explicitly names the call. Phase-1 `list_exemplars` is in the prep checklist but described as "use the prep checklist" rather than "call this tool" — short-circuited both runs.
3. **Confabulation crosscheck unmapped families** (2/2 with 11 + 15 flags). Multi-session evidence for the existing backlog item.
4. **Auth save-to-memory** — depends on what the user observed this run; if they had to re-paste vs. reused saved token, that's the second datapoint.
5. **`preview_similar` underused** — HL-STEM specifically would have been saved ~190 noise articles by previewing first. Not a new observation but fresh evidence.

## Run artifacts

- Scoreboard: `benchmarks/hispanic-latino-stem-us/runs/20260428T144522_hispanic-latino-stem-us-thin_20260428t1416.{md,json}`
- Two `submit_feedback` records on host: `/opt/topic-builder/logs/feedback.jsonl`
- Tool-call log: `/opt/topic-builder/logs/usage.jsonl`
- Review one-shot: `bash scripts/smoke.sh scripts/review_run.py -- 70`
