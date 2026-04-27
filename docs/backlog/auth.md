# Authentication + topic visibility plan

Detailed design for adding **identity + per-topic visibility** to the
Topic Builder MCP server. Refreshes the 2026-04 deferred design with
the three-tier visibility model (private / public-read / public-edit)
and a concrete rollout sequence.

## Goals

1. **Identify the user** via Wikimedia OAuth 2.0, so topics can be
   scoped per-person and feedback is attributable to a real Wikipedia
   editor.
2. **Default to private.** A user's topics are only visible to them
   unless they explicitly publish.
3. **Two publish tiers:** `public_read` (anyone can read; only the
   owner can edit) and `public_edit` (anyone authenticated can read
   AND edit).
4. **Keep anonymous abuse off our Wikipedia rate-limit bucket** once
   the URL is publicly shared.
5. **Wikipedia-native, no new credential.** Sign in with the account
   you already have for Wikipedia work.

Non-goals (deferred): paywalling; team / org sharing; making edits to
Wikipedia on the user's behalf; admin role beyond the operator
direct-DB ability we already have.

## Hard constraints

- **Token-paste-into-chat, not client-config.** The whole point of
  the landing page is that setup is one URL, no auth box. Pushing
  setup into Claude settings or the ChatGPT custom-connector form
  breaks the "one URL, no config" pitch and would have to be
  documented per-client. Token-in-chat keeps setup identical and
  pushes the auth step into the conversation where the AI can guide
  the user. (The MCP-native OAuth 2.1 flow exists in the spec and
  Claude's client supports it; ChatGPT's support has been
  inconsistent. Token-paste is the lowest-common-denominator path; an
  MCP-native flow can be added later as a parallel option.)
- **Read-public-without-auth must work.** The "publish" tiers are
  pointless if a recipient has to authenticate to look at the
  published topic. Anonymous access to `visibility != 'private'`
  topics is allowed for read-only tools.
