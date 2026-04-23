# orchids

Benchmark topic: orchid (Orchidaceae) taxonomy + cultural tail + cross-
wiki context. The largest of the five benchmarks — representing the
"taxonomy at scale" shape and the marquee completeness test.

See `../README.md` for the umbrella.

## Why this topic

- **Scale stress test.** 18,122 articles — 27× the next-largest
  benchmark. Lets us ratchet the tools' behavior at scale.
- **Known completeness frontier.** Original build did 21 cross-language
  gap-fills; many more likely reachable. The per-topic feedback named
  cross-wiki as the biggest unexploited reach strategy.
- **Well-triangulated.** 22.6% multi-sourced, multiple orchid-focused
  categories, hundreds of genus-specific list pages. The triangulation
  is the source of the 98%+ precision of the classifier.
- **Cross-wiki parallel builds exist** (orchids-zh, orchids-ja,
  orchids-pt, orchids-nl) — gives us a cross-wiki_diff target for
  future reach work.

## Status

| Artifact | Status |
|---|---|
| `scope.md` | First draft 2026-04-23. |
| `rubric.txt` | First draft 2026-04-23. |
| `baseline.json` | Computed from arc corpus, multi-session build. |
| `gold.csv` | Audited 2026-04-23 via keyword classifier with source-trust. 17,930 in / 183 peripheral / 9 out / 0 uncertain. |
| `audit_notes.md` | Classifier rules, approach notes, sample-audit results. |
| `calls.jsonl` | **Pending** — exemplar script written after first ratchet run. |
| `runs/` | (empty) |

## Audit approach

At 18k articles, enumerative classification isn't feasible. The
approach:

1. **Keyword-rule classifier** handles the taxonomic bulk.
   Descriptions containing orchid-specific terms (species of orchid,
   genus of orchid, Orchidaceae) → IN. Genus names (Phalaenopsis,
   Cattleya, etc.) → IN. Orchid-role people (orchidologist, orchid
   grower) → IN.
2. **Source-trust for uncertain-description cases.** Articles pulled
   from `category:Orchids` or `list_page:` sources in an orchids
   build are trusted as on-topic taxa — the build context guarantees
   orchid relevance. This catches the ~5000 articles whose Wikidata
   shortdesc says only "Species of plant" (generic) but whose genus
   (e.g. Acianthera, Stelis, Pleurothallis) is orchid-specific.
3. **Botanist bios → PERIPHERAL.** Without orchid-specific work
   mentioned, general naturalists / biologists / horticulturists /
   explorers land as peripheral (they described orchid taxa but
   their primary notability isn't orchid-specific).
4. **Hard OUT** only fires on descriptions that are clearly
   non-botanical AND lack any orchid-source affiliation (e.g. the
   Besi semiconductor company, Bruce Gray the actor).
5. **Random sample of 30 IN articles** spot-audited 2026-04-23 — all
   30 were legitimate orchid-related topics. Implies ~99% precision
   on the IN bucket; exact confidence bounds would require a
   larger sample.

See `audit_notes.md` for the classifier code location and the full
approach.

## Ratchet targets

- **Cross-wiki reach.** The arc run only did 21 cross-language gap-
  fills against the 5 parallel builds. `cross_wiki_diff` (backlog 5.2)
  would let a future run systematically enumerate the frontier.
- **Wikidata P171 (parent taxon) against Q25308 (Orchidaceae).**
  Not exercised in the arc run; likely captures a handful of orchid
  species missing from the enwiki corpus.
- **Reduce the 9 OUT false-positives** — Besi, Bruce Gray, and the
  non-botanical cross-wiki-reconciliation entries. A ratcheting run
  with relevance filtering or title-Wikidata-type verification would
  drop these pre-commit.
- **Cultural-tail expansion.** Current rubric keeps Chinese literary
  figures (Qu Yuan, Ma Shouzhen) OUT. A future scope revision could
  elevate them to PERIPHERAL if Wiki Education wants broader cultural-
  tail coverage.

## How a future run competes

1. Establish topic, persist rubric via `set_topic_rubric` (or lift
   from `rubric.txt`).
2. Run the build end-to-end.
3. Compare against `baseline.json`:
   - Precision vs. `gold.csv` — must not drop below the baseline's
     ~99% classifier-inferred precision.
   - Recall vs. gold — must not drop. Missing articles are
     reach-candidate losses.
   - At least one cost metric improves.
   - Reach (audited on-topic additions beyond `gold.csv`) is the
     aspirational win — cross-wiki walk + Wikidata P171 probe should
     both find new members.
