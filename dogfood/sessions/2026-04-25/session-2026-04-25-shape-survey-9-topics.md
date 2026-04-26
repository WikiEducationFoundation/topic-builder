# Dogfood session notes — 2026-04-25 (shape survey, 9 new topics, Claude Code, low effort)

> **What this is.** A breadth-first survey across nine *non-benchmark*
> topics deliberately chosen to be shape-different from each other and
> from the existing benchmark suite. Not a precision/recall measurement
> — there is no gold for any of these topics. The goal was to stress
> the server's exemplar coverage, the SHAPE → WIKIDATA PROPERTY table,
> and the standard pipeline against shapes we haven't measured before,
> and to surface the cross-topic friction patterns that single-topic
> sessions miss.
>
> Each run was kept lean (~10–20 metered calls): start_topic →
> set_topic_rubric → find_wikiprojects → survey_categories →
> get_category_articles (with branch excludes) → maybe a navbox or
> list-page harvest → resolve_redirects → fetch_descriptions →
> submit_feedback. No spot check, no scoring pass, no export. Per-run
> feedback is in `usage.jsonl`; this doc is the cross-cutting rollup.

## Topline

| Topic | Shape | Corpus | Redirects collapsed | WP exists / used? | Notes |
|---|---|---:|---:|---|---|
| Sufism | religious tradition | 2,788 | 134 (5%) | Mysticism (broader); Sufism: none | Adversarial subcats (Salafi, Wahhabi) under topic root |
| Tour de France | recurring annual event | 1,453 | 0 (0%) | Cycling (broader) | Meticulously curated; near-zero noise |
| Bluegrass music | musical genre | 1,292 | 51 (4%) | Country music (broader); Bluegrass: none | Genre-bleed via full discographies |
| Chernobyl disaster | bounded incident | 464 | 31 (6%) | Soviet Union (broader) | Main-article harvest = 65% of corpus, much noise |
| Vietnam War | multi-decade conflict | 2,977 | 34 (1%) | Military history (massive); Vietnam (broader) | WP too broad to safely pull |
| Type 2 diabetes | disease subtype | 1,235 | 7 (1%) | Medicine (broader); T2D: none | Wikipedia categorizes parent class; no narrow path |
| London Underground | physical infrastructure | 1,786 | 914 (34%) | London Transport (broader, all transit) | Heritage-rail dense redirect mass |
| Studio Ghibli | single-creator oeuvre | 132 | 15 (10%) | Anime (broader); Ghibli: none | Wikipedia consolidates per-work into list pages |
| Esperanto | constructed language / movement | 636 | 6 (1%) | **Esperanto (registered, tags 0!)** | Native-wiki (eo) is the highest-leverage reach axis |

## The single biggest signal: every shape exposes a missing exemplar

The six existing exemplars (orchids / climate-change / apollo-11 /
crispr / AA-STEM / HL-STEM) cover taxonomic / event / discipline /
demographic-intersection shapes. Across nine new topics, the closest
existing exemplar was a useful inspiration in maybe two cases (Apollo
for Chernobyl; climate-change for Sufism) — and even there the
divergences mattered more than the alignments.

Concrete missing shapes, ordered by how often they're likely to come
up in production guided-mode use:

1. **Religious / spiritual tradition** — figures + texts + orders +
   practices + geographic spread + saint/lineage cult.
   Exemplar: Sufism. Recurs: Tibetan Buddhism, Hasidism, Jainism, etc.
2. **Single-creator oeuvre** — small core + per-work consolidation
   into list pages + per-creator navboxes as primary reach.
   Exemplar: Studio Ghibli. Recurs: Pixar, Stephen King bibliography,
   Tarantino filmography.
3. **Musical genre** — biographies + bands + albums + songs +
   festivals, severe genre-bleed under full-discography
   categorization.
   Exemplar: Bluegrass. Recurs: bossa nova, punk rock, hip-hop
   subgenre topics.
4. **Recurring annual event** — year-edition subcategory pattern,
   structurally distinct from Apollo's single event.
   Exemplar: Tour de France. Recurs: Wimbledon, Olympics editions,
   Eurovision, Super Bowls, every annual award show.
5. **Multi-decade military conflict** — battles × units × weapons ×
   factions × multiple sides; layered category + WP-too-broad
   tension.
   Exemplar: Vietnam War. Recurs: every named war.
6. **Disease subtype within categorized parent** — Wikipedia
   categorizes the parent (Diabetes); there is no Category:Type 2
   diabetes; no clean narrow path.
   Exemplar: Type 2 diabetes. Recurs: ALS within MND, Asperger's
   within autism spectrum, type-of-cancer topics.
7. **Bounded industrial accident with sprawling aftermath** — distinct
   from Apollo: no positive-meaning umbrella; main-article-as-list
   pattern dominates.
   Exemplar: Chernobyl. Recurs: Bhopal, Fukushima, Deepwater Horizon,
   Hindenburg.
8. **Physical infrastructure / transit system** — heritage-era dense
   redirect mass, WP-broader-than-topic mismatch, infobox
   transclusion as canonical-instance enumeration.
   Exemplar: London Underground. Recurs: NYC Subway, every metro.
