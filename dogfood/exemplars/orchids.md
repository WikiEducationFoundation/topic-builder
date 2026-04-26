---
slug: orchids
title: Orchids
shape: very large taxonomic topic with a small genuine cultural / biographical / historical periphery
last_validated_against: 2026-04-26
---

# Menu card

**Shape axes**

- structural: taxonomic
- scale: thousands (~7-8K articles in working set as of 2026-04-26;
  ~30k species exist on enwiki long-term)
- layered_shape: taxonomy+cultural — taxonomic mass + cultural /
  biographical / horticultural periphery
- non-Anglosphere depth: yes — Chinese, Japanese, Brazilian, German,
  Dutch traditions
- biography density: low overall, concentrated in periphery
  (orchidologists, 19th-century nursery families like Veitch)
- canonical category coverage: high — `Category:Orchids` is the
  topic-definitional root on enwiki (`Category:Orchidaceae` does NOT
  exist on enwiki — it's an alias on a few non-en wikis but not the
  canonical English category)
- recall_ceiling_driver: cross-wiki cultural gap (Chinese
  symbolism, Brazilian orchidology, German Veitch-era nursery
  history) + ambiguous parent-taxon placement on Wikidata + SPARQL
  response-size truncation on the large P171 transitive closure
  (~7,300 descendants)

**Doesn't apply when:** the topic isn't taxonomic; OR the canonical
category is incomplete or fuzzy; OR there's no non-Anglosphere
cultural depth to sweep.

**Shape (prose).** Very large taxonomic topic with a small but
genuine cultural / biographical / historical periphery (orchidology
biographies, cultural symbolism in Chinese / Japanese / Brazilian
traditions, taxonomic history, 19th-century nursery families).
Wikipedia's structural primitives for orchids are mixed: a clean
canonical category (`Category:Orchids`) of decent depth, no
dedicated WikiProject (just the broader WikiProject Plants), no
family-level navbox (`Template:Orchidaceae` and `Template:Orchids`
both don't exist on enwiki — orchids has no equivalent of the
parent-class template that other taxonomic-or-event topics
sometimes use), but rich Wikidata: P171 (parent taxon) is densely
populated for orchid taxa.

**Summary.** A complete build needs three layers: a category-tree
mass pull for taxa (precision-safe because the topic-named category
IS the topic), a Wikidata parent-taxon probe (P171=Q25308) to
recover ambiguously-placed species, and a cross-language sweep for
the cultural / biographical periphery English-only discovery
misses. Best thin run on record (2026-04-26) reached 7,986 articles
at 99.5% precision and 89.5% recall, with phase-2 reach extension
adding cross-cultural finds (Lantingji Xu / Orchid Pavilion
Gathering, Veitch Nursery cluster, P101-tagged historical botanists
that P106=orchidologist missed). Earlier expansive builds reached
6K+ via deeper category recursion but conflate scale figures
because gold has matured significantly.

**High-leverage moves**:

- **Source-trust on `Category:Orchids`.** Taxa categorized as
  orchids ARE orchids by definition — don't second-guess by
  shortdesc. Hard-filtering on "Species of plant" descriptions
  silently drops thousands of real species. Sweep to depth=4 for
  ~6,500-article taxonomy backbone; deeper recursion adds noise
  via Plant-of-the-day / phylogeny categories.
- **Wikidata P171 (parent taxon) probe** as an additive layer on
  top of the category sweep. Direct probe on Q25308 returns ~66
  enwiki sitelinks. Transitive walk via SPARQL returns ~7,300
  descendants — but the response truncates around row 385 due to
  60K-byte cap; paginate by ORDER BY ?item DESC vs Q-prefix to
  consume more.
- **Cross-language category walks** for the cultural /
  biographical periphery. ~20 enwiki articles for orchid-related
  people and cultural works that English-only discovery misses
  across multiple sessions are sitting one cross-wiki sweep away.
- **Wikidata P101 (field of work) PAIRED with P106 (occupation)**
  for orchid-specialist biographies. P106=Q118727241 (orchidologist)
  catches the explicitly-tagged figures; P101 targeting catches
  Reichenbach, Swartz, Lindley-class historical botanists whose
  occupation is "botanist" but field is orchids.
- **morelike: from named cluster anchors** — `Veitch Nurseries` for
  19th-century horticulture; `Orchidelirium` for cultural reception;
  `Orchid hunting` for plant-collector biographies. Each anchor
  contributes 5-10 net new at low noise.

**Doesn't work for orchids:**
- `Category:Orchidaceae` does not exist on enwiki — try
  `Category:Orchids` instead. Same root, different name.
- `Template:Orchidaceae` and `Template:Orchids` don't exist —
  there's no family-level navbox. The navbox cascade pattern that
  works for "Apollo 11" / "single Tour de France" doesn't apply
  here.
- `WikiProject Orchids` does not exist — only WikiProject Plants
  (broader, ~28K articles, includes all flowering plants; partial
  intersection useful as recon but too broad to commit wholesale).

# Full case study

## Tool sequence (key moves)

