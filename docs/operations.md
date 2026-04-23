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

