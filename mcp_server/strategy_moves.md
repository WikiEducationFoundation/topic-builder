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

## seed-anchored-mining-from-canonical-article

```
preconditions: topic has a single canonical article that represents
                 it (named historical event, named work, named
                 building, named person, single named theory).
                 Especially valuable for sparse-resource topics
                 where category / navbox / Wikidata routes alone
                 give thin recall — Apollo 11 (no dedicated navbox,
                 thin P138), single Olympics editions, named
                 expeditions, single political events.
sequence:      identify the canonical article (e.g. "Apollo 11") →
               get_article_content(title) — RTFA. Read the article
                 to surface domain context: section structure, named
                 items the article treats as central, terminology.
                 Informs rubric authoring before commit. →
               get_article_categories(title) — list the categories
                 the article belongs to. Each is a descent candidate
                 for survey_categories / get_category_articles. →
               get_article_templates(title, filter="navbox") — the
                 navboxes used on the article. Each is a
                 harvest_navbox target. →
               get_article_templates(title, filter="wikiproject") —
                 WikiProjects claiming the article (queried from the
                 talk page). Cross-reference with check_wikiproject /
                 get_wikiproject_articles. →
               wikidata_get_entity(qid) — full property dump on the
                 topic's QID. Reveals which properties are populated
                 (e.g., P361 dense, P138 sparse for 1969 events).
                 Targeted property probes follow. →
               get_article_see_also(title) — the article's editor-
                 placed See also section. 5-30 manually-curated
                 related articles; the *intentional* relatedness
                 layer the article asserts. Higher precision than
                 morelike: or the full outgoing-link list on niche
                 topics. Empty result is fine — many articles have no
                 See also. →
               get_article_links(title) — outgoing first-degree
                 neighborhood, ~80-400 candidates. Review and add. →
               get_article_backlinks(title, limit=500,
                                     filter_redirects="nonredirects")
                 — incoming tail. Prominent topics have 10K+
                 backlinks; cap aggressively, sample if needed.
expected:      surfaces the topic's first-degree neighborhood
                 comprehensively from a single anchor. Yields:
                 categories ~95% on-topic, navboxes ~80-90%,
                 see-also ~85-95% (curation-dense; small N),
                 outgoing links 70-90%, backlinks 40-70%
                 (filter-heavy). The strategy's value is breadth
                 across signal types, not any single signal.
WARNING:       backlinks tail is enormous on prominent topics.
                 Don't try to review all of them; use limit=500
                 (default) and consider sampling. The first 100-200
                 backlinks are usually highest-signal because
                 MediaWiki returns them in page-id order
                 (older / more central articles first).
rescue:        if the canonical article isn't a single page (the
                 topic spans multiple peer articles — "WW2" /
                 "Climate change"), apply this to each anchor in
                 turn or fall back to category-led sweep.
                 If the article is too short / too narrow (a stub
                 or a redirect-target meta-article), fall back to
                 standard structural sweep — seed-anchored mining
                 needs a substantive article to anchor on.
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
               structural-primitives.canonical-category=yes AND
               broader WP small enough to pull in full
                 (≤ a few thousand articles). When the broader WP
                 is too big to safely ingest (e.g., WikiProject
                 Spaceflight, WikiProject Plants), use
                 category-intersect-wikiproject instead — it does
                 the intersection at pull-time via PetScan without
                 ingesting either side.
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

## category-intersect-wikiproject

```
preconditions: a narrow on-topic category (depth 0–2 yields ≤2K
                 candidates) AND a relevant but broader WikiProject
                 you DON'T want to ingest in full (overpull risk
                 on WP Spaceflight, WP Plants, WP Biography, etc.).
                 The pull-time alternative to wp-intersect-category
                 when ingesting the WP would be wasteful.
sequence:      petscan(params={
                 "language": <wiki>, "project": "wikipedia",
                 "categories": <category>, "depth": "<0–2>",
                 "ns[0]": "1",
                 "templates_yes": "WikiProject <name>",
                 "templates_use_talk_yes": "1",
               }, commit=False) →
               review count + sample →
               petscan(<same params>, commit=True,
                       source_label="cat∩wp:<cat>:<wp>")
expected:      high-confidence on-topic core (typically 30-70%
                 of the category, depending on how scoped the
                 category is). One HTTP round-trip; far cheaper
                 than ingesting the WP.
rescue:        if intersection is empty: the WP probably doesn't
                 tag this subtopic (check find_wikiprojects for
                 a more specific WP), OR the category is mis-
                 chosen, OR templates_use_talk_yes was forgotten
                 (the most common bug — without it, templates_yes
                 checks article ns instead of talk and silently
                 returns 0).
