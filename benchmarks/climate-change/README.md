# climate-change

Benchmark topic: climate change. The "well-organized academic topic"
shape — strong WikiProject, dense category tree, mature curated
indexes — and the project's original exploratory subject. See
`../README.md` for the umbrella.

## Why this topic

- **Origin topic.** Climate change was the test subject for the
  2026-04-16 development phase that produced the project's load-
  bearing design principles (LLM-as-quality-gate, centrality-not-
  binary, periphery-edge-browsing, multi-strategy gather). See
  `docs/development-narrative.md`. The original build hit ~5,349
  articles via standalone Python scripts, before the MCP server
  existed. This benchmark exists so future MCP-server runs can
  be measured against — and ideally exceed — that early reach.
- **Shape:** all three primary gather paths fire strongly.
  WikiProject Climate change tags 4,453 articles. Depth-3
  category sweep with chemistry-drift pruned reaches ~2,933
  more (~1,400 net new on top of the WikiProject). Curated
  indexes (Index of climate change articles, Glossary of climate
  change, List of countries by greenhouse gas emissions) add
  another ~700. Search + Wikidata-property probes + edge-browse
  fill remaining gaps.
- **Triangulation:** 32% multi-sourced in the 2026-04-25 baseline.
  Articles found by ≥2 strategies are high-confidence core; the
  single-sourced periphery is the audit work.
- **Cross-wiki latent reach.** Cross-language sitelink walks
  weren't exercised in the baseline. Aspirational reach target:
  non-Anglosphere climate scientists, regional impact articles,
  country-scale climate movements one Wikidata-sitelink walk
  away.

## Status

| Artifact | Status |
|---|---|
| `scope.md` | First draft 2026-04-25, mirroring 2026-04-16 expansive scope. |
| `rubric.txt` | First draft 2026-04-25 (CENTRAL / PERIPHERAL / OUT). |
| `baseline.json` | Computed 2026-04-25 from autonomous-rebuild run. Final article count 6,562; precision / recall null pending audit. |
| `gold.csv` | **Pending audit** — 6,562 rows all `pending_audit`. Available locally; gitignored. |
| `audit.py` | **Not yet written.** See `audit_notes.md` (TBD) for classifier approach when authored. |
| `runs/` | (empty) — per-run scoreboards land here as future runs land. |

## Origin

Bootstrapped 2026-04-25 from a single autonomous Claude Code session
(Opus 4.7, high effort). The session re-executed the original
2026-04-16 exploratory build's strategy through the current MCP tool
surface:

1. WikiProject Climate change → 4,453 articles.
2. Depth-3 category sweep with `Methane`, `Greenhouse gases`,
   `Carbon dioxide`, `Sustainable energy` excluded → +1,402 new
   (chemistry-drift branches deliberately pruned at the depth-3
   boundary).
3. List-page harvests on the curated indexes (Index of climate
   change articles, Glossary of climate change, List of countries
   by greenhouse gas emissions, Outline of solar energy / energy
   development / wind energy, List of climate change controversies)
   → ~700 new.
4. CirrusSearch `intitle:` and `morelike:` (climate change, global
   warming, greenhouse gas, deforestation, sea level rise, carbon
   capture, IPCC, Kyoto/Paris, climate-in-X) → ~400 new.
5. Wikidata property probes: P31=Q7888355 (annual UN COPs, 33),
   P106=Q61048378 (climate activists), P106=Q1113838 (climatologists),
   P101=Q7942 (field-of-work climate change) → ~140 manual additions
   after sitelink filter.
6. `resolve_redirects` collapsed 436 dupes (instrumental
   temperature record / global temperature record / earth's
   radiation balance, etc.).
7. `filter_articles` dropped 256 disambig / list / meta pages.
8. Targeted pruning: 42 Toyota-vehicle articles + 70 "Geography
   of [country]" articles + 18 hand-rejections.
9. Edge-browse from periphery seeds added ~70 articles (yearly
   summaries 2019–2026, missed country variants, REDD+, climate
   movement adjacencies).

Final: 6,562 articles, 32.2% multi-sourced, ai_self_rating 8.

## Known gaps the baseline run left on the table

- **Cross-wiki sitelink walks not exercised.** Non-Anglosphere
  climate scientists / regional climate-impact articles likely
  add a few percent reach.
- **PetScan-style category∩template intersection** would surface
  mitigation-tech articles with explicit climate framing more
  reliably than the bare Outline-of-solar-energy harvest produced.
- **Author / journalist climate beats** (Naomi Klein bibliography,
  Guardian environment-desk staff biographies) would hit a
  cluster the current strategies miss.
- **`auto_score_by_keyword(score=9)` over-counts centrality** when
  keywords like 'climate' alone match a peripheral article's
  shortdesc. The keyword passes here used tiered keyword sets to
  mitigate, but a future audit may revise scores accordingly.

## How a future run should compete against this baseline

1. On topic creation, persist a rubric via `set_topic_rubric`.
   Lift from `rubric.txt` if matching benchmark scope; adapt for
   narrower interest.
2. Run the build end-to-end. At export, pull the final corpus +
   usage log via `scripts/benchmark_score.py`.
3. Compare against `baseline.json`:
   - Once `gold.csv` is audited, precision and recall become
     gate metrics. Until then, only cost and reach axes are
     measurable.
   - At least one of `wall_time_s`, `total_api_calls`,
     `tool_call_count` must improve.
   - Reach (audited on-topic additions beyond `gold.csv`) is
     the aspirational win — cross-wiki walk + PetScan-style
     intersections are the targets.
4. If precision / recall hold (post-audit) and at least one cost
   metric improves, the run passes; its metrics become the new
   baseline.

## Auditing the gold (next step)

`gold.csv` is currently 6,562 rows of `pending_audit`. To produce
classified gold:

1. Write `benchmarks/climate-change/audit.py` — a keyword-rule
   classifier following the rubric. The orchids and crispr-gene-
   editing audits are the closest templates (well-organized
   topic with strong source-trust signals).
2. Use source-trust on `wikiproject:Climate change` (high) and
   `category:Climate change` at depth ≤3 with chemistry pruned
   (high) — articles from those sources are mostly IN.
3. Stricter filtering on `list_page:Outline of solar energy` —
   the source surfaces engineering / biographical noise.
4. Sample-audit 30–100 IN classifications via WebFetch to gauge
   precision before freezing.
