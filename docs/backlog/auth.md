# Authentication plan

Detailed design for adding authentication to the Topic Builder MCP server.
Deferred — this doc captures the shape so we can pick it up later.

## Goals

1. **Identify the user** so topics can be scoped per-person and feedback is attributable to a real Wikipedia editor.
2. **Keep anonymous abuse off our Wikipedia rate-limit bucket** once the URL is publicly shared.
3. **Keep it Wikipedia-native** — users sign in with the account they already have for Wikipedia work. No new credential.

Non-goals: paywalling, role-based access control, team sharing. Those can come later if needed.

## Hard constraint

> The token must be something a user can paste into the chat, not something they configure inside the MCP client.

Why it matters: the whole point of the landing page is that setup is dead simple — one URL, "None" for authentication. Making users configure a token in Claude settings or a ChatGPT custom-connector form defeats that. Token-in-chat keeps setup identical and pushes the auth step into the conversation where the AI can guide the user.

## End-to-end user flow

1. User adds the MCP connector (`https://topic-builder.wikiedu.org/mcp`, no auth) — unchanged.
2. User asks the AI to build a topic.
3. First write-tool call returns:
   > "Authentication required. Visit https://topic-builder.wikiedu.org/login to sign in with your Wikipedia account and copy your token, then paste it to me."
4. User opens the URL in a new browser tab. The page shows:
   - "Sign in with Wikipedia" button.
   - On click, they're redirected to Wikipedia's OAuth consent page ("Allow Wiki Education Topic Builder to verify my Wikipedia account").
   - On return, the page displays their token: `tb_7f3a9c...` with a "Copy" button and expiration info ("valid for 30 days; revoke at …").
5. User pastes the token into the chat: *"My token: tb_7f3a9c..."*
6. AI calls `authenticate(token=...)` → returns `{"username": "Sage Ross", "expires_at": "..."}`. For stateful sessions that's enough; the server caches `(session_id → username)`. For stateless clients (ChatGPT), the AI passes `auth_token=tb_...` on every subsequent call, same pattern as the `topic=` param we just added.
7. AI proceeds with topic-building tools, now scoped to `wikipedia_username="Sage Ross"`.

## Server-side shape

### New HTTP endpoints

Small Starlette or Flask app mounted next to the MCP server (or in nginx, or in the same process):

- `GET /login` — Landing page with "Sign in with Wikipedia" button.
- `GET /login/start` — Redirects to Wikipedia OAuth 2.0 authorize URL with our client_id and `redirect_uri=https://topic-builder.wikiedu.org/login/callback`.
- `GET /login/callback?code=...` — Exchanges code for access token, fetches user's Wikipedia username, generates a new Topic Builder bearer token, stores it, displays it to the user.
- `GET /logout` — Revokes the active token for that session (optional; tokens expire anyway).

### New DB tables

```sql
CREATE TABLE auth_tokens (
    token TEXT PRIMARY KEY,                -- opaque random string, e.g. "tb_" + 32 bytes hex
    wikipedia_username TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,              -- 30 days from creation, renewable
    revoked_at TEXT
);
CREATE INDEX idx_auth_tokens_user ON auth_tokens(wikipedia_username);
```

