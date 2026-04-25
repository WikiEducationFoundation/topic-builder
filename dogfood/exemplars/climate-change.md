---
slug: climate-change
title: Climate change
shape: well-organized academic + movement + policy topic with strong WikiProject and dense category, plus geographic/cultural periphery
last_validated_against: 2026-04-25
---

# Menu card

**Shape axes**

- structural: well-organized public-policy + science + movement topic
- scale: thousands (~6,500 articles in working set; ~5,300 in the
  original 2026-04-16 expansive build before the MCP server existed)
- layered_shape: multi-layered — science core + IPCC / UNFCCC
  institutions + climate movement / activism + per-country regional
  reach + mitigation-tech periphery (renewable energy / EVs / CCS) +
  cultural-works tail
- non-Anglosphere depth: yes — UN-COPs are international, climate
  ministries exist on every continent, regional impact and movement
  articles are heavily non-en
- biography density: medium — climate scientists, activists, policy
  figures are present but don't dominate; mostly concept articles
- canonical category coverage: high — `Category:Climate change` is
  topic-definitional, well-curated WikiProject Climate change tags
  4,400+ articles
- recall_ceiling_driver: cross-wiki periphery (non-Anglosphere
  climate figures + regional movements) + PetScan-style category ∩
  template intersections to surface mitigation-tech with explicit
  climate framing

**Doesn't apply when:** the topic doesn't have all three primary
gather paths firing (no WikiProject; OR no dense category tree; OR
no curated index pages); OR the topic isn't a multi-axis
public-policy / movement subject; OR there's no per-country regional
content to enumerate.

**Shape (prose).** A multi-disciplinary public-policy + science +
movement subject. Wikipedia organizes it strongly on all three
axes — a canonical WikiProject, a topic-named category tree dense
enough to need depth-pruning, and mature curated index/glossary
pages. Reach lives across distinct concentric layers: a science
core (attribution / modeling / projections); named international
institutions and agreements (IPCC, UNFCCC, every annual COP); the
climate movement and named protests; per-country regional impacts
and policy ("Climate change in [country]"); mitigation-tech
periphery (renewables, CCS, EVs); and a cultural-works tail (films,
novels, art).

**Summary.** A complete build needs all three primary gather paths
firing (WikiProject + depth-3 category sweep with chemistry-drift
branches pruned + curated index/glossary harvests), plus targeted
Wikidata property probes for specific layers (P31 = Q7888355 cleanly
enumerates the 33 annual UN COPs; P101 / P106 with climate Q-items
surface specific climate figures), plus edge-browse from periphery
seeds for the cultural / movement tail. Best run reached 6,562
articles at 32% multi-sourced triangulation, vs. the original
2026-04-16 expansive build at 5,349 (executed via standalone Python
scripts before the MCP server existed). Cross-wiki periphery sweep
remains an unexploited reach axis.

**High-leverage moves**:

- **WikiProject Climate change pull as the backbone.** ~4,500
  articles, human-curated, the highest-quality single source. Run
  this first; everything else fills gaps around it.
- **Depth-3 category sweep with chemistry-drift branches excluded.**
  Specifically `Methane`, `Greenhouse gases`, `Carbon dioxide`,
  `Sustainable energy` at the depth-3 boundary — these branches
  drift into petroleum geology / individual fluorocarbon chemistry /
  generic engineering at depth ≥ 3 and contaminate the corpus
  fast. Run depth-3 with these in `exclude=[...]` and pull the
  branches separately at depth-1 if you want their core members.
- **Wikidata `P31=Q7888355` (UN Climate Change Conferences).**
  Returns all 33 annual COPs cleanly with sitelinks. Use as a
  precision check (every result should already be in the corpus
  after a complete WikiProject + category build) and as a
  completeness probe.
