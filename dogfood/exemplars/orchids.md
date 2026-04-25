---
slug: orchids
title: Orchids
shape: very large taxonomic topic with a small genuine cultural / biographical / historical periphery
last_validated_against: 2026-04-25
numbers:
  corpus_size: ~13000
  precision: 100%
  recall: ~85%
  reach_audited: ~456
  api_calls: ~2000
  tool_calls: ~50
---

> **Stub status (2026-04-25):** drafted from memory of recent session
> notes for schema-pressure-testing. Numbers and specific moves need
> verification against the actual best orchids run before this
> exemplar is loaded into the seed table.

# Menu card

**Shape axes**

- structural: taxonomic
- scale: very large (~30k species exist on enwiki)
- layered: yes — taxonomy + cultural + biographical periphery
- non-Anglosphere depth: yes — Chinese, Japanese, Brazilian, German,
  Dutch traditions
- biography density: low overall, concentrated in periphery
  (orchidologists)
- canonical category coverage: high — `Category:Orchidaceae` is
  topic-definitional

**Shape (prose).** Very large taxonomic topic (~30k species exist on
Wikipedia) with a small but genuine cultural / biographical /
historical periphery (orchidology biographies, cultural symbolism in
Chinese / Japanese / Brazilian traditions, taxonomic history).

**Summary.** A complete build needs three layers: a category-tree
mass pull for taxa (precision-safe because the topic-named category
IS the topic), a Wikidata parent-taxon probe to recover
ambiguously-placed species, and a cross-language sweep for the
cultural / biographical periphery that English-language discovery
misses. Best run reached ~13k articles at 100% precision and ~85%
recall, with ~456 audited beyond-gold finds — most reach value in
the cultural / biographical layer, not the taxonomy.

**High-leverage moves**:

- **Source-trust on the topic-named category.** Taxa categorized as
  orchids ARE orchids by definition — don't second-guess by
  shortdesc. Hard-filtering on "Species of plant" descriptions
  silently drops thousands of real species.
- **Wikidata parent-taxon probe** as an additive layer on top of the
  category sweep. Surfaces taxa whose category placement is
  ambiguous; finds ~25–30 articles a full sweep misses.
- **Cross-language category walks** for the cultural / biographical
  periphery. ~20 enwiki articles for orchid-related people and
  cultural works that English-only discovery misses across
  multiple sessions are sitting one cross-wiki sweep away.

# Full case study

## Tool sequence (key moves)

1. **`start_topic` + `set_topic_rubric`.** Scope locked: Orchidaceae
   taxonomy + orchid biology / cultivation / pollination /
   phytochemistry + orchid-focused people and institutions + orchid
   cultural works. Excluded: things named after orchids that aren't
   *about* orchids; general botany unless orchid-specific.

2. **`survey_categories(root="Category:Orchidaceae", count_articles=True)`.**
   *Why it mattered:* established the topic shape — a very large
   taxonomic tree (~25k descendants) with small siblings (Cultural
   depictions of orchids, History of orchidology, Orchidologists).
   Confirmed the build needs a taxonomy-mass strategy + periphery
   strategy, not a single sweep.

3. **`get_category_articles(category="Category:Orchidaceae", recursive=True)`.**
   Primary mass pull for the taxonomy layer.
   *Why it mattered:* source-trust principle — taxa in this category
   ARE orchids; don't filter by shortdesc. Pulled ~12k taxa, many
   with shortdesc only "Species of plant."

4. **`wikidata_entities_by_property(property="P171", value="Q25308")`**
   (parent taxon = Orchidaceae).
   *Why it mattered:* additive Wikidata probe surfaces taxa whose
   category placement is ambiguous or wrong. Returned ~66 enwiki
   sitelinks, of which ~27 were not in the corpus after the category
   sweep. **NEVER use as a subtractive filter** — Wikidata's coverage
   is incomplete; many real orchid taxa lack P171, and excluding
   them would silently drop hundreds.

5. **`find_list_pages(topic="orchid")` + `harvest_list_page(main_content_only=True)`**
   on the surfaced curated lists (List of Orchidaceae genera, etc.).
   *Caution:* genus-level species lists (Dendrobium, Cattleya, etc.)
   can leak biographies of people whose surnames match species
   epithets. Sample-verify a slice before trusting bulk harvest;
   `annotate_types=True` once shipped will help.

6. **Cross-language walks.** `get_category_articles` on
   `Category:Orchideen` (de), `Category:兰科` (zh), `Category:ラン科`
   (ja), `Category:Orchidaceae` (pt). Then `wikidata_search_entity` +
   `resolve_qids` to surface enwiki sitelinks.
   *Why it mattered:* cultural / biographical orchid content
   (Brazilian orchidologists, Chinese orchid symbolism in classical
   poetry, Japanese cultural depictions) is preserved primarily on
   those wikis. ~21 enwiki articles recovered that several sessions
   of English-only discovery had collectively missed. **For any
   topic with significant non-Anglosphere depth, this isn't
   optional.**

