# Exemplars: getting our strategy wisdom actually used

Active design doc for a brief-driven two-phase dogfood flow with
structured phase-2 reflection (Ship 1) and a pair of exemplar
MCP tools — `list_exemplars` and `get_exemplar` — with five
authored exemplars (Ship 2). Sequenced as two ships because Ship 1
is independently useful and produces both evidence and content
that Ship 2 needs.

## Status / next actions

Active checklist:

- [x] **Revise this doc** to reflect the simplified design — done.
- [x] **Stub the orchids exemplar** at `dogfood/exemplars/orchids.md`
  — done.
- [x] **Pressure-test menu cards.** Done. Wrote three sibling cards
  (apollo-11, crispr-gene-editing, hispanic-latino-stem-us). A fresh
  agent matched all four test topics (Mariner program, Black women
  in U.S. computing, carnivorous plant species, quantum computing)
  to their expected exemplar at **high confidence**. Four schema
  refinements emerged from the agent's meta-comment and are folded
  into the Ship 2 spec below: scale → order-of-magnitude buckets,
  `layered: yes/no` → `layered_shape` sub-typed, new
  `recall_ceiling_driver` structured field, new required "Doesn't
  apply when" counter-examples section.
- [ ] **Review and plan implementation next steps** — Ship 1 ready
  to start.

## Privacy invariant (load-bearing)

Gold article lists never appear in any tool response, in any phase,
ever. Both new tools surface only:

- Tool-call traces (the *moves* a prior run made)
- Numeric metrics (reach, precision, recall, costs)
- Authored narrative (lessons; non-revealing of specific gold titles)
- Class-level descriptions of missed-and-found article shapes
  ("Brazilian orchidologists", not literal names)

This invariant is the reason gold gating is uniform across phases,
across production / dogfood, and across both new tools. Don't relax
it for "convenience" — biographies in gold include real people whose
inclusion judgments shouldn't leak even to the AI building the list.

## The problem

The biggest failing of current runs — production AND dogfood — is
that the strategic wisdom and tool surface we already have don't
get used. The AI dives in with a plausible-looking plan, exhausts
the obvious moves, and stops. Our principles aren't wrong; they
don't reach the AI at the moment of choice.

Concrete shapes this takes (cross-validated across recent dogfood
runs):

- AI doesn't browse the rubric framework or available probes before
  starting; gets to "stuck" before consulting authored guidance.
- AI ignores additive Wikidata-property probes (P138 / P171 / P361)
  on shapes where they'd be high-leverage first moves.
- AI under-uses `morelike:` and cross-wiki checks even when
  `server_instructions.md` mentions both.
- Phase-1 self-rated confidence sits at 0.7+ while actual recall
  lands 35–60% — the AI doesn't know what it doesn't know, because
  it hasn't seen what others did on similar shapes.

The plan: a brief-driven two-phase dogfood flow with structured
reflection, plus curated worked examples (exemplars) consulted via
a preparatory-phase posture that makes consulting them a step the
AI *checks off*, not a hint it routes around.

## Intent

Two ships:

- **Ship 1** — Brief restructure into two phases (thin build →
  reflect-and-extend) with structured reflection fields on
  `submit_feedback`, scoreboard separation, and a partial server-
  instructions update covering reach-extension meta-tactics + a
  degraded preparatory-phase checklist (rubric + strategy sketch).
  Lands in days. Validates the flywheel. Reflections from the
  first 5 thin runs become both evidence (whether worked-example
  guidance is what's missing) and content (drafts of the first
  exemplars).
- **Ship 2** — Two exemplar tools (`list_exemplars`,
  `get_exemplar`), five authored exemplars, the upgraded prep
  checklist with exemplar steps, and staleness discipline. Lands
  once Ship 1 has shown the reflection mechanism is paying off.

Ship 1 is genuinely independent — it's not a stripped Ship 2. The
two ships solve overlapping but distinct problems: Ship 1 surfaces
*where the AI got stuck and what it would have wanted*; Ship 2
*provides what it would have wanted*.

## Why

- **AI underuses authored wisdom.** Primary motivation. See "The
  problem" above.
- **Reduces server-instructions bloat.** Concrete topic-shape
  teaching goes to exemplars; instructions hold abstract principles
  and meta-tactics only.
- **Doubles dogfood signal per session.** Thin baseline + reach-
  extension attempt in one run instead of two separate sessions.
