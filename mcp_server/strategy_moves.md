# Strategy moves

A catalog of named atomic strategy moves for topic building. Each
move is a small composable recipe (typically 1–3 tool calls) with
preconditions keyed to the shape axes (`mcp_server/shape_axes.md`),
an expected yield + noise characterization, and a rescue path if it
underperforms.

A topic build is a *plan assembled from moves*, not a single
procedure. Pick moves whose preconditions match your topic's axis
profile; compose them in an order that builds confidence (recon →
bulk → reach → cleanup → audit). The pipeline in
`server_instructions.md` is the outer loop; this catalog is what
fills each phase.

## How to use this catalog

- Every move's `preconditions` line names axis values from
  `shape_axes.md`. If your committed profile matches, the move likely
  applies.
- `sequence` is the tool-call shape, not exact parameters. Adapt to
  your topic.
- `expected` is the yield + noise characterization; deviations are
  signals, not failures. If yield is much lower than expected, your
  topic profile may be wrong (revisit) or a failure-mode is active
  (`failure_modes.md`).
- `rescue` points either to a fix or to another move that
  complements this one.

## This catalog is a starting point, not a closed enum

If you find yourself reaching for a strategy that isn't here — or
adapting one of these in ways the entry doesn't cover — name it in
`submit_feedback.strategy_execution.moves_attempted` so we can grow
the catalog. Out-of-tool strategies (canonical-source consultation,
external databases, expert curation) are also valid namings — they
reveal where the wiki-API toolkit falls short.

## Move schema

```
move: <name-with-hyphens>
preconditions: <axis-value combinations that activate this move>
sequence:      <1–3 tool calls, with parameter sketches>
expected:      <yield characterization + noise characterization>
rescue:        <what to do if it underperforms; may point to another move>
```

---

# Recon & planning

Cheap or free moves that characterize the topic before any heavy
gather call. Spend liberally here — five minutes of recon routinely
saves hours of metered API calls on a wrong-shape strategy.

## category-shape-survey-with-branch-identification

```
preconditions: scoping or rubric-time, regardless of axis profile
sequence:      survey_categories(<topic name>, depth=2,
                                 count_articles=True) →
               identify adversarial / cultural-tail / fictional /
               images subcats →
               commit them to an exclude list for the bulk pull
expected:      total-article estimate within ±50%; identifies subcats
               whose presence under the topic root is contraindicated
rescue:        if survey returns 0 articles on an existing category,
                 it's a container/redirect — try sibling names
                 (failure-mode: container-category-empty)
               if survey returns >5K articles at depth=2, plan
                 depth-3 with explicit excludes (don't depth-3 blind)
```

## wikiproject-recon

```
preconditions: any topic; especially before committing to gather order
sequence:      find_wikiprojects(keywords=[topic, parent-discipline,
                                           sibling-discipline]) →
               check_wikiproject(<best candidate>) →
               (Ship 2: count_wikiproject_articles before pulling)
expected:      classifies the WP into one of three states —
               (a) dedicated WP that tags many articles (rare;
                   pull as backbone),
               (b) broader-only WP (common; use wp-intersect-category
                   instead of pulling outright),
               (c) registered-but-empty (skip; rely on category +
                   list + search)
rescue:        if dedicated and broader both exist, pull dedicated
                 only and treat broader as recon
```

## list-page-discovery-and-triage

```
preconditions: structural-primitives includes curated-list-pages,
               OR you don't yet know
sequence:      find_list_pages(subject=<topic-name>, topic=<topic>) →
               filter results by topic-token relevance (the
                 disambiguation filter helps but isn't perfect —
                 token-overlap on a generic profession noun like
                 "musicians" still admits "List of Welsh musicians"
                 on a Bluegrass topic)
expected:      0–6 candidate list pages for the topic; 0 is common
                 for awards / named concepts / art movements / events
                 (try main-article-as-list-page instead)
rescue:        if 0 results: try main-article-as-list-page
               if many noisy results: skim shortdescs before harvest;
                 prefer titles that contain the topic's specific
                 token, not just the generic noun
```