- **`resolve_redirects` mid-build.** Climate change has substantial
  redirect-sibling mass (Instrumental temperature record / Global
  temperature record → Global surface temperature; Earth's
  radiation balance → Earth's energy budget; Carbon credit →
  Carbon offsets and credits; etc.). Baseline run collapsed 436
  redirect dupes — without this step, the working list is
  inflated and downstream comparisons are dishonest.
- **`describe_topic` after gather to catch contamination
  patterns.** The top-first-words histogram surfaces noise:
  Toyota=42 (motor vehicles from Outline of solar energy) and
  Geography=70 ("Geography of [country]" articles that drifted in
  via the by-country GHG list) were both off-topic and prunable
  via `remove_by_pattern`. This is the load-bearing diagnostic
  step before scoring.

# Full case study

## Tool sequence (key moves)

1. **`start_topic` + `set_topic_rubric`.** Scope locked: expansive
   climate change including science / IPCC / agreements / movement
   / impacts / "Climate change in [country]" / climate figures /
   cultural works about climate / mitigation tech in climate framing.
   Excluded: petroleum geology, fluorocarbon chemistry not in
   atmospheric context, generic motor vehicles, "Geography of
   [country]", generic meteorology not framed as climate.

2. **`survey_categories(category="Climate change", depth=2,
   count_articles=True)`.**
   *Why it mattered:* established shape — 45 categories / ~2,097
   articles at depth=2, with chemistry branches (Methane,
   Greenhouse gases, Carbon dioxide) at depth-2 already flagging
   as likely drift sources at depth ≥ 3. Confirmed the strategy:
   safe core sweep depth=3 with those excluded, plus separate
   targeted pulls for the chemistry branches.

