# Exploratory calibration kickoff

Paste this whole document into a fresh Claude Code (or Codex)
session that has the topic-builder MCP registered. It dispenses a
benchmark topic via `fetch_task_brief()` round-robin, but overrides
the standard `<slug>-thin` brief with explicit calibration
instructions: try every move and tool at least once, report
per-move yield + noise + fit. The deliverable is the per-move
breakdown, not corpus precision/recall.

Sibling to the standard `Call fetch_task_brief(...), then follow
its instructions` kickoff. Distinct from the legacy fat-variant
prompts in this directory by purpose (calibration, not ratchet
measurement).

If we run enough of these to want them seeded as a `<slug>-exploratory`
task variant in `dogfood_tasks`, the brief body below moves into
per-slug `dogfood/tasks/<slug>-exploratory.md` files and the kickoff
collapses to `Call fetch_task_brief(task_id="<slug>-exploratory"),
then follow its instructions.`

---

## Paste from here ↓

You're running an exploratory CALIBRATION dogfood — not a product-
quality build. The deliverable is a per-move breakdown of yield,
noise, and fit across the strategy catalog. Corpus precision/recall
on this run does NOT get ratchet-scored; the value is the
calibration report.

## Setup

1. Call `fetch_task_brief()` to get a round-robin topic assignment.
   **Use the returned `run_topic_name_template` ONLY to extract the
   benchmark slug** — e.g., `apollo-11-thin {ts}` → slug =
   `apollo-11`. **IGNORE the rest of the returned brief content;
   follow THESE instructions instead.**
2. Construct your run topic name as
   `<slug>-exploratory <YYYYMMDDTHHMM>` using current minute-UTC
   (e.g., `apollo-11-exploratory 20260428T2130`). The `-exploratory`
   suffix keeps these calibration runs distinct from the regular
   `-thin` ratchet runs.
3. Authenticate using the standard pattern (check long-term memory
   for a saved `tb_<hex>` token first; sign in via
   https://topic-builder.wikiedu.org/oauth/login if needed).
4. `start_topic(name="<your constructed name>", wiki="en")`.
5. Set a rubric via `set_topic_rubric`. Make a real attempt, but
   don't over-invest — the rubric serves the build phase only;
   the calibration phase is what we care about.

## Posture

- Don't optimize for cost or recall. Try moves even when they look
  duplicative or obviously inapplicable. Confirming irrelevance on
  this shape IS the measurement.
- Use `preview_*` variants where available. When you commit
  articles, label them `source="exploratory:<move-name>"` so
  per-move contribution is visible in `list_sources`.
- Don't stop early on diminishing returns. Diminishing returns is
  itself a thing we're calibrating.
- Read your own-topic exemplar via `get_exemplar(slug=<slug>,
  topic=<your run topic>, allow_own=True)` — measurement integrity
  isn't at stake on a calibration run.

## Hard coverage requirements

These run even if you'd naturally skip them:

1. **Full seed-anchored sweep on the canonical article.** All seven
   steps: `get_article_content` → `get_article_categories` →
   `get_article_templates(filter="navbox")` →
   `get_article_templates(filter="wikiproject")` →
   `get_article_see_also` → `get_article_links` →
   `get_article_backlinks(limit=500, filter_redirects="nonredirects")`.
2. **Both new Cirrus operator probes.** `hastemplate-typed-probe`
   (pick the matching infobox; if no clean match, try the closest
   one and report). `articletopic-classifier-probe` (pick the
   matching ORES topic; combine with `morelike:` or `incategory:`
   per the move's guidance).
3. **`llm-fabricate-and-verify`** — one round of 30–50 fabricated
   candidate titles with pre-validation. Report yield.
4. **`audit_progress`** at least once mid-build. Compare its output
   to your own narrative and flag any disagreement.
5. **For each named move you SKIP**, populate
   `submit_feedback.strategy_execution.moves_skipped_reason` with
   the reason ("no canonical infobox for this shape," "topic has
   no parent program," etc.) — silent skipping defeats the point.

Beyond these, walk `strategy_moves.md` and exercise at least one
move from every section (Recon, Bulk gather, Reach, Similarity,
Cleanup, Audit). Note `intersection-via-source-overlap` requires
≥2 sources first.

## Phase 1 — build (normal posture)

Run a thin build of the topic at standard quality. Roughly 20–40
metered calls. End with `submit_feedback(phase=1, ...)` capturing
the build proper — rating, coverage band, what worked, what didn't,
the standard reflective fields.

This phase gives the calibration report a "what I would have done
normally" baseline to contrast against.

## Phase 2 — calibration sweep

Now go back through the move catalog and execute everything from
the "Hard coverage requirements" list above that you didn't already
exercise in phase 1. Use `source="exploratory:<move-name>"` on
every commit so per-move contribution stays auditable.

End with `submit_feedback(phase=2, ...)`. The phase-2 `summary`
field is THE deliverable — structure it as:

```
## Calibration report — <topic>

### High-leverage moves on this shape (kept)
- <move>: <N candidates>, ~<P>% on-topic, notable find: <example>
...

### Low-leverage moves on this shape (would skip in production)
- <move>: <N candidates>, ~<P>% on-topic, why low: <reason>
...

### Inapplicable / refused
- <move>: <reason>
...

### Friction observed
- <one-liner per surprise>

### Catalog refinements
- Moves whose expected yield/noise characterization was off
- Moves whose preconditions need refinement
- Moves missing from the catalog that I wanted
```

Populate the structured phase-2 fields too: `strategies_used`
(every move attempted, canonical names from `strategy_moves.md`),
`tool_friction` (one-liners), `missed_strategies` (moves wished
for). Skip `coverage_estimate` — corpus completeness isn't the
goal.

## Stop conditions

End the run when EITHER:
- You've executed every Hard coverage requirement AND at least one
  move from each `strategy_moves.md` section, OR
- You've hit ~80 metered tool calls (substantially higher than a
  thin run; that's expected).

Whichever comes first.