## topic-qid-resolution

```
preconditions: any topic that will get a Wikidata probe
sequence:      wikidata_search_entity(term=<topic name>) →
               pick the canonical QID
expected:      one or two candidate QIDs; pick by description match,
                 not Q-number guessing (Q27868 looks like Bulbophyllum
                 but is the Eacles moth genus)
rescue:        if no clear QID, skip Wikidata moves; the topic may
                 not have an entity, or may be encoded as multiple
                 entities (e.g., "the language" + "the speakers")
```

## concentric-rubric-for-named-event

```
preconditions: shape includes named-historical-event with bounded
                 timeframe; the topic sits inside a parent program
                 (Apollo 11 in Apollo program; Chernobyl in Soviet
                 nuclear program; a single Tour de France inside the
                 ongoing race).
sequence:      at scoping time, before set_topic_rubric, draft the
                 rubric in three explicit rings:
                 CENTRAL  — the event itself, its participants, its
                            outputs, items named after it.
                 PERIPHERAL — direct-flanking events the topic-event
                            causally depends on or leads to (immediate
                            predecessors / successors); facilities
                            operationally used during the event;
                            people with event-specific roles even if
                            their broader employer is generic.
                 OUT      — non-flanking events under the same parent
                            program; generic parent-org articles;
                            unrelated facilities of the same operator.
               sanity-check by asking "if I ran the parent program's
                 navbox harvest, which of these would I keep?" — the
                 YES set is PERIPHERAL, not OUT.
expected:      keeps the program-tail axis open without bloating
                 CENTRAL; prevents over-pruning during cleanup.
rescue:        if the rubric already overshot OUT (silent recall loss
                 on flanking events / used facilities), run
                 unreject_articles on the direct-flanking +
                 operationally-used set before final cleanup. See
                 failure-mode: rubric-too-narrow-for-bounded-event.
```

---

# Bulk gather

The moves that actually populate the working list.

## branch-excluded-category-sweep

```
preconditions: structural-primitives.canonical-category=yes;
               survey identified branches to exclude
sequence:      get_category_articles(category=<topic>, depth=3,
                                     exclude=[<branches from recon>])
expected:      70–90% of corpus on category-rich topics; low noise
               when the exclude list honestly covers cultural-tail /
               adversarial / fictional / images subcats
rescue:        if subtle bleed survives: description-fetch-then-pattern-clean
               if depth=3 times out: pull subcategories individually,
                 or drop to depth=2 with manual sub-pulls
```

## wp-intersect-category

```
preconditions: structural-primitives.dedicated-wp=broader-only AND
               structural-primitives.canonical-category=yes
sequence:      get_wikiproject_articles(<WP name>) +
               get_category_articles(<topic category>) →
               get_articles(sources_all=[wikiproject:<WP>,
                                          category:<topic>])
expected:      high-precision core where both sources agree;
               very low noise. Diminishing returns when the
               canonical category is small (<500): the intersection
               is bounded above by the category's size, and a
               broader WP pull mostly adds noise that the category
               already filtered. For small canonical categories,
               the category alone is often enough.
rescue:        if recall too low: union-add the WP-only or
                 category-only sets and review tail (often the
                 WP captures recent additions the category hasn't
                 caught up to)
```

## founder-navbox-cascade

```
preconditions: shape is single-creator-oeuvre OR concentric-event-with-named-principals
sequence:      harvest_navbox(<principal-1 template>),
               harvest_navbox(<principal-2 template>),
               harvest_navbox(<principal-3 template>)
                 (1 call per principal, expecting 1–3 principals)
expected:      surfaces the per-creator dimension that the
               company / event category misses; small per-call
               yield (5–20 new) but reliably additive
rescue:        cross to per-work navboxes (Template:<film>,
                 Template:<album>) if creator coverage is thin
```

## parent-program-navbox