- **Auth is required for any write.** Even on `public_edit` topics,
  writes require an authenticated identity so we can attribute
  changes. (Otherwise public_edit becomes an attractive vandalism
  surface against the project's Wikipedia rate-limit bucket.)

## Visibility model

Three values for `topics.visibility`:

| Value | Read access | Write access | Default? |
|---|---|---|---|
| `private` | owner only (auth required) | owner only (auth required) | yes |
| `public_read` | anyone (auth NOT required) | owner only (auth required) | no |
| `public_edit` | anyone (auth NOT required) | any authenticated user | no |

Two columns added to `topics`:

```sql
ALTER TABLE topics ADD COLUMN owner_username TEXT;        -- NULL until set
ALTER TABLE topics ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private';
CREATE INDEX idx_topics_owner ON topics(owner_username);
CREATE INDEX idx_topics_visibility ON topics(visibility);
```

`owner_username` is NULL only for legacy / unclaimed topics (see
migration plan). For new topics created via `start_topic`,
`owner_username = <authenticated caller>`.

### Permission rules in one place

```python
def can_read(topic_owner, topic_visibility, caller_username):
    if topic_visibility != 'private':
        return True
    return topic_owner is not None and caller_username == topic_owner

def can_write(topic_owner, topic_visibility, caller_username):
    if caller_username is None:
        return False                                # always need auth to write
    if topic_visibility == 'public_edit':
        return True
    return topic_owner is not None and caller_username == topic_owner
```

These get called from one helper, `_check_topic_access(topic_id,
caller, mode)`, which `_require_topic` extends.

## End-to-end user flows

### Flow A — first authenticated session

1. User adds the MCP connector
   (`https://topic-builder.wikiedu.org/mcp`, no auth) — unchanged.
2. User asks the AI to start building a topic.
3. AI calls `start_topic("Photography")`. Server returns:
   > `{"error": "Authentication required to create or edit topics.
   > Visit https://topic-builder.wikiedu.org/oauth/login to sign in
   > with your Wikipedia account; copy the token shown and paste it
   > to me."}`
4. User opens the URL in a new tab. The page shows:
   - "Sign in with Wikipedia" button → redirects to
     `meta.wikimedia.org/w/rest.php/oauth2/authorize`.
   - On approval, returns to `/oauth/callback?code=…`. Server
     exchanges code → access token → username, mints a Topic Builder
     bearer token, displays it.
5. User pastes: *"My token: tb_7f3a9c…"*
6. AI calls `authenticate(token=tb_…)` → returns
   `{"username": "Sage Ross", "expires_at": "2026-05-26"}`. Stateful
   sessions cache `(session_id → username)`. Stateless clients
   (ChatGPT) pass `auth_token=tb_…` on every subsequent call, same
   pattern as `topic=`.
7. AI retries `start_topic` and succeeds. The topic is created with
   `owner_username = "Sage Ross", visibility = 'private'`.

### Flow B — sharing a topic publicly

1. User: *"Make this topic readable by anyone with the link."*
2. AI calls `set_topic_visibility(visibility="public_read")`.
3. Server checks: caller is owner → OK. Updates column.
4. User shares the topic name with a colleague.

### Flow C — colleague reads a public topic

1. Colleague adds the MCP connector (no auth).
2. Colleague: *"Show me the corpus for the photography topic."*
3. AI calls `resume_topic("photography")` then `get_articles(...)`.
4. Server: topic visibility = `public_read`, mode = read → OK without
   auth. Tools return data.
5. Any write attempt → auth-required error, with the OAuth URL.

### Flow D — public-edit collaboration

1. Owner: *"Open this topic to collaborators — anyone with a
   Wikipedia account can edit."* AI sets visibility = `public_edit`.
2. Collaborator (authenticated) calls `add_articles(...)`. Server:
   visibility = `public_edit`, caller is authenticated → OK.
3. Server logs `(tool, topic, caller_username)` for every write so
   we have an audit trail.

### Flow E — anonymous browsing of a public topic (no MCP at all)

`/exports/<slug>.csv` already serves CSVs over HTTP. Restrict to
public topics: nginx-or-app-level check on the slug → look up
visibility → 404 if private. Out of scope for the MCP tool surface
but worth wiring at the same time so private topics don't leak via
the export URL.

## Server-side shape

### New HTTP endpoints

A small Starlette router mounted alongside the FastMCP ASGI app.
FastMCP exposes its inner app via `mcp.streamable_http_app()`; we
wrap that in a parent app that also serves `/oauth/*`. Single process,
single port — nginx already routes `/` (landing), `/exports/*`,
`/mcp`. Add:

- `GET /oauth/login` — landing with "Sign in with Wikipedia" button.
- `GET /oauth/start` — sets a CSRF state cookie, redirects to
  `https://meta.wikimedia.org/w/rest.php/oauth2/authorize`
  with our `client_id`, `response_type=code`, `redirect_uri`,
  `state=<csrf>`.
- `GET /oauth/callback?code=…&state=…` — verifies state cookie;
  POSTs `code` to `…/oauth2/access_token`; calls
  `…/oauth2/resource/profile` with the access token to get username;
  generates a Topic Builder bearer token; stores `(token_hash,
  username, expires_at)`; renders a "your token" page with copy
  button + revoke link.
- `POST /oauth/revoke` — invalidates a token. Linked from the token
  page so users can self-revoke.

### Wikimedia OAuth 2.0 specifics

- **Consumer registration:**
  https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose
- **Type:** Confidential (we hold the client secret server-side).
- **Grants:** the bare minimum that yields a username — typically
  the default "Basic rights" / `userinfo` profile grant. We do **not**
  request edit grants.
- **Callback URL:** `https://topic-builder.wikiedu.org/oauth/callback`.
- **Approval turnaround:** typically 3–7 days. Wiki Education already
  operates consumers (dashboard.wikiedu.org); a steward may approve
  faster if there's institutional continuity.
- **Endpoints** (current as of 2026):
  - Authorize: `https://meta.wikimedia.org/w/rest.php/oauth2/authorize`
  - Token: `https://meta.wikimedia.org/w/rest.php/oauth2/access_token`
  - Profile: `https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile`
- **Secrets:** `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` go in the
  existing `.env` mechanism. `deploy.sh` already syncs `.env`.

### Token format + storage

- Raw token: `tb_<32 hex chars>` (16 bytes from `secrets.token_hex`).
  Easy to grep, easy to recognize, doesn't look like anything else.
- DB stores SHA-256 hash, not plaintext. A leaked DB doesn't yield
  active tokens.
- `expires_at`: 30 days from issue. Auto-renewed on
  successful `authenticate()` call (sliding TTL). Hard expiry can be
  configured later if we want; 30-day-sliding is the lowest-friction
  default for ongoing dogfood.
- Revocation: setting `revoked_at` invalidates a token; any cached
  session loses access on the next non-cached check.

### New DB tables

```sql
CREATE TABLE auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    wikipedia_username TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_used_at TEXT
);
CREATE INDEX idx_auth_tokens_user ON auth_tokens(wikipedia_username);
CREATE INDEX idx_auth_tokens_expires ON auth_tokens(expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE oauth_states (
    state TEXT PRIMARY KEY,                  -- the CSRF nonce
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Cleaned up on a 10-min sweep; rows older than that are expired.
```

`init_db()` already adds tables idempotently — same pattern.

### Tool changes

**New tools:**

| Tool | Purpose |
|---|---|
| `authenticate(token: str)` | Validates token, caches `(session → username)`, returns `{username, expires_at}`. Stateful clients call once; stateless clients can use this to verify their token is still valid. |
| `whoami()` | Returns the authenticated username (or "anonymous"). Useful for the AI to confirm state mid-session. |
| `set_topic_visibility(visibility: str)` | Owner-only. Values: `private`, `public_read`, `public_edit`. |
| `get_topic_visibility()` | Returns `{owner, visibility}`. Anyone who can read the topic can call it. |

**Modified tools:**

Every topic-touching tool gains `auth_token: str | None = None` as
the last optional kwarg before `ctx`. This is the same shape as
`topic=`; the AI is already used to threading per-call params for
stateless clients.

Each tool calls `_require_topic_with_access(ctx, topic, mode,
auth_token)` instead of today's `_require_topic`. Mode is `'read'` or
`'write'`. The helper resolves the topic, resolves the caller (from
session cache or `auth_token`), checks the permission rules, returns
`(topic_id, wiki, caller_username, error)`.

`list_topics` becomes:
- Authenticated: returns the user's own topics + a separate list of
  public topics owned by others.
- Anonymous: returns only public topics.

`submit_feedback` requires auth. No anonymous feedback — kills its
attribution value.

`start_topic` requires auth. New topics default to private with
`owner_username = caller`.

### Permission helper sketch

```python
def _require_topic_with_access(ctx, topic, mode, auth_token=None):
    """Resolve topic + caller; enforce read/write permission.
    Returns (topic_id, wiki, caller_username, error)."""
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return None, "en", None, err
    caller = _resolve_caller(ctx, auth_token)  # None if anonymous
    owner, visibility = db.get_topic_acl(topic_id)
    if mode == 'read' and not can_read(owner, visibility, caller):
        return None, wiki, caller, _auth_required_error()
    if mode == 'write' and not can_write(owner, visibility, caller):
        if caller is None:
            return None, wiki, caller, _auth_required_error()
        return None, wiki, caller, _not_owner_error(owner, visibility)
    return topic_id, wiki, caller, None

def _resolve_caller(ctx, auth_token):
    # 1. session cache (Claude / stateful)
    cached = _session_users.get(_session_key(ctx))
    if cached and not _expired(cached):
        return cached.username
    # 2. explicit token (ChatGPT / stateless)
    if auth_token:
        row = db.lookup_auth_token(_hash(auth_token))
        if row and not _expired(row):
            _session_users[_session_key(ctx)] = (row.username, time.time())
            db.touch_token(row.id)
            return row.username
    return None
```

### Session caching

In-process dict `_session_users: {session_key: (username,
cached_at)}`, parallel to `_session_topics`. TTL 5 min; falls back to
DB lookup. Multi-worker: state is per-worker. nginx `ip_hash` (already
shipped) keeps a session pinned, so a given session's auth state is
consistent within the worker that owns it. Token validation falls
back to the DB anyway, so cross-worker revocation propagates within
TTL.

### `/exports/<slug>.csv` gating

nginx serves these directly today. Two options:

- **App-level gate.** Move serving into the Python app; check
  `topics.visibility` before streaming. Simpler permission model;
  costs a Python round-trip per CSV.
- **nginx + auth_request.** A small `/internal/check_export?slug=…`
  endpoint returns 200/403; nginx `auth_request` consults it before
  serving. Faster per-CSV but more nginx config.

Recommendation: app-level for v1. CSVs are small + infrequent.

## Migration plan for existing topics

The current DB has topics with no owner. We have to assign one.

**Recommendation: configurable default-owner one-shot.** Add an env
var `MIGRATION_DEFAULT_OWNER` (e.g., `"Sage Ross"`). On the auth
deploy, run a one-shot migration:

```sql
UPDATE topics
SET owner_username = :default_owner,
    visibility = 'private'
WHERE owner_username IS NULL;
```

Today's only active user is Sage; pre-existing topics belong to him.
This is a single, auditable SQL step. Sage can then individually
publish any topic he wants others to see.

After the migration, `owner_username IS NULL` is a real "orphan"
state used only for benchmark / dogfood-task topics that aren't tied
to a specific user. Those should probably get
`visibility='public_read'` so anyone exercising the benchmark can
read prior runs.

**Alternative (rejected):** "first authenticated writer becomes
owner." Cute but creates ambiguity for topics that have multiple
historical contributors. Keep migration explicit.

## Rollout phases

Each phase is independently deployable; later phases assume the
earlier ones are live. Total span: ~1–2 weeks elapsed (most of which
is waiting for OAuth consumer approval), ~1 solid day of
implementation per phase.

### Phase 0 — out-of-band prerequisites (in parallel with Phase 1 code)

1. Submit Wikimedia OAuth consumer registration. Approval turnaround
   is the long pole.
2. Decide token TTL (default proposal: 30-day sliding).
3. Decide migration owner (default proposal: env var, `"Sage Ross"`).

### Phase 1 — schema + login page + `authenticate` tool, NO enforcement

- DB: add `auth_tokens`, `oauth_states`, `topics.owner_username`,
  `topics.visibility` (default `'private'`). Run migration to assign
  default owner.
- HTTP: `/oauth/login`, `/oauth/start`, `/oauth/callback`,
  `/oauth/revoke`. Display the token; let users self-revoke.
- Tools: `authenticate`, `whoami`. Add the auth-token cache.
- Tools: every topic-touching tool gets `auth_token=` as a no-op
  passthrough (collected but not enforced). This is plumbing only —
  later phases flip the enforcement on.
- **Verification:** drive the OAuth dance manually; verify tokens
  validate; verify session cache; smoke-test in Claude AND ChatGPT
  that the token-paste flow works end-to-end. Watch ChatGPT
  specifically: does it strip / sanitize `tb_…` strings, or pass
  them through? If it strips them, fall back to a tutorial-style
  workaround on the token page (e.g. wrap as
  `authenticate token "tb_…"` so it looks like a quoted command
  argument, not a credential).

### Phase 2 — enforce auth on writes

- Switch all write-shaped tools to use
  `_require_topic_with_access(mode='write')`. New rule: write
  requires auth and (owner OR `public_edit`).
- All read-shaped tools stay open (no enforcement yet).
- `start_topic` requires auth; new topics default `private`,
  `owner_username = caller`.
- `submit_feedback` requires auth.
- `list_topics` filters by ownership for authenticated callers (own
  + public). Anonymous still sees all (legacy behavior preserved
  one phase longer, then closed in Phase 3).

### Phase 3 — enforce auth on reads + publish/unpublish UI

- Switch read-shaped tools to
  `_require_topic_with_access(mode='read')`.
- Anonymous can read `public_read` / `public_edit` topics; private
  topics return auth-required.
- `set_topic_visibility(visibility)` shipped. Owner-only check.
- `get_topic_visibility()` shipped.
- `list_topics` for anonymous returns only public topics.
- `/exports/<slug>.csv` gated on visibility.

### Phase 4 — polish + observability

- Per-user usage telemetry surfaced in `get_status` (logged_calls
  by-user this session).
- Per-user rate limit on the noisy gather tools (optional;
  nice-to-have).
- Admin-only `transfer_topic(slug, new_owner)` for ownership
  reassignment edge cases.
- Token rotation tooling: `/oauth/tokens` lists active tokens for
  the logged-in user with revoke buttons.

## Tool-by-tool impact

Roughly 50-ish tools touch topics. They split cleanly:

**Read-mode (`mode='read'`)** — affected by Phase 3 only:
`list_topics` (filtered), `get_status`, `get_articles`,
`get_articles_by_source`, `describe_topic`, `audit_progress`,
`list_rejections`, `list_sources`, `get_topic_rubric`, `export_csv`,
`browse_edges`, `filter_articles` (preview), `get_topic_visibility`,
`resume_topic`.

**Write-mode (`mode='write'`)** — affected by Phase 2:
`start_topic`, `add_articles`, `remove_articles`, `remove_by_source`,
`remove_by_pattern`, `set_scores`, `score_by_extract`,
`auto_score_by_keyword`, `auto_score_by_description`,
`score_all_unscored`, `set_topic_rubric`, `reject_articles`,
`unreject_articles`, `reset_topic`, `resolve_redirects`,
`harvest_list_page`, `preview_harvest_list_page` (read; the commit
form writes), `harvest_navbox`, `get_category_articles` (commits),
`preview_category_pull` (read), `get_wikiproject_articles`,
`search_articles` (commits), `preview_search` (read), `search_similar`
(commits), `preview_similar` (read), `submit_feedback`,
`set_topic_visibility`.

**Recon-only / no topic** — unaffected:
`survey_categories`, `find_list_pages`, `find_wikiprojects`,
`check_wikiproject`, `get_article_*` family, `wikidata_*` family
(except commits), `fetch_descriptions`, `fetch_article_leads`.

**Special**: `fetch_task_brief`, `list_tasks`, `list_exemplars`,
`get_exemplar` — research tools, not topic-scoped, no auth needed.

## Open questions

- **Will ChatGPT pass `tb_…` strings through?** Tokens look credential-ish;
  ChatGPT has been known to redact things that pattern-match secrets.
  Verify in Phase 1 with a live test. Mitigation if it strips: format
  the token page output as a chat command (`authenticate token
  "tb_…"`) that looks more like an argument and less like a leaked
  credential.
- **Per-user topic-name uniqueness vs. global uniqueness.** Today
  `topics.slug` is globally UNIQUE. Should two users be able to have
  topics with the same name? Yes — namespace by owner. Schema change:
  drop `UNIQUE(slug)`, replace with `UNIQUE(owner_username, slug)`,
  with NULL owner counting as a single "orphan" namespace. Important:
  this also affects `start_topic` — name collisions with a different
  owner now create a new topic, not collide.
- **Wikipedia username casing.** Wikipedia normalizes the first
  letter case-insensitive but is case-sensitive on the rest. Normalize
  via `db.normalize_username(name)` (capitalize first char, replace
  spaces with underscores) to avoid `Sage Ross` vs `sage ross`
  collisions.
- **Session-state leak across users.** If User A authenticates, then
  User B somehow connects with the same session ID (extremely
  unlikely under MCP's session-init protocol, but worth thinking
  about): B inherits A's identity. Mitigation: tie the session cache
  entry to `ctx.client_id` if available, fail closed if it changes
  mid-session. Belt-and-suspenders; the session-init flow already
  randomizes the session ID.
- **MCP-native OAuth 2.1 flow as a parallel path.** The spec supports
  it; Claude implements it; ChatGPT's support has been spotty. Worth
  adding as a second path once the token-paste path is solid, so
  Claude users can skip the paste. Defer to Phase 4+ unless ChatGPT
  ships reliable support sooner.
- **Editing on Wikipedia via the OAuth grant.** The grant we'd
  request is identity-only; no edit scope. If we ever want to make
  edits on the user's behalf (e.g., post a curated topic to a
  WikiProject page), we'd request a wider grant in a future
  registration. Out of scope here.