3. **`find_wikiprojects(keywords=["Climate", "Environment", "Energy",
   "Sustainability", "Weather"])` + `check_wikiproject("Climate change")`.**
   Confirmed the dedicated `WikiProject Climate change` exists.
   Also surfaced WikiProject Energy, Environment, Weather as
   adjacent — not pulled (would've added noise) but flagged for
   targeted intersection probes.

4. **`get_wikiproject_articles("Climate change")`** → 4,453 articles.
   *Why it mattered:* highest-quality single source, the high-
   confidence backbone. Includes every COP, IPCC report, named
   movement, climate scientist with a primary climate identity,
   country variants, and most cultural works.

5. **`preview_category_pull("Climate change", depth=3,
   exclude=["Methane", "Greenhouse gases", "Carbon dioxide",
   "Sustainable energy"], sample_size=30)`** then commit via
   `get_category_articles(...)` → 2,933 articles, +1,402 net new.
   *Why the excludes:* depth-3 of those branches drifts into
   chemistry of individual fluorocarbon refrigerants /
   petroleum-industry articles / generic engineering. The
   excluded subtrees are real climate subcategories at depth-2
   but their depth-3 children aren't.
   *Why the sample preview:* gauged shape before commit;
   confirmed the depth-3 sample was clean (UN conferences,
   regional haze events, droughts) before pulling 1,400+ articles.

6. **List-page harvests** with `harvest_list_page(main_content_only=True)`:
   - `Index of climate change articles` → 107 new (curated index
     is highest-signal)
   - `Glossary of climate change` → 77 new
   - `List of countries by greenhouse gas emissions` → 226 new
     (note: these include the bare country articles, which are
     OUT — country pages aren't climate articles)
   - `Outline of solar energy` → 234 new — **noisiest by far**:
     pulled in 42 Toyota vehicles, individual chemists / inventors
     (Abram Ioffe, Adolf Goetzberger), and even Elon Musk and
     "Light", "Heat", "Sun", "Ancient history" as articles.
   - `Outline of energy development`, `Outline of wind energy`,
     `List of climate change controversies` — small yields.

7. **CirrusSearch passes for gap-fill.** `search_articles` with:
   - `intitle:"climate change"` → +155 new
   - `intitle:"renewable energy"` → +149 new
   - `intitle:"deforestation"` → +87 new
   - `intitle:"emissions"` → +47 new (with downstream noise:
     Atomic emission spectroscopy, Diesel exhaust, etc.)
   - `intitle:"global warming"` → +24 new
   - `intitle:"greenhouse gas"` → +18 new
   - `morelike:<canonical climate-activist seed>` → +43 new
     (movement adjacency)
   - `morelike:"Effects of climate change"` → +9 new
   - `morelike:"Carbon dioxide in Earth's atmosphere"` → +14 new
   - `morelike:"Carbon tax"` → +4 new
   - `morelike:"Climate movement"` → +19 new

8. **Wikidata property probes.**
   - `wikidata_search_entity("climate change")` returned the
     concept QID Q7942 (with "Climate change" as alias for "global
     warming") and the activist Q61048378, climatologist Q1113838,
     UN COP Q7888355.
   - `wikidata_entities_by_property("P31", "Q7888355")` → 33 UN
     Climate Change Conferences with sitelinks. **All of them
     were already in the corpus from the WikiProject + category
     pulls** — useful as a precision check.
   - `wikidata_entities_by_property("P101", "Q7942")` (field of
     work = climate change) → 53 entities with enwiki sitelinks.
     +14 new manual additions; the rest already present.
   - `wikidata_entities_by_property("P106", "Q61048378")` (climate
     activist occupation) → 99 with sitelinks. Mixed quality — major
     U.S. climate-policy officials and named-foundation founders are
     correctly tagged; many tag matches are celebrities whose
     primary identity is non-climate (poets, actors, novelists with
     climate causes). Filter by description before bulk-promoting.
   - `wikidata_entities_by_property("P106", "Q1113838")`
     (climatologist occupation) → 84 with sitelinks. Mostly
     19th–20th-century founders of modern climatology; some
     contemporary (NASA / NOAA / European-institution-affiliated
     climate scientists). Note: the limit=500 default returned a
     result too large for the MCP transport — had to halve the
     limit.

9. **`resolve_redirects()`** → collapsed 436 dupes (e.g.
   Instrumental temperature record → Global surface temperature,
   Hydrogen fuel → Hydrogen economy, Forestation → Forest
   management, Carbon credit → Carbon offsets and credits).
   *Why it mattered:* without this step, 436 articles were being
   double-counted under their redirect-source variants. Critical
   before any source-trust analysis or scoring pass.

10. **`filter_articles(remove_disambig=True, remove_lists=True)`**
    → dropped 256 disambig + list + meta pages (Index of climate
    change articles itself, Glossary of climate change itself,
    "Climate change-related lists", etc.). Lists are
    discovery tools, not corpus members.

11. **`fetch_descriptions(time_budget_s=180)`** to drain the
    description backlog before scoring. ~2,500 API calls; took 3
    rounds at 60-90s each.

12. **`describe_topic`** — top-first-words histogram surfaced
    contamination: Toyota=42, Geography=71, Energy=142,
    Solar=86, Carbon=60. The Toyota and Geography clusters were
    pruned via `remove_by_pattern("Toyota", dry_run=False)` and
    `remove_by_pattern("Geography of", dry_run=False)`.

13. **Tiered keyword-based scoring** via `auto_score_by_keyword`:
    - Strong-CENTRAL keywords → score 9 (907 articles): "climate
      change", "IPCC", "UNFCCC", "Paris Agreement", "Kyoto",
      "Climate Change Conference", "carbon tax", "carbon market",
      "climate crisis", "Climate Act"
    - Mitigation/atmospheric/impact keywords → score 5 (1,150
      articles): solar/wind/photovoltaic/EV/carbon-capture/
      paleoclimate/sea-level/ocean-acidification/deforestation/etc.
    - Climate-impact event keywords → score 5 (245 articles):
      drought/flood/wildfire/heatwave/El Niño/La Niña/glacier/
      ice-sheet/etc.
    - Generic "climate" catch-all → score 7 (398 articles)
    - Remainder → score 4 default (4,107 articles)

14. **Edge-browse from periphery seeds.** Used 10 seed articles
    spanning regional + movement + mechanism layers (Climate
    change in Africa / Australia / India, Effects of climate
    change on the water cycle, a canonical climate-movement
    activist, Climate Justice, Climate movement, Carbon dioxide
    removal, Geoengineering, Reforestation). Surfaced 72 net-new
    articles including `[YYYY] in climate change` annual summaries
    (2019-2026), country-variant articles we missed (Eastern
    European + Pacific island states), REDD+, environmental-
    movement adjacencies (Chipko movement, Conservation movement).

15. **`reject_articles`** — hand-rejected 18 articles from the
    obvious-out set surfaced during description scan: `A.I.
    Artificial Intelligence` (2001 Spielberg film), Acura CDX/RDX
    motor vehicles, ACT New Zealand (political party), Acharavadee
    Wongsakon (Thai meditation teacher), Adalah (legal center),
    Abu Dhabi, etc.

16. **`submit_feedback`** with structured `coverage_estimate`,
    `strategies_used`, `spot_check`, `sharp_edges_hit`,
    `tool_friction`, `runtime`. Self-rating 8 / coverage 0.85.

## Numeric results

- Corpus: 6,562 articles
- Multi-sourced: 32.2% (2,115 articles)
- API calls: 2,476
- Tool calls: 83
- Wall time: ~17 min
- AI self-rating: 8
- AI coverage confidence: 0.85
- First-pass classifier (vs. unaudited gold = corpus snapshot):
  1,770 IN / 4,276 PERIPHERAL / 435 OUT / 81 uncertain.

For comparison, the original 2026-04-16 build (standalone Python
scripts, before the MCP server existed) reached 5,349 articles after
filtering. The MCP-driven rebuild exceeded it by ~1,200 articles
through the WikiProject + Wikidata-property + edge-browse layers
that the original build didn't have access to.

## Lessons

1. **WikiProject is the spine of well-organized topics.** When a
   topic has a dedicated WikiProject, run `get_wikiproject_articles`
   first — it's the highest-confidence single source. The
   downstream strategies should fill gaps around it, not duplicate
   it.

2. **Depth-pruning at the boundary, not at depth-2.** Chemistry
   branches (Methane, Greenhouse gases, Carbon dioxide) belong in
   the climate corpus at depth=2 (their direct articles ARE
   climate-relevant). The drift only starts at depth ≥ 3. Use
   `exclude=[...]` to prune at the depth-3 boundary; pull the
   excluded branches separately at depth=1 if you want their
   anchor articles.

3. **`resolve_redirects` mid-build is mandatory, not optional.**
   Climate change has hundreds of redirect siblings. Without
   running this before any source-trust analysis, the working
   list is inflated by ~7-8% under variant titles.

4. **`describe_topic` is the contamination diagnostic.** Top-
   first-words histogram catches noise patterns the per-source
   review can't (Toyota=42, Geography=71). Run it before scoring;
   inspect anything outside the expected vocabulary.

5. **Outline-of-X list pages are the noisiest harvest source.**
   Outline of solar energy pulled in 234 articles, of which ~40%
   was off-topic noise (vehicles, individual chemists, Elon Musk,
   bare physics articles). Use them but expect to prune
   afterwards via `describe_topic` + `remove_by_pattern`. They
   are NOT clean like Index of / Glossary of pages.

6. **Wikidata occupation tags are noisy on biographies.**
   `P106=Q61048378` (climate activist) returned poets, actors,
   celebrities-with-climate-causes alongside genuine climate
   activists. Don't bulk-add without filtering by description;
   default to PERIPHERAL when the description names a non-climate
   primary identity (actor, poet, novelist, comedian).

7. **`P31=Q7888355` (UN COPs) is a clean enumeration.** Use
   `wikidata_entities_by_property` of well-defined Wikidata
   classes as a *precision check* — if any of those 33 COPs
   weren't in the corpus, the build is incomplete. They were all
   there, which corroborated the WikiProject + category pulls.

8. **Tiered keyword scoring beats single-pass.** Running
   `auto_score_by_keyword` with the keyword "climate" alone
   over-counts CENTRAL — it'd promote PERIPHERAL articles whose
   shortdesc mentions "climate" without being primarily about
   climate. Use a strong-CENTRAL set first (score 9), then a
   mitigation/atmospheric set (score 5), then a generic catch-all
   (score 7) for stragglers. The order matters because earlier
   passes don't overwrite by default.

9. **Cross-wiki periphery is the unexploited reach axis.** Not
   exercised in the baseline run. Estimated 5-10% reach
   improvement available via cross-wiki sitelink walks for non-
   Anglosphere climate scientists, regional movements, country-
   scale climate ministries. Same lesson the orchids exemplar
   surfaces — for any topic with international depth, cross-wiki
   isn't optional.

10. **PetScan-style category ∩ template intersection** would
    surface mitigation-tech articles with explicit climate
    framing more reliably than the bare Outline harvest. The
    intersection `Category:Renewable energy ∩ template:climate-
    change-banner` (or equivalent) hits real climate-mitigation
    articles without the engineering / vehicle drift. Tool
    doesn't exist yet; would be a high-leverage addition.

## Anti-patterns / dead ends

- **Pulling the Methane / Greenhouse gases subtrees at depth ≥ 3.**
  The drift into individual fluorocarbon refrigerants / petroleum
  geology pollutes the corpus with several hundred OFF-topic
  articles whose shortdesc doesn't naturally land them out via
  keyword filtering.
- **Trusting `intitle:emissions` blindly.** Catches Atomic
  emission spectroscopy, electromagnetic radiation, "Emissions
  from the Monolith" (heavy-metal festival), Diesel exhaust
  (industrial-process article). Use it but require a climate
  keyword cross-check before accepting single-sourced results.
- **Bulk-promoting Wikidata `P106` biographies as CENTRAL.**
  The activist tag is heavily over-applied; promotion to PERIPHERAL
  is the safe default.
- **`auto_score_by_keyword` with "climate" as a single keyword.**
  Massively over-counts CENTRAL.
- **Skipping `resolve_redirects`.** Inflates the working list by
  hundreds of articles via redirect-source duplicates; corrupts
  every downstream metric.

## Extend, don't replicate

This is one path through a well-organized academic + movement
topic. If your topic also has a strong WikiProject + dense category
+ curated indexes, the recipe transfers. If any of those is
missing, the strategy needs different anchors:

- **No WikiProject.** Lean harder on category + curated indexes;
  the climate-change build's WikiProject contributed >2/3 of the
  multi-source articles.
- **No dense category tree.** Lean on `morelike:` chains from
  named anchors and `intitle:` searches with topic-specific
  vocabulary. The CRISPR exemplar has more on this.
- **No curated index page.** Skip the `find_list_pages` step;
  fall back to `find_list_pages` with broader subjects and
  filter manually. Or build the index yourself from a navbox
  via `harvest_navbox`.
- **No international / non-Anglosphere depth.** Skip the
  cross-wiki sweep; it won't pay off the way it does on orchids
  or (presumed) on language-family or religious-tradition topics.

The shape that makes the climate-change recipe transfer cleanly
is: **multi-axis public-policy + science + movement subjects
with strong canonical category coverage.** Likely sibling shapes:
public-health policy topics ("Tobacco control", "Antimicrobial
resistance"), other treaty-grounded environmental topics
("Biodiversity loss", "Plastic pollution"), human-rights
movements ("Reproductive rights", "Disability rights").
