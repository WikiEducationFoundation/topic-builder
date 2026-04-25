# Exemplars + reach pass: two-phase dogfood

Active design doc for three new MCP tools — `list_exemplars`,
`get_exemplar`, and `start_reach_pass` — and the dogfood-flow
restructure they enable. Targeted to ship as one bundle.

## Intent

Two coupled changes:

1. **Exemplar tool.** A new MCP tool returns annotated worked examples
   (tool-call sequence + numeric results + light narrative + lessons)
   for known benchmark topics. Server instructions encourage calling
   it right after rubric is set, before any gather call. This pulls
   concrete teaching out of `server_instructions.md` into an
   on-demand resource so instructions stay general (per the
   server-instructions-style memory).

2. **Two-phase dogfood runs.** A run becomes two phases in one
   session: thin build → submit_feedback → call `start_reach_pass` →
   continue with reach as the explicit goal. `start_reach_pass`
   returns the best prior run's tool-call sequence + (for benchmark
   topics) the topic's own exemplar that was withheld in phase 1.
   Replaces the current thin-vs-informed split.

Both tools are generally available; benchmark topics happen to be the
first source of fuel.

## Why

- **Reduces server-instructions bloat.** Concrete topic-shape teaching
  goes to the exemplar tool; instructions hold abstract principles only.
- **Doubles dogfood signal per session.** Thin baseline AND a
  reach-extension attempt in one run, instead of separate
  thin-only and informed-only sessions.
- **Phase 2 maps directly to the reach axis.** "Reach grows gold" is the
  point of the system per `CLAUDE.md`; phase 2 makes that the explicit
  optimization target rather than a happy side effect.
- **Phase-2 reflection feeds the flywheel.** With phase 1 still fresh,
  the AI is asked to diagnose what it missed and what guidance would
  have helped it not miss those things. Those reflections become
  inputs to reach-strategies updates, server-instruction sharpening,
  and new exemplars — making phase 1 strictly better over time.
  Phase 1 is what we optimize; phase 2 is what helps us optimize it.
- **Privacy-safe by design.** Neither tool ever exposes the gold
  article list. Only metrics + tool-call traces leak. Biographies in
  gold (Pulitzer winners, AA-STEM scientists, etc.) stay private
  regardless of phase. This is a hard invariant, not a soft default.

## New tools

### `list_exemplars(topic: str)` + `get_exemplar(slug: str, topic: str)`

Two tools, menu-then-detail, to keep context lean while letting the AI
read deeply on the exemplars it judges most relevant.

**`list_exemplars(topic)`** — required `topic` parameter (the current
topic). Returns a menu of available exemplars, **excluding** the one
matching `topic` if any. Each menu entry includes:

- Slug + title.
- Shape one-liner (e.g. "named historical event with peripheral
  program / agency reach").
- 2–3 sentence summary of approach + outcome.
- Headline numbers (final corpus size, audited reach, precision /
  recall, total api/tool calls).
- 2–3 "high-leverage move" teasers — enough signal to judge relevance
  without committing to the full case study.

**`get_exemplar(slug, topic)`** — both parameters required. Returns
the full case study for one exemplar:

- Tool-call sequence in execution order — tool name + key params +
  one-line "why this call mattered" narrative per call.
- Full numeric results.
- 3–6 lessons capturing what worked, what dead-ended, what the AI
  almost missed.
- Anti-patterns / known dead ends.

Refuses (returns withheld notice) when `slug == topic` matches a
benchmark topic — defense in depth on the gating the menu already
applies.

The expected flow: AI calls `list_exemplars` once, scans the menu,
calls `get_exemplar` on 1–2 most-relevant entries. The other 2–3
exemplars never enter context.

### `start_reach_pass(topic: str)`

- Required `topic` parameter.
- Returns:
  - **Best prior run's tool-call sequence** (annotated like an
    exemplar, but pulled from the actual best run on this topic by
    audited beyond-gold reach). Available for any topic with run
    history; absent when the pool is empty.
  - **The current topic's own exemplar** (if benchmark topic; the one
    that was withheld from `list_exemplars` / `get_exemplar` during
    phase 1). Returned in full — this one is maximum-relevance, not
    a candidate for menu/detail splitting.
  - **Reach-strategies excerpt** (always; see section below). Phase 2
    is by definition the moment when obvious strategies have been
    exhausted — these meta-tactics belong in every reach-pass response,
    not only the empty-pool case.
  - Numeric framing: best run's reach number (when present) + a note
    that phase 2's job is to exceed it, not replicate.