- **Phase-2 reflection feeds the flywheel.** With phase 1 still
  fresh, the AI is asked to diagnose what it missed and what
  guidance would have helped. Reflections become inputs to
  instruction sharpening + new exemplars — the mechanism by which
  phase 1 improves. Phase 1 is what we optimize; phase 2 is how we
  optimize it.
- **Calibrates self-confidence.** Today's confidence-vs-recall gap
  is 0.7+ confidence vs. 35–60% recall. Phase-2 reflection
  including a `phase_1_confidence_recalibration` field surfaces the
  delta directly so we can track whether interventions actually
  shrink it.

---

# Ship 1: brief + structured reflection

Lands first. No new tools; brief content + `submit_feedback` schema
+ a partial server-instructions update.

## Dogfood task-brief update

Thin briefs (the only briefs after this lands; `<slug>-informed`
variants get retired) describe both phases up front.

**Phase 1.** Build thinly, export, submit_feedback. Brief includes
the **degraded preparatory-phase checklist** (Ship-1 version):

> 1. [ ] Read your rubric in full. Confirm it captures the scope
>    edges your topic actually has (lists in/out, biographies
>    in/out, "in popular culture" in/out, etc.).
> 2. [ ] Sketch a 3–5-step strategy to the user (or to yourself
>    if autonomous). Name the *first* metered tool you'll call and
>    *why*.
> 3. [ ] Confirm scope + strategy with the user, if interactive.
>
> Skip preparation only if you've already done it earlier in this
> session. Don't skip individual sub-steps.

This is the measurement variant — phase-1 metrics drive the ratchet
scoreboard.

**Phase 2.** After phase-1 `submit_feedback` lands, brief instructs:

1. Look at your phase-1 corpus. Identify articles or *classes* of
   articles that you may have missed.
2. Extend reach. Use the reach-extension meta-tactics in
   `server_instructions.md` (cross-wiki, eponym chains, structured
   spot-check, Wikidata-property probes) that you didn't try in
   phase 1. The strategies are general — apply them to your
   specific topic.
3. Re-export.
4. Submit phase-2 `submit_feedback` with the **structured phase-1
   reflection** (see schema below).

Phase-2 budget (autonomous-only, first-cut numbers — flag for
tuning after several runs):

- **Ceiling: ~30 metered tool calls.**
- **Early exit**: stop when last 10 metered calls yielded fewer
  than 2 on-topic finds.
- **Soft headroom to ~60** if mid-strategy with high expected
  yield on the next call.

**Production reach passes are user-driven**, not budget-driven.
The autonomous budget applies only when no user is in the loop.

Phase 1 and phase 2 produce separate scoreboard rows (phase 1 =
precision/recall/cost; phase 2 = audited reach). Ratchet gate runs
on phase 1 only.

## Phase-2 reflection schema

Add to `submit_feedback` (structured from day 1):

- `phase: int` — 1 or 2; identifies the round.
- `phase_1_misses: list[dict]` *(phase 2 only)* — each entry:
  - `pattern: str` — e.g. "missed all eponymous taxonomy genera",
    "missed Spanish-language biographies".
  - `guidance_that_would_help: str` — what an instruction or
    exemplar could say to surface this class next time.
- `phase_1_confidence_recalibration: float | None` *(phase 2 only)*
  — delta between phase-1 self-rated confidence and retrospectively-
  true confidence after seeing phase-2 finds. Negative = phase-1
  was overconfident; near-zero = well-calibrated. Tracks whether
  interventions actually shrink the calibration gap.
- `prep_calls_made: list[str]` *(phase 1)* — which prep-checklist
  steps were completed (rubric re-read, strategy sketch, user
  confirmation). Retrospective accountability — closes the loop on
  whether the prep checklist actually got followed.
- `prep_calls_skipped: list[str]` *(phase 2)* — looking back, which
  prep steps would have helped that you didn't take?

Fields are optional/nullable. Phase-1 calls populate `prep_calls_made`;
phase-2 calls populate `phase_1_misses` +
`phase_1_confidence_recalibration` + `prep_calls_skipped`.

## Server-instructions update (Ship 1 portion)

Two additions in `server_instructions.md`:

**1. Cost-asymmetry principle** (new bullet near KNOWN SHARP EDGES):

> **Free vs. metered tools.** Tools that read authored content
> (`get_topic_rubric`, `fetch_task_brief`) hit local storage only —
> no Wikimedia API quota. Tools that hit Wikipedia or Wikidata
> (`harvest_*`, `get_category_*`, `preview_search`,
> `fetch_descriptions`, `wikidata_*`) cost real API budget. Spend
> liberally on the free preparatory tools.

