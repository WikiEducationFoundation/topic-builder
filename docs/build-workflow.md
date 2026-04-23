# Build workflow

Operational companion to `docs/backlog/README.md`. Defines how Claude works through plan items with minimal friction during extended autonomous build sessions.

Reader's TL;DR: stage-level checkpoints with Sage (kickoff + recap); per-item autonomy in between (implement → verify → commit → update plan → deploy → smoke). Ship per `.X` item unless a Sequencing note groups them. Pause only on unexpected.

---

## Stage-level checkpoints — the only interactive moments

### Kickoff (start of stage)

Claude produces a short brief:
- Items in the stage in proposed build order.
- Any cross-item dependencies (from Sequencing notes).
- Open questions in the plan items that need Sage's input.
- Last-minute plan reshapes Claude would propose based on what's been learned.

Sage responds with answers + go-ahead (or reshape). Claude proceeds.

### Recap (end of stage)

Claude produces a short summary:
- What shipped (item numbers + commit hashes).
- Anything reshaped mid-stage and why.
- New learnings that should be noted for future stages.
- Memory updates made inline (recap-batch: lessons that only matter going forward).
- Proposed kickoff for the next stage (same turn — recap + next-kickoff combine).

Sage reacts; we discuss if needed; next stage kickoff or stop.

### Mid-stage pause triggers

Most work proceeds without interruption. Pause and ask Sage only when:
- A plan item's assumptions turn out materially wrong; the item needs genuine reshape, not just a small judgment call.
- A deploy breaks something unexpected and the cause isn't obvious.
- An open question surfaces that light-touch judgment can't resolve (e.g. a real architectural tradeoff with user-visible consequences).
- Something shipped reveals that a later-stage item now looks different.

Everything else: proceed, note decisions inline in the commit message and/or the plan.

---

## Per-item build loop

One pass per plan `.X` item. Ship per item unless its Sequencing note groups it with another.

1. **Read.** Open the plan item; read the source files it touches. Confirm assumptions still hold against current code.
2. **Implement.** Make the change. Small enough edits that a diff is reviewable.
3. **Pre-commit verify.**
   - Syntax check: `python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"` (and same for any other Python file touched).
   - Schema inspection (when the change affects tool signatures or docstrings): copy the edited `server.py` to `/tmp/` on the host and run it through `mcp.list_tools()` per `docs/operations.md`.
   - Nothing more unless the item needs it. No test suite exists; don't invent one.
4. **Commit.** One commit per item (or per self-contained sub-change within an item). Message style matches existing repo convention:
   - Imperative, sentence case, no trailing period, ~60–70 chars.
   - Body optional; use only if the item has a non-obvious rationale worth preserving.
   - Include the plan item number at the end in brackets: `[plan 1.2]`.
   - Example: `Add main_content_only flag to harvest_list_page [plan 1.2]`.
   - Do NOT add `Co-Authored-By` or other trailers — the repo doesn't use them.
5. **Update backlog + shipped log atomically.** Same commit updates:
   - `docs/backlog/README.md`: remove the shipped item (or change ☐ to ☑ briefly before pruning next cleanup).
   - `docs/shipped.md`: append a one-liner under the appropriate stage section.
6. **Deploy.** Run `bash mcp_server/deploy.sh`. The script itself self-checks: `set -euo pipefail` aborts on any failure; the last step runs `systemctl is-active` + `curl 127.0.0.1:8000/mcp/`. If those pass, the deploy is good.
7. **Smoke-test.** Call a read-only MCP tool relevant to the change — `get_status`, `list_topics`, or whatever verifies the change is live. If the change modified a specific tool's behavior, call that tool.
8. **Next item.**

---

## Autonomy contract

### Autonomous (do without asking)

- Edit anything under `mcp_server/`, `docs/`, `scripts/`, `benchmarks/`.
- Read any file in the repo or on the host (`/opt/topic-builder/**` is allowlisted).
- Run syntax checks, grep, git read-only subcommands, Python local scripts.
- Commit on `main` with the conventions above.
- `bash mcp_server/deploy.sh` — fully autonomous; this is the per-item deploy.
- Update the plan doc + backlog doc.
- SSH read-only to prod: `tail`, `cat`, `systemctl is-active`, `journalctl -u topic-builder`, log pulls via `scp`.
- Update memory files when a non-obvious rule or lesson emerges that a fresh context should know.

