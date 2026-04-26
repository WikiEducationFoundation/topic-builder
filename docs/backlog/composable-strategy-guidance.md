# Composable strategy guidance

> **Status (2026-04-26):** Ships 1 + 2 + 3 all landed. See
> `docs/shipped.md` "Composable strategy guidance — Ships 1 + 2 + 3
> (2026-04-26)" for the canonical record. This doc is preserved as
> the design rationale; the status checklist below records what
> shipped vs what's deferred.

Active design doc for adding a **decompositional strategy layer** to
complement the existing case-based exemplar layer. Three sequenced
ships, each independently useful:

- **Ship 1 — Information architecture.** Canonical shape-axis
  vocabulary, move catalog, failure-mode catalog, restructured
  `server_instructions.md`. No server code. All authoring is
  synthesis from existing dogfood notes.
- **Ship 2 — Active scaffolding hooks.** Structured `topic_profile`
  on `set_topic_rubric` whose response returns axis-applicable
  moves and relevant failure modes; synthetic-signal additions to
  `describe_topic`; new `audit_progress` diagnostic. Small server
  work; lands once Ship 1's catalogs exist to reference.
- **Ship 3 — Decomposed calibration.** Replace single-float
  `coverage_estimate.confidence` with a structured signal object
  plus server-derived band plus AI-override-with-rationale; record
  named moves and observed failure modes on `submit_feedback`.
  Builds on Ship 2's signal surfaces.

## Status / next actions

- [x] Review and align on scope before Ship 1 starts
- [x] Author shape-axis vocabulary doc (Ship 1.a)
- [x] Author move catalog (Ship 1.b) — 27 moves, all grounded
- [x] Author failure-mode catalog (Ship 1.c) — 19 anti-patterns
- [x] Restructure `server_instructions.md` (Ship 1.d) — 13 thematic sections
- [x] Validate Ship 1 with one dogfood run (Brutalist architecture, 2026-04-25)
- [x] Ship 2.a — `topic_profile` on `set_topic_rubric`
- [x] Ship 2.b — synthetic signals on `describe_topic`
- [x] Ship 2.c — `audit_progress(topic)` diagnostic
- [x] Ship 3.a — decomposed `coverage_estimate` schema
- [x] Ship 3.b — `strategy_execution` on `submit_feedback`
- [x] Ship 3.c — `scripts/analyze_calibration.py`
- [ ] Empirical validation: thin-variant against an actual benchmark
      (apollo-11 is the highest-leverage test — 2026-04-24
      calibration was 0.74 confidence vs 33% recall, the worst
      anchoring case). Run `analyze_calibration.py` after to verify
      band-vs-recall alignment.

## The problem

Four cycles of dogfood evidence converge on the same gap: the
strategic wisdom in `server_instructions.md` (~50k chars, including
the SHAPE → WIKIDATA PROPERTY table, KNOWN SHARP EDGES,
intersectional warnings, reach extension) doesn't reach the AI at the
moment of choice. Specifically:

- **2026-04-24 thin-variant cycle.** Across 5 topics, every
  self-rating 7/10, every confidence 0.68–0.74, actual recall
  33%–85%. Zero `wikidata_query` / `harvest_navbox` calls on 4 of 5
  topics despite the SHAPE table explicitly recommending them.
  Calibration pegged at "I followed the protocol," not at corpus
  quality. Documented at
  `dogfood/sessions/2026-04-24/session-2026-04-24-thin-claude-code-medium.md`.
- **2026-04-25 nine-topic shape survey.** None of the 6 existing
  exemplars matched any of 9 chosen-to-be-shape-different topics
  (Sufism, Tour de France, Bluegrass, Chernobyl, Vietnam War, Type 2
  diabetes, London Underground, Studio Ghibli, Esperanto). The AI
  defaulted to the same outer pipeline on every one. Documented at
  `dogfood/sessions/2026-04-25/session-2026-04-25-shape-survey-9-topics.md`.
- **2026-04-23 run-2 notes** named ~8 tool/workflow gaps that
  classify as either "moves we wished existed" or "failure modes we
  hit blind."
