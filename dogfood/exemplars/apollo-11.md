---
slug: apollo-11
title: Apollo 11
shape: named historical event with concentric program / agency / people reach
last_validated_against: 2026-04-26
---

# Menu card

**Shape axes**

- structural: named event with concentric program / agency / people reach
- scale: hundreds (gold ~164; thin runs land 92–297; expansive runs 600+)
- layered_shape: concentric — flagship event + parent program +
  agencies / facilities + crew + ground-side personnel + cultural
  reception
- non-Anglosphere depth: moderate — Cold War context, Soviet response,
  international scientific community, country-by-country broadcast
  reception
- biography density: medium-high (astronauts, flight controllers,
  contractors, political figures)
- canonical category coverage: partial — `Category:Apollo 11` is the
  topic-definitional core (~102 articles) but reach lives across
  Apollo program / Kennedy Space Center / Mission Control personnel
  / 1960s spaceflight categories
- recall_ceiling_driver: stitching across concentric layers — the
  flagship category alone caps recall around 50%; sparse Wikipedia
  structural primitives for 1969 events (no dedicated navbox; thin
  Wikidata) cap further reach at ~65%

**Doesn't apply when:** there's no clear parent program / framing
institution to stitch outward to; OR the flagship category already
covers ~all the reach (no concentric layers); OR the topic has
abundant structural primitives (dedicated navbox + dense WikiProject
+ rich Wikidata properties — a richer-resource shape than this
exemplar models).

**Shape (prose).** A well-known historical event with a small
flagship core and significant peripheral reach via the parent
program, the agencies and facilities that executed it, and the
people involved. Recall depends on stitching across the concentric
layers, not just working the event category. Apollo 11 specifically
is **structurally sparse** for a topic of its prominence: there is
no `Template:Apollo 11` navbox, Wikidata P138 (named after) returns
near-zero hits because 1969-era events predate dense semantic-web
curation, and the cultural tail is concentrated in one over-linked
list page rather than dispersed across categories with structure.
Plan for these limitations from the start.

**Summary.** Best thin-variant run on record reached 209 articles at
49.5% precision and 62.8% recall (2026-04-25, 102 tool calls);
heavier runs trade tool count for recall. The expansive 2026-04-23
build hit 699 articles at 19.6% precision and 100% recall — useful
as a corpus ceiling. The move that consistently separates strong
runs from weak ones is recognizing this is a *concentric* topic
with sparse structural primitives — the flagship category alone
caps recall around 50%, and the available structural extensions
(parent navbox, named-after Wikidata) need substantial cleanup or
fall through entirely.

**High-leverage moves**:

- **Concentric three-ring rubric at scoping time** — direct-flanking
  missions (Apollo 8 / 10 / 12) and operationally-used facilities
  (KSC, Mission Control Center, Manned Space Flight Network,
  Crawler-transporter) are PERIPHERAL, not OUT. See move:
  `concentric-rubric-for-named-event`.
- **Navbox harvest on `Template:Apollo program`** is the single
  biggest reach move — but expects ~75% noise that needs cleanup.
  `Template:Apollo 11` does not exist on enwiki; don't waste time
  probing for it.
- **Agency / facility category sweeps** for ground-side personnel
  and contractors (Kennedy Space Center, Mission Control personnel,
  Apollo program hardware, North American Aviation contractors).
- **Wikidata `P361` (part of) Q43653** for hardware sub-components
  (EASEP, Solar Wind Composition Experiment, etc.) — works where
  P138 (named after) fails.
- **Compound `intitle:` on canonical mission catchphrases**
  ("Tranquility Base", "Eagle has landed", "one small step") for
  the eponym chain. Returns mixed signal + noise; needs filtering.
- **WikiProject Spaceflight intersection** for assessment-tagged
  Apollo-adjacent articles. Untried in all 5 thin runs to date —
  flagged as `missed_strategies` repeatedly. Try this.

# Full case study

## Tool sequence (key moves)

Modeled on the 2026-04-25 thin-variant run (best recall on record,
62.8%) and the 2026-04-26 phase-2 extension. Numbered steps describe
what worked, what failed, and what needs care.