- Empty-pool case (novel topic with no run history): the
  reach-strategies excerpt becomes the main payload, framed
  explicitly — "no prior runs to learn from on this topic; lean on
  these meta-tactics, ask the user for niche examples, try
  cross-language comparison, run structured spot-check probes."

## Storage shape

### Exemplars

Mirror the dogfood task-brief pattern:

- Source of truth: `dogfood/exemplars/<slug>.md` markdown files, one
  per benchmark topic. Frontmatter holds topic shape + numeric
  summary; body is narrated tool-call sequence + lessons.
- Seeded into a `dogfood_exemplars` SQLite table by an analog of
  `scripts/seed_dogfood_tasks.py`. Tool reads from DB at call time.
- Five initial exemplars to author — one per benchmark topic
  (apollo-11, crispr-gene-editing, african-american-stem,
  hispanic-latino-stem-us, orchids). Distill from existing run
  history + audit notes, not invented.

### Best-run plumbing

- Compute on the fly when `start_reach_pass` is called: scan
  `benchmarks/<slug>/runs/*.json`, pick the one with the highest
  audited beyond-gold reach, return its tool-call sequence.
- No best-run pointer file. Self-correcting; no maintenance step
  when new runs land.
- If the scan becomes a perf issue, add an in-memory cache keyed by
  `(slug, mtime of newest run file)`. Defer until measurement
  warrants it.

## Reach-strategies doc

A new authored markdown file at `docs/reach-strategies.md` (or
similar) capturing meta-tactics for extending reach when the obvious
strategies have already been used. Distinct from per-topic exemplars
(which teach by example) and from `server_instructions.md` (which
holds principles, not tactical playbooks).

**Content shape.** A short menu of moves the AI can pick from when
"obvious strategies" feel exhausted:

- **Cross-language / cross-wiki diff.** Walk a non-English wiki for the
  same topic; pull articles that have an enwiki sitelink but aren't in
  the corpus yet, plus articles that exist only in the other-language
  wiki.
- **Ask the user.** When working interactively, request 3–5 niche
  examples the user expects to see. Each miss is a strategy lead, not
  just one article.
- **Structured spot-check probes.** Hypothesize ~50 candidate titles
  across ≥5 natural subdomains, batch-verify presence, classify
  misses (variant-name / hallucination / real gap), diagnose
  miss-classes into strategies.
- **Wikidata-property probes you didn't think of.** P138 (named after)
  for eponym chains; P171 (parent taxon) for taxonomy; P361 (part of)
  for parent-program shapes; P31 (instance of) for class-based reach.
  Always additive, never subtractive (per the additive-vs-subtractive
  principle).
- **Navbox on parent / sibling articles.** If you ran `harvest_navbox`
  on the topic article, try it on the parent program / parent taxon /
  framing institution.
- **`morelike:` with high-centrality seeds.** `preview_search` with
  `query="morelike:<seed>"` using a top-centrality article as the
  seed often surfaces analogous articles category trees miss.
- **Eponym / namesake chains.** When a person is core, search for
  articles named after them (institutions, awards, concepts).
- **Subject-specific list pages on other wikis.** `find_list_pages`
  / `intitle:` searches on other wikis can surface curated lists
  enwiki doesn't have.

**Storage.** Single markdown file. Server reads it at startup or on
call; `start_reach_pass` returns the body (or a pointer + excerpt
if the file grows). No DB seeding needed.

**Authoring.** Initial content distilled from accumulated audit
insights across the 5 benchmark runs. Updated over time as new
tactics surface. Lives in version control like other docs.

## Server-instructions update

Two small additions in `server_instructions.md`.

**1. Cue exemplars after rubric is set** (in the SCOPE → RUBRIC
section):

