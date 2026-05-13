# Article tags — flexible per-topic stratification

**Status:** ☐ first sketch — will be refined in a separate planning
session before any implementation.

## Why

IV has a "classifications" feature that stratifies graphs by
Wikidata-derived membership (e.g. *Biography* = `P31=Q5`, with
sub-axes like gender = `P21` segmented Female/Male/Other). It
works for the cases it's shaped for, but it's awkward to use in
practice. After reading the IV code (see § How IV classifications
work today below), the awkwardness has three sources:

1. **Classifications are global, admin-managed records.** Adding a
   classification means hand-editing a JSONB blob in ActiveAdmin
   that encodes Wikidata predicates (`property_id`, `value_ids`,
   `required` flags, segment groupings). You have to know that
   *Politicians* = `P106=Q82955` to author the prereqs.
2. **Classification is Wikidata-only.** Membership is computed by
   matching Wikidata claims. Topic-internal stratifications that
   don't have a structured Wikidata signature — *climate /
   mitigation / adaptation*, *apollo / crew / ground-control* —
   simply can't be expressed.
3. **Classify-time fan-out is expensive.** `classify_all_articles`
   makes one Wikidata claims call per article per topic. At
   6,700 articles + a few classifications that's ~20K API calls
   on top of every topic build.

A **tag** feature on the TB side addresses all three: the
AI+user define tags in plain language during the build (no JSONB
editor); tag membership can come from any signal — Wikidata,
source label, regex, or pure judgment — so AI-judgment-only
stratifications work natively; and TB pre-computes membership and
ships it in the IV package, so IV doesn't have to fan out claims
calls.

Tags layer **alongside** centrality (the existing 1–10 scoring
axis), not on top of it. Centrality answers "how core is this
article?"; tags answer "what subset is this article in?" — IV's
existing chart machinery already separates these axes (centrality
filter applied first, then classification stratification).

Use cases the feature is shaped for:

- **Topic-internal stratifications** — for *climate change*, tags
  like "policy / mitigation / adaptation / science / impacts /
  activism / litigation". This is what IV's Wikidata-only
  classifications **cannot do today**, and is the strongest
  argument for the feature.
- **Role within topic** — for *apollo-11*: "crew", "spacecraft",
  "ground-control", "media-coverage". Also AI judgment, also
  inexpressible in IV today.
- **Biographies** — tag every article where Wikidata says
  `P31=Q5`. IV's classifications already cover this *with* the
  gender/country sub-stratification (see "properties/segments"
  below); TB tags would cover only the binary axis in v1.
- **Geographic** — "global-south", "us", "europe" assigned via
  Wikidata `P17` (country), category match, or judgment when
  Wikidata coverage is uneven.

## How IV classifications work today

Reference for everything below — distilled from
`impact-visualizer/app/models/classification.rb`,
`app/services/classification_service.rb`, the migrations, and the
chart code.

**Two-layer model:**

- **`prerequisites`** — JSONB array of clauses defining who's *in*
  the classification. Each clause is `{name, property_id,
  value_ids, required}`. Required clauses are AND-ed; non-required
  clauses are OR-ed. Match means the article is classified.
- **`properties`** — JSONB array of sub-axes for stratification
  *within* the class. Each property has `{name, slug, property_id,
  segments}`. Segments are either:
  - `segments: true` — auto-grouped into the top 19 values found
    across the corpus, with everything else lumped into "other"
    (used when the value space is large, e.g. countries).
  - `segments: [{label, key, value_ids, default}]` — explicit bins
    (e.g. gender → Female / Male / Other).

**Per-article state:** `article_classifications` rows store the
matched property values (`{name, slug, property_id, value_ids}`)
so that "Biography by gender" can be charted per timepoint.

**Concrete example** (factory default for *Biography*):

```
prerequisites: [{ property_id: P31, value_ids: [Q5], required: true }]
properties:    [{ name: Gender, slug: gender, property_id: P21,
                  segments: [
                    { label: Female, key: female, value_ids: [Q6581072] },
                    { label: Male,   key: male,   value_ids: [Q6581097] },
                    { label: Other,  key: other,  default: true } ] }]
```

**Chart axes IV exposes today:** "*Classification* vs. Other"
(binary stratification), "*Classification* by *Property*" (segment
breakdown), and WP10 prediction stratified by classification.

