# Wikipedia Topic Builder

## What this project is

An MCP server that helps an AI assistant identify every Wikipedia article belonging to an arbitrary subject, ending with a downloadable CSV ready for the Wiki Education [Impact Visualizer](https://github.com/WikiEducationFoundation/impact-visualizer). The AI drives the workflow; users steer it through conversation.

The server runs at `https://topic-builder.wikiedu.org/mcp` and exposes ~45 tools across start/reset, reconnaissance, gathering, scoring, cleanup, export, and feedback. Two MCP clients matter right now: **Claude** (stateful sessions) and **ChatGPT** (stateless — opens a new session per tool call).

## How we're evolving this system

Three user modes matter, and we optimize for depth:

1. **Quick autonomous** — an AI builds a topic end-to-end without user involvement. Used in dogfood sessions to surface tool gaps.
2. **Deep consultative** — a power user steers an AI through careful exploration, pushing for completeness. **This is the mode we optimize for** — serving it well makes mode 1 better too.
3. **Guided** (end goal) — a published Claude web skill on claude.ai that a teacher or researcher can use to build a topic and download a CSV, without needing to know about MCP.

Principles for changes:

- **Completeness, not corpus size.** The goal is finding articles that belong to a topic, not inflating the count. A topic with 800 on-topic articles is better than one with 1200 mostly-on-topic articles.
- **Measure improvements, don't just ship them.** The 5-topic benchmark ratchet (`docs/ratchet-plan.md`) is the proving ground. A tool change that doesn't pass the gate — precision + recall don't regress, ≥1 cost metric improves — doesn't land.
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
├── ratchet-plan.md    # current: how to use the benchmark ratchet
├── shipped.md         # log of items that landed
├── operations.md      # host layout, admin one-liners
├── build-workflow.md  # how the AI works through backlog items
└── backlog/           # open work — prioritized list + specific plans
    ├── README.md                  # open-items list
    ├── auth.md                    # deferred: Wikipedia OAuth
    └── impact-visualizer.md       # deferred: IV handoff

scripts/             # standalone helpers for benchmark scoring, dogfood
                     # monitoring, and host smoke tests. `legacy/` holds
                     # pre-MCP one-offs kept as shell-usable probes.

benchmarks/          # gold-standard topic audits + replay harness.
                     # 5 topics scaffolded 2026-04-23: apollo-11,
                     # crispr-gene-editing, african-american-stem,
                     # hispanic-latino-stem-us, orchids. Each has
                     # scope.md, rubric.txt, baseline.json, gold.csv
                     # (gitignored — names + judgments). See
                     # benchmarks/README.md for the workflow.
```

## Architecture at a glance

- The MCP server is a FastMCP app (`mcp.server.fastmcp`) speaking the streamable-HTTP transport.
- SQLite holds topics, articles, sources, and scores. Durable across restarts.
- A dict keyed by `id(ctx.session)` holds the session's "current topic" so a stateful client doesn't have to pass the topic on every call. Stateless clients (ChatGPT) pass `topic=<name>` on every call.
- nginx fronts the service: `/` serves `landing.html`, `/exports/*` serves generated CSVs, `/mcp` proxies to the Python service on `127.0.0.1:8000`.
- systemd unit `topic-builder.service` supervises the process.

See `docs/operations.md` for the host layout, log locations, and administration recipes.

## Deployment

Two scripts, both in `mcp_server/`:

- **`bash mcp_server/deploy.sh`** — full deploy. Syncs server code, rewrites systemd + nginx config, restarts the service. Drops in-flight MCP sessions; clients reconnect. ~10 seconds.
- **`bash mcp_server/deploy_landing.sh`** — landing-page-only deploy. Just SCPs the HTML. No service restart.

Both read `.env` for `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`. The deploy key is checked in at `deploy_key` (repo root).

Before a full deploy, sanity check: `python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"`.

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

- **Syntax:** `python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"`.
- **Tool schema check on the server:** copy the edited `server.py` to `/tmp/` on the host and run it through `mcp.list_tools()` to inspect what schemas the clients will see. See `docs/operations.md` for the one-liner.
- **Live dogfood.** Build a small topic end-to-end in Claude and ChatGPT after a deploy. The Seattle / educational psychology topics are useful known shapes.

## Pointers for future work

- `docs/ratchet-plan.md` — how to use the 5-benchmark ratchet for proving tool improvements; prioritized open shortlist.
- `docs/backlog/README.md` — open items list.
- `docs/backlog/auth.md` — deferred Wikipedia OAuth plan.
- `docs/backlog/impact-visualizer.md` — deferred IV integration plan.
- `docs/shipped.md` — log of items that landed.
- `docs/operations.md` — admin reference.

## Legacy pieces still in the tree

- **`scripts/legacy/*.py`** — pre-MCP local-workflow tools (`category_tree.py`, `wikiproject_articles.py`, etc.). Nothing in the current server depends on them. Useful as one-off probing tools when you want to run a query from a shell without going through an MCP client. Don't build new features on them.