> After `set_topic_rubric` lands, call `list_exemplars(topic=<your
> topic>)`. Scan the menu, then call `get_exemplar(...)` on the 1–2
> entries whose shape most resembles your topic. Use them as a
> starting menu for which strategies to try first. Don't replicate;
> analogize.

**2. Cost-asymmetry principle** (new bullet, near the additive-vs-
subtractive principle or KNOWN SHARP EDGES):

> **Free vs. metered tools.** Tools that read our authored content
> (`list_exemplars`, `get_exemplar`, `get_topic_rubric`,
> `start_reach_pass`, `fetch_task_brief`) hit local storage only —
> they cost no Wikimedia API quota and barely any compute. Tools
> that hit Wikipedia or Wikidata (`harvest_*`, `get_category_*`,
> `preview_search`, `fetch_descriptions`, `wikidata_*`) cost real
> API budget. Spend liberally on the free preparatory tools: pull
> exemplars, re-read the rubric, consult reach-strategies. Five
> minutes of preparation routinely saves hours of metered API calls
> on a wrong-shape strategy.

No `start_reach_pass` cue in instructions — phase 2 lives in the
dogfood task brief, not the general workflow. (Reasoning: phase 2
is a dogfood / measurement convention; the tool is
general-availability but the *protocol* of "thin-then-reach" is
benchmark-specific. Mode-2 power users can call `start_reach_pass`
directly when useful, and it's discoverable from the tool list.)

**Production reach passes are user-driven, not budget-driven.** When
a power user is in the loop steering the AI, the AI should iterate
as long as the user judges progress is being made — no
AI-self-imposed call ceiling. The autonomous budget above only
applies in dogfood / benchmark runs where there's no user to call
"that's enough." `start_reach_pass` itself does not return a budget
framing; the dogfood brief layers it on for autonomous runs.

## Dogfood task-brief update

Thin briefs (the only briefs after this lands; the `<slug>-informed`
variants get retired) describe both phases up front:

- **Phase 1.** Build thinly, export, submit_feedback. **This is the
  measurement variant** — phase-1 metrics drive the ratchet
  scoreboard. Performance here is what we optimize for.
- **Phase 2.** Call `start_reach_pass(topic=<run topic>)`. Returns the
  best prior run's tactics, the current topic's own exemplar, and
  reach-strategies. Goal is two-fold:
  1. **Harvest gold.** Find articles even the best prior run missed.
     Phase-2 audited additions grow `gold.csv` over time.
  2. **Reflect on phase 1.** Specifically diagnose: which articles
     were missed in phase 1 and *why*, and what guidance would have
     helped phase-1-self find them. These reflections come back via
     a second `submit_feedback` call after phase 2 settles. They
     are inputs to reach-strategies / server-instructions / exemplar
     updates — the mechanism by which phase 1 improves.

  Phase-2 budget (autonomous-only — see below):
  - **Ceiling: ~30 metered tool calls** (Wikipedia/Wikidata-hitting).
    Free preparatory tools — `get_exemplar`, rubric re-reads,
    reach-strategies consults — don't count.
  - **Early exit**: stop when the last 10 metered calls have yielded
    fewer than 2 on-topic finds.
  - **Soft headroom to ~60** if mid-strategy with high expected
    yield on the next call.
  - Re-export and submit phase-2 feedback when settled.

`submit_feedback` itself stays unchanged — phase-2 instructions live
in the brief, not in the feedback response. Phase-2 reflection
content can ride on the existing `notes` / `tool_friction` fields
for now; if the reflection shape stabilizes, a structured field can
land later (deferred).

Phase 1 and phase 2 produce separate scoreboard rows (different
metric: precision/recall/cost on phase 1, audited reach on phase 2).
The ratchet gate runs on phase 1 only.

## Landing-page update

Add `list_exemplars`, `get_exemplar`, and `start_reach_pass` entries
to the appropriate sections (probably Reconnaissance for the first
two, Review for the third).

## Sequencing

Ship as a single coordinated bundle. Partial ship leaves the
dogfood flow inconsistent.

1. **Exemplar storage + seed script.** New table, markdown files,
   seed script. Stub one exemplar to validate the shape end-to-end
   before authoring all five.
2. **`list_exemplars` + `get_exemplar` MCP tools.** Implement both
   (menu + detail). Smoke against the stub.
3. **Author the five exemplars.** Distill from run history + audit
   notes. This is the bulk of the human work.
4. **Author `docs/reach-strategies.md`.** Initial menu of meta-tactics
   (cross-wiki, structured spot-check, Wikidata-property probes,
   navbox-on-parent, eponym chains, `morelike:` seeding, etc.).
5. **`start_reach_pass` MCP tool.** Implement with on-the-fly best-run
   scan; load reach-strategies into the response. Smoke against
   existing benchmark run JSONs and an empty-pool case.
6. **Server-instructions cue.** Single addition in scope/rubric
   section pointing at `list_exemplars` + `get_exemplar`, plus the
   cost-asymmetry principle bullet.
7. **Dogfood task-brief rewrite.** Five briefs updated to describe
   two-phase flow with explicit phase-2 reflection ask. Retire
   `<slug>-informed` variants from `dogfood_tasks` (drop, not
   archive — two-phase replaces them).
8. **Scoreboard separation.** Score script emits separate phase-1 and
   phase-2 rows; ratchet gate runs on phase 1 only.
9. **Landing-page entries.**
10. **Deploy + smoke.**
11. **End-to-end dogfood run** — single benchmark topic through both
    phases, validate the seam.

## Decisions locked during design

- **Retire `<slug>-informed` briefs.** Drop, not archive. Two-phase
  replaces what informed-variant was meant to measure.
- **Empty-pool `start_reach_pass`.** Returns reach-strategies as
  primary payload + explicit framing ("no prior runs; lean on
  meta-tactics, ask the user, try cross-wiki"). No silent fallback.
- **Separate scoreboards.** Phase 1 and phase 2 produce distinct
  scoreboard rows; ratchet gate runs on phase 1 only. Phase 2's
  metric is audited reach, not precision/recall.
- **Phase-2 stopping criterion is context-dependent.** Autonomous
  dogfood runs get a budget (~30 metered calls; early exit on <2
  on-topic finds in the last 10; soft headroom to ~60). Production
  reach passes are user-driven with no AI-self-imposed ceiling —
  the AI iterates as long as the user judges progress is being
  made. `start_reach_pass` does not return a budget; the dogfood
  brief layers it on.
- **Phase-2 reflection rides on existing `submit_feedback` fields.**
  Free-form in `notes` / `tool_friction` for now. Promote to a
  structured field (e.g. `phase_1_misses: [{pattern,
  guidance_that_would_help}]`) only if a stable shape emerges from
  several runs.
- **Exemplar authoring depth solves itself.** Author the first
  exemplar, see how the menu-card and case-study lengths feel; the
  remaining four follow whatever shape that one settles into.

## Out of scope / deferred

- **Production-topic exemplars.** Anyone could in principle accumulate
  exemplars for arbitrary topics over time; for now, exemplars =
  benchmark topics only. Revisit if production users want to seed
  their own.
- **Exemplar similarity ranking.** Returning exemplars in order of
  topic-shape similarity to the current topic would be a real lift,
  but premature without seeing how the AI uses the unranked set
  first.
- **Per-tool exemplar fragments.** A future variant could pull
  exemplar fragments by tool (e.g. "show me how `harvest_navbox`
  was used in the apollo-11 run"). Useful but not urgent.
- **Production reach-pass UX.** Mode-2 power users may want a
  formalized two-phase flow too; for now they can call
  `start_reach_pass` directly. If demand surfaces, document a
  recipe.

## Privacy invariant (load-bearing)

Gold article lists never appear in any tool response, in any phase,
ever. Both new tools surface only:
- Tool-call traces (the *moves* a prior run made)
- Numeric metrics (reach, precision, recall, costs)
- Authored narrative (lessons; non-revealing of specific gold titles)

This invariant is the reason gold gating is uniform across phases
and across production / dogfood. Don't relax it for "convenience" —
biographies in gold include real people whose inclusion judgments
shouldn't leak even to the AI building the list.