Modeled on the 2026-04-26 thin-variant run (best on record under
the locked thin-prompt format) plus phase-2 extension. Numbered
steps describe what worked, what failed, and what needs care.

1. **`start_topic` + `set_topic_rubric`** with three layers
   declared explicitly: taxonomy core (Orchidaceae taxa, hybrids,
   cultivars), orchid-focused biographies / institutions (P106 +
   P101 axis), cultural-symbolic-horticultural periphery (cultural
   depictions, books, Veitch-era nursery history). Excluded:
   things named after orchids that aren't *about* orchids (e.g.,
   The Black Orchid film); general botany unless orchid-specific.

2. **`survey_categories(category="Orchids", depth=2,
   count_articles=True)`.** Establishes the topic's structural
   shape — sub-categories include Orchids by country, Orchidology,
   Cultural depictions of orchids, and the long taxonomy tail.
   *DO NOT* try `survey_categories("Orchidaceae")` first — returns
   0 articles + 1 category. The canonical name is `Orchids`.

3. **`get_category_articles(category="Orchids", depth=4)`** for the
   taxonomy mass pull. Returns ~6,500 articles, ~520 API calls,
   no timeout. Source-trust this set: many shortdescs are bare
   "Species of plant" — keep them.
   *Why not deeper:* depth=5+ starts pulling Plant-of-the-day /
   phylogeny categories with non-orchid drift.

4. **`wikidata_entities_by_property(property_id="P171",
   value_qid="Q25308")`** — parent taxon = Orchidaceae.
   Returns ~66 direct children (subfamilies + nothogenera) with
   enwiki sitelinks. Cleanest enumeration of subfamily-level taxa.

5. **Transitive P171 walk via `wikidata_query`** (SPARQL):
   ```sparql
   SELECT ?item ?article WHERE {
     ?item wdt:P171+ wd:Q25308 .
     ?article schema:about ?item ;
              schema:isPartOf <https://en.wikipedia.org/> .
   } LIMIT 500
   ```
   *Why it matters:* recovers taxa whose category placement is
   ambiguous or wrong. Returns ~7,300 descendants but the response
   truncates at row 385 due to 60K-byte cap — paginate by changing
   `ORDER BY ?item DESC` or by Q-prefix slicing to consume the rest.
   See backlog: `preview_wikidata_property` titles-only mode would
   solve this.

6. **`wikidata_entities_by_property(P106, Q118727241)`**
   (occupation = orchidologist). Returns ~13 sitelinked figures —
   the explicitly-tagged orchid specialists.

7. **`wikidata_entities_by_property(P101, Q25308)`** (field of work
   = Orchidaceae). PAIRED probe with P106 — catches the
   historical figures (Reichenbach, Swartz, Lindley) whose
   occupation is tagged generic-botanist but whose field is
   orchids. ~6 net new high-quality biographies.

8. **`find_list_pages(subject="orchid")`** + curated
   `harvest_list_page(main_content_only=True)` on the surfaced
   country-level lists (List of orchids of Ireland, Metropolitan
   France, Western Australia, Philippines). The Philippines list
   alone added +905; South Africa +461.
   *Caution:* genus-level species lists (Dendrobium, Cattleya) can
   leak biographies of people whose surnames match species
   epithets (Smith, Robinson). Sample-verify before bulk harvest.

9. **Cross-language walks via `wikidata_search_entity` +
   sitelinks.** `Q25308` (Orchidaceae) → walk sitelinks to
   `Category:Orchideen` (de), `Category:兰科` (zh),
   `Category:ラン科` (ja), `Category:Orquídeas` (pt). For each, do
   `get_category_articles` on that wiki, then `resolve_qids` to
   surface enwiki sitelinks.
   *Why it matters:* the Chinese-symbolism cluster (Lantingji Xu /
   Orchid Pavilion Gathering / Wang Xizhi context / Winding stream
   party / Manchukuo imperial emblem) had been missed by 8 prior
   English-language sessions — recovered via this layer in
   phase-2 of 2026-04-26.

10. **morelike: from named cluster anchors.**
    - `Veitch Nurseries` (19th-century horticulture cluster) → +7
      including John Gould Veitch, Thomas Lobb, Veitch Memorial
      Medal.
    - `Orchidelirium` (Victorian cultural reception) → seeds
      Susan Orlean, Adaptation film, Fakahatchee Strand.
    - `Orchid hunting` → plant-collector biographies cluster.

11. **Cleanup pass.** `resolve_redirects` collapsed ~222 duplicates
    + dropped 1,278 missing-on-Wiki titles; `filter_articles`
    dropped 272 list/disambig pages; pattern-removal of
    Toyota/Lexus/Cyclone/Hurricane noise (118 OUT articles);
    `auto_score_by_description` with vehicle+weather disqualifiers
    (67 more OUT); `remove_by_source` with
    `keep_if_other_sources=True` for 300 single-sourced
    popular-culture noise (without losing 174 triangulated
    cultural works).