WARNING:       templates_yes alone (without templates_use_talk_yes=1)
                 returns 0 for WikiProject membership checks.
                 WikiProject tags live on talk pages.
```

## founder-navbox-cascade

```
preconditions: shape is single-creator-oeuvre OR concentric-event-
                 with-named-principals AND no mature WikiProject
                 already covers the topic. Near-zero net-new when a
                 mature dedicated WP exists — the navbox typically
                 overlaps the WP membership.
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
                 (Apollo program, Olympic Games edition, etc.) AND
                 no mature WikiProject already covers the topic.
                 Useful when WP is absent or partial; near-zero net-
                 new when a mature dedicated WP exists — the navbox's
                 article set typically overlaps the WP membership.
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
               (when the property has hundreds of well-attested
                 entities and the full-body call would overflow
                 the transport cap, use preview_wikidata_property
                 instead — same args, returns only
                 {qid, title, sitelink_count} sorted by sitelink
                 count desc.)
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

## hastemplate-typed-probe

```
preconditions: typed-thing axis — the topic shape implies a clean
                 entity type (biographies-of-X, films-with-Y,
                 species-of-Z). Especially valuable for intersectional
                 shapes (demographic × discipline) where category ∩
                 category leaks. Also a precision cleanup probe.
sequence:      identify the canonical infobox / navbox that marks
                 the typed entity ("Infobox scientist", "Infobox
                 film", "Infobox musical artist", "Infobox
                 spaceflight", "Infobox botanist") →
               search_articles(query='hastemplate:"<Template>"
                              [+ incategory:"<Scope>"]')
expected:      precision typically high (90-99%) — the template is a
                 type marker editors maintain. Recall depends on
                 template adoption: popular topic types (films,
                 musicians, athletes) have near-complete coverage;
                 niche or historical types have gaps. Stronger than
                 categorical type-tagging on Wikipedia, comparable
                 to or better than Wikidata P31 on shapes editors
                 actively maintain.
WARNING:       compound `hastemplate:"A" OR hastemplate:"B"`
                 silently returns 0 (same Cirrus quirk as compound
                 `intitle:`); split into separate calls and merge.
                 See KNOWN SHARP EDGES.
rescue:        if recall is low, the template name may be wrong (try
                 sibling templates: Infobox person vs Infobox
                 scientist) or the typed concept doesn't have a
                 dedicated infobox (fall back to category + Wikidata
                 P31). If precision is low, narrow with incategory:
                 scope or intersect via
                 get_articles(sources_all=[...]).
```

## articletopic-classifier-probe

```
preconditions: topic has fuzzy or incomplete canonical category
                 coverage AND maps to a broad ORES domain (biology,
                 culture, geography, history, stem, ...). On topics
                 with comprehensive category coverage, this move adds
                 little — the broad-domain articletopic intersected
                 with a topic-vocabulary term mostly returns articles
                 already covered by the canonical category sweep.
                 Used as a *coarse filter* on a noisy probe more than
                 as a primary gather.
sequence:      search_articles(query='articletopic:<broad-domain>
                              <topic-vocabulary-term> [+ -incategory:
                              <canonical-cat> | + morelike:"<Seed>"]')
                 e.g., articletopic:biology orchid -incategory:Orchids
                 — broad ORES domain (biology) intersected via free-
                 text vocabulary (orchid), with the canonical category
                 negated so only the long tail surfaces.
                 NOTE: dot-separated subtopics
                 (e.g., articletopic:stem.earth-and-environment) are
                 unreliable on enwiki today — many subtopics return
                 zero results. Stick to broad domains and intersect
                 via free-text vocabulary.
                 NOTE: `-incategory:X` excludes articles in X
                 directly, NOT articles in subcategories of X. For
                 "not anywhere under X" semantics there's no clean
                 Cirrus form; combine `articletopic` or `morelike`
                 with `incategory:X` and remove matches client-side.
                 Same Cirrus single-level limitation applies wherever
                 you use `-incategory:` (intitle-canonical-phrasing-
                 enumeration, hastemplate-typed-probe, etc.).
expected:      ML-classifier — precision moderate (70-90%) depending
                 on training-data overlap; recall moderate. On a
                 well-curated topic, expect mostly already-known
                 articles plus a small handful of net-new finds
                 (e.g., orchids 2026-04-28: 30 results, 1 net-new
                 committed). On a sparse-category topic the yield is
                 typically higher.
                 Multiple values OR by default within one operator:
                 `articletopic:biology|stem`.
WARNING:       ORES coverage isn't uniform — sparse on stub articles,
                 historical figures, or recent topics post-cutoff.
                 Treat results as candidates needing review, never as
                 a subtractive filter.
rescue:        if 0 results from a broad-domain query, drop the
                 incategory negation or widen the vocabulary term. If
                 results are dominated by canonical-category articles
                 you already have, this topic doesn't need the move —
                 skip and triangulate by other strategies.
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
preconditions: corpus has ≥100 articles AND topic-canonical-category
               is dense (so the obvious neighbors are already in)
               AND the topic has lateral connectivity — events,
               movements, intersections, biographical hubs sharing
               affiliations. Near-useless on taxonomy-dominated
               topics (orchids: 5 candidates from 5 periphery seeds
               at min_links=2, mostly noise — ISBN identifier,
               Greenhouse, Pest control, Victorian era — because
               species sit on parallel-not-overlapping taxonomic
               branches and don't share many incoming edges).
sequence:      pick 5–10 PERIPHERAL on-topic articles (not central
                 hubs) →
               browse_edges(seed_titles=[...], min_links=3)
expected:      thin yield on dense topics (most edges already in);
               higher yield from peripheral seeds whose neighborhood
               is sparse compared to topic core
rescue:        if 0 candidates: edge-browse is exhausted on this
                 topic; reach is now bounded by other strategies
```