```
preconditions: shape is single-historical-event-with-cultural-tail
                 (Apollo program, Olympic Games edition, etc.)
sequence:      harvest_navbox(<parent-program template>)
                 — e.g. Template:Apollo program, not Template:Apollo 11
expected:      stitches across concentric layers (mission ↔ program
               ↔ agencies ↔ facilities ↔ contractors); the move that
               consistently separates strong runs from weak ones for
               this shape
rescue:        also pull agency / facility category sweeps if program
                 navbox is sparse (Apollo 11: Kennedy Space Center,
                 North American Aviation contractors, Mission Control)
```

## wikidata-property-probe-additive

```
preconditions: topic has a clean QID; one of the standard property
               joins applies (P171 taxonomy, P166 award, P135 art
               movement, P140 religion, P136 genre, P607 conflict,
               P101 field of work, etc.)
sequence:      topic-qid-resolution →
               wikidata_entities_by_property(<P-ID>, <topic-QID>) →
               review with sitelink_count flag → add_articles for
                 those with enwiki sitelinks
expected:      catches articles whose category placement was
                 ambiguous or absent on Wikipedia; orchids P171 probe
                 found 27 articles a full category sweep missed
WARNING:       ADDITIVE ONLY. Never use as a subtractive filter.
                 Wikidata coverage is uneven; many real on-topic
                 articles lack the property. Filtering by
                 P-property silently drops them. See ADDITIVE vs
                 SUBTRACTIVE in server_instructions.md.
rescue:        if 0 results: the property isn't well-curated for this
                 topic class; skip and triangulate by other strategies
```

## wikidata-occupation-and-field-paired-probe

```
preconditions: shape includes biography-heavy periphery (climate
                 change, AI safety, public health, scientific-
                 discipline or social-movement topics); topic QID
                 is resolved; P101 (field of work) is a plausible
                 probe.
sequence:      run wikidata-property-probe-additive with
                 P101=<topic QID> and capture results →
               identify the canonical occupation QIDs members
                 typically hold (climatologist, climate activist,
                 epidemiologist, AI researcher, etc.); look them
                 up via wikidata_search_entity if you don't know
                 them →
               run the same probe with P106=<occupation QID> for
                 each. Treat both passes as additive.
expected:      P101 catches researchers whose Wikidata explicitly
                 tags their field as the topic. P106 catches
                 historical and adjacent-field figures whose
                 occupation matches the typical role but whose
                 field-of-work is tagged differently. The two
                 overlap heavily but each catches biographies the
                 other misses by 30-40%.
evidence:      climate-change run 2026-04-26 phase 2:
                 P106=climatologist (Q1113838) added 51 historical
                 scientists that P101=Q125928 had entirely missed
                 — Humboldt, Halley, Wegener, Köppen, Milanković,
                 Bjerknes, Plass, Callendar.
rescue:        if you can't enumerate occupation QIDs cleanly,
                 fall back to intitle searches over the canonical
                 occupation noun + a topic-vocabulary anchor.
```

## wikidata-class-instance-enumeration

```
preconditions: topic includes well-defined named classes (UN
                 Climate Change Conference, IPCC report, NATO
                 summit, Olympic Games edition, Apollo mission,
                 climate treaty); the class QID is identifiable.
sequence:      identify the class QID via wikidata_search_entity
                 (e.g., Q7888355 = UN Climate Change Conference) →
               wikidata_entities_by_property(P31, <class-QID>) →
               check sitelinks; add_articles for the missing ones.
expected:      clean enumeration with very high precision —
                 typically every result is a topic-class instance.
                 Doubles as a precision check (everything returned
                 should already be in corpus) AND a recall
                 completeness probe (anything missing is a clear
                 gap).
evidence:      climate-change run 2026-04-26 phase 2: P31=Q7888355
                 returned 33 COPs cleanly and surfaced 6 yearly
                 conferences category+search had missed.
rescue:        if the class returns >100 instances and you only
                 want a sub-period, follow up with a SPARQL
                 wikidata_query that adds a date-range filter.
```

## genus-species-list-harvest

