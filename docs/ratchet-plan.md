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
3. **Run fresh builds** of each ratchet-included benchmark topic,
   under NEW topic names (e.g. `apollo-11 ratchet-2026-04-25`) so the
   historical baseline topics stay intact as the ground truth. The
   ratchet doesn't have to run on every benchmark — see
   `docs/adding-exemplars.md` for the inclusion rubric.
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
- **≥1 cost metric** improved — any of {tool_call_count, total_api_calls}
  must be strictly lower than baseline

A run that matches baseline exactly on every axis fails the gate (no
improvement = no ratchet). That's intentional — we only promote when
something genuinely got better.

**Wall time is NOT in the gate.** Codex, Claude Code, and similar
operator-approval harnesses prompt for permission on first use of each
tool per session; the operator's click latency inflates wall-time
without reflecting tool efficiency. The 2026-04-23 CRISPR ratchet run
showed 1,783s wall vs. a 300s baseline — almost entirely permission-
prompt overhead, not a real 6× slowdown. api_calls + tool_calls are the
honest cost signals; wall-time is reported for visibility but doesn't
count toward the gate. A subsequent Codex session that has already
approved the full tool surface will have a cleaner wall-time number,
but any new or rarely-used tool re-prompts, so the signal is never
fully clean.

## "Reach" is the aspirational axis

Alongside the gate, track **reach** — audited on-topic articles the
run found that weren't in prior gold. Reach doesn't affect the
pass/fail gate, but growing reach IS the long-term goal (a fuller
gold = better recall measurements on future runs). When a scoreboard
flags reach additions, audit them, and if they pass, append to
`gold.csv`.

## Current state snapshot

`docs/shipped.md` is the authoritative log of what's landed; this doc
points at what to do next, not what's been done. `docs/backlog/README.md`
holds the open items with full evidence citations.

Benchmark scaffolding lives under `benchmarks/<slug>/` — six benchmarks
as of 2026-04-25 (`apollo-11`, `crispr-gene-editing`,
`african-american-stem`, `hispanic-latino-stem-us`, `orchids`,
`climate-change`), each with `scope.md`, `rubric.txt`, `baseline.json`,
audited `gold.csv`, `audit.py` (reproducible classifier), and
`audit_notes.md`. `scripts/bootstrap_benchmark.py` and
`scripts/benchmark_score.py` are the harness. Suite size isn't fixed —
see `docs/adding-exemplars.md` for the inclusion rubric. `.gitignore`
keeps names-paired-with-judgments out of the repo; scaffolding shape +
metrics + prose commentary IS tracked.

## Prioritized candidates

See `docs/backlog/README.md` for the full list — items are grouped
there by the same Tier 1 / 2 / 3 structure used below. This section
is just the "what I'd pick up next" opinion.

## What I'd work on next (opinion)

The strongest live signal is the **`topic_diff` at-pull-time
intersection** sub-item (still ◐ on the backlog). The Apollo 11
ChatGPT autonomous run on 2026-04-27 explicitly flagged its absence
as the #1 missed strategy — wanting WikiProject × Category
intersection without a full WikiProject ingest first ("would likely
improve triangulation without broad overpull"). The corpus-diff
sibling shipped same day, so half the surface is built; this adds
the at-pull-time variant. Bounded scope, recent multi-source signal,
ratchetable.

Adjacent small ship: **type-hinted annotation on `harvest_list_page`**
(Tier 1, multi-session evidence — AA-STEM and orchids flagged the
same shape from opposite directions, bio lists leaking non-bios vs
taxonomy lists leaking bios). Annotation rather than hard-filter
avoids the silent-drop trap.

Bigger Tier 2 lever, when a multi-day slot opens:
**`cross_wiki_diff`**. Most directly unlocks orchids / phenomenology /
Latino-STEM reach. Real 2–3 day build.

Single-session-evidence holds (waiting for a second signal to
promote): **`preview_wikidata_property`** titles-only output, after
climate-change 2026-04-26 hit the MCP token cap.

Whatever ships, run the 5-benchmark ratchet after.

## Kick-off-and-leave-for-a-while mode

Kickoff is one line per session. Task briefs live server-side in the
`dogfood_tasks` DB table; each fetch renders a fresh timestamped
run-topic name so sessions never collide. Practically:

1. Open a fresh terminal + MCP-capable client (Codex, Claude Code) in
   any empty directory. Topic Builder MCP must be registered (one-time
   setup — see `dogfood/README.md`).
2. Paste as the first message (swap the task_id per benchmark):
   ```
   Call fetch_task_brief(task_id="apollo-11-thin"), then follow its instructions.
   ```
   Task IDs currently seeded (all `thin` variant):
   `apollo-11-thin`, `crispr-gene-editing-thin`,
   `african-american-stem-thin`, `hispanic-latino-stem-us-thin`,
   `orchids-thin`.
3. Start 5 parallel sessions this way, one per benchmark.
4. 20–60 min later, each session ends with `submit_feedback`.
5. Score with `--task` mode (auto-resolves the most recent matching
   run):
   ```bash
   for t in apollo-11-thin crispr-gene-editing-thin \
            african-american-stem-thin hispanic-latino-stem-us-thin \
            orchids-thin; do
     python3 scripts/benchmark_score.py --task "$t"
   done
   ```

Review the 5 scoreboards. Precision / recall / reach / cost are
computed against the frozen `gold.csv` + `baseline.json` per
benchmark.

**Legacy kickoff path** (copy-paste-fat-prompt): the standalone
`dogfood/kickoffs/ratchet-2026-04-23-*.md` files are historical
artifacts from the first ratchet cycle. Keep for reference; prefer the
`fetch_task_brief` path for all new runs.
