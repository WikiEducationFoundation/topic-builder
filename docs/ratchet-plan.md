# Ratchet plan — the short version

Written 2026-04-23 to consolidate the benchmark + ratchet work into a
single reference. The open backlog lives in `docs/backlog/README.md`; shipped
items are logged in `docs/shipped.md`. This doc is the "pick this up
and know what to do" entry point.

## The one-loop workflow

Each improvement cycle:

1. **Pick one candidate** from the prioritized shortlist below.
2. **Implement + deploy** — match the precedent from Chunks 2–6: one
   small focused change, syntax-checked, smoke-tested, deployed via
   `bash mcp_server/deploy.sh`.
3. **Run fresh builds** of each of the 5 benchmark topics, under NEW
   topic names (e.g. `apollo-11 ratchet-2026-04-25`) so the historical
   baseline topics stay intact as the ground truth.
4. **Score each:**
   ```
   python3 scripts/benchmark_score.py <slug> "<run-topic>"
   ```
   Each run emits a `benchmarks/<slug>/runs/<timestamp>_<topic>.{md,json}`.
5. **Decide:**
   - **All 5 PASS gate** → promote. Update `baseline.json` with the new
     metrics. Grow `gold.csv` with audited reach additions.
   - **≥1 FAIL** → revert or tighten. The scoreboard tells you which
     axis regressed (precision / recall / cost) so you can debug.

## What the gate checks

Per `benchmark_score.py`:

- **Precision** vs. audited gold doesn't regress (within 0.001 tolerance)
- **Recall** vs. audited gold doesn't regress (same tolerance)
- **≥1 cost metric** improved — any of {tool_call_count, total_api_calls,
  wall_time_s} must be strictly lower than baseline

A run that matches baseline exactly on every axis fails the gate (no
improvement = no ratchet). That's intentional — we only promote when
something genuinely got better.

## "Reach" is the aspirational axis

Alongside the gate, track **reach** — audited on-topic articles the
run found that weren't in prior gold. Reach doesn't affect the
pass/fail gate, but growing reach IS the long-term goal (a fuller
gold = better recall measurements on future runs). When a scoreboard
flags reach additions, audit them, and if they pass, append to
`gold.csv`.

## Current state snapshot

**Shipped (server-side, all live):**
- Chunks 1–6 from the post-dogfood sprint (Oct 23): `intitle:OR`
  silent-empty fix, `find_list_pages` widen + disambiguation filter,
  `harvest_list_page` caption-as-title fix, `wikidata_entities_by_property`
  sitelink_count + auto-trim, `wikidata_query` auto-truncate,
  `fetch_descriptions` REST fallback on enwiki + deadline-aware,
  `filter_articles` drops unresolved titles, triangulation warning at
  export, `harvest_navbox` primitive, `find_wikiprojects` /
  `check_wikiproject` harmonize, plus two hot-patches.
- `set_topic_rubric` / `get_topic_rubric` tools + server-instructions
  integration (the three-tier rubric is MANDATORY before gather).
- Shape → Wikidata property table in `server_instructions.md`.
- Main-article-as-list-page fallback pattern in instructions.

**Scaffolded (benchmark infrastructure):**
- 5 benchmark topics — `apollo-11`, `crispr-gene-editing`,
  `african-american-stem`, `hispanic-latino-stem-us`, `orchids` —
  each with `scope.md`, `rubric.txt`, `baseline.json`, audited
  `gold.csv`, `audit.py` (reproducible classifier), `audit_notes.md`
  (human commentary), `README.md`.
- `scripts/bootstrap_benchmark.py` — baseline.json + gold.csv dumper
  for new benchmarks.
- `scripts/benchmark_score.py` — the scoreboard.
- Gitignore keeps names-paired-with-judgments out of the repo; shape
  of scaffolding + metrics + prose commentary IS tracked.

**Documented:**
- `docs/backlog/README.md` — open items with full evidence citations.
- `docs/shipped.md` — log of what landed.

## Prioritized candidates

See `docs/backlog/README.md` for the full list — items are grouped
there by the same Tier 1 / 2 / 3 structure used below. This section
is just the "what I'd pick up next" opinion.

## What I'd work on next (opinion)

**Ship the Tier 1 bundle together.** The three items
(`fetch_article_leads`, `coverage_estimate` field on `submit_feedback`,
known-bug workarounds in `server_instructions.md`) are small,
independent, and each unambiguously good. The benchmarks re-run
after that gives us:
- Evidence on whether `fetch_article_leads` improves rubric adherence
  (expect: better precision on weak-triangulation topics like
  phenomenology-class and aa-stem marginal cases).
- A durable `coverage_estimate` signal to track over time.
- A small instruction-hygiene win.

That's a one- or two-sitting package. **Then run the 5-benchmark
ratchet against it** — the first real ratchet cycle with a
non-trivial expected gain.

After that, **Tier 2 `cross_wiki_diff`** is the biggest
single-change leverage — but it's also a real 2–3 day build. It most
directly unlocks orchids / phenomenology / Latino-STEM reach.

## Kick-off-and-leave-for-a-while mode

The current design needs one manual step per benchmark: you start a
fresh dogfood session (or an agent-driven build) for each of the 5
benchmark topics. The score script is then a ~5-second run per
benchmark. Practically:

1. Pick a build mode (autonomous via `dogfood/task.md`, or a fresh
   guided session).
2. Start 5 parallel sessions, one per benchmark topic. Each builds
   to a distinct new topic name so it doesn't clobber the baseline
   topic.
3. 20–60 min later, they submit_feedback and stop.
4. `for slug in apollo-11 crispr-gene-editing african-american-stem
   hispanic-latino-stem-us orchids; do
      python3 scripts/benchmark_score.py "$slug" "<run-topic-for-$slug>"
    done`
5. Review the 5 scoreboards.

A single orchestration script that does steps 2–4 in one command
would be the natural next build if this workflow starts getting run
regularly. For now, manual is fine.