```
preconditions: shape is taxonomy; canonical-category=yes
sequence:      find a per-genus list page (e.g. "List of Dendrobium
               species") → preview_harvest_list_page →
               harvest_list_page(main_content_only=True)
expected:      near-zero noise; structural tables of binomials.
               Per-genus lists in taxonomic topics are among the
               cleanest sources in the entire toolkit.
rescue:        eponym collisions (Smith, Robinson) on big lists —
                 sample-verify before committing if the list is
                 mixed-content
```

## award-anchored-biography-pull

```
preconditions: shape is awards-anchored (Pulitzer, Nobel, Academy
               Awards); canonical-category=yes for the award itself
sequence:      topic-qid-resolution(award) →
               wikidata_entities_by_property(P166, <award-QID>)
expected:      canonical winners list when Wikidata is well-maintained;
               returns one row per recipient with sitelinks
rescue:        modern winners often undertagged on Wikidata —
                 supplement with harvest_navbox on the award's
                 canonical navbox, which editors curate per ceremony
```

## main-article-as-list-page

```
preconditions: list-page-discovery returned 0 or only homonym hits
                 (common for awards, named concepts, art movements,
                 events); the topic has a substantial main article
sequence:      harvest_list_page(title=<topic-main-article>,
                                 main_content_only=True)
expected:      surfaces the topic's nearby cluster — figures, works,
                 sub-concepts mentioned in the main article body
WARNING:       HIGH NOISE on single-event topics. Chernobyl's main
                 article harvest brought in physics context links
                 (Iodine-135, Zircaloy, Neutron poison) that the
                 rubric calls OUT. For event shapes, prefer navbox
                 if available.
rescue:        post-pull, run description-fetch-then-pattern-clean
                 against context-link patterns
```

## targeted-search-anchored-by-vocabulary

```
preconditions: structural-primitives weak (no canonical category, no
               dedicated WP, no curated list pages); time-profile=recent
sequence:      preview_search(query=<topic-specific vocabulary>,
                              within_category=<broader scope>) →
               review → add_articles(titles=[filtered subset])
expected:      tight precision on vocabulary-led probes;
               recall-bounded by the vocabulary you can name
rescue:        if recall too low: morelike-from-pure-topic-seed
                 from the search-discovered articles, OR expand
                 the vocabulary set with named techniques /
                 sub-concepts
```

## intitle-canonical-phrasing-enumeration

```
preconditions: topic has multiple canonical phrasings (climate
                 change / global warming / decarbonization / net
                 zero / greenhouse gas; gun control / firearm
                 regulation / Second Amendment; women in STEM /
                 women in science / female scientists). Topics
                 whose name in casual usage and in technical
                 literature differ.
sequence:      enumerate the canonical phrasing variants (3–7
                 typical) →
               for each: preview_search(query=intitle:<phrasing>)
                 → review → add_articles, OR run them as a single
                 compound intitle: query joined by OR (mind the
                 query-length limit — CirrusSearch silently
                 truncates long compound queries).
expected:      phrasing variants frequently disagree on which
                 articles they title-match; "climate change"-
                 titled articles miss "global warming"-titled ones
                 and vice versa. Per-variant yield typically
                 10-100 new articles depending on phrasing
                 diversity.
evidence:      climate-change run 2026-04-26 phase 2: enumerating
                 "deforestation" / "global warming" / "greenhouse
                 gas" / "carbon emission" added 101 articles after
                 phase 1 had only run "climate change".
rescue:        if a variant returns 0 net-new: its hits are already
                 covered by other variants — skip and don't enumerate
                 deeper.
```

## geographic-feature-class-probe

```
preconditions: shape is geographic-feature (lakes, mountains, rivers,
               etc.); canonical-category=yes intersected with country
sequence:      wikidata_query: SELECT items where wdt:P31/wdt:P279*
                 = <feature-class> AND wdt:P17 = <country>
expected:      catches feature subtypes (reservoirs as subclass of
                 lake, etc.) that the category sweep may miss; very
                 low noise
rescue:        if SPARQL times out, narrow the class (drop
                 wdt:P279* and use wdt:P31 only) or split by
                 region within the country
```