12. **Phase-2 reach extension** (own-topic exemplar with
    `allow_own=True` after phase-1 submit) — mostly the moves
    above 6/7/9/10 that phase-1 may have skipped, plus
    description-rewalk on borderline taxonomy cases.

## Numeric results

Best thin run on record: 2026-04-26 (apollo-11-thin-style brief,
two-phase):

- Corpus: 7,986 articles (phase 1: 7,885 → phase 2: 7,986)
- Precision: 99.5% (7,873 gold hits of 7,906 audited in corpus)
- Recall: 89.5% against grown gold (post-2026-04-26 audit)
- Reach (audited beyond-gold): 23 articles
- API calls: 4,517
- Tool calls: 87
- Wall time: ~44 minutes
- AI self-rating: 7 / 7 (phase 1 / phase 2)

## Lessons

1. **Source-trust beats shortdesc filtering on taxonomy.** Categories
   named after the topic itself are definitionally on-topic — don't
   re-judge by Wikidata shortdesc. Hard-filtering "Species of plant"
   would have silently dropped ~5,000 real species.

2. **Wikidata properties are additive, never subtractive.** P171
   probe finds species a category sweep misses. If used as a filter
   ("only items with P171=orchidaceae"), it would have wrongly
   excluded hundreds of real species whose P171 isn't set.

3. **Cultural / biographical periphery lives on non-en wikis.** ~20
   enwiki articles for the orchid periphery had been collectively
   missed by 8 separate English-language sessions — one cross-wiki
   sweep recovers them. For any topic with non-Anglosphere depth,
   cross-wiki is a primary strategy, not a fallback.

4. **Big species list pages leak via eponym collisions.** Genus-
   level lists can include biographies of people whose surnames
   match species epithets. Sample-verify before trusting bulk
   harvest.

5. **NULL centrality is correct for most species.** Don't try to
   score every taxon 1–10. Score the canonical / cultural /
   historical layer (a few hundred articles); leave the long tail
   at NULL.

6. **Three-layer topics need three-layer strategies.** Trying to
   do all of orchids with a single approach (category-only, or
   list-only, or Wikidata-only) caps recall at ~60%. Each layer
   has its own tool fit: categories for taxonomy mass, Wikidata
   for ambiguous placement, cross-wiki for cultural periphery.

7. **P101 + P106 paired probes catch what either alone misses.**
   P106=orchidologist returns the explicitly-tagged figures;
   P101=Orchidaceae field-of-work catches the historical-botanist
   figures whose occupation is generic. ~30-40% non-overlap.

## Anti-patterns / dead ends

- **Probing for `Category:Orchidaceae`.** It does not exist on
  enwiki. The canonical category is `Category:Orchids`. Same
  topic, different name. Burns one tool call if you guess wrong;
  use `survey_categories("Orchids")` directly.

- **Probing for `Template:Orchidaceae` or `Template:Orchids`.**
  Neither exists on enwiki. There is no family-level navbox for
  orchids — orchids does not fit the parent-class navbox-cascade
  shape. If you need a navbox-type signal, use
  `get_article_templates(title="Orchid", filter="navbox")` to
  enumerate what's actually used on the canonical article.

- **Probing for `WikiProject Orchids`.** It does not exist on
  enwiki. The nearest project is WikiProject Plants (broader,
  ~28K articles). `find_wikiprojects(["Plants", "Botany",
  "Tree of Life"])` enumerates the relevant adjacent projects.

- **Trying to build orchids without a Wikidata P171 probe.** Cap is
  ~75% recall; you'll never find the ambiguously-placed species.

- **Filtering by Wikidata P31 (instance of).** P31 is incomplete
  on plant taxa; using it as a gate drops real species silently.
  Same failure mode as shortdesc filtering.

- **Hand-translating category names per wiki.** "Orchids" is
  "Orchideen" (de), "兰科" (zh), "Orquídeas" (pt). Use Wikidata
  sitelinks via `resolve_qids`, not guesses — guessing burns API
  calls on dead categories.

- **Hand-judging each species title for inclusion.** With 7K+
  taxa, this is prohibitive and unnecessary — source-trust + the
  cleanup pass for the cultural-tail narrowness covers it.

- **Bulk-harvesting "Orchids in popular culture" or similar
  cultural list pages without preview.** Same noise pattern as
  Apollo 11 in popular culture: broadcasters / countries /
  eponymous-works dominate. Use `preview_harvest_list_page` and
  hand-pick.

## Extend, don't replicate

This case study is *one* path through the topic, not a recipe.
Wikipedia's structural primitives change: a `Template:Orchidaceae`
may eventually be authored; Wikidata P101 / P106 coverage will
grow; new orchid species articles get created continually (and
some get merged or redirected). The numeric results reflect a
2026-04-26 snapshot; verify each structural primitive before
assuming it works.

For an analogous shape (other large taxonomic topics — ferns,
beetles, mosses, bony fish), expect the layered strategy to
transfer cleanly, but the specific category / Wikidata richness
varies. Some taxonomic groups have dedicated WikiProjects (Birds,
Fungi); others don't. Verify with `find_wikiprojects` rather than
assuming.