- **Public-edit DOS via Wikipedia API consumption.** A `public_edit`
  topic can be hammered by an authenticated bystander, eating our
  shared rate-limit bucket. The Phase 4 per-user rate limit is the
  durable answer; in the interim, watch
  `usage.jsonl` for abusive patterns and block by username via a
  simple denylist file.
- **Feedback log audit trail.** `usage.jsonl` will gain a `caller`
  field. Existing entries don't have it; downstream scripts
  (`scripts/benchmark_score.py`, etc.) need to tolerate its absence
  on old rows.

## What's already in place that helps

- Per-session state plumbing (`_session_topics`, `_session_key`,
  `_get_topic`, `_set_topic`) — directly reusable for
  `_session_users`.
- Stateless-client `topic=` parameter pattern — `auth_token=` is a
  direct parallel; the AI-facing UX and the code shape are familiar
  to both clients and to anyone reading the code.
- SQLite migration pattern — `init_db()` already adds tables /
  indices / columns idempotently via `CREATE TABLE IF NOT EXISTS` /
  `ALTER TABLE` guarded by `PRAGMA table_info`.
- Tool usage logging (`log_usage`) — adding `caller` is a one-line
  threading change.
- nginx already proxies path-prefixes; adding `/oauth/*` is a few
  lines in `mcp_server/deploy.sh`'s nginx template.