## llm-fabricate-and-verify

```
preconditions: ANY topic where structural moves have run and you
                 want to detect remaining gaps. This is a gap-
                 detector, not just a sparse-topic recall extension.
                 Two recent calibration runs surfaced 30-50% novel
                 net-new on well-curated topics (climate-change
                 4.5K-WP corpus: 31% gap-detect rate; orchids 3.5K
                 corpus: 51% gap-detect rate). Especially valuable on
                 sparse-canonical-surface topics (no WP, sparse
                 categories) where structural tools surface thin
                 recall.
sequence:      sketch 50-100 candidate article titles you'd expect
                 on enwiki from your training-data knowledge of
                 Wikipedia, grouped by subdomain. Anchor each in a
                 brief reason ("X is the canonical figure in
                 <subdomain>"; "Y is named after Z and likely has
                 its own article"). →
               PRE-VALIDATE before committing — batched
                 preview_search(query='intitle:"<Title>"', limit=1)
                 per candidate, OR a compound search that hits all
                 of them. Plausible-sounding titles routinely don't
                 exist; committing without verification = false-
                 positive corpus noise. →
               for verified hits: add_articles(titles=[...],
                                  source="llm-fabricate:<topic-stem>")
                 — keep the source label so post-hoc audit can
                 measure fabrication's contribution. →
               optional 2nd round: ask "what *category* of articles
                 did I miss in round 1?" (non-Anglosphere bias,
                 pre-cutoff, adjacent disciplines).
expected:      pre-validation hit rate 70-100% (well-known topic
                 vocabulary). Of validated titles: 30-50% net-new on
                 well-curated topics (gap-detector behavior); higher
                 yield on sparse-canonical-surface topics. The gap-
                 detect signal is the win on mature topics — even
                 small absolute novel counts (e.g., 15 of 49 on a
                 4K-corpus) are a strong reach signal.
WARNINGS:      pre-validation is non-optional. Cap rounds at 2-3 —
                 diminishing returns are real. Track via the
                 source label so contribution is auditable.
rescue:        if pre-validation drops most candidates, the topic
                 is narrower than your training data suggests —
                 refine the rubric and try a more specific
                 subdomain. Adjacent: niche-example-fabrication-
                 spot-check is a wrap-up coverage probe (smaller N,
                 structured by subdomain) — this move is mid-build
                 recall extension (larger N, commit-oriented).
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

## morelike-from-niche-anchor

```
preconditions: anchor article is topic-internal AND narrowly-scoped
                 (a specific institution, person, work, or concept
                 entirely contained within the topic). Distinct from
                 morelike-from-generic-cultural-anchor, which uses a
                 topic-adjacent cultural concept and accepts more
                 noise.
sequence:      pick a niche anchor whose entire neighborhood is
                 plausibly on-topic →
               preview_similar(seed_article=<anchor>, limit=30) →
               commit clean candidates with add_articles.
expected:      ~85-95% on-topic, high net-new rate. Recovers tight
                 clusters that escape category sweeps. Orchids run
                 2026-04-28: Veitch Nurseries anchor → 28/30 net-
                 new, ~93% on-topic; recovered the entire Veitch
                 collector network.
WARNINGS:      use for precision-priority recall passes. The anchor
                 must be tightly topic-scoped — a polymath
                 biography or a popular cross-disciplinary concept
                 is NOT a niche anchor. Same polymath caveat as
                 morelike-from-pure-topic-seed.