9. **Constructed language / community movement** — native-wiki of the
   topic should be a default reach move, not "primary then
   secondary."
   Exemplar: Esperanto. Recurs: Volapük, Lojban; also generalizes to
   minority-language topics where the language IS the topic.

Half the "no exemplar fits" pain in this session is resolvable with
**menu cards alone**, no full case studies — and the menu-card
authoring cost is low (the authoring recipe at `docs/adding-exemplars.md`
is in place). A pure menu-card pass at six of these shapes would lift
the fraction of incoming production topics that find an analogous
exemplar from "rare" to "usually."

## SHAPE → WIKIDATA PROPERTY table is incomplete

Six runs tried Wikidata probes mentally and stopped because the table
in `server_instructions.md` doesn't list a row for their shape. New
rows worth landing:

| Shape | Property(ies) | First-leverage move |
|---|---|---|
| Religious tradition | `P140` (religion or worldview), `P611` (religious order) | `wikidata_entities_by_property(P140, <tradition-QID>)` for adherents/figures |
| Recurring competition | `P1346` (winner) | Returns canonical winners across all editions |
| Disease | `P780` (symptoms), `P2293` (genetic association), `P2176` (drug used for treatment) | Joins a disease QID to its causally-linked articles |
| Musical genre | `P136` (genre) | Filters bleed by primary-genre; subtractive guard |
| Constructed language | `P407` (language of work) | Every work in that language |
| Single conflict | `P607` (conflict) | Participants/units/operations missing from the category tree |
| Single creator's oeuvre | `P57` / `P58` / `P162` / `P50` (director / screenwriter / producer / author) | Founder-anchored work enumeration |

Each is a one-line addition, but the absence consistently caused me
to think "is there a Wikidata move here?" and not have an answer.

## Recurring tool gaps (multi-topic evidence)

In rough priority by how often I felt the absence:

1. **`count_wikiproject_articles(name)` reconnaissance.** `find_wikiprojects`
   says "exists" but doesn't say *how many articles tagged*. Bitten
   twice in this session: had to skip WP Military history blind on
   Vietnam (it tags hundreds of thousands), and got 0 articles from
   WP Esperanto on Esperanto despite the WP being registered. The AI
   has no signal to distinguish "load-bearing dedicated WP" from
   "registered but inactive" or "discipline-tagged firehose." Cheapest
   tool win in this report.

2. **WikiProject ∩ Category intersection.** London Underground
   exposed it acutely: WP London Transport pulled 2,186 articles, but
   WP ∩ `Category:London Underground` would have been the right move.
   Recurs anytime the WP scope is broader than the topic — common
   for "X within larger discipline Y" topics.

3. **Subtree centrality demotion.** Bluegrass (Mumford & Sons albums
   subcat under bluegrass), Tour de France (Femmes subtree), Vietnam
   War (popular-culture seepage) all wanted "include this subtree as
   PERIPHERAL centrality 4," not "include same as everything else"
   or "exclude entirely." Today the rubric is corpus-wide; per-source
   scoring exists but per-subtree-at-pull-time tagging doesn't.

4. **Pattern-based subcat exclude.** I had to enumerate
   `["Films set on", "Novels set on", "Works set on", "...in popular
   culture"]` separately on London Underground. An
   `exclude_pattern=".*(in popular culture|set on|fiction about)"`
   would generalize and de-noise the cultural-tail problem across
   most of these topics.

5. **`harvest_template_uses` (transclusion harvest).** Multiple
   topics wanted this primitive: London Underground (Template:Infobox
   London station tags every Tube station canonically), Esperanto
   (Template:Infobox Esperanto), Studio Ghibli (per-film templates),
   Tour de France (per-edition templates). Stations / works /
   canonical-instance topics often have an infobox that uniquely
   identifies them; harvesting transcluding pages is cleaner than
   category sweeps for these shapes.

6. **Lightweight cross-wiki gap probe.** The current cross-wiki
   workflow is "1–2 hours per parallel wiki" — too heavy to use as a
   reach move on a 132-article Studio Ghibli or 636-article Esperanto.
   But on Sufism (ar/fa/tr/ur), Esperanto (eo!), Studio Ghibli (ja),
   Vietnam War (vi), Tour de France (fr), Chernobyl (uk/ru), the
   native-language wiki is BY DEFINITION the highest-leverage reach
   axis. A cheap probe — "for each QID in my corpus, list QIDs with
   sitelinks on wiki X but no enwiki article" — would surface real
   gaps in seconds and cost a single SPARQL.