Existing tables:
- `topics` gains a `wikipedia_username TEXT` column. NULL means "legacy pre-auth topic" (see transition plan below).
- `articles` unchanged (FK'd to topics).

### Tool changes

- Every tool that operates on a topic gains an optional `auth_token: str = None` parameter (same pattern as `topic=`).
- A new `authenticate(token: str)` tool that validates and binds the token to the current MCP session. Stateful clients (Claude) call this once; stateless clients (ChatGPT) pass `auth_token=` on every call.
- `_require_topic` helper gains a companion `_require_auth(ctx, auth_token=None)` helper. If the session has a cached username, use it. If `auth_token` is passed, validate and cache. Otherwise return a clear error with the `/login` URL.
- `list_topics` becomes per-user.
- `start_topic` / gather / scoring / export all check the caller's username against `topics.wikipedia_username`. Mismatch → "That topic belongs to a different user."
- `submit_feedback` is authenticated (so the feedback record has a verified username, not just a self-reported one).

### Token cache

- In-process dict `{session_id: (username, cached_at)}` with a short TTL (say 5 min) to avoid hitting the DB on every call. Resilient to restart because the DB is authoritative; losing the cache just means the next call revalidates.

## Out-of-band prerequisites

These take real time and can't be automated:

1. **Register a Wikipedia OAuth 2.0 consumer.**
   - URL: https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose
   - Type: "Confidential" (we have a server-side secret).
   - Grants: minimal — just identity. We don't need to edit on the user's behalf.
   - Callback URL: `https://topic-builder.wikiedu.org/login/callback`
   - Approval turnaround: typically 3–7 days.
   - Wiki Ed already operates consumers (for dashboard.wikiedu.org); if there's institutional continuity, a steward may approve faster.

2. **Decide the transition policy** (see below).

3. **Decide token lifetime** — default proposal: 30 days, auto-renewed on each authenticate call.

## Transition from anonymous to authenticated

Two options. Decide before deploying:

- **Hard flag-day.** On the cutover, all existing topics become `wikipedia_username = NULL` (orphan/admin-only). New topics require auth. Simplest to reason about; users lose nothing they didn't start anonymously.
- **Soft transition.** For a week: requests without a token still work (as now) but get a deprecation warning in every response. After the week, flip the switch. Friendlier but requires the warning plumbing.

Recommendation: **hard flag-day.** The current user base is small (dogfooding), the "data" at risk is working-list state that's cheap to rebuild, and the soft-transition code is throwaway.

## Open questions

- **Does the AI accept pasted tokens reliably?** Claude and ChatGPT both happily pass user-supplied strings as tool args, but need to verify with a live test that e.g. ChatGPT doesn't scrub/sanitize the token from the conversation context. Fallback: the login page can also show a "copy as a prompt line" button that formats it for the AI.
- **MCP-native OAuth 2.0 flow instead of paste-in-chat?** The spec supports it; Claude supports it; ChatGPT's support has been inconsistent. If ChatGPT catches up, we could offer both mechanisms — MCP-OAuth for clients that support it, pasted token as a fallback. For now, pasted-token-first.
- **Per-user topic namespacing granularity.** Should usernames with different casing collide (`Sage_Ross` vs `sage_ross`)? Wikipedia usernames are case-sensitive in display but the first letter is case-insensitive. Normalize at write time.
- **Rate limit per user.** Once authenticated, we could enforce per-user request ceilings on the noisy gather tools. Nice-to-have, not launch-blocking.
- **Admin view for feedback / orphan topics.** Needed eventually but not for the initial auth rollout.

## What's already in place that helps

- Per-session state plumbing (`_session_topics`, `_session_key`) — the same machinery can cache `(session_id → username)`.
- Stateless-client `topic=` parameter pattern — `auth_token=` would be a direct parallel, so the AI-facing UX and the code shape are both familiar.
- SQLite migration pattern — `init_db()` already adds tables/indices idempotently; adding `auth_tokens` and the `topics.wikipedia_username` column is routine.
- Tool usage logging — `log_usage` can easily include the username once we have it.

## Rough effort estimate

Assuming OAuth consumer is approved:

- Login page + OAuth dance: ~half a day.
- DB schema + migration: ~1 hour.
- `authenticate()` + `auth_token=` parameter plumbing across tools: ~half a day (same shape as the `topic=` rollout, which took about that).
- Per-user topic scoping: ~1-2 hours.
- Docs + landing page update: ~1 hour.
- Testing with both Claude and ChatGPT: ~1-2 hours.

Total: roughly one solid day of work after the OAuth consumer is live.
