---
slug: african-american-stem
title: African American scientists in STEM
shape: demographic × discipline × geographic intersection (biographies-only)
last_validated_against: 2026-04-25
---

> **Stub status (2026-04-25):** menu card drafted from session notes
> for schema pressure-testing. Full case study deferred to a later
> authoring pass. Numbers reflect best run on record; verify against
> actual data before relying on them.

# Menu card

**Shape axes**

- structural: demographic × discipline × geographic intersection
  (essentially all biographies)
- scale: hundreds (~600–900 in best runs)
- layered_shape: single — biographies only, no real outer rings
- non-Anglosphere depth: low — predominantly U.S.-bounded and
  English-dominant
- biography density: very high — ~100% of in-scope articles
- canonical category coverage: medium — `Category:African-American
  scientists` exists with several sub-discipline siblings, but
  coverage is incomplete and feeder categories often miss
  intersection cases
- recall_ceiling_driver: shortdesc ambiguity on demographic axis +
  the STEM/medicine boundary on individuals whose primary work was
  clinical rather than research

**Doesn't apply when:** the demographic axis has comprehensive
category coverage on its own (don't need this whole pattern); OR
the topic isn't biographies-only; OR the discipline boundary
question (research vs. applied/clinical) doesn't matter for scope.

**Shape (prose).** A demographic intersection topic that is almost
entirely biographies. Better-served by Wikipedia's category
infrastructure than HL-STEM (more sub-discipline categories exist),
but the harder problem is the STEM/medicine boundary — many
candidates are physicians whose notability is clinical practice, not
research, and a research-primary rubric needs to exclude them.
Recall depends on category sweeps + WikiProject + similarity probes;
precision depends on the medicine-blocklist work.

**Summary.** Best run reached ~860 articles at ~99% precision and
~85% recall by combining `Category:African-American scientists`
sub-categories with `WikiProject African diaspora` membership lists,
`morelike:` searches seeded from canonical figures, and a final
filter pass that removed clinical-only physicians using a
description-pattern blocklist. Cross-language walks added little.
The hard work was the medicine-blocklist judgement, not finding
candidates.

**High-leverage moves**:

- **Sub-discipline category sweeps under the demographic root** —
  `Category:African-American chemists`, `Category:African-American
  physicists`, etc., are higher-precision than the parent category
  alone and surface candidates that aren't tagged with the
  demographic axis explicitly.
- **WikiProject African diaspora membership.** WikiProject coverage
  is unusually strong for this topic relative to other intersectional
  demographic topics — worth a `find_wikiprojects` + `check_wikiproject`
  probe early.
- **Medicine-blocklist post-filter.** After gather, run
  `auto_score_by_description` (or `remove_by_pattern`) against a
  blocklist of clinical-only profession terms (cardiologist,
  surgeon, family-physician, etc.) when the rubric is research-primary.
  Without this step precision falls fast.