7. **Main-article harvest noise warning for single-event topics.**
   Chernobyl: harvest of the main article body added 308 articles;
   a heavy fraction are physics context links (Iodine-135, Zircaloy,
   Neutron poison) the rubric calls OUT. Server instructions
   currently *recommend* this move ("the topic's own main article
   often functions as the canonical list page") but don't warn that
   on event shapes specifically it's the highest-yield AND
   highest-noise pull.

8. **`find_list_pages` token filter is too lenient.** Bluegrass got
   "List of Welsh musicians" because *musicians* matched the derived
   token. Sufism got "Glossary of logic" tier candidates filtered out
   correctly, but the token logic should require ALL topic-specific
   tokens, not ANY — especially when a generic profession/category
   noun is one of the derived tokens.

## resolve_redirects collapse rate as a noise diagnostic

Cross-topic numbers from this session:

```
London Underground:   914 / 2,700  (34%)  — heritage-rail name churn
Studio Ghibli:         15 /   147  (10%)  — character-page consolidation
Chernobyl:             31 /   495  ( 6%)  — pop-culture/physics aliases
Sufism:               134 / 2,922  ( 5%)  — name-variant transliteration
Bluegrass:             51 / 1,343  ( 4%)  — genre-bleed via song→album merges
Vietnam War:           34 / 3,011  ( 1%)  — meticulous editor curation
Type 2 diabetes:        7 / 1,242  ( 1%)
Esperanto:              6 /   642  ( 1%)
Tour de France:         0 / 1,453  ( 0%)  — meticulously curated
```

The rate is a real diagnostic signal. >10% means heritage
restructuring, transliteration variants, or per-work consolidation
worth investigating before trusting source counts. **Suggested
addition to `describe_topic`**: include
`redirects_collapsed_rate_at_last_resolve` alongside the first-words
histogram. Today this is only visible as a one-shot return value;
making it a corpus property would let an AI flag heavy-redirect-mass
topics the second time they look at the corpus.

## What worked surprisingly well

- **Branch exclusion at category-pull time.** Listing `exclude=[...]`
  before the depth-3 sweep paid off on 7 of 9 topics and was cheap
  (the survey makes adversarial / fictional / images branches
  obvious). This is a stable, learnable pattern; worth a short
  callout in instructions if it isn't already there.
- **Navbox + category combination as a yield diagnostic.** When the
  navbox added few new (Tour 6, Chernobyl 16, Vietnam 23), it
  confirmed category dominance. When the navbox added more (Studio
  Ghibli founder navboxes 17 + 6), it signaled the per-creator
  dimension was undercategorized. Treating the
  navbox-marginal-yield as a structural signal about the topic's
  category coverage was useful enough to be worth naming.
- **`resolve_redirects` mid-build catches noise at a glance.**
  Bluegrass genre-bleed via Mumford redirects, London heritage-rail
  mass, Chernobyl pop-culture aliases — all visible in the first
  20-row redirect sample without any per-article review.

## Affordances I noticed myself routing around

- **Spot check / gap check** — skipped on every run for time. The
  instructions describe autonomous fabrication of 30–50 probe titles
  but the brief structure of a thin run rewards completing the
  pipeline; spot check feels optional. Either land a stronger cue
  ("PHASE 2 wrap-up: spot check is non-optional") or accept that
  thin/quick runs reasonably skip it.
- **`fetch_article_leads`** — never reached for it across nine runs.
  Described as "the disambiguation workhorse on intersectional
  shapes" but isn't surfaced for non-intersectional review where it
  could still help (Sufism saint biographies; Vietnam War commander
  vs cultural figure).
- **`auto_score_by_description`** — would have been the right tool to
  demote pop-culture / fictional-character bleeds in Vietnam War and
  London Underground, but I didn't reach for it because the rubric
  structure rewards skipping numeric scoring on flat topics. The
  instructions could be sharper that auto_score_by_description is a
  REJECTION tool (sticky) regardless of whether the topic gets
  centrality scoring.

## Suggested next steps

Prioritized by ratio of value to authoring effort:

1. **Author menu-card stubs for the six missing shapes.** Half the
   pain in this session resolves at this layer alone. Recipe is
   already documented at `docs/adding-exemplars.md`.
2. **Add the missing SHAPE → WIKIDATA PROPERTY rows.** Each is a
   one-line edit to `server_instructions.md`.
3. **Build `count_wikiproject_articles(name)`.** Cheapest tool win;
   would have de-risked WP Military history and called out
   empty-WP Esperanto immediately. A wrapper over the existing API
   path that already powers `get_wikiproject_articles`, returning
   only the count.
4. **Build `harvest_template_uses(template)`.** Second-cheapest;
   opens the infobox-anchored canonical-instance pattern that
   recurs on transit, taxonomic, and oeuvre topics.
5. **Lightweight cross-wiki gap probe** as a less-than-full-parallel-build
   primitive — one SPARQL per direction.
6. **Pattern-based subcat exclude** on `get_category_articles` /
   `survey_categories`. Trivial to add; immediately useful.
7. Two instruction-only additions: callout that
   `resolve_redirects` collapse rate is a noise diagnostic, and a
   warning on main-article-harvest noise for single-event topics.

## Per-topic feedback

All nine runs submitted `submit_feedback` with structured
`tool_friction`, `sharp_edges_hit`, and `missed_strategies` fields.
The granular per-topic signal lives in `usage.jsonl`; this doc rolls
the cross-cutting patterns up.
