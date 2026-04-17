# Topic Builder → Impact Visualizer handoff

Deferred design doc. Captures the idea of ending a Topic Builder session with a ready-to-import Impact Visualizer topic package, identified by a short handle the user pastes into IV instead of downloading a CSV and running console commands.

## Why this is worth doing

Today's outcome of a TB session is a CSV the user downloads, then someone (currently Sage, via Rails console) runs IV rake tasks to create the topic, assign the article list, set dates, wire up the wiki, etc. That's a lot of friction between "I have a curated list" and "there's an Impact Visualizer topic users can look at."

Impact Visualizer has no web UI for topic creation. It's Rails Console + Rake. So this integration isn't duplicating an existing path — it's creating IV's first end-to-end topic-creation UX, via Topic Builder as the front door.

## End-to-end user flow

1. User finishes curating an article list in a TB conversation (existing flow).
2. AI offers to prepare an Impact Visualizer handoff. Asks the user for the IV-specific fields (see below).
3. AI calls a new `publish_topic(...)` tool. TB writes a package record, returns a handle like `tbp_a1b2c3…`.
4. AI shows the handle to the user with one-sentence instructions: "Go to impact-visualizer.wmcloud.org/new, paste this handle: `tbp_a1b2c3…`."
5. User opens IV's new-topic page, pastes handle, clicks Import.
6. IV calls back to `https://topic-builder.wikiedu.org/packages/tbp_a1b2c3…` (server-to-server, no auth beyond the handle being unguessable), receives a JSON payload with the config + article list, creates the Topic + ArticleBag + ArticleBagArticles, and redirects the user to the new topic view.

## What IV needs (from reading the model docs)

Required topic fields:

- `name` — title-cased topic name
- `slug` — URL-safe identifier
- `description` — topic and participant-group description
- `editor_label` — lowercase word for "the users whose activity is visualized" (e.g. "students", "editors", "participants")
- `start_date` — analysis window start
- `end_date` — analysis window end
- `timepoint_day_interval` — snapshot cadence
- `wiki_id` — which Wikipedia (probably enwiki for our cases)
- `display` — public flag; should stay false until data is ready

Plus an `ArticleBag` with the article list — IV has an `Article` model, an `ArticleBag`, and an `ArticleBagArticle` join table, so the ingestion shape is "one bag per topic, N articles per bag."

TB already has the article list. The new config fields are what the AI needs to elicit.

## Server-side shape (Topic Builder)

### New DB table

```sql
CREATE TABLE iv_packages (
    handle TEXT PRIMARY KEY,              -- "tbp_" + random; unguessable
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    config_json TEXT NOT NULL,            -- full IV config (name, slug, dates, wiki_id, editor_label, description)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    consumed_at TEXT,                     -- set when IV first fetches it
    expires_at TEXT                       -- e.g. 30 days
);
```

Topics themselves are unchanged — the package is a snapshot pointer; the article list is read live from the topic at fetch time (or frozen at publish time — see open questions).

### New MCP tool

```
publish_topic(
    iv_name: str,
    iv_slug: str | None,                  # default: slugify(iv_name)
    iv_description: str,
    editor_label: str,
    start_date: str,                      # ISO 8601
    end_date: str,
    timepoint_day_interval: int = 30,
    wiki_id: int = 1,                     # enwiki; look up later if needed
    min_score: int = 0,                   # what slice of the list to package
    topic: str | None = None,             # session topic
    ctx: Context = None,
) -> str
```

Returns JSON with `handle`, pasteable instructions, expiry, and a preview of the first few articles.

### New HTTP endpoint (server-to-server, no MCP)

```
GET /packages/<handle>
```

Returns:

```json
{
  "handle": "tbp_a1b2c3...",
  "config": { "name": "...", "slug": "...", ... },
  "articles": ["Article title 1", "Article title 2", ...],
  "source_topic": "educational psychology",
  "created_at": "2026-04-16T...",
  "article_count": 929
}
```

Records `consumed_at`. Returns 404 once expired. Returns 404 for unknown handles. No auth beyond handle unguessability — the handle is a capability.