---

# Reach & cross-wiki

Moves for surfacing on-topic articles that the bulk gathers
systematically miss. Apply after the bulk gather has settled, when
adding more from existing strategies hits diminishing returns.

## cross-wiki-gap-probe-lightweight

```
preconditions: multilinguality=deep (or moderate);
               scale != huge (full parallel build is overkill on small
               topics)
sequence:      resolve_qids on the current corpus →
               (Ship 2: SPARQL diff for sitelinks-on-wiki-X-not-on-en)
                 — TODAY: per-QID preview_search on the relevant
                 wiki, slow but possible
expected:      surfaces enwiki articles that English-language
                 discovery systematically missed because the
                 cultural-native chain of association lives in
                 another language
cost:          1 SPARQL when the tool ships; ~N preview_search calls
                 manually today
rescue:        if 0 gaps surface: the topic genuinely is English-
                 dominant and you over-rated multilinguality
                 (recalibrate the profile)
```

## parallel-wiki-build-and-walk-back

```
preconditions: multilinguality=deep AND topic has cultural / biographical
               / regional content that lives natively in non-en;
               willing to spend ~1–2 hours per parallel wiki
sequence:      start_topic on the non-en wiki with the same scope →
               category-crawl + preview_search for native-language
                 cultural clusters →
               for each cluster, walk to enwiki: does this article
                 exist? Is it in my topic already?
               add genuine gaps under
                 source="manual:cross-wiki-reconciliation-<wiki>"
expected:      orchids: 21 enwiki articles recovered after eight
                 separate English-language sessions had collectively
                 missed them. Highest-leverage reach axis on
                 multilingual-deep topics.
rescue:        if reconciliation surfaces too many items to walk
                 manually, fall back to cross-wiki-gap-probe-lightweight
                 once it ships
```

## eponym-namesake-chain-walk

```
preconditions: shape includes eponymous individuals (people whose
               legacy is partly things named after them); P138 (named
               after) is well-tagged for those individuals
sequence:      for each canonical figure: wikidata_entities_by_property(
                 P138, <figure-QID>) →
               review for institutions / awards / concepts / species
               named after them
expected:      catches eponymous reach (Curie temperature, Einstein
                 cross-section, Linnaean species named after botanists)
                 that the figure's biography category misses
rescue:        manual search on "<Figure name>" with intitle: prefix
                 if P138 tagging is sparse for the era
```

## peripheral-edge-browse

```
preconditions: corpus has ≥100 articles and topic-canonical-category
               is dense (so the obvious neighbors are already in)
sequence:      pick 5–10 PERIPHERAL on-topic articles (not central
                 hubs) →
               browse_edges(seed_titles=[...], min_links=3)
expected:      thin yield on dense topics (most edges already in);
               higher yield from peripheral seeds whose neighborhood
               is sparse compared to topic core
rescue:        if 0 candidates: edge-browse is exhausted on this
                 topic; reach is now bounded by other strategies
```

---

# Similarity

## morelike-from-pure-topic-seed

```
preconditions: time-profile=recent OR canonical-category=no (when
               structural backbone is thin); the seed is a *concept,
               event, or work* (not a polymath biography)
sequence:      preview_similar(seed_article=<concept/event/work>,
                               limit=20) →
               review → add_articles(titles=[filtered])
expected:      near-zero noise from pure-topic seeds; ~50% noise from
                 biographical hub nodes whose edges span many fields
WARNING:       avoid seeding from polymaths or politically-prominent
                 figures. CirrusSearch's similarity model weights
                 profession over topic identity, so morelike: from
                 a Hispanic chemist returns mostly non-Hispanic
                 chemists.
rescue:        if seed turned out polymath-shaped: revert via
                 remove_by_source("search:morelike:<seed>") and
                 reseed from a concept/work
```

## morelike-anchor-cluster-from-rubric-layers

