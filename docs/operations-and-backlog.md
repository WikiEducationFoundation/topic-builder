# Operations and backlog

Working doc covering two things:
1. How the server is deployed and administered day-to-day.
2. The running list of things we've considered but haven't built.

Keep this current as it diverges — if you do something operationally that's not written down here, add it. If you finish a backlog item, move it to a brief "done" section (or strike it).

---

## Administration

### Where things live

- **Host:** `172.232.161.125` (Linode), user `root`, SSH key `deploy_key` at the repo root.
- **Server URL:** `https://topic-builder.wikiedu.org/mcp` — fronted by nginx, proxied to the Python service at `127.0.0.1:8000`.
- **Landing page:** `https://topic-builder.wikiedu.org/` — served by nginx directly from `/opt/topic-builder/static/index.html`.
- **Service:** systemd unit `topic-builder.service`, running `/opt/topic-builder/venv/bin/python /opt/topic-builder/app/server.py`.

### Layout on the host

```
/opt/topic-builder/
├── app/                        # the MCP server code
│   ├── server.py
│   ├── db.py
│   ├── wikipedia_api.py
│   └── requirements.txt
├── venv/                       # Python virtualenv
├── data/
│   └── topics.db               # SQLite — topics, articles, sources, scores
├── exports/                    # CSVs written by export_csv; served via /exports/
├── logs/
│   ├── usage.jsonl             # one JSON line per interesting tool call
│   └── feedback.jsonl          # one JSON line per submit_feedback
└── static/
    └── index.html              # the landing page
```

### Deploying

Two scripts, both in `mcp_server/`:

- `deploy.sh` — full deploy. Syncs server code, rewrites systemd unit, rewrites nginx config, restarts the service. Takes ~10 seconds. Existing MCP sessions get dropped; clients reconnect on their next request.
- `deploy_landing.sh` — landing-page-only deploy. Just SCPs `landing.html` to `static/index.html`. No service restart.

Both read `.env` for `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY`.

### Monitoring

No dashboard; run-time visibility is via SSH + journalctl + a couple of useful one-liners:

```bash
# service status + resource baseline
ssh -i deploy_key root@$HOST "systemctl is-active topic-builder && uptime && free -m"

# recent tool calls (from the AI's perspective)
ssh -i deploy_key root@$HOST "tail -n 30 /opt/topic-builder/logs/usage.jsonl"

# recent feedback submissions
ssh -i deploy_key root@$HOST "tail -n 10 /opt/topic-builder/logs/feedback.jsonl"

# live service log
ssh -i deploy_key root@$HOST "journalctl -u topic-builder -f"

# what topics exist and their sizes
ssh -i deploy_key root@$HOST "/opt/topic-builder/venv/bin/python -c '
import sqlite3; c=sqlite3.connect(\"/opt/topic-builder/data/topics.db\")
[print(r) for r in c.execute(\"SELECT t.name, COUNT(a.title) FROM topics t LEFT JOIN articles a ON a.topic_id = t.id GROUP BY t.id ORDER BY t.id\")]'"

# full session summary (overview of all topics + recent usage log tail)
ssh -i deploy_key root@$HOST "/opt/topic-builder/venv/bin/python /opt/topic-builder/bin/status.py"

# drill into one topic (by id or name substring)
ssh -i deploy_key root@$HOST "/opt/topic-builder/venv/bin/python /opt/topic-builder/bin/status.py 6"
ssh -i deploy_key root@$HOST "/opt/topic-builder/venv/bin/python /opt/topic-builder/bin/status.py hispanic --recent 30"
```

`status.py` lives in `scripts/session_status.py` in the repo; `deploy.sh` copies it to `/opt/topic-builder/bin/status.py`. For ad-hoc use before a deploy, scp it to `/tmp/status.py` on the host and run from there — the script has the invocation in its docstring.

### Sessions / per-client state

