# Legacy ratchet kickoff prompts

Historical artifacts from the **2026-04-23 ratchet cycle** — the
first round of benchmark runs against the 5-topic suite. Each file
is a fully self-contained markdown prompt (scope + rubric + reach
targets + topic-specific guardrails all inlined) designed to be
copy-pasted into a fresh Codex session.

**These are not the current ratchet path.** Prefer the
server-mediated task-brief system for all new runs:

```
Call fetch_task_brief(task_id="apollo-11-thin"), then follow its instructions.
```

See `../README.md` for the full kickoff recipe and `../tasks/README.md`
for the authoring format. The server-mediated path produces fresh
`{ts}`-stamped run-topic names automatically, scales to parallel
sessions without collisions, and keeps briefs general so instruction
changes don't require per-prompt edits.

## Why keep these

- **Historical record.** These prompts captured the operational
  wisdom from 8+ prior dogfood sessions in one place — useful for
  understanding how the fat-variant prompt shape evolved.
- **Fallback kickoff.** If the server-mediated path is unavailable
  (seed lost, tool broken), copy-pasting one of these still works.
- **Reference for the "informed" variant authoring.** When we seed
  `<slug>-informed.md` briefs, the inlined scope / reach targets /
  shape-specific guardrails here are a good source of what
  "informed" should contain beyond the thin brief.

## Files

- `ratchet-2026-04-23-all-in-one.md` — full 5-benchmark sequential
  build as a single session.
- `ratchet-2026-04-23-apollo-11.md`
- `ratchet-2026-04-23-crispr-gene-editing.md`
- `ratchet-2026-04-23-african-american-stem.md`
- `ratchet-2026-04-23-hispanic-latino-stem-us.md`
- `ratchet-2026-04-23-orchids.md`

A future consolidation step might migrate these into the DB as
`<slug>-fat` task briefs, at which point this directory can retire.
Open question in the backlog.