- **Existing backlog items.** 1.d (shape-wisdom abstraction, shipped),
  the 2026-04-24-proposed items A (force-shape-first-move), B
  (calibrate-vs-signals), C (shape-typed wrap-up checklist), D
  (surface triangulation) — all touch the same surface from
  different angles.

The pattern across all of these: **passive prose loses to procedural
inertia.** A 50k-char instructions file can't compete with the AI's
plausible default plan. The leverage is in active, modular,
axis-keyed guidance that arrives in-context at the moment of
decision.

## Intent

Treat the problem as one of **information architecture + active
scaffolding** rather than authoring more exemplars. Two complementary
postures already exist in the system:

- **Case-based reasoning** (exemplars) — "what's the closest known
  case, what worked?" — works on close cases, fails on novel ones.
  The 9-topic survey demonstrated that 6 carefully-chosen exemplars
  don't cover most of what production sees, and shape enumeration
  doesn't scale (every "religious tradition" is different from every
  other; even within an oeuvre, Studio Ghibli ≠ Stephen King ≠
  Tarantino).
- **Decompositional reasoning** (axes + primitives) — "what are the
  orthogonal properties of this topic, what moves apply per
  property?" — works on novelty.

Today the system leans heavy case-based. This doc ships the
decompositional complement. The two layers reinforce each other:
exemplars become axis-indexed and move-cited (shorter to author,
more useful to compose against); novel topics get approached by
composing primitives from the catalogs.

## Why

- **Shape enumeration doesn't scale.** Direct evidence: the 9-topic
  survey. Even with the existing 6 exemplars + the SHAPE table, no
  authored shape matched the 9 novel topics' shapes; the AI defaulted
  to "category sweep + maybe navbox" on all of them.
- **Active beats passive.** The 2026-04-24 evidence is unambiguous:
  prose hints upstream of the call get skimmed; structured prompts at
  decision points get answered. Ship 2's active scaffolding at
  `set_topic_rubric` is what closes the gap.
- **Calibration is metacognitive, not vibe-driven.** The 0.7-pegged
  confidence isn't laziness; the AI has no signals to ground the
  number. Ship 3's decomposed calibration gives it grounded signals.
- **Authoring cost is low.** The session notes already implicitly
  contain ~25 named moves and ~15 named failure modes. Ship 1 is
  synthesis work, not invention work — battle-tested against real
  cases by construction.
- **Reduces instructions bloat.** Today's 50k `server_instructions.md`
  mixes pipeline + principles + sharp edges + intersectional + reach
  extension. Splitting axis vocabulary, moves, and failure modes
  into addressable docs lets future additions land in obvious places
  without growing the central file unboundedly.
- **Subsumes 4 distinct backlog items into one coordinated framework.**
  Items A / B / C / D from 2026-04-24 each touch one surface;
  shipping them piecemeal misses the connective tissue (the shared
  axis vocabulary). Coordinating them produces a coherent system
  rather than four loosely-related tools.

---

# Ship 1: shape-axes + move catalog + failure-mode catalog

Lands first. **No server code.** All authoring is synthesis from
existing dogfood notes; nothing speculative.

## 1.a Canonical shape-axis vocabulary

A short doc — provisionally `mcp_server/shape_axes.md` — defining the
small, coordinated set of axes used across exemplars, moves, failure
modes, the SHAPE table content, and (Ship 3) calibration. Tentative
axes from current usage:

- **Scale** — small (<200) / medium (200–2k) / large (2k–10k) /
  huge (>10k).
- **Structural primitives present** — boolean flags for
  `canonical-category`, `dedicated-WP`, `curated-list-pages`,
  `canonical-navbox`, `canonical-infobox`.
- **Biographical density** — high / medium / low.
- **Multilinguality depth** — deep / moderate / shallow /
  English-dominant.
- **Topic-vs-parent relationship** — standalone / subtype-of-parent /
  superset / peer-of-parent.
- **Time profile** — recent / historical-bounded / ongoing /
  multi-period.