(The list expands in Ship 2 when `list_exemplars` / `get_exemplar`
land.)

**2. Reach-extension meta-tactics delta** — fold into existing
sections only the *delta* not already covered. Specifically:

- Cross-wiki / cross-language sweeps as a reach move, not just a
  primary strategy.
- "Ask the user for 3–5 niche examples" framed as a reach probe,
  not just a scope tool.
- Eponym / namesake chains for person-centric topics.
- Structured spot-check probes (~50 candidates × ≥5 subdomains).

Existing content (SHAPE → PROPERTY table, KNOWN SHARP EDGES,
SOURCE-TRUST, intersectional-leads pointer) stays as-is — those
already cover the rest of the meta-tactic surface.

## Sequencing for Ship 1

1. **`submit_feedback` schema update.** Add the structured
   reflection fields. DB migration if needed.
2. **Server-instructions update.** Cost-asymmetry principle +
   reach-extension meta-tactic delta.
3. **Dogfood task-brief rewrite.** Five briefs updated to describe
   two-phase flow with degraded prep checklist + phase-2 reflection
   ask. Retire `<slug>-informed` variants from `dogfood_tasks`.
4. **Scoreboard separation.** Score script emits separate phase-1
   and phase-2 rows; ratchet gate runs on phase 1 only.
5. **Deploy + smoke.**
6. **End-to-end dogfood run** through both phases — single benchmark
   topic.
7. **Run all 5 thin variants** under the new flow. Reflections from
   these become Ship 2's evidence + content.

---

# Ship 2: exemplar tools + authored content

Lands after Ship 1 has produced reflections that confirm exemplar-
shaped guidance is what's missing. Tools, content, prep-checklist
upgrade, and staleness discipline.

## New tools

### `list_exemplars(topic: str)` + `get_exemplar(slug: str, topic: str, allow_own: bool = False)`

Two tools, menu-then-detail, to keep context lean.

**`list_exemplars(topic)`** — required `topic` parameter. Returns a
menu of available exemplars, **excluding** the one matching `topic`
if any. Each menu entry includes:

- Slug + title.
- **Shape axes block** — structured tags so the AI can filter by
  structured signal *as well as* prose:
  - `structural` — high-level kind (taxonomic / named-event /
    technical-discipline / demographic-intersection / etc.)
  - `scale` — order-of-magnitude bucket (`tens` / `hundreds` /
    `thousands` / `tens of thousands`). Crisp non-overlapping
    buckets, not fake-precise bands.
  - `layered_shape` — `single` / `concentric` / `core+periphery` /
    `taxonomy+cultural`. Replaces `layered: yes/no`, which
    flattened too much.
  - `non-Anglosphere depth` — `yes` / `moderate` / `low`.
  - `biography density` — `low` / `medium` / `high` / `very high`.
  - `canonical category coverage` — `high` / `medium` / `partial` /
    `low`.
  - `recall_ceiling_driver` — short phrase naming the single thing
    that caps recall (`substrate dispersal under parent canopy`,
    `parent-program stitching`, `shortdesc ambiguity`, `cross-wiki
    cultural gap`, etc.). This is what the high-leverage moves are
    organized around; surfacing it as a structured field makes
    matching faster.
- **"Doesn't apply when" section** — required. Explicit
  counter-examples calibrating where this exemplar should NOT be
  picked. 1–3 short clauses.
- Shape one-liner.
- 2–3 sentence summary of approach + outcome.
- Headline numbers (final corpus size, audited reach, precision /
  recall, total api/tool calls).
- 2–3 "high-leverage move" teasers — enough signal to judge
  relevance without the full case study.

Menu cards omit literal call params (tool name + decision narrative
only) — see anti-replication framing below.

**Off-shape framing.** When no exemplar's shape axes match the
caller's topic axes within a similarity threshold, response includes
an explicit framing line: *"None of the available exemplars closely
match this topic's shape — they're from English-language
taxonomy / biographical / event-program shapes. Skim if curious;
don't force a match."* Surfacing the limitation rather than relying
on the AI to infer it.

**`get_exemplar(slug, topic, allow_own=False)`** — returns the full
case study for one exemplar:

- Tool-call sequence in execution order — tool name + key params
  + one-line "why this call mattered" narrative per call.