```
preconditions: phase-2 reach extension OR your rubric distinguishes
                 multiple layers (science core / policy / movement /
                 cultural / regional, etc.) and you want each layer's
                 neighborhood probed.
sequence:      pick 5–8 anchor articles, one per rubric layer
                 (climate-change example: Carbon-tax for policy,
                 Climate-movement for activism, Effects-of-climate-
                 change for impacts, Climate-change-denial for
                 controversy, Carbon-dioxide-in-the-atmosphere for
                 science core) →
               for each: preview_similar(seed_article=<anchor>,
                                         limit=20) →
               filter low-noise candidates → add_articles.
expected:      cheap reach-extension at low noise per anchor.
                 Each anchor contributes 2-8 finds on average; the
                 cumulative cluster of 5-8 anchors is the value —
                 reaches into corners of the topic that single-
                 anchor morelike misses by being too central.
WARNING:       same polymath caveat as morelike-from-pure-topic-
                 seed — pick concept/event/work anchors, not
                 biographical hub nodes.
evidence:      climate-change run 2026-04-26 phase 2: 5 anchors
                 added 23 articles cumulatively for low cost
                 (Carbon-tax, Climate-movement, Climate-change-
                 denial, Effects-of-climate-change, Carbon-dioxide-
                 in-the-atmosphere).
rescue:        if an anchor returned 0 finds, it's saturated by
                 your existing corpus — pick a different layer
                 representative; don't keep digging on a single
                 axis.
```

## intersection-via-source-overlap

```
preconditions: ≥2 high-confidence sources have fired (two
               independent gathers, or category + WP, or
               category + list-page)
sequence:      list_sources →
               get_articles(sources_all=[<source-A>, <source-B>])
expected:      the highest-confidence core of the topic; multi-sourced
                 articles are the precision-safe baseline
rescue:        — (purely informational; doesn't gather new articles)
```

---

# Cleanup

## redirect-resolution-pass

```
preconditions: any topic, post-bulk-gather, especially if heritage /
               transliteration / consolidation is plausible (axis:
               recall-ceiling-driver includes heritage-redirect-mass
               OR consolidation-into-list-pages)
sequence:      resolve_redirects(dry_run=False)
expected:      collapse rate is itself a diagnostic — see
                 failure_modes.md "heritage-redirect-mass":
                 0–5%   = clean editor curation (Tour de France: 0)
                 5–10%  = normal noise
                 >10%   = heritage / transliteration / consolidation
                          mass — investigate before trusting source
                          counts (London Underground: 34%)
rescue:        if a sample of redirects shows lossy semantic
                 merges (biography → non-biography target),
                 surface for review before next bulk gather (the
                 redirect target may have stolen articles from a
                 different scope)
```

## description-fetch-then-pattern-clean

```
preconditions: corpus mid-build, post-gather
sequence:      fetch_descriptions →
               remove_by_pattern(pattern=<noise term>,
                                 match_description=True,
                                 dry_run=True) →
               review samples → commit
expected:      bulk-removes off-profession noise (actor, footballer,
                 musician on STEM topics) in seconds
rescue:        if pattern over-matches (matches "martial artist"
                 when removing "artist"): use a multi-word phrase
                 or anchor with another pattern
```

## auto-reject-by-disqualifying-shortdesc

```
preconditions: corpus has fetch_descriptions populated;
               disqualifying terms reliably indicate off-topic
sequence:      auto_score_by_description(disqualifying=[<terms>],
                                         required_any={},
                                         dry_run=True) →
               review samples_by_reason → apply with dry_run=False
expected:      sticky rejection — disqualified titles won't reappear
                 on later gathers
WARNING:       required_any axes leak on intersectional shapes
                 (implicit-axis problem). For intersectional bio
                 topics, run with disqualifying-only first, axes
                 only if profession is reliably stated.
rescue:        if rejection samples show genuine on-topic articles:
                 the terms are too broad; narrow them, or accept
                 lower precision and don't apply
```

## source-targeted-noise-removal

