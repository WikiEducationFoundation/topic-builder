# Wikipedia Topic Builder

## What this project is

An MCP server that helps an AI assistant identify every Wikipedia article belonging to an arbitrary subject, ending with **either** a downloadable CSV **or** a clickable `publish_topic` handoff to the Wiki Education [Impact Visualizer](https://github.com/WikiEducationFoundation/impact-visualizer). The AI drives the workflow; users steer it through conversation.

The server runs at `https://topic-builder.wikiedu.org/mcp` and exposes ~66 tools across start/reset, reconnaissance (including a seed-anchored mining cluster: `get_article_content` / `get_article_links` / `get_article_backlinks` / `get_article_categories` / `get_article_templates` / `wikidata_get_entity`), gathering, scoring, cleanup, review (incl. `audit_progress` diagnostic and `topic_diff` for same-wiki two-topic comparison), export (CSV via `export_csv`, frozen-snapshot IV handoff via `prepare_iv_handoff` / `publish_topic` → `GET /packages/<handle>`), feedback, benchmark-run entry points, and an auth cluster (`authenticate` / `whoami` / `revoke_my_token` / `get_topic_visibility` / `set_topic_visibility`). Authentication is live in production with `AUTH_ENFORCEMENT=writes` (mutations require a Wikimedia identity; reads stay open). Phase 3 (gate reads) and Phase 4 (polish) remain on the backlog. See `docs/shipped.md` for the cutover record and `docs/backlog/README.md` for what's left. The AI-facing strategy substrate runs two complementary postures: a **case-based** layer via worked-example exemplars (`dogfood/exemplars/*.md`, served by `list_exemplars` / `get_exemplar` — close-cases-fail-on-novel) and a **decompositional** layer via shape-axis vocabulary + atomic-move catalog + failure-mode catalog (which works on novelty). The decompositional substrate is split across `mcp_server/server_instructions.md` (pipeline + principles + sharp edges), `mcp_server/shape_axes.md` (canonical 8-axis topic-shape vocabulary), `mcp_server/strategy_moves.md` (named atomic moves with preconditions / sequence / yield / rescue), and `mcp_server/failure_modes.md` (named anti-patterns with detection cues + rescues); all four are concatenated into the FastMCP `instructions=` string at startup. Two MCP clients matter right now: **Claude** (stateful sessions) and **ChatGPT** (stateless — opens a new session per tool call); Codex is the third and what we use for ratchet runs.

## How we're evolving this system

Three user modes matter, and we optimize for depth:

1. **Quick autonomous** — an AI builds a topic end-to-end without user involvement. Used in dogfood sessions to surface tool gaps.
2. **Deep consultative** — a power user steers an AI through careful exploration, pushing for completeness. **This is the mode we optimize for** — serving it well makes mode 1 better too.
3. **Guided** (end goal) — a published Claude web skill on claude.ai that a teacher or researcher can use to build a topic and download a CSV, without needing to know about MCP.

Principles for changes:

- **Completeness, not corpus size.** The goal is finding articles that belong to a topic, not inflating the count. A topic with 800 on-topic articles is better than one with 1200 mostly-on-topic articles.
- **Measure improvements, don't just ship them.** The benchmark ratchet (`docs/ratchet-plan.md`) is the proving ground. A tool change that doesn't pass the gate — precision + recall don't regress, ≥1 cost metric improves — doesn't land. The suite size isn't fixed; new shapes get added when worth measuring (`docs/adding-exemplars.md`).
- **Reach grows gold.** The aspirational axis isn't the gate — it's whether a run surfaces on-topic articles beyond current gold. Audited additions grow `gold.csv` and make future recall measurements honest.
- **Centrality is AI judgment, not tool computation.** The server persists rubrics and scores; the AI drafts the rubric with the user and assigns scores. Don't build "compute score X from signal Y" features — lean into the AI + rubric.
- **Evidence-based tool additions.** New tools emerge from observed failures in dogfood sessions (usually cross-validated across multiple sessions), not from speculation. Single-session signals go to the backlog's deferred tier.

This shapes the backlog: items with multi-session evidence and measurable benchmark impact get prioritized; speculative items wait.

## Repository layout

```
mcp_server/          # production code
├── server.py        # all MCP tools + per-session state
├── server_instructions.md  # the AI-facing workflow prompt (Markdown)
├── db.py            # SQLite persistence layer
├── wikipedia_api.py # thin wrapper around api.php with rate limiting
├── landing.html     # static landing page at topic-builder.wikiedu.org/
├── deploy.sh        # full deploy (syncs code, restarts systemd)
└── deploy_landing.sh# landing-only deploy (no service restart)

docs/                # plans and operational reference
├── ratchet-plan.md      # current: how to use the benchmark ratchet
├── shipped.md           # log of items that landed
├── operations.md        # host layout, admin one-liners
├── build-workflow.md    # how the AI works through backlog items
├── adding-exemplars.md  # recipe for new exemplars / dogfood tasks / benchmarks
└── backlog/             # open work — prioritized list + specific plans
    ├── README.md                  # open-items list
    ├── auth.md                    # deferred: Wikipedia OAuth
    └── impact-visualizer.md       # deferred: IV handoff

scripts/             # standalone helpers for benchmark scoring, dogfood
                     # monitoring, and host smoke tests. `legacy/` holds
                     # pre-MCP one-offs kept as shell-usable probes.

benchmarks/          # gold-standard topic audits + replay harness.
                     # 2026-04-23: apollo-11, crispr-gene-editing,
                     # african-american-stem, hispanic-latino-stem-us,
                     # orchids. 2026-04-25: climate-change (origin
                     # topic). Suite size isn't fixed; see
                     # docs/adding-exemplars.md. Each has scope.md,
                     # rubric.txt, baseline.json, gold.csv (gitignored
                     # — names + judgments). See benchmarks/README.md
                     # for the workflow.
```

## Architecture at a glance

- The MCP server is a FastMCP app (`mcp.server.fastmcp`) speaking the streamable-HTTP transport.
- SQLite holds topics, articles, sources, scores, sticky rejections, and dogfood task briefs. Durable across restarts.
- A dict keyed by `id(ctx.session)` holds the session's "current topic" so a stateful client doesn't have to pass the topic on every call. Stateless clients (ChatGPT) pass `topic=<name>` on every call.
- nginx fronts the service: `/` serves `landing.html`, `/exports/*` serves generated CSVs, `/mcp` proxies to the Python service on `127.0.0.1:8000`.
- A systemd template unit `topic-builder@.service` supervises the process; two worker instances run, `topic-builder@8000.service` and `topic-builder@8001.service` (restart/status both). Both load `EnvironmentFile=-/etc/topic-builder.env`.
- **Dogfood / benchmark task system**: `dogfood_tasks` DB table holds pre-seeded task briefs; `fetch_task_brief(task_id)` MCP tool renders `{ts}` placeholders and serves the brief to an AI. Source-of-truth markdown lives under `dogfood/tasks/`, seeded via `scripts/seed_dogfood_tasks.py`. Authoring + operator recipe in `dogfood/README.md` and `dogfood/tasks/README.md`.

See `docs/operations.md` for the host layout, log locations, and administration recipes.

## Deployment

Two scripts, both in `mcp_server/`:

- **`bash mcp_server/deploy.sh`** — full deploy. Syncs server code, rewrites systemd + nginx config, restarts the service. Drops in-flight MCP sessions; clients reconnect. ~10 seconds.
- **`bash mcp_server/deploy_landing.sh`** — landing-page-only deploy. Just SCPs the HTML. No service restart.

Both read `.env` for `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`. The deploy key is checked in at `deploy_key` (repo root).

Before a full deploy, sanity check: `python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"`.

### `/etc/topic-builder.env` is operator-owned — AI does not touch it

`/etc/topic-builder.env` (on the production host) holds OAuth client_id + client_secret, `AUTH_ENFORCEMENT`, and `MIGRATION_DEFAULT_OWNER`. **AI never reads or edits this file.** Any command that names it is denied via `.claude/settings.json` (`Bash(*topic-builder.env*)`), and that deny pattern catches SSH-wrapped invocations too.

To request changes: propose the line for the operator to add (the values themselves are non-secret instructions like `AUTH_ENFORCEMENT=writes`). The operator edits the file and restarts the service. AI verifies the running process picked up the change via runtime introspection — `/proc/<pid>/environ` (loadable through `bash scripts/smoke.sh`), or observable side effects (HTTP responses, DB state, behavior of auth-gated tools).

This rule exists because the file's contents flow into transcripts when read — and a transcript is durable, indexable, and not under operator control. Verification via runtime state is just as reliable and doesn't expose secrets.

## How to add a new tool

Tools follow a consistent shape so stateless clients keep working and usage is logged correctly. Copy from an existing tool as the template (`get_category_articles` is a good one).

**Required patterns:**

1. **Parameters end with `ctx: Context = None`.** FastMCP auto-injects `ctx` and excludes it from the client-visible schema. Keep it as the last parameter.
2. **If the tool reads or writes topic state, it accepts `topic: str | None = None`.** Call `topic_id, err = _require_topic(ctx, topic)` and early-return `err` if set. This makes the tool work for both stateful sessions (topic comes from `_get_topic(ctx)`) and stateless clients (topic comes from the explicit argument).
3. **Log interesting calls.** Use `log_usage(ctx, "tool_name", {params}, "result summary")`. Reserve logging for gather / mutation / export-shaped tools; don't log paging or read-only queries.
4. **Return JSON as a string** (`json.dumps(..., indent=2, ensure_ascii=False)`). The AI reads it.
5. **Include an `undo` hint** if the tool adds articles under a source label. Pattern: `"note": f'To undo this pull, use: remove_by_source("{source_label}")'`.

**Document new behavior in BOTH places:**

- The tool's docstring — FastMCP publishes it in the schema.
- `mcp_server/server_instructions.md` — the AI-facing workflow prompt, loaded by `server.py` at startup and passed to FastMCP as `instructions=`. Edit the Markdown file directly; a deploy + restart picks it up.

Why both: **ChatGPT's MCP client caches tool schemas and doesn't reliably refresh them on server deploys.** If a new parameter lives only in the schema, ChatGPT may never see it. The server instructions are re-sent on every session init, so information there reliably reaches the AI regardless of client caching. This is load-bearing — don't skip the instructions update for non-obvious tool behavior.

**Also update `mcp_server/landing.html`.** The landing page at `https://topic-builder.wikiedu.org/` shows a human-readable tool surface (Reconnaissance / Gather / Review / Cleanup / Export sections). A new user-facing tool should get a one-line entry in the appropriate section so the page stays a reliable index of what's available. This step is easy to forget when the PR is server-side only — make it a reflex. `bash mcp_server/deploy_landing.sh` pushes just the HTML without restarting the service.

## Workflow principles

Runtime workflow decisions (scoping discipline, rubric requirement,
scope-edge probes, spot-check / gap-check wrap-up, feedback etiquette,
the immutable per-topic wiki binding, etc.) live in
`mcp_server/server_instructions.md` — that's what the AI reads at
session start, and it's the canonical source for these principles.

To change AI behaviour, edit `server_instructions.md` and redeploy —
changes don't take effect until the server restarts. Each principle
there is derived from specific dogfood observations; see the feedback
memories for the evidence trail.

## Testing and verification

The project has no automated test suite. Verification is via:

- **Syntax:** `python3 -m py_compile mcp_server/server.py` (the project's `.claude/settings.json` denies `python3 -c`; use `py_compile` or a throwaway script).
- **Tool schema check on the server:** write a smoke as `/tmp/check_<whatever>.py` that imports from `server` and prints what you want to inspect, then run it on the host via `bash scripts/smoke.sh /tmp/check_<whatever>.py`. The wrapper reads `.env` internally, scp's the script to `/tmp/` on the host, and runs it through `/opt/topic-builder/venv/bin/python`. Don't hand-roll `source .env && scp ... && ssh ...` — it triggers permission prompts the wrapper was built to avoid. See `docs/operations.md` for additional admin one-liners.
- **Reviewing a finished run:** `bash scripts/smoke.sh scripts/review_run.py -- <topic-id-or-substring>` — prints corpus state, tool-call tail, all `submit_feedback` entries (with confabulation flags + moves observed from log), and export status in one screen. Use after a session wraps before reaching for ad-hoc scripts. Sibling `scripts/session_status.py` is the broad cross-topic overview; `scripts/review_run.py` is the focused single-topic deep-dive. Both also installed at `/opt/topic-builder/bin/{status.py, review.py}` after deploy.
- **Scoring a benchmark run:** `python3 scripts/benchmark_score.py --task <slug>-thin` — runs *locally* (SSHes to the host itself); don't wrap it in `smoke.sh` or it'll fail importing local-only `redirect_utils`.
- **Live dogfood.** Build a small topic end-to-end in Claude and ChatGPT after a deploy. The Seattle / educational psychology topics are useful known shapes.

## Benchmark gold maintenance

Gold-set audits use a two-layer model: a per-topic keyword classifier
(`benchmarks/<slug>/audit.py`, gitignored — pairs names with judgments)
plus a shared ground-truth validator
(`benchmarks/audit_lib.py`, tracked — generic plumbing). Every
`audit.py`'s `main()` ends with `validate_gold_titles(GOLD_PATH,
wiki="en")` so existence facts trump pattern-derived verdicts on each
run. The full pattern + drop-in snippets live in `benchmarks/README.md`.

Running an audit:

```
python3 benchmarks/<slug>/audit.py
```

…is enough. It rewrites `gold.csv`, regenerates `audit_summary.md`,
and then validates redlinks/redirects against MediaWiki. ~10–30 sec
for small benchmarks, ~10 min for orchids' 18K rows on the validate
pass.

**Two safety nets** are load-bearing — verify both are present in any
`audit.py` you write or inherit:

1. **Preserve hand-classifications** when the keyword classifier
   returns `uncertain` but `gold.csv` has a non-uncertain prior. Set:
   `PRESERVE_FROM_FILE = {"in", "peripheral", "out", "redirect", "redlink"}`.
   Without this, a re-run silently flattens any verdict that doesn't
   have a matching rule. The 2026-04-26 apollo-11 incident is the
   motivating case.
2. **Validate against Wikipedia ground truth** via `validate_gold_titles`
   at the end of `main()`. Without this, the keyword classifier can
   label thousands of orchid-pattern-matching titles `in` even when
   the articles don't exist (the same 2026-04-26 incident wiped the
   ~10,763 redlink classifications on orchids gold; recovery required
   a full API sweep).

**Reach-audit + baseline-refresh flow** for ratcheting (this is what
you do after a thin run lands):

1. **Pull corpus from server** via a `/tmp/dump_<slug>_corpus.py`
   smoke (see `dogfood/sessions/2026-04-26/` for templates).
2. **Append reach to `gold.csv`** with `on_topic=pending_audit` and
   the run's name as `source_run`.
3. **Run `python3 benchmarks/<slug>/audit.py`** — classifier picks up
   the new rows; validate_gold_titles finalizes redlinks/redirects.
4. **Refresh `baseline.json`** if gold grew significantly: a fresh
   baseline corpus is the original bootstrap rows (rows where
   `source_run` is empty), and its precision/recall is what the gate
   compares against. Use a one-shot `/tmp/fill_<slug>_baseline.py`
   that reads the partitioned gold and computes baseline corpus ∩
   grown gold (climate-change has the worked example).
5. **Re-run `scripts/benchmark_score.py --task <slug>-thin`** to
   confirm the gate verdict against the grown gold.

**What NOT to do:**

- Never re-run `audit.py` on a benchmark whose `audit.py` lacks both
  safety nets. Check first; add them if missing (see
  `benchmarks/README.md`).
- Never edit `gold.csv` directly without expecting `audit.py` to
  preserve your edit only when its classifier returns `uncertain` for
  that row. If you want a verdict to stick across re-runs, add it as
  an explicit rule in `audit.py`.
- Don't trust scoreboard recall numbers when `gold_redlink_count`
  drops to 0 between runs of the same gold.csv — that signals
  redlink classifications got flattened and the denominator is
  bogus.

## Pointers for future work

- `docs/ratchet-plan.md` — how to use the 5-benchmark ratchet for proving tool improvements; prioritized open shortlist.
- `docs/backlog/README.md` — open items list.
- `docs/backlog/impact-visualizer.md` — deferred IV integration plan.
- `docs/shipped.md` — log of items that landed.
- `docs/operations.md` — admin reference.

## Legacy pieces still in the tree

- **`scripts/legacy/*.py`** — pre-MCP local-workflow tools (`category_tree.py`, `wikiproject_articles.py`, etc.). Nothing in the current server depends on them. Useful as one-off probing tools when you want to run a query from a shell without going through an MCP client. Don't build new features on them.