- Full numeric results.
- 3–6 lessons capturing what worked, what dead-ended, what the AI
  almost missed.
- Anti-patterns / known dead ends.
- Required closing section: "Extend, don't replicate" — frames the
  case study as a menu of moves with known costs and yields, not a
  recipe.

Refuses (returns withheld notice) when `slug == topic` matches a
benchmark topic UNLESS `allow_own=True`. Phase 2's brief instructs
the AI to set `allow_own=True` after submitting phase-1 feedback.

The gate is *measurement-integrity*, not privacy — exemplars don't
leak gold articles in any case. The gate prevents accidental self-
fetch from contaminating the thin baseline.

**Expected flow in phase 1** (Ship 2 onward): AI calls
`list_exemplars` once during the preparatory phase, scans the menu,
calls `get_exemplar` on 1–2 most-relevant entries. The other 2–3
exemplars never enter context.

**Phase 2** (Ship 2 onward): AI calls `get_exemplar(slug=<own>,
topic=<own>, allow_own=True)` to pull the case study for the topic
it just built. Compares to its own moves, identifies misses, extends
reach.

**Anti-replication framing.** The artifact is a tool sequence and
will get followed as a recipe unless we frame against it.
Mitigations:
- Menu cards omit literal params; full params live behind
  `get_exemplar`.
- Lessons sections lead with "why this approach" not "do this."
- Closing section explicitly says "extend, don't replicate."
- Server instructions and dogfood briefs both repeat the framing.

## Storage shape

Mirror the dogfood task-brief pattern:

- Source of truth: `dogfood/exemplars/<slug>.md` markdown files,
  one per benchmark topic. Frontmatter holds shape axes + numeric
  summary + `last_validated_against`. Body holds menu-card content
  + full case study, split by header.
- Seeded into a `dogfood_exemplars` SQLite table by an analog of
  `scripts/seed_dogfood_tasks.py`. Tool reads from DB at call time.
- Five initial exemplars to author — one per benchmark topic
  (apollo-11, crispr-gene-editing, african-american-stem,
  hispanic-latino-stem-us, orchids). Distill from existing run
  history + audit notes + Ship-1 reflections, not invented.

### Staleness discipline (concrete)

Each exemplar carries `last_validated_against`: a commit hash of
the repo state at last human review.

**Triggers** that mark an exemplar stale (flagged in
`list_exemplars` menu output):

- Any commit since `last_validated_against` that touches
  `server_instructions.md`.
- Any commit that changes the signature, removes, or renames a tool
  the exemplar references in its tool-call sequence (parsed from
  the case-study body).
- 90-day backstop: if neither of the above fires within 90 days,
  flag for periodic revalidation regardless.

Detection is a small helper script (`scripts/check_exemplar_staleness.py`)
that runs locally or in CI; it emits a list of stale exemplars +
reasons. `list_exemplars` calls it (or reads its cached output) and
surfaces stale-flags in menu entries: *"⚠ Validated 2026-04-25;
`server_instructions.md` has changed 4 times since — verify before
relying."*

## Server-instructions update (Ship 2 portion)

**Upgrade the preparatory-phase checklist** (introduced in Ship 1)
to include exemplar steps and the comparison move:

> **PREPARATORY PHASE.** After scope is plain-language confirmed
> and the rubric is set, complete this checklist before any
> Wikipedia-or-Wikidata-hitting tool call. All steps use free
> tools (no API quota). Spending a few minutes here routinely
> saves hours of wrong-shape strategy:
>
> 1. [ ] Call `list_exemplars(topic=<your topic>)`. Scan the menu.
> 2. [ ] Identify 1–2 menu entries whose **shape axes** most
>    resemble your topic. Call `get_exemplar(slug=..., topic=<your
>    topic>)` on each. Read the full case study.
> 3. [ ] **Compare** the exemplars' approach to your rubric. Note
>    where the exemplar's shape matches yours and where it
>    diverges. Don't just re-read the rubric — verify alignment.
> 4. [ ] Sketch a 3–5-step strategy to the user (or to yourself
>    if autonomous). Name the *first* metered tool you'll call and
>    *why*. Extend the exemplar's approach, don't replicate it.
>
> Skip preparation only if you've completed it earlier in this
> session. Don't skip individual sub-steps — prep-phase short-
> circuits correlate strongly with low recall and high cost.

**Extend the cost-asymmetry principle bullet** to include
`list_exemplars` and `get_exemplar` in the free-tools list.