- **Periphery type** — cultural / technical / political / minimal.
- **Recall ceiling driver** — short enum naming what's likely to cap
  completeness on this topic: category-incompleteness /
  cross-wiki-gap / shortdesc-ambiguity / consolidation-into-list-pages /
  wp-broader-than-topic / etc.

Each axis: definition, how to detect it, concrete examples spanning
current exemplars and the 9-topic survey. Total file ~1k chars.
Referenced by every other guidance artifact going forward.

**Why this is the keystone.** Today the exemplars use one set of
axes (`structural`, `layered_shape`, `non-Anglosphere depth`), the
SHAPE table uses shape names ("intersectional biography," "single
historical event"), and the rubric uses CENTRAL/PERIPHERAL/OUT — all
disjoint vocabularies. A single shared axis vocabulary is the
connective tissue that lets moves declare preconditions, exemplars
index by similarity, failure modes have axis-keyed detection, and
calibration signal-bands compose. Without it, the rest of Ship 1
fragments back into prose; with it, the framework is coherent.

## 1.b Move catalog

A new doc — provisionally `mcp_server/strategy_moves.md` — listing
~20–30 named atomic strategy moves, each with the same five-field
schema:

```
move: <name-with-hyphens>
preconditions: <axis-value combinations that activate this move>
sequence:      <1–3 tool calls, with parameter sketches>
expected:      <yield characterization + noise characterization>
rescue:        <what to do if it underperforms>
```

Two illustrative entries:

```
move: branch-excluded-category-sweep
preconditions: canonical-category=yes; survey shows adversarial /
               cultural-tail / fictional / images subcats present
sequence:      survey_categories(count_articles=True) →
               identify exclude list →
               get_category_articles(exclude=[...])
expected:      70–90% of corpus on category-rich topics, low noise
rescue:        post-pull pattern-remove if subtle bleed survives

move: cross-wiki-gap-probe (lightweight)
preconditions: multilinguality=deep AND scale<huge
sequence:      resolve_qids → SPARQL: sitelinks-on-wiki-X-not-on-en →
               review surfaced QIDs
expected:      highest-leverage reach axis for native-language-deep
               topics; surfaces enwiki articles English search missed
cost:          1 SPARQL
rescue:        fall back to a full parallel build if too many items
               surface to reconcile manually
```

The full ~25-move first cut comes from synthesizing across:

- the orchids exemplar full case study (~6 moves embedded);
- the 2026-04-23 run-2 notes (~6 moves);
- the 2026-04-24 thin-variant notes (~3 moves);
- the 2026-04-25 nine-topic survey (~10 moves);
- the existing SHAPE → PROPERTY table (7 shape-keyed Wikidata-probe
  moves directly extractable).

Cumulatively ~32 candidate moves; after dedup ~25. Every entry maps
to at least one observed case where it was applied successfully or
where it was named-as-missing. **Nothing speculative.**

Once moves are addressable, an exemplar becomes "a sequence of moves
typical for this shape" — much more compact than today's case-study
prose, and decomposable: the AI can mix-and-match for a novel topic
by reaching for moves whose preconditions match its axis profile.

## 1.c Failure-mode catalog

A new doc — provisionally `mcp_server/failure_modes.md` — listing
~15 named anti-patterns. Each entry: name + symptom + detection
cue + rescue move + evidence pointer. Two illustrative entries:

```
failure-mode: adversarial-categories-under-topic-root
  symptom:    subcats explicitly opposed-to or competitive-with the
              topic appear under the canonical category root
  detection:  survey_categories shows subcats whose names contradict
              the topic ("Salafi"/"Wahhabi" inside "Sufism";
              "Anti-X" cats; etc.)
  rescue:     enumerate at survey time; pass exclude=[...] before
              pulling get_category_articles
  evidence:   2026-04-25 Sufism

failure-mode: wp-broader-than-topic
  symptom:    WikiProject exists and tags many articles, but covers
              a superset of the topic
  detection:  WP article count >>> topic-relevant scope; pulling WP
              alone adds 30–50% out-of-scope material
  rescue:     WP-intersect-category move (1.b); or skip WP if no
              canonical category exists
  evidence:   2026-04-25 London Underground (WP London Transport
              covers buses, river services, etc.); 2026-04-24
              Vietnam War (WP Military History scope concern)
```

The full ~15-entry first cut from existing notes:

- `adversarial-categories-under-topic-root` (Sufism)
- `genre-bleed-via-full-discography` (Bluegrass)
- `wp-broader-than-topic` (London Underground, Vietnam War)
- `wp-registered-but-empty` (Esperanto)
- `topic-is-subtype-of-parent` (Type 2 diabetes)
- `consolidation-into-list-pages` (Studio Ghibli)
- `heritage-redirect-mass` (London Underground)
- `main-article-context-link-noise` (Chernobyl)
- `fictional-X-bleeds-under-real-X-root` (Vietnam War, Chernobyl)
- `shape-typed-first-move-skipped` (every 2026-04-24 topic)
- `calibration-pegged-at-protocol-following` (every 2026-04-24 topic)
- `sticky-rejection-blocks-manual-add` (AA-STEM 2026-04-24)
- `lossy-redirect-merging-bio-to-non-bio` (AA-STEM 2026-04-24)
- `list-page-prose-contamination` (3 of 5 in 2026-04-24)
- `eponym-collisions-on-genus-lists` (orchids exemplar)

Same authoring principle: every entry maps to at least one observed
case. Many are detectable from observable signals (resolve_redirects
rate, navbox vs category yield ratio, source overlap %), so they
can power the Ship 2 `audit_progress` diagnostic.

## 1.d Restructure server_instructions.md

After 1.a–c, the central instructions file should reference (rather
than inline) content that belongs in the new catalogs.

Concrete moves:

- **Replace** the SHAPE → WIKIDATA PROPERTY table with a pointer to
  the move catalog. The shape→property mapping becomes a sub-axis
  ("Wikidata property probes") within the relevant catalog moves —
  same content, reframed move-by-move with proper preconditions and
  rescue paths.
- **Pointer** to the failure-mode catalog from KNOWN SHARP EDGES.
  KNOWN SHARP EDGES stays as a section — sharp edges are tool-API
  quirks, not strategy anti-patterns; the two are complementary.
- **Pointer** to the shape-axis vocabulary from SCOPE RUBRIC and
  PREPARATORY PHASE.
- **Section labels** for clean navigation — pipeline, principles,
  vocabulary references, sharp edges, intersectional, reach
  extension, wrap-up. Each as its own labeled block.

Estimated size: 50k → ~30k chars in the central file, with the moved
content addressable and updatable independently. Smaller central
file = lower skim cost = higher chance the AI actually reads it.

## Sequencing within Ship 1

1.a → 1.b → 1.c → 1.d. The vocabulary doc is the keystone; moves and
failure modes reference it. Restructure happens last, after the
catalogs exist to reference.

## Validation for Ship 1

A new dogfood run on a novel topic (any of the 9 from the
2026-04-25 survey is suitable, since none have benchmark gold and all
are shape-different from the existing exemplars). Compare:

- Did move-shaped guidance fire more than the pre-1.d shape table?
  (Easy proxy: did the AI cite the move catalog by name in
  reflection?)
- Did the AI name failure-modes-it-saw using the catalog vocabulary?
- Did structural posture change at all without active scaffolding
  (Ship 2)?

**Honest expectation: Ship 1 alone may not change behavior much.**
Passive guidance still loses to procedural inertia. Ship 1's value
is content + IA; behavior change comes with Ship 2. Ship 1 is
worthwhile on its own only if the catalogs are subsequently
referenced by Ship 2 — they're written for that, not as standalone
reading material.

---

# Ship 2: active scaffolding at decision points

Lands after Ship 1's catalogs exist. Small server-side work that
makes catalog content arrive in-context at the moment of decision
rather than 50k chars upstream.

## 2.a Structured `topic_profile` on `set_topic_rubric`

Add an optional `topic_profile` dict to `set_topic_rubric` mirroring
the canonical axis vocabulary:

```python
topic_profile: dict | None = None
# {
#   "scale": "medium",
#   "structural_primitives": {"canonical_category": True,
#                             "dedicated_wp": False, ...},
#   "biographical_density": "high",
#   "multilinguality": "deep",
#   "topic_vs_parent": "subtype-of-parent",
#   "time_profile": "historical-bounded",
#   "periphery_type": "cultural",
#   "recall_ceiling_driver": "cross-wiki-gap",
# }
```

The response, in addition to confirming the rubric, returns:

```python
{
  ... existing fields ...,
  "applicable_moves": [<names from 1.b matching the profile axes>],
  "relevant_failure_modes": [<names from 1.c the profile axes flag>],
  "recommended_first_move": <single name + one-sentence rationale>,
  "recall_ceiling_estimate": <textual cue based on profile>,
}
```

The AI commits to a profile at the natural commit point (it's
already required to call `set_topic_rubric` before gather), and
strategy guidance arrives tailored to its profile. **Active
scaffolding at the decision moment.**

If `topic_profile` is omitted, the response stays as today
(back-compat).

**Why at `set_topic_rubric` rather than a separate
`suggest_strategy` tool.** Reusing an existing required call
minimizes friction and ensures the active scaffolding fires every
session. A standalone tool would be skippable; the existing one
isn't.

## 2.b Synthetic signals on `describe_topic`

Today `describe_topic` returns title-length distribution, top-first-
words, suspicious patterns, source-shape counts. Add:

- `triangulation_pct` — `multi_sourced / total_articles`. Already
  computable; surface it as a first-class field.
- `redirect_collapse_rate_at_last_resolve` — persistent corpus
  property updated on each `resolve_redirects` call.
- `single_source_breakdown` — top sources by single-sourced article
  count (which sources are NOT triangulating with the rest).
- `yield_last_n_calls` — articles-added-per-call trend over the last
  N gather calls; classifies as rising / plateau / declining.
- `shape_strategies_attempted` — derived from usage log: which named
  moves the AI has fired this session.
- `shape_strategies_unused_but_applicable` — derived from
  `topic_profile` (2.a) plus the move catalog.

`describe_topic` becomes a calibration surface, not just a
shape-of-corpus surface.

## 2.c New `audit_progress(topic)` diagnostic

Read-only synthesis tool combining:

- which shape-typed moves the AI has fired (from usage log);
- which axis-applicable moves remain unused (from topic profile +
  catalog);
- which named failure modes the corpus shows symptoms of (from
  failure-mode catalog detection cues run against current state);
- yield trajectory (last-N-calls);
- a one-paragraph recommendation.

Equivalent to the 2026-04-24-proposed item C ("shape-typed
gap-check checklist at wrap-up") but as an active diagnostic the AI
can call any time, not a passive prose checklist at wrap-up.

Hand-off in WRAP-UP guidance: `audit_progress` becomes a
recommended pre-export step. Hand-off in mid-build: when
`yield_last_n_calls = declining`, the AI has reason to reach for it
and pivot strategy.

---

# Ship 3: decomposed calibration

Lands after Ship 2's signals exist. Replaces the single-float
`coverage_estimate.confidence` with a structured signal object plus
server-derived band plus AI-override-with-rationale.

## 3.a `coverage_estimate` schema redesign

Today: `{confidence: float, rationale: str, remaining_strategies: [str]}`.

Proposed:

```python
coverage_estimate: {
  signals: {
    triangulation_pct: float,            # from describe_topic
    shape_strategies_attempted: int,
    shape_strategies_applicable: int,    # from topic_profile
    spot_check_hit_rate: float | null,
    redirect_collapse_rate: float,
    failure_modes_observed: [str],       # names from 1.c catalog
    yield_trajectory: "rising" | "plateau" | "declining",
  },
  band: "low" | "moderate" | "high",     # server-derived
  band_rationale: str,                   # server-supplied
  ai_override: float | null,             # AI may override
  ai_override_rationale: str,            # required if override set
  remaining_strategies: [str],           # existing field, retained
}
```

Server has a small explicit function mapping the signal vector to a
band:

```
if triangulation_pct < 0.20 OR
   shape_strategies_attempted / shape_strategies_applicable < 0.50:
    band = "low"
elif triangulation_pct >= 0.40 AND
     shape_strategies_attempted / shape_strategies_applicable >= 0.75 AND
     yield_trajectory != "rising":
    band = "high"
else:
    band = "moderate"
```

Thresholds tunable; the explicit mapping is what makes calibration
**auditable across sessions**. The single float remains as a derived
summary, but with grounded rationale.

## 3.b `submit_feedback` records strategy execution log

Add a `strategy_execution` field:

```python
strategy_execution: {
  moves_attempted: [<names from the 1.b catalog>],
  moves_succeeded: [<subset>],
  moves_skipped_reason: {move_name: reason, ...},
  failure_modes_observed: [<names from the 1.c catalog>],
}
```

Aggregating across sessions lets us see which moves fire when, where
playbooks break down, and where new moves are needed. Closes the
flywheel between dogfood evidence and catalog growth.

## 3.c Calibration trend analysis

Small post-hoc script that joins `submit_feedback` records to
gold-derived recall (where benchmarks exist), plots calibration band
vs actual recall, and surfaces the residual error after the
band-mapping. The signal-to-band thresholds get tuned from this
data.

Ships as a one-off `scripts/analyze_calibration.py`; not an MCP
tool.

---

# Sequencing across ships

```
Ship 1 (info-architecture, no code)
  1.a vocabulary
  1.b move catalog
  1.c failure-mode catalog
  1.d server_instructions.md restructure
       │
       ▼
Ship 2 (active scaffolding, small code)
  2.a topic_profile on set_topic_rubric
  2.b describe_topic synthetic signals
  2.c audit_progress diagnostic
       │
       ▼
Ship 3 (decomposed calibration)
  3.a coverage_estimate redesign
  3.b strategy_execution on submit_feedback
  3.c calibration trend analysis
```

Each ship is independently useful:

- **Ship 1 alone** improves authoring posture and creates a
  referenceable vocabulary; even without behavior change it makes
  future authoring (more exemplars, more moves) faster.
- **Ship 1 + 2** is the behavior-change unit. Active scaffolding at
  `set_topic_rubric` is what closes the 2026-04-24
  "shape-typed first move skipped" gap.
- **Ship 1 + 2 + 3** is the calibration unit. Closes the
  0.7-pegged-confidence gap with grounded signals.

Ratchet implications:
- Ship 1 doesn't change baselines (no behavior change expected).
- Ship 2's first cycle becomes the new baseline. Compare against
  the post-Ship-1 baseline to attribute the lift to active
  scaffolding specifically.
- Ship 3 introduces calibration-band-vs-recall as a separate axis on
  the scoreboard.

---

# Authoring strategy: synthesize, don't speculate

All Ship 1 content can be authored from existing dogfood notes. A
first-pass mining gives:

| Source | Moves | Failure modes |
|---|---:|---:|
| `dogfood/exemplars/orchids.md` (full case study) | ~6 | ~3 |
| `dogfood/sessions/2026-04-23/run2-notes.md` | ~6 | ~4 |
| `dogfood/sessions/2026-04-24/thin-claude-code-medium.md` | ~3 | ~5 |
| `dogfood/sessions/2026-04-25/shape-survey-9-topics.md` | ~10 | ~8 |
| Existing SHAPE → WIKIDATA PROPERTY table | ~7 | — |
| **Total (pre-dedup)** | **~32** | **~20** |
| **Total (post-dedup)** | **~25** | **~15** |

Every catalog entry maps to at least one observed case. Nothing
speculative. **Authoring is a synthesis exercise on the existing
corpus, not an invention exercise.**

# Open questions

- **Where do the catalogs live physically?** Three options:
  1. `mcp_server/strategy_moves.md` and `mcp_server/failure_modes.md`,
     loaded as part of the substrate at session start. Pro: AI reads
     them automatically. Con: grows the central instructions size.
  2. `docs/strategy-moves.md` and `docs/failure-modes.md`, referenced
     from but not inlined into `server_instructions.md`. Pro: keeps
     central file small. Con: AI doesn't see them unless guided to.
  3. `dogfood/moves/` and `dogfood/failure_modes/` mirroring
     `dogfood/exemplars/`, served via paired `list_moves` /
     `get_move` MCP tools. Pro: parallel structure to exemplars,
     clean DB-backed access. Con: most server scaffolding to build.

  Lean toward (1) for Ship 1 simplicity, then optionally migrate to
  (3) when Ship 2 wires the catalogs into responses. Defer the
  decision to Ship 2 design.

- **Does Ship 2's `topic_profile` get inferred or AI-supplied?** Lean
  AI-supplied — the AI is committing to its model of the topic at
  rubric time anyway, and forcing explicit commitment is a feature.
  A future inference helper could read `survey_categories` /
  `find_wikiprojects` results to suggest a profile.

- **Does Ship 3's band get exposed to the AI mid-build, or only at
  `submit_feedback`?** Lean mid-build — Ship 2's `audit_progress`
  is the natural surface — so calibration shapes execution, not just
  retrospection.

- **Should the move catalog include cost expectations (API calls,
  wall time)?** Useful for COST AWARENESS but adds maintenance
  burden. Defer to v2 of the catalog; first cut is preconditions +
  sequence + yield + rescue.

- **How do we keep the catalogs from rotting?** Same staleness
  discipline as exemplars: `last_validated_against` per entry; flag
  entries unrevisited for >N cycles. Ship as part of the catalog
  frontmatter from day 1.

- **Does Ship 2's `audit_progress` need its own benchmark scoring
  axis?** Probably not — its diagnostic value is captured indirectly
  through Ship 3's calibration band accuracy. If `audit_progress`
  is informative, calibration error shrinks. If it's not, no harm
  in having a diagnostic the AI can ignore.

# Cross-reference to existing backlog

Items this plan **subsumes** (drop separate tracking once shipped):

- 2026-04-24 proposed item A (force-shape-first-move) →
  Ship 2.a (active scaffolding via `topic_profile` +
  `applicable_moves` response).
- 2026-04-24 proposed item B (calibrate-vs-signals) →
  Ship 3.a (decomposed `coverage_estimate`).
- 2026-04-24 proposed item C (shape-typed wrap-up gap-check) →
  Ship 2.c (`audit_progress` diagnostic).
- 2026-04-24 proposed item D (surface triangulation in
  `get_status` / `describe_topic`) → Ship 2.b.

Items **adjacent but distinct**, still worth shipping on their own
merits:

- Tier 3 `topic_policy(...)` (Phenomenology feedback) — per-topic
  scope rules; this plan is per-topic-shape strategy guidance.
  Could compose: a topic's policy could declare which catalog moves
  it's whitelisting / blacklisting.
- Tier 2 `cross_wiki_diff`, `resolve_category`, `harvest_navbox`
  preview/discovery, `completeness_check`, etc. — these add new
  tools that catalog moves will compose. Ship on their own merits;
  the move catalog will reference them as they land.
- Type-hinted harvest annotation, sticky-rejection unblock,
  lossy-redirect detection, etc. — tool-correctness fixes adjacent
  to but distinct from strategy guidance.
- Benchmark / ratchet system items — separate axis (measurement
  infrastructure, not strategy guidance).

Items this plan **does not address** (and shouldn't):

- Adding more exemplars. The 6 existing exemplars are still useful as
  anchors. New exemplars are still authorable per `adding-exemplars.md`
  and will compose with the catalogs (a new exemplar can declare
  "this build used moves [X, Y, Z]; failure mode [F] was active").
  The point of the catalog approach is that we can go further with
  the existing 6 exemplars + ~25 moves than we could go with 25
  exemplars alone.
- Shape-name → strategy lookup (the existing SHAPE → PROPERTY
  table). 1.b reframes this content as moves; the lookup-table form
  goes away after 1.d.