7. **`harvest_navbox(template="Template:Orchidaceae")`** for higher-
   order taxa, well-known cultivated genera, framing concepts.

8. **`fetch_descriptions`** to drain the description backlog before
   centrality scoring.

9. **`auto_score_by_description(rubric=...)`** for centrality
   scoring of the canonical / cultural / historical layer. Left
   most species at NULL — centrality of one species among 13k is not
   useful information.

10. **Spot-check probe.** Hypothesized ~50 candidate titles across
    five subdomains: taxonomy, cultivation / horticulture, pollination
    biology, cultural symbolism, biography. Misses classified into
    variant-name vs hallucination vs real gap. Real-gap classes drove
    a final round of targeted probes (e.g. "Orchid show" surfaced a
    cluster of cultivation / horticulture events that the category
    sweep missed).

11. **`filter_articles` / `remove_by_pattern`** for the cultural-tail
    narrowness — articles named after orchids that aren't *about*
    orchids ("The Black Orchid", several Pokemon, etc.) get the
    narrowness rule applied.

12. **`submit_feedback`** with structured `coverage_estimate`,
    `strategies_used`, `spot_check`, `sharp_edges_hit`,
    `tool_friction`.

## Numeric results

- Corpus: ~13,000 articles
- Precision: 100% (after cleanup)
- Recall: ~85% against then-current gold (~15k articles)
- Reach (audited beyond-gold): ~456 articles
  - ~440 taxa
  - ~16 cultural / biographical
- API calls: ~2,000
- Tool calls: ~50
- Wall time: ~25 min

## Lessons

1. **Source-trust beats shortdesc filtering on taxonomy.** Categories
   named after the topic itself are definitionally on-topic — don't
   re-judge by Wikidata shortdesc. Hard-filtering "Species of plant"
   would have silently dropped ~5,000 real species.

2. **Wikidata properties are additive, never subtractive.** P171
   probe found ~27 articles a category sweep missed. If used as a
   filter ("only items with P171=orchidaceae"), it would have
   wrongly excluded hundreds of real species whose P171 isn't set.
   Coverage is genuinely uneven.

3. **Cultural / biographical periphery lives on non-en wikis.** ~20
   enwiki articles for the orchid periphery had been collectively
   missed by 8 separate English-language sessions — one cross-wiki
   sweep recovered them. For any topic with non-Anglosphere depth,
   cross-wiki is a primary strategy, not a fallback.

4. **Big species list pages leak via eponym collisions.** Genus-
   level lists can include biographies of people whose surnames
   match species epithets (Smith, Robinson, etc.). Sample-verify
   before trusting bulk harvest. Type-annotated harvesting (when
   shipped) is the right durable fix.

5. **NULL centrality is correct for most species.** Don't try to
   score every taxon 1–10. Score the canonical / cultural / historical
   layer (a few hundred articles); leave the long tail at NULL.
   Centrality is "how core to the topic," not "is this in the topic"
   — those are orthogonal axes.

6. **Three-layer topics need three-layer strategies.** Trying to do
   all of orchids with a single approach (category-only, or list-
   only, or Wikidata-only) caps recall at ~60%. Each layer has its
   own tool fit: categories for taxonomy mass, Wikidata for
   ambiguous placement, cross-wiki for cultural periphery.

## Anti-patterns / dead ends

- **Trying to build orchids without a Wikidata P171 probe.** Cap is
  ~75% recall; you'll never find the ambiguously-placed species.
- **Filtering by Wikidata P31 (instance of).** P31 is incomplete on
  plant taxa; using it as a gate drops real species silently. Same
  failure mode as shortdesc filtering.
- **Hand-translating category names per wiki.** "Orchids" is
  "Orchideen" (de), "兰科" (zh), "Orquídeas" (pt). Use Wikidata
  sitelinks via `resolve_qids`, not guesses — guessing burns API
  calls on dead categories.
- **Trying to scope "orchids in popular culture" exhaustively in a
  single pass.** This tail is genuinely fuzzy; better to set a
  narrow scope rule ("orchid as primary subject of the work") and
  revisit only if the spot-check surfaces gaps.
- **Hand-judging each species title for inclusion.** With 13k taxa,
  this is prohibitive and unnecessary — source-trust + the
  cleanup pass for the cultural-tail narrowness covers it.

## Extend, don't replicate

This case study is *one* path through the topic, not a recipe. Your
topic may be taxonomic but on a smaller scale; in that case the
cross-wiki layer may not pay off. Or your topic may be primarily
cultural with a small taxonomic core, in which case the layering
inverts. Use this as a menu of moves whose costs and yields are
known, not a sequence to follow.