- Each MCP connection has a `Mcp-Session-Id`. Claude reuses its session across tool calls; ChatGPT opens a fresh session for every call.
- The server's "current topic" is keyed per session. Stateless clients should pass `topic=<name>` on every call; that pattern is documented in the server instructions and in every tool's `topic` docstring.

### Log formats

`logs/usage.jsonl` — one JSON object per line:
```json
{"ts": "...", "topic": "...", "tool": "...", "articles_count": N, "params": {...}, "result": "..."}
```
Only some tools call `log_usage` (the "interesting" ones: gather, start, reset, export, feedback). Scoring/paging/listing calls aren't logged — keeps the log signal-rich.

`logs/feedback.jsonl` — one JSON object per line:
```json
{"ts": "...", "topic": "...", "client_id": "...", "rating": N, "summary": "...",
 "what_worked": "...", "what_didnt": "...", "missed_strategies": "...",
 "articles_count": N, "scored_count": N}
```

### Common admin tasks

- **Wipe all topics and exports** (destructive, use only on clearly-dev data):
  ```bash
  ssh root@$HOST "rm /opt/topic-builder/data/topics.db /opt/topic-builder/exports/*.csv; systemctl restart topic-builder"
  ```
  On restart, `db.init_db()` recreates schema.
- **Delete a single topic via SQL:** `DELETE FROM topics WHERE name = '...'` — `articles` is cascaded.
- **Revoke an old export:** `rm /opt/topic-builder/exports/<filename>` — download link goes 404.

---

## Backlog

Roughly prioritized. Items live here until they ship or get explicitly dropped.

### Recently shipped

- **2026-04-22** — `find_wikiprojects(keywords)` discovery tool (`[plan 1.9]`). Prefix-search on the Wikipedia: namespace to enumerate WikiProjects matching given keywords. Hard-enwiki. Addresses the orchids "tried WikiProject Plants, too broad, skipped WikiProjects" failure — AI now has an enumeration primitive to discover "WikiProject Orchids" before giving up.
- **2026-04-22** — `remove_articles` batched DELETEs + clarified docstring (`[plan 1.7]`). Pre-flight: observed ~200-title cap is client-side truncation, not server. Server now batches deletes as `DELETE … WHERE title IN (…)` of up to 500 titles/query. Docstring redirects large removals (>200) to `remove_by_source` / `remove_by_pattern`.
- **2026-04-22** — `fetch_descriptions` auto-loop + higher defaults (`[plan 1.6]`). Default limit 500 → 2000; added `time_budget_s=60` parameter; tool auto-loops until the topic is fully described or budget exhausted. Response includes `batches_run` + `time_budget_exhausted` so callers know whether to re-invoke.
- **2026-04-22** — `get_articles` regex filters + `sources_all` intersection (`[plan 1.5+1.20]`). Added `title_regex`, `description_regex` (case-insensitive Python re), and `sources_all` (require ALL listed sources — intersection, vs the existing `source` which is any / OR). Filter now runs fully in Python so `total_matching` is accurate across all combinations. Invalid regex returns a structured error.
- **2026-04-22** — `preview_harvest_list_page` + `preview_category_pull` (`[plan 1.4]`). Dry-run siblings to harvest_list_page / get_category_articles. Return link/article count + new-vs-overlap + a sampled preview with descriptions without committing. Share logic via `_fetch_list_page_links` / `_walk_category_tree` helpers.
- **2026-04-22** — `preview_similar(seed_article, limit=50)` (`[plan 1.3]`). Read-only sibling to `search_similar`. Returns titles + descriptions + already-in-topic flags without committing. Delegates to `preview_search(morelike:<seed>)`.
- **2026-04-22** — `harvest_list_page(main_content_only=True)` (default) (`[plan 1.2]`). Parses `action=parse` HTML with a stdlib `html.parser`, drops navboxes / sidebars / infoboxes / reflists / hatnotes and everything past See-also/External-links/References headings. Reads link targets from `title="..."` (captures redlinks alongside blue links). Validated against 5 list-page shapes; SA orchids list drops 809 of 1,503 navbox links while the transclusion-heavy genera / outline pages gain hundreds of links that `prop=links` missed. Opt out with `main_content_only=False` for raw-link behavior.
- **2026-04-22** — observability backfill (`[plan 1.1]`). `log_usage` now fires on all 27 `@mcp.tool` entry points (previously 11 of 27); every entry carries `elapsed_ms`, `wikipedia_api_calls` (per-call, via ContextVar counter in `wikipedia_api.py`), `rate_limit_hits_this_call`, and `timed_out`. All logging tools gained an optional `note: str = ""` parameter — zero-ceremony way for the AI to attach a mid-flow observation to the log entry. Pre-flight confirmed existing rate-limit backoff is real (linear retry on 429 + Retry-After honoring), not just counter-only.
- **2026-04-21** — multi-wiki support. `start_topic` takes a `wiki`
  parameter (default `"en"`); the value is persisted on the topic row
  and threaded through every Wikipedia API call. Reconnaissance tools
  (`survey_categories`, `check_wikiproject`, `find_list_pages`) accept
  optional `wiki=` too, inheriting the active topic's wiki otherwise.
  `check_wikiproject` / `get_wikiproject_articles` warn on non-enwiki;
  `find_list_pages` hints when its English prefixes return nothing.
  Prompt updated with wiki-selection guidance during scoping.
  Motivated by 2026-04-21 dewiki dogfood (see prior flagged item).