- Multi-worker with `ip_hash` keeps session-cache state coherent
  per-session.
- Landing page (`mcp_server/landing.html`) is already the operator-
  facing surface for "what's here" — an "Account" link to
  `/oauth/login` slots in naturally.

## Effort estimate

Assuming OAuth consumer is approved before Phase 2 code lands:

| Phase | Code | Test/verify | Total |
|---|---|---|---|
| Phase 0 (consumer reg) | — | — | 3–7 days elapsed wait |
| Phase 1 (schema + OAuth dance + plumbing, no enforcement) | ~1 day | half-day across Claude + ChatGPT | ~1.5 days |
| Phase 2 (enforce on writes) | ~half day | half-day | ~1 day |
| Phase 3 (enforce on reads + publish/unpublish) | ~half day | half-day | ~1 day |
| Phase 4 (polish) | ~half day | quarter-day | ~1 day |

**Total implementation:** ~4.5 working days, gated on Phase 0
approval. Phases 1–3 are the must-ship; Phase 4 is harvest-as-needed.

## Pre-implementation checklist

Before writing Phase 1 code, confirm:

- [ ] Wikimedia OAuth consumer submitted (Phase 0 step 1).
- [ ] `MIGRATION_DEFAULT_OWNER` decided (proposed: `"Sage Ross"`).
- [ ] Token TTL decided (proposed: 30-day sliding).
- [ ] Topic-name uniqueness decision: per-owner namespacing (proposed)
      vs. global. This is load-bearing on the schema migration.
- [ ] ChatGPT token-paste smoke test plan (Phase 1 verification): a
      throwaway token to confirm the string round-trips through the
      conversation untouched.
- [ ] Username normalization rule confirmed
      (`first-char-upper, spaces→underscore`).