```
preconditions: a specific gather (category, list page, search) turned
               out noisier than expected
sequence:      list_sources →
               remove_by_source(source=<noisy source>, dry_run=True,
                                keep_if_other_sources=True) →
               review → commit with dry_run=False
expected:      undoes a noisy gather without touching multi-sourced
                 articles (which presumably have other warrant)
rescue:        if remove is over-broad even with
                 keep_if_other_sources=True: drop the
                 keep_if_other_sources flag (full removal),
                 but spot-check the affected list first
```

## shortdesc-ambiguity-disambiguation

```
preconditions: biographical-density=high AND topic intersectional
               (recall-ceiling-driver=shortdesc-ambiguity)
sequence:      get_articles(description_regex=<thin-shortdesc pattern>,
                            limit=50) →
               fetch_article_leads(titles=[batch of 20], sentences=3) →
               classify CENTRAL / PERIPHERAL / OUT against rubric →
               set_scores or reject_articles
expected:      precision rescue on intersectional bio. The
                 shortdesc says "American academic"; the lead
                 reveals applied-STEM specialization. Cheap (1 REST
                 call per 20 titles).
rescue:        if many leads still ambiguous: read the article body
                 directly via score_by_extract for those titles
```

---

# Audit & meta

## triangulation-audit

```
preconditions: any topic, mid-build or pre-export
sequence:      describe_topic →
               check single_sourced / multi_sourced ratio
expected:      multi_sourced ratio:
                 <20%   → undertriangulated; reach for an orthogonal
                          gather strategy before declaring done
                 20–40% → typical
                 >40%   → strong triangulation; remaining gaps are
                          unlikely to come from another bulk pull
                          (cross-wiki / Wikidata / spot-check yield
                          most reach from here)
rescue:        — (read-only diagnostic; informs next-move choice)
evidence:      2026-04-24 thin-variant cycle showed strict-monotone
                 correlation between triangulation % and recall
                 across 5 benchmark topics
```

## niche-example-fabrication-spot-check

```
preconditions: pre-export OR pre-reach-extension; user not available
                 to nominate probe titles
sequence:      fabricate ~30–50 candidate titles spanning ≥5 of the
                 topic's natural subdomains (e.g., for an
                 awards-anchored biography: classic-era winners /
                 modern marquee / winning works / team orgs /
                 institutions / recent-era winners) →
               check_article_presence (Ship 2 primitive) OR batched
                 preview_search →
               classify each miss: variant-name-already-in-corpus /
                                   LLM-hallucination /
                                   real-gap →
               for real gaps: pattern-match into strategies
                 (a cluster of missed cultural-tail probes is a
                 cultural-tail strategy gap, not 5 individual fetches)
expected:      hit rate is itself a coverage proxy; clusters of misses
                 are reach-extension leads
rescue:        if the missed-strategy cluster names a tactic the
                 toolkit doesn't support: capture in
                 submit_feedback.missed_strategies
```

## intersectional-occupation-ethnicity-probe

```
preconditions: shape is demographic-×-discipline intersection
                 (AA-STEM, HL-STEM, women-mathematicians)
sequence:      wikidata_query: SELECT items where
                 wdt:P106 in (occupation set) AND
                 wdt:P172 in (ethnic-group set) OR
                 wdt:P27 in (citizenship set)
expected:      additive — surfaces candidates that demographic-axis
                 categories miss because the intersection isn't
                 categorically named on Wikipedia
WARNING:       Wikidata ethnicity coverage is uneven and politically
                 sensitive. Treat results as candidates needing
                 review, never as a subtractive filter. Many
                 in-scope biographies have no P172 set.
rescue:        if 0 results: ethnicity tagging is sparse for this
                 demographic; rely on category + morelike from
                 canonical figures
```

---

## Pointers

- Shape axes vocabulary: `mcp_server/shape_axes.md`
- Failure modes catalog: `mcp_server/failure_modes.md`
- Worked examples: `dogfood/exemplars/*.md`
- The active scaffolding (Ship 2): when `set_topic_rubric` accepts a
  structured `topic_profile`, its response will return the subset of
  this catalog whose preconditions match — bringing the relevant
  moves in-context at the moment of decision.