**Implication for TB tags:** the plan is to **deprecate IV's
Classifications altogether** in favour of TB tags. v1 carries the
full feature surface — binary membership *and* properties +
segments + per-article values — so IV's existing chart machinery
("Classification vs. Other", "Classification by Property") keeps
working unchanged, just reading from the TB-supplied payload
instead of running a per-article Wikidata fan-out.

Concretely on the IV side: existing topics that use IV
classifications keep working through the deprecation; new topics
go through tags only; the chart code keeps its existing segment
rendering and learns to read input from the tag payload; the
per-article classification fan-out (`classify_all_articles`) and
the ActiveAdmin classification editor go away. **The IV-side
deprecation is its own plan** — this doc only commits to what TB
emits.

## Locked decisions (proposed; refine before implementation)

These are the design commitments I'd start from. Each is open to
re-debate during the refinement session — flagging them up front so
the conversation has somewhere to start.

1. **Tags are per-topic, not global.** Each topic defines its own
   tag taxonomy. No cross-topic tag reuse. (Direct response to IV
   awkwardness #1 — global admin-managed records.)
2. **Many-to-many.** An article can carry zero or more tags.
3. **Tags can be binary OR value-bearing.** Most tags are
   binary — an article either has the tag or doesn't (e.g.
   *mitigation*, *crew*). A tag may *optionally* declare one or
   more properties (e.g. *Biography* with `gender`, `country`,
   `field_of_study` properties). Tagged articles carry zero or
   more values per declared property. v1 ships both shapes — the
   binary case is the dominant simple path; the property case
   covers what IV's classifications do today.
4. **Tags fully replace IV classifications.** v1 carries IV's
   complete chart surface: "Tag vs. Other" (binary stratification)
   and "Tag by Property" (segmented breakdown). IV deprecates its
   Wikidata-fan-out classification machinery; the chart code
   reads stratification from the TB payload.
5. **Tags layer alongside centrality, not under it.** Centrality is
   an axis; tags are sets. The two don't merge.