1. **`start_topic` + `set_topic_rubric` with three-ring concentric
   scope.** The single most-leverage decision. Draw the rings
   explicitly:
   - CENTRAL: the mission itself, the three crew, A11 hardware
     (Saturn V SA-506, CSM-107 "Columbia", LM-5 "Eagle"), landing
     site (Tranquility Base), A11 science payload (EASEP, Passive
     Seismic, LRRR, Solar Wind Composition), A11 lunar samples,
     A11 cultural artifacts (flag, plaque, "One small step"
     transmission), items officially named after A11
     (commemorative coins, asteroid, A11 Cave Mountains), A11
     anniversaries.
   - PERIPHERAL: Apollo program flagship, program-level hardware
     overviews (Apollo CSM, LM, Saturn V), **direct-flanking
     missions Apollo 8 / 10 / 12** (predecessors and successor),
     ground-side personnel with documented A11 roles (Gene Kranz,
     Christopher Kraft, Charlie Duke, Steve Bales, Jack Garman,
     Margaret Hamilton, Bruce McCandless II), recovery operations
     (USS Hornet, helicopters), Lunar Receiving Lab / quarantine,
     Kennedy Space Center, Mission Control Center, Manned Space
     Flight Network, Space Race rivalry framing.
   - OUT: other Apollo missions (1, 7, 9, 13–17), generic NASA /
     MSC / Houston articles not tied to A11, post-A11 lunar
     missions, unrelated astronaut biographies, broad Cold War
     history, Apollo conspiracy theories and theorists.

   *Common error:* writing "Other Apollo missions: OUT" without
   distinguishing flanking from non-flanking. Apollo 8 / 10 / 12
   are PERIPHERAL by direct adjacency and are a meaningful chunk of
   recall. See failure-mode: `rubric-too-narrow-for-bounded-event`.

2. **`survey_categories(category="Apollo 11", depth=2,
   count_articles=True)`.** Establishes the core. Yields ~102
   articles in the canonical category — the topic-definitional
   backbone. Clean signal; minimal subcategory drift.

3. **`find_wikiprojects(keywords=["Spaceflight", "Space exploration",
   "Apollo", "NASA"])` → `check_wikiproject("Spaceflight")`.**
   *Why it should matter:* WikiProject Spaceflight tags
   Apollo-adjacent articles by assessment, surfacing periphery
   the category misses. **This step has been flagged as
   `missed_strategies` in every run from 2026-04-24 onward and
   never executed.** It is the single highest-leverage untried
   move on record. Try it.