- **2026-04-17** — benchmark harness scaffolding (`benchmarks/` directory + `scripts/benchmark.py`). First topic `hispanic-latino-stem-us` scope frozen; gold.csv + PetScan query + calls.jsonl pending user attachment in a later session. Purpose: regression-test tool/prompt changes against a vetted gold set with scripted call replay.
- **2026-04-17** — audit-driven quality tools: `auto_score_by_description` (with intersectional-axis warning), `preview_search`, per-query search provenance (`search:<query>` source labels) + `remove_by_source` prefix_match, `remove_by_pattern` match_description mode, `filter_articles` year-prefix meta-page drop. morelike:-is-dangerous + preview-before-commit instruction bullets.
- **2026-04-17** — session-start user guidance added to `server_instructions.md` (SET EXPECTATIONS bullet, right after scope confirmation). Tells users continue-prompts and transient errors are routine. Revisit after first feedback with it live.
- **2026-04-17** — CSV export: UTF-8 BOM, csv.writer + CRLF line endings, new second column with Wikidata short description. Fixes the mojibake-accents report and the review-friction feature request from dogfood feedback.
- **2026-04-17** — server instructions: PARAMETER NAMES bullet (topic-scoped vs recon tools), HANDLING TOOL ERRORS bullet (schema-not-loaded, approval denied, unexpected responses), tightened `check_wikiproject` docstring.
- **2026-04-17** — `scripts/session_status.py` + host-side deploy. Admin helper; invocation one-liners in the Monitoring section above.

### Planned — design docs exist

1. **Authentication** (`docs/auth-plan.md`). Wikipedia OAuth 2.0, paste-in-chat bearer token, per-user topic scoping. Prerequisite: register the consumer on meta.wikimedia.org (3–7 day approval).
2. **Impact Visualizer handoff** (`docs/impact-visualizer-handoff.md`). End a session with a pasteable handle that IV's import page fetches from TB. Replaces the current CSV-then-Rails-console flow. Prerequisite: agree on the JSON schema with the IV maintainer.

### Flagged for investigation

