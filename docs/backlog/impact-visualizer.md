# Topic Builder → Impact Visualizer handoff

Spec doc + implementation-status tracker for the TB ↔ IV handoff
feature. The TB side shipped 2026-05-01; the IV side shipped
2026-05-08 (IV PR #55, plus a 6562-article climate-change end-to-end
dogfood the same day against wmcloud + wiki-ed prod). The v1 loop is
now end-to-end. What remains is forward-compat (atomic edits, schema
version coordination) and breadth (TB → IV user list, broadening
the IV-side admin gate).

Source for the IV-side status: `impact-visualizer/docs/topic-builder-handoff-status.md`.

## Implementation status

| Side | Component | Status | Notes |
| ---- | --------- | ------ | ----- |
| TB   | `iv_packages` table + helpers | ☑ shipped 2026-05-01 | `db.py` |
| TB   | `prepare_iv_handoff` MCP tool | ☑ shipped 2026-05-01 | preview, no DB write |
| TB   | `publish_topic` MCP tool | ☑ shipped 2026-05-01 | mints handle, frozen snapshot |
| TB   | `GET /packages/<handle>` endpoint | ☑ shipped 2026-05-01 | `iv_packages.py`, JSON shape locked |
| TB   | `packages.jsonl` audit log | ☑ shipped 2026-05-01 | publish + fetch events |
| TB   | nginx `/packages/` route | ☑ shipped 2026-05-01 | `deploy.sh` |
| TB   | `server_instructions.md` IV-handoff section | ☑ shipped 2026-05-01 | |
| TB   | landing.html + CLAUDE.md update | ☑ shipped 2026-05-01 | |
| IV   | `GET /imports/<handle>` preview page | ☑ shipped 2026-05-08 | IV PR #55 |
| IV   | `POST /imports/<handle>` import handler | ☑ shipped 2026-05-08 | IV PR #55; admin-only |
| IV   | `ArticleBagArticle.centrality` column | ☑ shipped 2026-05-08 | IV PR #55; nullable int |
| IV   | `Topic.tb_handle` column | ☑ shipped 2026-05-08 | IV PR #55 |
| Both | End-to-end dogfood run | ☑ shipped 2026-05-08 | 6562-article climate-change topic, wmcloud + wiki-ed prod |
| IV   | Schema-version bump coordination story | ☐ not started | needed before TB ships `schema_version=2` |
| IV   | Broaden import gate beyond admin-only | ☐ deferred | `TopicBuilderImportService` already accepts a `topic_editor` |
| TB   | TB → IV user list (parallel users CSV / package field) | ☐ deferred | IV's TB-topic UI hides Users panel; symmetric ingest straightforward once TB emits |
| Both | Atomic edits (`patch_iv_topic`) | ☐ deferred | post-v1; see § Forward-compat |

## Adjacent IV-side work that landed alongside

Not on the spec table but visible in the IV repo's status doc — useful
context if you're tracing why the climate-change end-to-end run
worked at 6562-article scale:

- Parallelized `GenerateArticleAnalyticsJob` (3 threads) + Wikimedia
  OAuth 2 bearer auth on Action + REST APIs + 429 retry jitter
  widened 0–0.5s → 0–3s (IV PR #56).
- Sequential chain: analytics → incremental timepoint build (IV PR #56).
- `TopicTimepointStatsService` N+1 fixes: eager-load
  `article_timepoint`, read `attributed_creator_id` directly,
  drop redundant `update_details_for_article`, memoize revision
  lookups, swap to `prop=contributors` for editor counts (IV branch
  `eager-load-article-timepoints`).
- `TopicsController#topic_article_analytics` nil-bag guard (Sentry
  IMPACT-VISUALIZER-1K) (IV branch `topic-article-analytics-nil-bag-fix`).

## Locked decisions

These were settled during the 2026-05-01 plan and are not up for
re-debate during implementation. Changing one of them is a separate
plan.

1. **Manual handoff via clickable link.** No cross-server auth between
   TB and IV. The MCP session ends with the AI showing the user a URL
   that opens IV; the user (already signed in to IV) clicks Import on
   the page that opens; IV server-side then fetches the JSON package
   from TB.
2. **Path-segment URL:**
   `https://impact-visualizer.wmcloud.org/imports/tbp_<handle>`. The
   AI gives the user only the URL — never asks them to copy/paste a
   bare handle.
3. **Two-step config flow on TB side.** `prepare_iv_handoff(...)` is a
   read-only preview that the AI shows to the user; `publish_topic(...)`
   commits and mints the handle, called only after user confirmation.
4. **`/packages/<handle>` payload is config + article titles inline.**
   No CSV-URL indirection. Centrality scores ride per-article as
   `{"title": ..., "centrality": int|null}`.
5. **Frozen at publish time.** publish_topic snapshots the article
   list + config into the package row. Re-publish mints a new handle.
   IV becomes source-of-truth post-import.
6. **Atomic post-import edits are out of scope for v1**, but reserved
   in shape (see § Forward-compat below) so v1 doesn't paint v2 into
   a corner.

## End-to-end user flow

1. User finishes curating the article list in a TB conversation.
2. AI offers the IV handoff (alongside, not instead of, `export_csv`).
3. AI elicits the genuinely-unintuitive config fields (`editor_label`,
   `start_date`, `end_date`) from the user; autofills `iv_name`,
   `iv_slug`, `wiki`, `timepoint_day_interval`; drafts
   `iv_description` from the rubric + scope discussion.
4. AI calls `prepare_iv_handoff(...)`. Pastes the preview into chat;
   user confirms or asks for edits.
5. AI calls `publish_topic(...)` with the same args. Returns
   `{handle, import_url, expires_at, article_count, user_instruction}`.
6. AI gives the user only `import_url` and `user_instruction`. User
   opens the URL.
7. IV (already authenticated; if not, redirected to login) renders a
   preview page: topic name, article count, first ~10 articles with
   centrality, dates, editor_label. Single button: **Import**.
8. User clicks Import. IV server-side fetches
   `https://topic-builder.wikiedu.org/packages/<handle>`, validates
   `schema_version == 1`, resolves `wiki_id` against its own wikis
   table, creates Topic + ArticleBag + ArticleBagArticles in a
   transaction (with `centrality` populated per row).
9. IV redirects the user to the new Topic show page.

## TB side — what shipped

### DB table `iv_packages`

```sql
CREATE TABLE IF NOT EXISTS iv_packages (
    handle TEXT PRIMARY KEY,                 -- 'tbp_' + 22-char url-safe
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,
    articles_json TEXT NOT NULL,             -- list of {title, centrality}
    source_topic TEXT NOT NULL,              -- denormalized canonical name
    publisher_user TEXT,                     -- OAuth username; NULL when anon
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,                        -- first /packages/<handle> hit
    expires_at TEXT NOT NULL,                -- created_at + 30 days
    schema_version INTEGER NOT NULL DEFAULT 1
);
```

Indexes: `idx_iv_packages_topic`, `idx_iv_packages_publisher`,
`idx_iv_packages_expires`.

### MCP tools

- `prepare_iv_handoff(iv_description, editor_label, start_date,
  end_date, iv_name=None, iv_slug=None, timepoint_day_interval=30,
  min_centrality=0, ...)` — preview, no DB write. Returns
  `{preview: {config, article_count, first_articles,
  centrality_distribution, would_be_handle_format, expiry_days,
  import_url_format}, validation: {errors, warnings}}`.
- `publish_topic(...)` — same args. Validates, snapshots, mints
  handle, writes the row, appends `publish` event to
  `packages.jsonl`, returns `{handle, import_url, expires_at,
  article_count, user_instruction}`.

Both tools are `mode='write'` on `_require_topic`. Under
`AUTH_ENFORCEMENT=writes` (current production posture), only the
topic owner (or public_edit-tier callers) can publish.

### HTTP endpoint `GET /packages/<handle>`

Lives in `mcp_server/iv_packages.py`. Public route — auth is handle
unguessability. Response shape (the contract IV consumes):

```json
{
  "handle": "tbp_a1b2c3...",
  "schema_version": 1,
  "config": {
    "name": "Educational Psychology",
    "slug": "educational-psychology",
    "description": "...",
    "editor_label": "students",
    "start_date": "2026-01-15",
    "end_date": "2026-05-30",
    "timepoint_day_interval": 30,
    "wiki": "en",
    "wiki_id": 1
  },
  "articles": [
    {"title": "Achievement gap", "centrality": 8},
    {"title": "Active learning", "centrality": null}
  ],
  "article_count": 187,
  "source_topic": "educational psychology",
  "created_at": "2026-05-01T20:14:00+00:00",
  "consumed_at": "2026-05-01T20:18:32+00:00"
}
```

404 protocol: unknown / expired / bad-prefix all return the same
`{"error": "not found"}` body. The reason rides on the JSONL log
line, not the response — no enumeration distinction. Sets
`consumed_at` on the first 200 fetch; subsequent fetches keep
returning the body but don't change `consumed_at`. The URL is
multi-use so IV can retry on transient failures.

### `wiki_id` advisory hint

TB carries an advisory `_IV_WIKI_ID` dict in `server.py`:
`{"en": 1, "de": 2, "fr": 3, "es": 4, "pt": 5, "zh": 6, "ja": 7,
"ru": 8, "it": 9, "nl": 10, "pl": 11, "ar": 12, "sv": 13}`. The
config carries both `wiki: "en"` (string, authoritative) and
`wiki_id: int | null` (TB's best guess). IV uses its own wikis table
to resolve; the TB hint is informational. Add languages to the dict
as new wikis come up.

### Audit log `${LOG_DIR}/packages.jsonl`

Two event shapes, both JSONL:

```json
{"event":"publish","handle":"tbp_...","topic":"...","publisher_user":"...","article_count":N,"ts":"..."}
{"event":"fetch","handle":"tbp_...","ip":"...","user_agent":"...","status":200|404,"consumed_first_time":true|false,"reason":"...","ts":"..."}
```

`reason` is set only on 404s (`bad_prefix`, `missing`, `expired`).
No rotation; tail it to monitor activity.

## IV side — what shipped

The spec below describes the contract IV implements; it shipped per
spec in IV PR #55 (2026-05-08). Kept here because the contract still
governs both sides — TB writes packages assuming this shape, IV reads
them assuming this shape.

### Routes

**`GET /imports/<handle>` — preview page.**

- Authenticated route. Unauthenticated users redirect to IV login
  with `return_to=/imports/<handle>`.
- Server-side fetches
  `https://topic-builder.wikiedu.org/packages/<handle>` (timeout 20s,
  retry once on 5xx).
- 404 → render error: "This Topic Builder handoff is unknown or has
  expired. Ask the AI to call `publish_topic` again to mint a fresh
  handle."
- 200 → render preview: topic name, article count, first ~10
  articles with centrality, dates, editor_label, wiki, source_topic,
  schema_version. Single button: **Import topic** (POSTs the same
  path with CSRF token, no other form fields).

**`POST /imports/<handle>` — import handler.**

- Auth-gated to admins (matches the current console-only posture).
  Future broadening to authenticated editors is a separate item.
- Re-fetch the package from TB (don't trust GET-side state).
- Hard-fail on `schema_version != 1` with a clear "update IV or
  re-publish from TB" error.
- Resolve `wiki_id` from IV's own `wikis` table by `language`
  matching `config.wiki`. Ignore TB's advisory hint. If IV has no
  row for that language → "This handoff is for `<lang>` Wikipedia;
  IV is not configured for that wiki. Contact an admin."
- Wrap creation in a DB transaction:
  1. Create `Topic` (name, slug, description, editor_label,
     start_date, end_date, timepoint_day_interval, wiki_id,
     display: false).
  2. Create the topic's `ArticleBag`.
  3. For each `{title, centrality}`: find_or_create `Article` by
     title + wiki, then create `ArticleBagArticle` linking the bag
     to the article with `centrality` populated.
- Success → redirect to the new Topic show page with a flash
  confirming N articles imported.
- Failure (slug collision, validation error) → actionable error
  page with a "back to handoff preview" link. No auto-retry.

### Article ingestion strategy

- Topics ≤ 500 articles: synchronous resolution inside the
  transaction.
- Topics > 500 articles: background job (Sidekiq or whatever IV
  uses). Create Topic + empty ArticleBag synchronously; return user
  to a "processing N articles" page that polls; job populates
  ArticleBagArticles row-by-row.

The 500-article cutoff is a tunable default — adjust based on IV's
Wikipedia-API latency budget. The TB package shape supports either
path.

### Model changes

- **`ArticleBagArticle.centrality`** — new nullable integer column,
  range 1..10. Migration:
  `add_column :article_bag_articles, :centrality, :integer`.
  Required day one even if IV doesn't expose centrality in the UI
  yet — TB is already emitting it, and re-imports must persist it
  cleanly. UI for the centrality threshold-slider filter is a
  separate IV roadmap item.
- **`Topic.tb_handle`** (recommended) — nullable string, records
  which TB handle created the topic. Useful for audit and for the
  future atomic-edits feature. Populate from `params[:handle]` in
  the import handler.

### Auth posture

Admin-only on the import endpoint for v1 (matches the current
console-only state). When IV adds editor auth (separate roadmap
item), the auth gate can broaden to "any authenticated editor."

### Schema version handling

```ruby
unless package["schema_version"] == 1
  return render_error(
    "This handoff was minted for an unknown schema version " \
    "(#{package['schema_version']}). Update Impact Visualizer or " \
    "ask Topic Builder to mint a fresh handle.")
end
```

This means TB bumping `schema_version` (to add new required fields)
is an explicitly-coordinated change: IV must update first, or TB
ships behind a feature flag.

### Error UX

The import page is the only place the user lands after the AI.
Errors here can't bounce back to the AI cleanly:

- Validation errors render with a "copy this error to your AI"
  textarea pre-filled with the error message + handle, plus a "Try
  a different slug?" or "Re-publish from TB?" suggestion.
- Network errors render with a "TB might be down — try again in a
  minute" message.

## Forward-compat (post-v1, deferred)

Documented so v1 doesn't paint v2 into corners. None of these are
built yet; they describe what *could* be built once a real signal
arrives.

### Atomic edits — `patch_iv_topic(...)` MCP tool

Future TB tool for pushing targeted edits to a live IV topic without
re-publishing the whole package:

```python
@mcp.tool()
def patch_iv_topic(
    iv_topic_slug: str,
    add: list[str] = None,
    remove: list[str] = None,
    centrality_updates: dict[str, int | None] = None,
    ...
) -> str:
    """Push add/remove/score-update edits to a live IV topic."""
```

Requires:
- A TB→IV admin API token (separate from user OAuth — server-to-
  server, operator-owned). New env var `IV_API_TOKEN`.
- IV-side `PATCH /api/v1/topics/<slug>/article_bag` accepting
  `{add, remove, centrality_updates}` with bearer-token auth.
- Linkage so TB knows which IV topic a TB topic maps to.

### What v1 reserves

- **`iv_packages.iv_topic_slug TEXT`** — set by IV calling back to
  TB on successful import (or set manually by an admin tool). Future
  ALTER TABLE.
- **`topics.iv_topic_slug TEXT`** — per-topic IV linkage so atomic
  edits don't have to look up the most-recent package row each
  time. Future ALTER TABLE.
- **Naming reserved**: `patch_iv_topic` is reserved for the
  atomic-edits tool; don't reuse the name.
- **Schema version bump path**: when atomic-edits ship, the package
  schema may grow new fields (e.g., the IV topic slug). That bumps
  `schema_version` to 2; TB+IV coordinate.

### Why atomic edits aren't v1

The current friction story is "admin runs rake tasks once per
topic." That's solved by publish-once-handoff. Atomic edits solve
"user wants to refine after IV has the topic" — no current bleeding
case. Re-publishing a fresh handle is a perfectly fine v1 fallback.

## Verification recipes

### Pre-deploy syntax (TB)

```
python3 -m py_compile mcp_server/server.py mcp_server/iv_packages.py mcp_server/db.py
```

### Live integration smoke (TB-only, post-deploy)

```
curl -i https://topic-builder.wikiedu.org/packages/tbp_does-not-exist
# expect 404, JSON body {"error": "not found"}
```

Then in a Claude session:
1. Build a small topic (10 articles, mixed centrality).
2. `prepare_iv_handoff(...)` — inspect preview.
3. `publish_topic(...)` — capture handle.
4. `curl https://topic-builder.wikiedu.org/packages/<handle> | jq .` —
   confirm article list, centrality, config block, schema_version=1.
5. Curl again — confirm `consumed_at` populated and unchanged on
   second fetch.
6. Tail `logs/packages.jsonl` — confirm one publish + two fetch
   events.

### End-to-end (after IV ships)

1. Repeat above to get a handle.
2. Open the import URL in a browser (signed in to IV as admin).
3. Confirm the preview page renders correctly.
4. Click Import. Confirm redirect to the new IV topic page.
5. Verify the IV topic has correct name/dates/editor_label/
   article_count and that ArticleBagArticles carry centrality.
6. Re-publish from TB; confirm a second handle works.

## Rough effort estimate (residual)

Original estimate: ~2 days IV-side + ~half day cross-system QA. Actuals
from the IV-side rollup: IV PR #55 covered the spec; IV PR #56 added
parallelism + OAuth + retry jitter to make 6000+-article topics finish
in a reasonable wall time; the 2026-05-08 climate-change run was the
cross-system QA.
