---
slug: hispanic-latino-stem-us
title: Hispanic / Latino scientists in U.S. STEM
shape: demographic × discipline × geographic intersection (biographies-only)
last_validated_against: 2026-04-25
numbers:
  corpus_size: ~400
  precision: ~95%
  recall: ~75%
  reach_audited: ~30
  api_calls: ~600
  tool_calls: ~80
---

> **Stub status (2026-04-25):** menu card drafted from session notes
> for schema pressure-testing. Full case study deferred to Ship 2.
> Numbers reflect best run on record; verify against actual data
> before seeding.

# Menu card

**Shape axes**

- structural: demographic × discipline × geographic intersection
  (essentially all biographies)
- scale: hundreds (~200–500)
- layered_shape: single — biographies only, no real outer rings
- non-Anglosphere depth: yes — Spanish-language sources and Latin
  American institutional context matter for ambiguous cases
- biography density: very high — ~100% of in-scope articles
- canonical category coverage: low — no single category captures the
  intersection; multiple feeder categories with imperfect overlap
  (`Hispanic and Latino American scientists`, etc.)
- recall_ceiling_driver: shortdesc ambiguity on the demographic
  axis — many in-scope biographies' shortdescs say only "American
  scientist" without flagging the demographic intersection

**Doesn't apply when:** any single axis (demographic / discipline /
geographic) has comprehensive category coverage on its own; OR the
topic isn't biographies-only; OR the demographic axis is reliably
present in shortdescs.

**Shape (prose).** An intersectional topic where neither the
demographic axis (Hispanic / Latino) nor the discipline axis (STEM)
nor the geographic axis (U.S.) has a comprehensive Wikipedia category
on its own; the intersection has none. The topic is essentially
biographical, with the hard problem being *recall on ambiguous
shortdescs* — many in-scope biographies have shortdescs that don't
flag any of the three axes.

**Summary.** Best run reached ~400 articles at ~95% precision and
~75% recall by combining feeder categories (Hispanic and Latino
American scientists, plus discipline-specific subcategories) with
heavy use of `search_articles` + `morelike:` seeded from high-
centrality biographies, plus `fetch_article_leads` for ambiguous
shortdescs. Cross-language walks on es-wiki recovered ~10 articles
missed by English-only routes. The hard work was *judging
inclusion* on ambiguous biographies, not finding candidates.

**High-leverage moves**:

- **`morelike:` search seeded from high-centrality biographies** is
  the most reliable recall move — categories are too patchy to anchor
  on, but the AI can iterate by similarity from confirmed in-scope
  biographies.
- **`fetch_article_leads`** is essential, not optional, for this
  shape. Wikidata shortdescs frequently say only "American scientist"
  without flagging the demographic axis; the article lead is where
  the inclusion-judgment evidence actually lives.
- **Cross-language walk on es-wiki** for biographies whose primary
  notability is documented in Spanish-language sources — recovers
  articles the English-language routes systematically miss.
