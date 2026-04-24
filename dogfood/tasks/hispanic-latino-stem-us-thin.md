---
task_id: hispanic-latino-stem-us-thin
variant: thin
benchmark_slug: hispanic-latino-stem-us
run_topic_name: hispanic-latino-stem-us ratchet-2026-04-23-thin
---

# Benchmark run: Hispanic and Latino people in STEM in the United States

You're executing a competitive benchmark against the Topic Builder MCP server. Build the best topic you can for the scope below, then submit feedback about the experience. Your final corpus will be scored against a frozen audit.

**Mode:** deep consultative, completeness-seeking — not speed. An honest 0.6 coverage estimate is more useful than an inflated 0.9. No human operator will steer you mid-session; fabricate spot-check probes yourself when the workflow calls for them.

## Scope statement

> Wikipedia biographies of people of Hispanic and Latino heritage, working in STEM fields, with a meaningful affiliation to the United States.

That paragraph is the whole scope you're given. Flesh out the rubric from it yourself (the server's instructions require you to persist a three-tier centrality rubric via `set_topic_rubric` before gathering).

## Protocol

1. Call `start_topic(name="hispanic-latino-stem-us ratchet-2026-04-23-thin", wiki="en", fresh=False)`. Use the EXACT name — the scoring script looks up the topic by this string. There is a separate, frozen baseline topic with a related name that you must NOT overwrite.
2. Draft a three-tier CENTRAL / PERIPHERAL / OUT rubric from the scope statement above and persist it via `set_topic_rubric(rubric=...)`.
3. Run the standard Topic Builder pipeline (reconnaissance → gather → descriptions → review → cleanup). The server's own workflow guidance (loaded on session init) covers preview-before-commit, noise taxonomy, known sharp edges, and wrap-up discipline — follow it.
4. Do SPOT CHECK + GAP CHECK before wrap-up per the server instructions. No user is here to propose spot-check titles — fabricate ~15–25 niche candidates yourself.
5. Call `submit_feedback(...)` with an honest `coverage_estimate={"confidence": <0.0–1.0>, "rationale": "<one sentence>", "remaining_strategies": ["<existing tool shapes you didn't apply>", ...]}`. Do NOT call `export_csv` — the scoring script pulls the corpus directly from the server.
6. Reply with a short summary: final article count, coverage_estimate.confidence, any notable friction.