- **`preview_search` bypass in Native American scientists dogfood
  (2026-04-17 22:33).** The session ran a broad keyword search
  (`"Native American scientist researcher"` → 500 results, became 82%
  of the topic) and three `morelike:` seeds without using
  `preview_search` — exactly the calls the new PREVIEW BEFORE COMMIT
  bullet in `server_instructions.md` says to preview first. Two
  candidate causes:
  (a) Claude client tool-schema caching from before the Bundle 2
      deploy (the same deferred-schema issue we've seen — new tools
      don't propagate to existing sessions reliably),
  (b) the AI saw the new instruction but chose to skip the step,
      possibly because of its urgency / brevity framing.
  Worth checking: does a fresh Claude session after the deploy know
  about `preview_search` and actually invoke it? If not, we need
  either a forced refresh mechanism or a workaround in instructions.
- **Scoring + removal tool calls are invisible in `usage.jsonl`.**
  The same Native American scientists session scored 511 articles and
  removed ~519 in the middle of the flow, but neither action shows in
  the usage log because `set_scores`, `score_by_extract`,
  `auto_score_by_description`, `remove_articles`, `remove_by_pattern`,
  and `remove_by_source` don't call `log_usage`. Adding logging to
  these makes `scripts/session_status.py` far more useful — flow
  stage inference currently reports "3. gather" when the topic is
  actually at score/cleanup/export.
- **Session ended without SPOT CHECK / GAP CHECK / submit_feedback.**
  Same session. The AI exported and stopped. Worth reviewing whether
  the instructions are being read/followed on wrap-up.

### Tool ideas that came out of dogfooding

3. **Wikidata / SPARQL integration.** No current support. High value for topics where Wikidata properties are the natural organizing principle (e.g. "all female educational psychologists", "all Supreme Court cases involving education"). Shape: a `sparql_query(query)` tool or a set of higher-level helpers (`find_by_property`, `find_by_class`) that build queries for common cases. Risk: SPARQL is expressive but easy to get wrong; users will need the AI to draft queries and explain them.
4. **PetScan integration.** Compound category + template + Wikidata queries. Existing external service (`petscan.wmcloud.org`) — we'd be wrapping its HTTP API. Much of what Wikipedia users reach for in practice.
5. **`preview_category_pull(category, depth)`**. Returns counts of new-vs-overlap without committing. Would have caught the "Developmental psychologists mostly duplicates Educational psychologists" mistake from the ed-psych transcript.
6. **Lower the `survey_categories` size warning threshold.** 2000 articles is too high; 1479 (Cognition depth 1) slipped through and was clearly too broad. ~1000 probably right.

### Design questions that need real thought

7. **Scoring at scale.** `score_by_extract` caps at 50 per call, and 900+ articles can't be scored within a single conversation's tool budget. Three directions:
   - (a) Drop scoring from the default workflow; treat it as an optional "quality cut" step.
   - (b) Cheapen scoring radically — the AI returns a JSON blob of 500 titles+scores in one call, with the server only validating shape.
   - (c) Accept that pruning-first is the real workflow and scoring is a bonus.
   Leaning toward (a), but needs a conversation with actual users.

### Smaller nice-to-haves

8. **Admin digest.** Script that reads `feedback.jsonl` and emails a weekly summary. Nothing fancy; `jq` + `mail`.
9. **Feedback viewer UI.** Lightweight HTML page at `/admin/feedback` showing recent submissions. Requires auth (see item 1).
10. **Better rate-limit visibility.** `get_status` already returns `rate_limits`, but it's buried. Consider logging when we approach Wikipedia's rate limit.
11. **Orphan-topic cleanup.** After enough testing, there are unused stub topics in the DB. A `DELETE FROM topics WHERE ...` script with clear "keep these" criteria.
12. **Backup cadence.** Right now: nothing. Simple plan: nightly cron `sqlite3 topics.db .dump > /backups/$(date +%F).sql`, keep 30 days.

### Explicitly deferred / not doing

- **Team / sharing features.** Out of scope; every user gets their own scoped topics (once auth lands) and that's enough.
- **Role-based access control.** Same.
- **A general "admin" UI.** SSH + sqlite3 is fine until it isn't.