### Confirm first

- `git push` — pushing to the remote is irrevocable; Sage can push when ready.
- Creating PRs.
- Any scripted operation that makes bulk Wikimedia API calls outside normal tool use.
- Adding a new Python dependency (touches `requirements.txt`; deploy picks it up but worth flagging).
- Anything that touches `/opt/topic-builder/data/topics.db` directly via SQL (topic state is Sage's data).
- Touching `systemctl stop` / `restart` directly (deploy.sh handles this).

### Never without explicit ask

- `rm` / `rm -rf` on any prod path.
- Force-push, `git reset --hard`, `git push --force`, amending shipped commits.
- Modifying the deploy key or `.env`.
- Wiping topics, exports, or logs on the host.

---

## Commit message style (from `git log`)

Existing style from `git log --oneline`:

```
df28d7a Add multi-wiki support: bind topics to a Wikipedia language edition
cd1eae6 Update exemplar calls + add topic-strategies guide
bb20e0e Gitignore benchmark review-queue + cursor state
b522dec Benchmark harness: exemplar calls + runner fixes
f2c960e Add auto_score_by_description tool
abbeab8 Fine-grained search provenance and prefix-based source removal
457ea57 Add preview_search tool for safer broad/similarity queries
```

Pattern: imperative, sentence case, optional colon for namespacing, short and specific. For plan items, append `[plan N.M]`.

---

## Handling blockers mid-item

- **Small judgment call with no clear right answer.** Use light-touch heuristic (smallest primitive that solves the problem). Note the decision in the commit message body. Proceed.
- **Open question listed in the plan item.** If the plan's own guidance resolves it (e.g. "leaning True"), go with that. If not, pick conservatively and note in the commit.
- **Surprise: tool/code behaves differently than the item assumed.** Record the surprise in the plan item (as a "Shipped: <notes on divergence>" line), ship what actually makes sense, don't force-fit the obsolete plan text.
- **Surprise: change affects a later item's shape.** Update the later item in the plan doc in the same commit. Flag it in the next stage-kickoff brief for Sage's awareness.
- **Genuine blocker.** Pause and ask.

---

## Continuity if context clears mid-stage

A fresh Claude should be able to pick up cold. Checklist:

1. Read `docs/backlog/README.md`. Find the next ☐ item in the current stage.
2. Read that item's Shape / Why / Open questions fully.
3. Read the source files it touches — don't trust memory of what's there.
4. `git log --oneline -20` to see what's been committed. Cross-check against ☑ items.
5. `cat docs/shipped.md` to see what's landed recently.
6. Read `CLAUDE.md` for project-wide conventions.
7. Read memory files — especially `feedback_planning_rhythm.md` and `feedback_silent_routing_around.md`.
8. Proceed with the per-item loop.

---

## Stage 5 checkpoint

Stage 5 (Wikidata layer) gets an extra mid-stage checkpoint: pause after `wikidata_query` lands (5.1) and before proceeding to 5.2–5.6. Reason: 5.1 is the substrate for everything else in the stage; real usage of 5.1 may reveal that 5.2 / 5.3 / 5.6 want different shapes than currently planned. Better to reassess than build four tools on an untested substrate.

Other stages: no intra-stage checkpoints unless a specific item triggers a pause-and-ask.

---

## Deployment and rollback

- Deploy after every item. Services briefly drop and reconnect; active user sessions re-initialize. Sage has confirmed this is OK.
- Rollback if something breaks: `git revert <sha> && bash mcp_server/deploy.sh`. Topic state in SQLite is preserved across deploys; only the Python service code and systemd config get rewritten.
- Data recovery: `/opt/topic-builder/data/topics.db` is SQLite; take a backup before any schema-affecting change (items 5.6, 1.22 both introduce new tables/columns). Nightly backups not yet implemented (backlog item).

---

## Notes

- No automated test suite exists. Verification is syntax check + schema inspection + live smoke. If an item would genuinely benefit from a test, add a targeted one under `benchmarks/` — but don't invent testing for its own sake.
- For measured-impact verification of a tool change, use the 5-topic ratchet (`docs/ratchet-plan.md` + `scripts/benchmark_score.py`).
- If a stage kickoff reveals that items should be resequenced, say so there; don't silently reorder mid-stage.