## Changes needed in Impact Visualizer

This is the bigger lift and needs coordination with whoever owns IV:

1. **New `/new` (or similar) page.** Single input: paste handle. Submit hits backend.
2. **New controller action** that fetches `https://topic-builder.wikiedu.org/packages/<handle>`, validates the shape, creates Topic + ArticleBag + ArticleBagArticles in a transaction, redirects to the new topic.
3. **Auth.** Who is allowed to import? Options: admins only (matches current console-only posture), or authenticated editors (if IV adds editor auth). For first cut, admins only.
4. **Config validation.** The publish_topic tool may not perfectly match IV's validation (slug uniqueness, date ranges, wiki_id existence). IV should return a clear error the user can act on.
5. **Article title normalization.** IV resolves titles to its own Article records, which may involve the Wikipedia API. Either IV does this on import (slow but self-contained) or TB pre-resolves (fast import, but TB needs to understand IV's normalization rules).

## Open questions

- **Frozen snapshot vs. live pull.** When IV calls `/packages/<handle>`, should it get the article list *as it was at publish time* (frozen in the package record), or the *current* state of the TB topic (live — so edits after publish are visible)? Frozen is simpler and more predictable; live lets users keep iterating after publish. Probably frozen; if a user wants to refresh, re-publish.
- **Who figures out `wiki_id`?** TB knows the user built for Wikipedia but not *which* Wikipedia. Either ask in the publish flow (most users are enwiki; default to that) or resolve from a language hint.
- **Handle format.** Short+unguessable (`tbp_` + 12 bytes base32 = ~20 chars) for pastability. Single-use vs. multi-use — probably multi-use so IV can retry on network failure, but track `consumed_at` for first successful import.
- **Auth interaction.** Once TB has auth (see `docs/auth-plan.md`), `publish_topic` should record the publishing user. IV could then assert the authenticated user matches, or leave it to IV admins. Separate the two concerns: TB auth lands first; IV import auth is its own policy.
- **Config elicitation UX.** Asking for 7 fields at once is a lot. Probably chunk it: dates + editor_label together, description after, slug auto-derived with override. Document this in the server instructions so every AI handles it similarly.
- **Versioning.** If IV's schema changes (new required field), old packages fail to import. The package record should include a `schema_version` from day one.
- **Error reporting.** If IV rejects a package (bad slug, dates out of range), the user is at IV's UI, not the AI. Either surface a clean error page with "copy this error back to your AI," or make IV's validation lenient-with-editable-form.

## Out-of-band prerequisites

1. **Confirm with the IV owner** that accepting programmatic topic creation from Topic Builder is the right path. There are other shapes — e.g., TB could post directly to IV's API, or IV could be extended with its own topic-creation form that happens to accept a TB CSV URL.
2. **Get a Wikipedia OAuth / identity story** decided. If IV gets editor auth later, the handoff story simplifies (both apps know the user). For now, assume IV stays admin-only on the import side.
3. **Spec the JSON shape** and version it. The field list above is a first draft.

## What's already in place that helps

- Topics in TB are persisted and resumable — the package is a thin pointer over existing storage.
- `submit_feedback` established the pattern of auxiliary JSON-lines logging; a similar `logs/packages.jsonl` would capture publish events for auditing.
- SQLite migration pattern is trivial for adding `iv_packages`.
- The landing page already highlights the Impact Visualizer as the destination; this closes that loop.

## Rough effort estimate

Assuming the IV owner green-lights the API shape:

- TB side (schema, `publish_topic`, `/packages/<handle>` endpoint, docs): ~1 day.
- IV side (new-topic page, import controller, article ingestion, admin auth): ~1-2 days for someone who knows the IV codebase.
- Integration testing: ~half a day.

Total: 2-3 days once both sides are ready.

## Naming decision to make

- `publish_topic` (proposed) vs. `prepare_for_impact_visualizer` vs. `export_to_iv`. Shorter is better; `publish_topic` is close but ambiguous ("publish where?"). Leaning toward `prepare_iv_package` or just making the tool very clear about IV in its description.