## Sequencing for Ship 2

1. **Pressure-test menu cards** (from next-actions checklist) —
   write 3–4 sibling cards, validate fresh-reader can match. Lock
   schema only after this passes.
2. **Exemplar storage + seed script.** New table, markdown files
   convention, seed script.
3. **`list_exemplars` + `get_exemplar` MCP tools.** Implement, with
   off-shape framing + staleness flag surfacing. Smoke against the
   orchids stub.
4. **Author the remaining four exemplars.** Distill from run
   history + audit notes + Ship-1 reflections.
5. **Staleness detection script.** `scripts/check_exemplar_staleness.py`
   + integration into `list_exemplars` response.
6. **Server-instructions update.** Upgrade prep checklist, extend
   cost-asymmetry list.
7. **Dogfood task-brief rewrite (Ship 2).** Briefs replace degraded
   prep checklist with full version; phase-2 instructions reference
   `get_exemplar(allow_own=True)`.
8. **Landing-page entries** for `list_exemplars` and `get_exemplar`.
9. **Deploy + smoke.**
10. **End-to-end dogfood run** through both phases with exemplar
    consultation.

---

## Decisions locked during design

- **Two-ship sequencing.** Ship 1 is independently useful;
  reflections from Ship-1 runs become evidence and content for
  Ship 2.
- **Drop `start_reach_pass`.** Phase 2 is brief-driven; existing
  tools cover the unlock.
- **Drop separate `reach-strategies.md`.** Meta-tactics fold into
  `server_instructions.md` (where production runs benefit).
- **Retire `<slug>-informed` briefs.** Drop, not archive — two-phase
  replaces them.
- **Separate scoreboards.** Phase 1 = precision/recall/cost; phase 2
  = audited reach. Ratchet gate runs on phase 1 only.
- **Phase-2 stopping criterion is context-dependent.** Autonomous
  dogfood: budget. Production: user-driven, no AI ceiling.
- **Structured reflection from day 1.** `phase`, `phase_1_misses`,
  `phase_1_confidence_recalibration`, `prep_calls_made/skipped`
  added to `submit_feedback` in Ship 1.
- **Preparatory phase is a numbered checklist, not a principle.** AI
  follows phase-level structure well; sub-steps within a phase
  short-circuit. Explicit list resists short-circuit.
- **Prep-checklist comparison step is a *comparison*, not a re-read.**
  "Re-read your rubric" is a no-op; "verify alignment between rubric
  and exemplar approach" is an actual move.
- **`get_exemplar` gate is measurement-integrity, not privacy.**
  `allow_own=True` bypass; brief-documented for phase 2.
- **Menu cards include structured shape axes.** Prose alone is too
  lossy for the AI to judge relevance; structured tags + prose give
  both kinds of signal. Pressure-test confirmed (all four test
  topics matched at high confidence by a fresh agent).
- **Schema refinements from the pressure-test.** `scale` uses
  order-of-magnitude buckets, not bands. `layered_shape` replaces
  `layered: yes/no` with sub-types (`single` / `concentric` /
  `core+periphery` / `taxonomy+cultural`). `recall_ceiling_driver`
  is a required structured field naming what caps recall. A
  "Doesn't apply when" counter-examples section is required on
  every menu card.
- **`list_exemplars` surfaces off-shape limitations explicitly.**
  Don't rely on the AI to infer "nothing relevant"; say it.
- **Exemplar staleness has concrete triggers.** Server-instructions
  edits + signature changes to referenced tools + 90-day backstop.
  Detection via helper script; surfaced in menu output.

## Out of scope / deferred

- **Production-topic exemplars.** For now, exemplars = benchmark
  topics. Revisit if production users want to seed their own.
- **Exemplar similarity ranking.** Topic-shape-similarity ordering
  would be a real lift, but premature without seeing how the AI
  uses the unranked set first.
- **Per-tool exemplar fragments.** Future variant could pull
  fragments by tool used. Useful but not urgent.
- **Soft runtime gate on first metered call.** First gather-shaped
  call after `set_topic_rubric` could warn if `list_exemplars`
  hasn't been called this session. Defense in depth, deferred until
  we see prep-phase short-circuits even with the brief checklist +
  retrospective accountability.
- **Best-run-trace tool.** The curated exemplar IS the institutional
  best-run trace; no runtime scan needed. Revisit if exemplars feel
  too high-level and a literal recent-best-run lookup would add
  value.