4. **`get_category_articles("Apollo 11")`** → adds the ~102 core
   articles. Topic-definitional. Source-trust this set: items
   that look generic in shortdesc (eg "Mineral named after a
   crater") should still be kept.

5. **`harvest_navbox("Template:Apollo program")` with cleanup
   plan ready.** No `Template:Apollo 11` exists on enwiki — don't
   probe for it. The parent-program template adds ~120 articles,
   of which ~75% are program-wide (Saturn variants, Skylab, other
   missions, generic infrastructure). Run it, then immediately
   `describe_topic` and pattern-clean.
   *Why it matters anyway:* the 25% that survives cleanup
   includes the program-level hardware and facility articles
   that anchor the PERIPHERAL ring. Without this step, recall
   stalls at the category-only ceiling (~50%).

6. **Concentric-layer category sweeps** — agencies, facilities,
   and program-wide infrastructure that reach into PERIPHERAL:
   - `Category:Kennedy Space Center` (LC-39A is the A11 launch
     pad; KSC infrastructure is operational-PERIPHERAL)
   - `Category:Mission Control Center personnel` (flight
     directors, CAPCOMs, software leads)
   - `Category:Apollo program hardware` (program-wide hardware
     that includes A11 components)
   - `Category:Lunar sample displays` (state and country goodwill
     samples — A11 + A17, mostly PERIPHERAL)

7. **Wikidata property probes — what works:**
   - **`wikidata_entities_by_property(P361, Q43653)`** ("part of"
     Apollo 11) — surfaces hardware sub-components: EASEP, Solar
     Wind Composition Experiment, Passive Seismic Experiment.
     Higher yield than named-after probes for this topic.
   - **`P39` (position held)** for "NASA flight director" /
     "NASA astronaut" / "NASA Capsule Communicator" if you can
     resolve the role QIDs cleanly.

   **What doesn't work for Apollo 11:**
   - **`P138` (named after) Q43653** returns 4 entities, only
     1 with an enwiki sitelink. Wikidata's named-after coverage
     for 1969 events is too thin to lean on; named-after items
     (commemorative coins, named asteroids, etc.) come in via
     compound `intitle:` instead.
   - **`P710`, `P800`, `P1830`, `P1408`, `P793`** all return
     mostly-empty or trivially-broad results (United States,
     1969, human spaceflight). Skip these.

8. **Compound `intitle:` on canonical mission catchphrases.**
   `preview_search(query='intitle:"Tranquility Base" OR
   intitle:"Eagle has landed" OR intitle:"one small step"')` →
   review individual matches. Yield: ~20 candidates, mixed signal
   (named monuments, stamp issues, music tracks legitimately
   named after the mission) with eponymous noise (films and
   novels titled "The Eagle Has Landed" about Operation Mincemeat,
   not Apollo 11). Filter the noise via title disambiguation; keep
   the genuinely-named-after-A11 items.

9. **Cross-language sitelink walk via Wikidata.** Untried in all
   thin runs but consistently flagged in `missed_strategies`. Walk
   QIDs for Apollo 11 (Q43653), the three crew, Eagle, Tranquility
   Base on de/fr/es/ja/pt and pull en sitelinks of any articles
   that have them. International monuments, country-by-country
   reception, and lunar-sample-display articles for non-en
   countries live here. Estimated yield: 10–30 articles based on
   shape.

10. **`harvest_list_page("Apollo 11 in popular culture")` with
    `preview_harvest_list_page` first — or skip.** The page is a
    notorious noise trap (see failure-mode:
    `popular-culture-list-page-overlinking`). Of ~144 raw links,
    ~95% are tangential entities (broadcasters that aired the
    mission, countries that observed it, films using the
    catchphrase). Phase-2 of 2026-04-26 added 148 articles via
    bulk harvest and the run's precision dropped from 0.55 to
    0.30 in one call. **Default: preview, then handpick the few
    real items (commemorative coins, named statues, named
    operas) by hand.**

11. **Cleanup pass.** After all gather: `resolve_redirects` for
    duplicate-target collapse; `auto_score_by_description` with
    disqualifying terms ("Other Apollo mission", "Skylab",
    "fictional"); `remove_by_pattern` for the program-wide
    Saturn / Skylab / other-mission noise; source-targeted
    `remove_by_source` with `keep_if_other_sources=True` to
    drop list-page-only items without losing triangulated cultural
    works.

12. **Phase-2 reach extension** (own-topic exemplar with
    `allow_own=True` after phase-1 submit) — re-include any
    PERIPHERAL items the AI over-pruned in phase-1 cleanup
    (commonly: KSC, MCC, Crawler-transporter, Earthrise from
    Apollo 8). Run any high-yield moves the phase-1 plan
    skipped — typically WikiProject Spaceflight and the
    cross-language walk.

## Numeric results

Across 5 thin/ratchet runs on record (latest scoring against grown gold):

| Run | Corpus | Precision | Recall | Tools | API | Wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| 2026-04-23 expansive | 699 | 19.6% | 100.0% | 50 | 478 | 1288 |
| 2026-04-23 ratchet | 150 | 56.8% | 54.7% | 51 | 189 | 673 |
| 2026-04-24 baseline | 92 | 55.4% | 33.1% | 35 | 117 | 682 |
| 2026-04-25 (best recall) | 209 | 49.5% | 62.8% | 102 | 389 | 702 |
| 2026-04-26 phase-2 | 297 | 29.5% | 54.3% | 49 | 100 | 551 |

The recall ceiling on thin runs is ~63% absent the cross-language
walk and WikiProject Spaceflight — both repeatedly flagged as
untried. Effort matters: 2026-04-25's 102-tool run is twice the
work of 2026-04-26's 49-tool run for ~10pp more recall.

## Lessons

- **Apollo 11 is a sparse-resource shape.** No dedicated navbox,
  thin Wikidata P138, popular-culture tail concentrated in one
  over-linked page. General "named historical event" advice
  reaches a structural ceiling here. Plan around the gaps; don't
  expect them to fill themselves.

- **Concentric, not flagship-only.** The flagship category has
  ~102 articles; gold has ~164. The 60+ remaining articles live
  in PERIPHERAL — direct-flanking missions, agencies, facilities,
  ground crew, named-after items. A flagship-only pull caps recall
  at ~50%.

- **Direct-flanking missions are PERIPHERAL.** Apollo 8 / 10 / 12
  belong in PERIPHERAL by direct adjacency (predecessors +
  successor of A11). Writing "Other Apollo missions: OUT" without
  this distinction loses ~10 articles of recall.

- **Operational facilities are PERIPHERAL.** Kennedy Space Center,
  Mission Control Center, Manned Space Flight Network,
  Crawler-transporter — they are operationally-used during the
  mission, even though their broader role is program-wide. Gold
  classifies them PERIPHERAL.

- **Source-trust the canonical category.** Items in
  `Category:Apollo 11` whose shortdesc looks generic ("mineral
  named after a crater"; "1969 photograph") are still topic-defined.
  Phase-1 cleanup that prunes by shortdesc loses on this dimension;
  phase-2 exemplar-aware re-inclusion typically recovers ~5–10
  articles.

- **`P361` beats `P138` for hardware sub-components.** The
  named-after axis is sparse; the part-of axis is dense for the
  hardware tree.

- **Compound intitle on catchphrases catches the eponym chain.**
  But filter ruthlessly — "The Eagle Has Landed" matches both
  Apollo 11 commemorations and the unrelated Operation Mincemeat
  novel/film series.

- **Phase-2 own-exemplar consultation reliably recovers
  over-pruned PERIPHERAL.** The phase-1-only run reads the rubric
  too aggressively; phase-2 with the case study re-includes
  ~5–15 articles of operational-infrastructure periphery.

## Anti-patterns / dead ends

- **Probing for `Template:Apollo 11`.** It does not exist on
  enwiki. The parent-program template (`Template:Apollo program`)
  is the only program-specific structural source. Don't waste a
  call.

- **Generic full-text search for "Apollo 11" without operators.**
  Returns ~80% off-topic on the first 200 results: Soviet Luna /
  Zond programs, Surveyor, Lunar Orbiter, Artemis, post-Apollo
  programs, individual countries' broadcast histories. Net new
  on-topic adds are small relative to cleanup cost.

- **`browse_edges` from core articles like "Apollo 11" or
  "Apollo program".** The dense linking from core articles to
  the wider program means edge browsing surfaces obvious
  non-A11 candidates faster than A11-specific gaps. Skip for
  this shape.

- **`morelike:` from non-mission-anchored seeds.** USS Hornet
  (CV-12) returned WW2 carrier siblings, not Apollo recovery
  context, because the article's primary identity is the WW2
  service. Pick concept/event seeds, not biographies or
  multi-role facilities.

- **Named-after Wikidata probes.** `P138` against Q43653 returns
  4 entities, 1 with an enwiki sitelink. Predates the dense-curation
  era; stick to `P361` for hardware and `P31` (instance of) for
  class-membership.

- **Bulk-harvesting "Apollo 11 in popular culture".** Drops
  precision by ~25pp in one call. Use `preview_harvest_list_page`
  first; eyeball the 30-title sample; then handpick the genuine
  named-after items (commemorative coins, named statues, named
  operas) and skip the broadcast/country/eponymous-work noise.

- **Aggressive shortdesc-based cleanup in phase 1.** Source-trust
  the canonical category over thin shortdescs; phase-2
  re-inclusion is the usual rescue, but a more conservative
  phase-1 cleanup avoids the round trip.

## Extend, don't replicate

This case study describes what worked, didn't, and is sparse on
Wikipedia at the time of authoring (2026-04-26). Wikipedia's
structural primitives change: a `Template:Apollo 11` may eventually
be authored; Wikidata's P138 coverage may improve; the popular-
culture article may be split or restructured. Treat the move
sequence as informed by these constraints, not bound to them.

For an analogous shape (other concentric named events with parent
programs — Olympic Games editions, single Tour de France years,
World Cups, named expeditions), expect the concentric-three-ring
rubric to transfer cleanly, but verify each structural primitive
before assuming it works. Don't apply this exemplar to
richer-resource shapes (topics with dedicated WP + dense category +
abundant Wikidata properties) — those have different ceilings and
different leverage points.