6. **AI judgment, with tool-generated candidates.** Same pattern as
   centrality: tools surface candidates (e.g. "every article whose
   Wikidata P31=Q5"), the AI applies the tag. Wikidata-derived tag
   membership is auto-applied within a tool call (the candidate
   set IS the tag set), but the AI initiates the call. *(See open
   question 2.)*
7. **No tag hierarchy in v1.** Flat namespace per topic.
8. **Terminology mirrors IV's wire format.** TB calls them
   *tags* / *properties* / *segments* / *values*; the package
   payload uses the same words IV's chart code already consumes.
   *(See open question 1 for the property-vs-dimension naming
   call.)*

## Data model (proposed)

Two new tables. The `properties_json` columns hold IV-shaped
property defs (on `topic_tags`) and per-article values (on
`article_tags`).

```sql
CREATE TABLE topic_tags (
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                -- short slug, e.g. "biography"
    description TEXT NOT NULL,         -- one-line definition
    ordering INTEGER NOT NULL DEFAULT 0,  -- IV display order
    derived_from TEXT,                 -- audit trail, e.g. "wikidata:P31=Q5"
                                        -- or "judgment" or "source:wikiproject:Climate change"
    properties_json TEXT NOT NULL DEFAULT '[]',  -- property defs (see below)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (topic_id, name)
);

CREATE TABLE article_tags (
    topic_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '[]',  -- per-article values
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (topic_id, article_id, tag_name),
    FOREIGN KEY (topic_id, tag_name) REFERENCES topic_tags(topic_id, name) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);
CREATE INDEX idx_article_tags_topic_tag ON article_tags(topic_id, tag_name);
```

A normalized table (rather than a JSON column on `articles`) makes
filter/aggregate queries cheap and matches the existing
`article_sources` pattern. The `properties_json` columns mirror the
shape of IV's `Classification.properties` and
`ArticleClassification.properties` exactly, so the package payload
is a near-identity transform.

**`topic_tags.properties_json` shape** — array of property defs,
each:

```json
{
  "slug": "gender",
  "name": "Gender",
  "wikidata_property_id": "P21",
  "segments": [
    {"key": "female", "label": "Female", "value_ids": ["Q6581072"]},
    {"key": "male",   "label": "Male",   "value_ids": ["Q6581097"]},
    {"key": "other",  "label": "Other",  "default": true}
  ]
}
```

`segments` follows IV's two shapes: an explicit array of
`{key, label, value_ids?, default?}` bins, OR `true` for
auto-grouping by top-N values across the corpus.
`wikidata_property_id` is optional — present when the property's
values came from Wikidata, absent for AI-judgment-only properties
that don't map to a Wikidata predicate.

**`article_tags.properties_json` shape** — array of values the
article carries on each declared property:

```json
[
  {"slug": "gender", "value_ids": ["Q6581072"]},
  {"slug": "country", "value_ids": ["Q30"]}
]
```

`value_ids` is an array (an article can have multiple gender values
or multiple citizenships). Empty `value_ids` means the article was
tagged but the property couldn't be resolved.

`derived_from` on `topic_tags` is non-load-bearing audit metadata:
it records how the tag was originally assigned (`wikidata:P31=Q5`,
`source:wikiproject:Foo`, `judgment`, `pattern:title_regex=^List of`)
so a future re-run can replay the same operation, and so the IV
side can show "this tag came from Wikidata P31=Q5" in a tooltip.

## Tool surface (rough)

Define / inspect:

- `set_topic_tags(tags=[{name, description, ordering?, properties?}])`
  — define or replace the topic's tag taxonomy. Each tag may
  optionally declare `properties` (see § Data model for the shape).
  Like `set_topic_rubric`, destructive replacement; AI passes the
  full set each time. *(Open question 1: extend `set_topic_rubric`
  instead, since tags + rubric are the same shape of thing —
  "topic taxonomy"? Or keep separate?)*
- `get_topic_tags()` — read the taxonomy including property defs.

Apply membership (binary):

- `tag_articles(tag, titles=[...], property_values=None)` — manual
  / AI-judgment apply. `property_values` is an optional dict of
  `{slug: [value_ids]}` for setting per-article values when the
  AI is judging values directly (e.g. AI decides this article is
  *climate-mitigation* and sets `subfield=adaptation`).
- `untag_articles(tag, titles=[...])` — symmetric remove.
- `tag_by_source(tag, source_label)` — bulk: "everything from
  `wikiproject:Climate change` is tagged `core`". No property
  capture (sources don't carry structured per-article values);
  property values can be filled in later via
  `set_tag_property_values`.
- `tag_by_pattern(tag, title_regex=..., description_regex=...)` —
  bulk: pattern-based tagging. Same no-property-capture caveat.

Apply Wikidata-driven (membership + values in one pass):

- `tag_by_wikidata(tag, predicates=[...], capture_properties=[...])`
  — the killer primitive for the IV-classifications use case.
  Two roles in one call:
  - **Membership match** via `predicates`: `[(P31, [Q5])]` →
    every article in the topic whose Wikidata satisfies the
    predicate is tagged. Multiple predicates AND together.
  - **Value capture** via `capture_properties`: for each declared
    property `[{slug: "gender", wikidata_property_id: "P21"},
    {slug: "country", wikidata_property_id: "P27"}]`, fetch the
    Wikidata claim and store as `article_tags.properties_json`.
  - Single SPARQL pass over the topic's QID set (one query per
    predicate + one per captured property, regardless of corpus
    size). Far cheaper than IV's per-article fan-out.
- `set_tag_property_values(tag, articles=[{title, slug, value_ids}])`
  — fill or override per-article values without changing
  membership. Useful when the AI has judgment values for tags
  that didn't come from Wikidata, or when a Wikidata-driven tag
  needs a specific override.

Filter / audit:

- Extend `get_articles(tag=..., tags_all=[...], tag_property={slug,
  value_ids})` to filter by tag membership and/or property values.
- Extend `audit_progress` to surface tag distribution: count per
  tag, untagged, double-tagged, and (per property) value coverage
  / missing values / segment breakdown.

Cleanup:

- `untag_by_source(tag, source_label)` — symmetric to bulk apply.
- *(Open question: do we need `untag_all(tag)` to wipe a tag without
  deleting its definition? Probably yes for "I assigned this wrong,
  let me redo".)*

## IV handoff changes

The `/packages/<handle>` payload gains:

- Top-level `tags: [{name, description, ordering, derived_from?,
  properties}]` — the taxonomy. `properties` is an array of
  property defs (slug, name, optional `wikidata_property_id`,
  segments) matching IV's existing `Classification.properties`
  shape.
- Per-article `tags: [{name: "biography", values: [{slug:
  "gender", value_ids: ["Q6581072"]}]}, {name: "policy",
  values: []}]` — array of `{name, values}` objects (binary tags
  carry an empty `values` array; value-bearing tags carry the
  per-property values).

This bumps `schema_version` from 1 → 2. The deprecation gives the
schema bump a clean ordering (see § Sequencing): IV ships the v2
reader and the chart code learns to consume the tag payload, then
TB flips on tag emission, then IV begins deprecating the
classification path.

**Concept mapping — TB tags ↔ IV classifications:**

| TB | IV |
|---|---|
| `topic_tags.name` | `Classification.name` |
| `topic_tags.description` | (no equivalent — IV has no description field) |
| `topic_tags.derived_from` | `Classification.prerequisites` (audit only — IV won't re-evaluate) |
| `topic_tags.properties_json` | `Classification.properties` |
| `article_tags(topic, article, tag)` row | `ArticleClassification` |
| `article_tags.properties_json` | `ArticleClassification.properties` |

A TB tag is structurally an IV classification minus the
`prerequisites` half. The IV side reads the tag payload directly;
it does not re-derive membership from `derived_from` (so a
`wikidata:P31=Q5` value is informational, not operational —
coverage gaps on TB's side don't get retried by IV).

CSV export — open question whether tags appear as additional
columns in `enriched=True` CSVs. Default-CSV (two-column for IV
import) stays as-is.

## Pipeline placement

Tagging happens **after** scoring is mostly settled, since:

- Tag taxonomy decisions benefit from seeing the full corpus.
- Bulk-tag-by-source operations need source labels to be stable.
- The IV handoff is the natural sink, and it's already at the end
  of the pipeline.

Updated pipeline (additive — earlier steps unchanged):

1. Scope → 2. Probe → 3. Gather → 4. Clean → 5. Score → **6. Tag
(new)** → 7. Review → 8. Export / publish.

`server_instructions.md` would gain a § Tagging section with the
recommended flow: define the tag taxonomy with the user
(consultative, like the centrality rubric), apply bulk tags from
structured signals, fill in judgment tags, audit distribution.

## v2 — deferred

- **Tag hierarchy** — `policy/mitigation`, `policy/adaptation` as
  parent/child. Rejected for v1 to avoid the depth-explosion
  failure mode the categories axis already hits.
- **Auto-suggest tags from descriptions** — LLM-side; no server
  primitive needed, but a `suggest_tags()` candidate generator
  could help the AI propose a taxonomy at scope time.
- **Tag co-occurrence / conflict warnings** — `audit_progress`
  flagging "you have 200 articles tagged both `mitigation` and
  `adaptation`; intended?"
- **Cross-topic tag reuse** — a global "biography" tag shared
  across topics with shared property defs (e.g. gender/country
  segments). Probably the wrong shape; per-topic taxonomies
  match how stratifications differ across topics. Could later
  add a "tag template" feature — *copy* a saved tag definition
  into a new topic — without making tags themselves global.
- **Property value enums beyond Wikidata QIDs** — v1 stores
  `value_ids` as Wikidata QID strings (matching IV's wire shape).
  A future enum-typed property could let topic-internal tags
  declare custom value spaces (e.g. *intensity = low | medium |
  high*) without leaning on Wikidata. Not urgent; current shape
  doesn't preclude it (value_ids is just a string array).

## Open questions to resolve before implementation

1. **Terminology — "property" or "dimension"?** TB needs a word for
   the value-axis within a tag. `property` matches IV's wire shape
   exactly (zero translation cost). `dimension` is more evocative
   ("Biography by *dimension* gender") but diverges by one word.
   Default lean: `property` for cross-repo coherence. Sage's
   call.
2. **`set_topic_tags` vs extending `set_topic_rubric`** — same
   shape of thing (per-topic taxonomy with descriptions). One tool
   or two? With property defs added to tags, the rubric and the
   tag taxonomy now look quite different in detail — argues for
   keeping them separate, but worth deciding.
3. **Auto-apply on Wikidata-driven tagging** — does
   `tag_by_wikidata(tag, predicates=...)` write rows directly, or
   surface candidates the AI then applies? Memory:
   `feedback_no_computed_centrality_tools` says don't *compute*
   centrality, but tag membership from a structured fact is
   different from a centrality score. I think auto-apply is fine
   here (the candidate set IS the tag), but worth confirming.
4. **Subtractive vs additive (per
   `feedback_wikidata_incomplete`)** — Wikidata coverage is
   uneven. `tag_by_wikidata` is additive ("find rows where
   P31=Q5") so the failure mode is "missed biographies", not
   "wrong biographies". Document this explicitly so the AI
   doesn't lean on tag absence as a negative signal. Same caveat
   applies to property *values* — a missing P21 (gender) value
   means "Wikidata didn't say", not "no gender".
5. **Tag namespace** — `biography` vs `wikidata:human` vs
   `bio`. Are tag names canonical-by-convention, or does the AI
   pick? Probably AI-picks, with the description carrying the
   meaning.
6. **Schema-version coordination** — given the deprecation, the
   ordering is: IV ships v2 reader + chart code that consumes the
   tag payload (the chart code itself stays mostly unchanged
   since the segment/property shape is preserved) → TB flips on
   tag emission → IV begins deprecating the classification editor
   + classify pass. Existing topics that were imported with
   classifications keep working through some grace period; new
   topics use tags only. See `impact-visualizer.md` § Forward-
   compat for the bump-coordination plumbing.
7. **Pipeline insertion point** — strictly post-scoring, or can
   tags be assigned during gather (e.g. tag-as-you-add)?
   Tag-as-you-add couples tagging to the source label, which is
   what `tag_by_source` already covers — probably not worth a
   separate per-add path.
8. **Cost of `tag_by_wikidata`** — IV's classify pass makes ~16
   Wikidata API calls per article (`classify_article` fetches
   full claims) — at 6.7K articles that's ~107K calls per
   classification. TB's SPARQL-driven design does one query per
   predicate + one query per captured property regardless of
   corpus size: `SELECT ?qid ?value WHERE { VALUES ?qid
   {<topic-qids>} . ?qid wdt:P21 ?value }`. For a *Biography*
   tag with two captured properties (gender, country), that's
   3 queries total instead of ~107K. Existing
   `wikidata_entities_by_property` already uses SPARQL so the
   primitive is in place. Flag this against
   `project_tool_cost_review`.
9. **Migration path for existing IV-classified topics.** Three
   options: (a) one-shot conversion script — read existing
   `Classification` + `ArticleClassification` rows on the IV side
   and synthesize TB-shaped tag payload for the topic, write back
   as `topic_tags` + `article_tags` (where? IV-side, or TB-side
   if the TB topic still exists and has source_topic_id linkage);
   (b) keep classifications working until the topic gets
   re-imported from TB, then it switches over; (c) users
   re-publish from TB, no auto-migration. Sage's call —
   probably (b) is the lowest-risk middle ground.
10. **Should the AI populate property values from Wikidata
    automatically when applying a value-bearing tag?** I.e. if
    the AI calls `tag_articles("biography", titles=[...])` on a
    tag that declares `gender` and `country` properties, should
    TB auto-fetch those values from Wikidata as a follow-up, or
    leave them empty and require an explicit
    `tag_by_wikidata` / `set_tag_property_values` call? Auto-
    fetching keeps the simple path simple but couples membership
    to value-resolution latency. Probably leave to the AI, with
    a clear pattern documented in `server_instructions.md`.

## Sequencing

This isn't on the ratchet — tagging won't move precision/recall
metrics, it's a downstream-stratification feature. The proving
ground is a dogfood session on a tag-rich topic (climate-change is
the obvious candidate; the post-cleanup 6,674 article version is
the substrate) where an AI builds out the taxonomy and bulk-tags
via the new primitives. The success criterion is whether IV can
render a useful stratified graph from the resulting handoff.

The deprecation makes the cross-repo ordering matter:

1. **TB v1 lands behind a feature flag.** Tag tools exist
   (including the property-aware ones); payload includes `tags`
   only when flagged on. `schema_version` stays 1 until the IV
   side is ready.
2. **IV ships the v2 reader.** The chart code itself changes
   minimally — the property/segment shape it consumes is
   preserved word-for-word from `Classification.properties` to
   the TB payload. What changes is the *source* of the data
   (TB-supplied instead of locally computed via
   `classify_all_articles`). Old classification-based topics
   keep working through this step.
3. **TB flips the flag.** New publishes emit `tags` and bump
   `schema_version` to 2. End-to-end dogfood on climate-change
   confirms the round-trip with at least one value-bearing tag
   (e.g. *biography* with gender + country properties) and one
   AI-judgment tag (e.g. *mitigation*).
4. **IV deprecates the Classification path.** Editor goes
   read-only, then disappears; `classify_all_articles` stops
   running on new topics; existing classified topics get a
   conversion or grace period (open question 9).

## Cross-references

- `impact-visualizer.md` — schema-version coordination, package
  payload shape.
- Memory `feedback_no_computed_centrality_tools` — informs the
  auto-apply question.
- Memory `feedback_wikidata_incomplete` — informs the
  additive-vs-subtractive framing.
- Memory `project_composable_strategy_guidance` — `audit_progress`
  is the existing diagnostic surface tags should plug into.