rescue:        if 0 finds: anchor is saturated. If > 30% noise:
                 anchor was less niche than expected — switch to
                 morelike-from-generic-cultural-anchor framing and
                 filter aggressively.
```

## morelike-from-generic-cultural-anchor

```
preconditions: anchor article is topic-adjacent cultural / historical
                 concept (e.g., a craze, fashion, public discourse
                 phenomenon). Used when cultural-tail breadth is the
                 explicit goal, not precision.
sequence:      pick a topic-adjacent cultural anchor →
               preview_similar(seed_article=<anchor>, limit=30) →
               filter by topic vocabulary BEFORE committing — expect
                 ~40% noise from "shared discourse" connections that
                 have nothing to do with your topic.
expected:      ~50-60% on-topic, ~40% noise. Reaches into the
                 cultural tail that pure-topic seeds miss. Orchids
                 run 2026-04-28: Orchidelirium anchor → 18/30 net-
                 new (60% on-topic) but pulled Tulip mania,
                 Bibliomania, Bookworm, Honey hunting, Oology — all
                 culturally-adjacent crazes that share Orchidelirium's
                 discourse but aren't orchid-specific.
WARNINGS:      reach for this only when cultural-tail breadth is the
                 goal AND you'll filter aggressively. For precision-
                 priority passes, prefer morelike-from-niche-anchor
                 or morelike-from-pure-topic-seed.
rescue:        if filtered yield is < 5%: the anchor's neighborhood
                 doesn't intersect the topic enough to justify the
                 noise; pick a different anchor.
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
WARNING:       single-word markers fire on canonical-topic articles
                 and on legit periphery. Climate-change run:
                 "video game" rejected the canonical "Climate change
                 video game"; "manufacturer" hit Solectrac (electric
                 tractor mfr) and Skeleton Tech (battery). Prefer
                 phrase markers ("video game journalism", not "video
                 game") or paired markers (require two co-occurring
                 disqualifiers) on topics with industrial / cultural
                 periphery. Always dry-run and review samples before
                 committing.
rescue:        if rejection samples show genuine on-topic articles:
                 the terms are too broad; narrow them, or accept
                 lower precision and don't apply
```

## leads-confirm-disqualifying

```
preconditions: corpus has a noisy bulk source (e.g., articles
               sourced ONLY from a wide-net WikiProject membership)
               where shortdescs are too thin to support clean
               auto-rejection.
sequence:      get_articles_by_source(<noisy source>, only_source=
                 True) → sample 5-15 candidate-removal titles →
               fetch_article_leads(titles=[...]) →
               for each lead: check whether the topic vocabulary
                 appears at all → reject titles whose lead has zero
                 topic-vocabulary mentions.
expected:      higher precision than shortdesc-only rejection; lead
                 text is dense enough to confirm or refute the
                 noise classification. Climate-change run: confirmed
                 4 Toyota-vehicle articles (Land Cruiser Prado,
                 etc.) had no climate text in their leads —
                 generalizes from one ad-hoc check into a move.
WARNINGS:      cap sample size to 5-15 per pass; lead fetches cost
                 real API calls. Use as a last-pass cleanup, not a
                 first-pass scan.
rescue:        if every sampled lead mentions the topic vocabulary,
                 the source isn't noisy — leave it alone or revisit
                 with a more specific rubric.
```

## country-level-list-page-harvest

```
preconditions: topic.scale=large/huge AND
                 geographic_distribution=cosmopolitan (taxonomy,
                 ecological / cultural phenomena that cross
                 borders). The high-yield reach surface for these
                 shapes — and one that find_list_pages misses by
                 default because per-country list titles use the
                 country name instead of the topic name.
sequence:      find_list_pages(subject=<topic>,
                               relax_disambiguation_filter=True) OR
               articletopic:<broad-domain> "List of" <topic-token>
                 via search_articles → enumerate "List of [topic]
                 of [country/region]" titles →
               preview_harvest_list_page on the most promising one,
                 then commit harvest_list_page on the rest.
expected:      45-60% novel rate, ~95% precision on taxonomy /
                 phenomenon shapes (orchids 2026-04-28 Western
                 Australia: 56 candidates → 25 net-new). Per-country
                 lists are typically curated by editors with deep
                 regional knowledge.
WARNINGS:      relax_disambiguation_filter is required on
                 find_list_pages or you'll see 0 of the per-country
                 lists. Once you have the list of list-pages,
                 review with preview_harvest_list_page before bulk-
                 committing — country-level lists occasionally
                 include peripheral content (museums, events) the
                 topic rubric may not cover.
rescue:        if per-country lists are sparse, fall back to
                 wikidata-property-probe-additive on the relevant
                 P-property (P171 for taxonomy, etc.) — different
                 reach surface, similar yield.
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
