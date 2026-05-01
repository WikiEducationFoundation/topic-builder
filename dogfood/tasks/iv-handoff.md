---
task_id: iv-handoff
variant: feature-dogfood
run_topic_name_template: tide-pools-iv-handoff {ts}
---

# Feature dogfood: Impact Visualizer handoff

You're testing a recently-shipped feature on the Topic Builder MCP
server: the Impact Visualizer handoff (`prepare_iv_handoff` +
`publish_topic` tools, with `GET /packages/<handle>` serving the
snapshot to Impact Visualizer server-side). The IV side is greenfield
— end-to-end import to Impact Visualizer is NOT possible yet. The
test is whether the TB-side elicitation flow, the preview's
legibility, and the URL-handoff ergonomics work in practice.

This is a **feature dogfood**, not a benchmark. There is no scoring
script. The goal is surfacing friction in: the conversation flow, the
tools' return shapes, and the AI-facing guidance in
`server_instructions.md`. Don't optimize for corpus quality; optimize
for thoroughly exercising the new tool surface and reporting honestly.

No human operator will steer you mid-session. Pretend a researcher
asked you to build a small topic on **tide pools** and prepare it for
Impact Visualizer for a fall course they're running.

## Protocol

1. `start_topic(name="tide-pools-iv-handoff {ts}", wiki="en", fresh=False)`.
   The name is pre-rendered with a fresh timestamp each fetch; use it
   verbatim. If you happen to be authenticated, this claims you as
   owner; that's fine.

2. Draft a brief rubric (centrality 1–10 with a short anchor at
   each tier) from the scope above and persist it via
   `set_topic_rubric(...)`. Keep it concise; a complex rubric isn't
   the point of this dogfood.

3. Build a SMALL corpus — target 30–60 articles. Use TWO gathering
   strategies, no more. A list-page harvest plus one complementary
   move (a search, a category pull, a navbox, your choice) is plenty.
   This is a feature exercise, not a coverage exercise — overbuilding
   wastes time.

4. After `fetch_descriptions`, score centrality on **at least 8–12
   articles** to exercise the centrality column in the IV package.
   Leave the rest NULL — unscored articles riding through the package
   as `centrality: null` is part of what's being tested.

5. (Optional, time-permitting.) Run `audit_progress` and a small
   spot-check probe round. Skip if you're already past 30+ articles
   with reasonable triangulation.

6. **Exercise the IV handoff flow** per the
   "Impact Visualizer handoff (publish_topic)" section of
   `server_instructions.md`. Specifically:

   - Pretend the user told you the editor cohort is **"students"**
     and the analysis window is **2026-09-01 to 2026-12-15**.
     (In real use the AI would ask; you're standing in for the user
     here so the dogfood is reproducible.)
   - Draft a 1–3 paragraph `iv_description` from the rubric and the
     scope statement. Don't fabricate facts; describe the topic and
     why it's framed this way.
   - Call `prepare_iv_handoff(...)`. Read the preview carefully:
     * Does the config block look right (name, slug, dates,
       editor_label)?
     * Does the centrality_distribution match what you'd expect from
       what you scored?
     * Are the first_articles a sensible representative sample?
   - Call `publish_topic(...)` with the same args. Capture
     `handle`, `import_url`, `expires_at`, and `user_instruction`.

7. Call `submit_feedback(phase=1, ...)` with the standard structured
   fields (`coverage_estimate`, `strategies_used`, `spot_check`,
   `sharp_edges_hit`, `tool_friction`, `prep_calls_made`, `runtime`).
   Plus, in `tool_friction` or as a free-text addendum, address each
   of these IV-handoff-specific questions:

   - **Two-step ceremony.** Did `prepare_iv_handoff` → user-confirm
     → `publish_topic` feel natural, or like excess friction? Could
     a one-shot tool replace it without losing safety?
   - **Preview legibility.** Was the `prepare_iv_handoff` return
     shape information-dense in the right way? Too much? Too little?
     What would you want added or removed?
   - **Instructions sharpness.** Did the
     `server_instructions.md` "Impact Visualizer handoff" section
     give you the guidance you needed? Where was it vague,
     redundant, or missing a case you hit?
   - **Autofill sanity.** Did `iv_name` (auto-derived from canonical
     name) and `iv_slug` (slugified) come out reasonable? Any
     surprises?
   - **Elicitation chunking.** Did the recommended two-turn
     conversation shape (1: who's editing + dates, 2: description +
     slug) fit the topic? If not, what did you want instead?
   - **Description-drafting cue.** The instructions say to draft
     `iv_description` from the rubric + scope discussion. Did that
     produce something usable, or did you need more guidance?

8. Reply with a short summary:
   - Corpus size + centrality distribution from the preview.
   - The published `import_url`.
   - 2–4 bullets of feedback on the IV handoff flow specifically —
     the most actionable friction you hit.

## What this dogfood is NOT

- Not a measurement run. No precision/recall scoring applies; don't
  overbuild for coverage.
- Not an end-to-end IV test. The published import URL won't lead to
  a working IV import page yet (greenfield on IV side). This dogfood
  ends at the URL.
- Not an exemplar source. Don't read or write benchmark exemplars
  for this run.
