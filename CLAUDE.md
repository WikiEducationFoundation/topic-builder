# Wikipedia Topic Builder

## What this project is

An MCP server that helps an AI assistant identify every Wikipedia article belonging to an arbitrary subject, ending with a downloadable CSV ready for the Wiki Education [Impact Visualizer](https://github.com/WikiEducationFoundation/impact-visualizer). The AI drives the workflow; users steer it through conversation.

The server runs at `https://topic-builder.wikiedu.org/mcp` and exposes ~27 tools (start/reset a topic, reconnaissance, gathering, scoring, cleanup, export, feedback). Two MCP clients matter right now: **Claude** (stateful sessions) and **ChatGPT** (stateless — opens a new session per tool call).

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
├── operations-and-backlog.md  # host layout, admin one-liners, backlog
├── auth-plan.md               # deferred: Wikipedia OAuth + paste-in-chat token
├── impact-visualizer-handoff.md # deferred: handle → IV import
└── development-narrative.md   # historical context

scripts/             # standalone helper scripts.
                     # session_status.py and benchmark.py are current. The
                     # older *.py files here are pre-MCP, kept for ad-hoc
                     # use. New primary path is the MCP tools, not these
                     # scripts.

benchmarks/          # gold-standard topic audits + replay harness for
                     # regression-testing tool/prompt changes. One
                     # subdirectory per benchmark topic with frozen
                     # scope.md, gold.csv, calls.jsonl. See benchmarks/README.md.

topics/              # legacy CSV outputs from the script-based workflow.
                     # Current exports live at /opt/topic-builder/exports/
                     # on the server, served via /exports/<filename>.
```

## Architecture at a glance

- The MCP server is a FastMCP app (`mcp.server.fastmcp`) speaking the streamable-HTTP transport.
- SQLite holds topics, articles, sources, and scores. Durable across restarts.
- A dict keyed by `id(ctx.session)` holds the session's "current topic" so a stateful client doesn't have to pass the topic on every call. Stateless clients (ChatGPT) pass `topic=<name>` on every call.
- nginx fronts the service: `/` serves `landing.html`, `/exports/*` serves generated CSVs, `/mcp` proxies to the Python service on `127.0.0.1:8000`.
- systemd unit `topic-builder.service` supervises the process.

See `docs/operations-and-backlog.md` for the host layout, log locations, and administration recipes.

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

## Workflow principles the server enforces

`server_instructions.md` is where we encode workflow decisions for the AI. Current principles, each derived from specific dogfood observations (see feedback memories):

- **Scoping is iterative dialogue, not a one-shot clarification.** The AI confirms scope with the user in plain language *before* calling any gather tool. Don't accept a quick-pick answer and immediately start pulling categories.
- **Don't ask for a target article count.** The tool's value is helping the user *discover* the natural size of a topic given their scope; a target makes the AI fit the result to an arbitrary number.
- **Probe scope edges explicitly.** Biographies, `List of…` / `Outline of…` pages, "X in popular culture", geographic breakdowns, stubs. Ask about these — they're where topics unexpectedly explode or shrink.
- **"Start fresh" means `start_topic(name, fresh=True)`.** Not bulk-remove-by-page.
- **Use `list_sources` then `remove_by_source(..., keep_if_other_sources=True)`** to prune noisy pulls, instead of iterating titles.
- **SPOT CHECK before wrap-up.** Before final export, ask the user to name 3–5 specific articles they'd expect to find — niche examples, not the famous ones. Confirm presence, investigate misses (search / categories / WikiProjects), add the genuinely-on-topic misses, and seed `browse_edges` from found examples to surface more neighbors.
- **GAP CHECK after SPOT CHECK.** Ask what other angles might have caught missed articles (Wikidata, SPARQL, PetScan, reading lists, awards, bibliographies, non-English wikis). Act on actionable suggestions; route the rest into `submit_feedback`'s `missed_strategies`.
- **Offer feedback at the end.** `submit_feedback` is how we learn. Ask first; never call unprompted.

When changing any of these, edit `mcp_server/server_instructions.md` and redeploy — behavior changes don't take effect until the server restarts.

## Testing and verification

The project has no automated test suite. Verification is via:

- **Syntax:** `python3 -c "import ast; ast.parse(open('mcp_server/server.py').read())"`.
- **Tool schema check on the server:** copy the edited `server.py` to `/tmp/` on the host and run it through `mcp.list_tools()` to inspect what schemas the clients will see. See `docs/operations-and-backlog.md` for the one-liner.
- **Live dogfood.** Build a small topic end-to-end in Claude and ChatGPT after a deploy. The Seattle / educational psychology topics are useful known shapes.

## Pointers for future work

- `docs/operations-and-backlog.md` — admin reference + running backlog of ideas.
- `docs/auth-plan.md` — deferred Wikipedia OAuth plan; paste-in-chat token flow.
- `docs/impact-visualizer-handoff.md` — deferred integration ending a session with a pasteable handle that IV imports directly.
- `docs/development-narrative.md` — historical context from the early (pre-MCP) phase.

## Legacy pieces still in the tree

- **`scripts/*.py`** — the original local-workflow tools (`category_tree.py`, `wikiproject_articles.py`, `petscan_query.py`, etc.). They work, but nothing in the current server depends on them. Useful as one-off probing tools when you want to run a query from a shell without going through an MCP client.
- **`topics/<slug>/articles.csv`** — old outputs from that workflow. Current CSV output lives on the server at `/opt/topic-builder/exports/`.
- **`skill.md`** — an early draft of the Claude skill we eventually want to publish. Not authoritative; the current server instructions (`instructions=` in `server.py`) are the real prompt.

These are kept around for reference; don't build new features on them.
