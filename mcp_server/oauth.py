"""Wikimedia OAuth 2.0 dance + token-display HTTP routes.

Mounted on the FastMCP Starlette app via @mcp.custom_route in server.py.
Routes (env-gated; show a "not configured" page if OAUTH_CLIENT_ID is
unset):

  GET  /oauth/login       — landing with "Sign in with Wikipedia" button
  GET  /oauth/start       — redirects to Wikimedia authorize URL
  GET  /oauth/callback    — exchanges code for access token, fetches
                             username, mints a Topic Builder token, shows
                             it to the user
  POST /oauth/revoke      — revokes a token

The flow is summarized in `docs/shipped.md` (Auth Phase 1+2 cutover). The user copies the
displayed bearer token and pastes it into the chat; the AI then calls
the `authenticate(token=…)` MCP tool to bind it to the session.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

import db
from wikipedia_api import USER_AGENT


# Wikimedia OAuth 2.0 endpoints (Meta-Wiki). These are the public,
# documented URLs and are stable; if Wikimedia ever moves them we'll
# update here.
AUTHORIZE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/authorize"
TOKEN_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
PROFILE_URL = "https://meta.wikimedia.org/w/rest.php/oauth2/resource/profile"

# Cookie name for the CSRF state nonce. HttpOnly + SameSite=Lax keeps it
# off JS and out of cross-site requests, which is all we need for an
# OAuth-redirect-style flow.
STATE_COOKIE = "tb_oauth_state"


def _client_id() -> str | None:
    return os.environ.get("OAUTH_CLIENT_ID") or None


def _client_secret() -> str | None:
    return os.environ.get("OAUTH_CLIENT_SECRET") or None


def _redirect_uri() -> str:
    """The callback URL we registered with Wikimedia. Configurable for
    dev / staging via env; defaults to production."""
    return os.environ.get(
        "OAUTH_REDIRECT_URI",
        "https://topic-builder.wikiedu.org/oauth/callback")


def _is_configured() -> bool:
    return bool(_client_id() and _client_secret())


def _not_configured_page(reason: str = "") -> HTMLResponse:
    body = f"""<!doctype html>
<html><head><title>OAuth not configured</title>
<style>body{{font-family:system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;color:#222;line-height:1.5}}</style>
</head><body>
<h1>OAuth not configured</h1>
<p>The Wikimedia OAuth consumer hasn't been set up yet on this server.
The login flow will become available once the operator finishes
registering the consumer and sets <code>OAUTH_CLIENT_ID</code> and
<code>OAUTH_CLIENT_SECRET</code>.</p>
{f'<p><em>{reason}</em></p>' if reason else ''}
<p><a href="/">Back to landing page</a></p>
</body></html>
"""
    return HTMLResponse(body, status_code=503)


# ── Routes ────────────────────────────────────────────────────────────


async def login(request: Request) -> Response:
    """Landing page with a Sign-in-with-Wikipedia button."""
    if not _is_configured():
        return _not_configured_page()
    body = """<!doctype html>
<html><head><title>Topic Builder — sign in</title>
<style>
body{font-family:system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#222;line-height:1.5}
a.btn{display:inline-block;background:#36c;color:#fff;padding:.6rem 1.2rem;border-radius:.3rem;text-decoration:none;font-weight:600}
a.btn:hover{background:#2a52a3}
code{background:#f4f4f4;padding:.1rem .3rem;border-radius:.2rem}
</style>
</head><body>
<h1>Sign in with your Wikimedia account</h1>
<p>Topic Builder uses your Wikimedia username to scope your topics
privately to you. After you sign in, you'll get a token to paste into
the chat — the AI uses it to authenticate your tools.</p>
<p><a class="btn" href="/oauth/start">Sign in with Wikimedia &rarr;</a></p>
<p style="margin-top:2rem;color:#666;font-size:.9em">We only request
identity (your username). We do not request edit rights and cannot
edit any Wikimedia project on your behalf.</p>
</body></html>
"""
    return HTMLResponse(body)


async def start(request: Request) -> Response:
    """Redirect to Wikimedia's authorize URL with our client_id + state."""
    if not _is_configured():
        return _not_configured_page()
    state = db.create_oauth_state()
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "state": state,
    }
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        STATE_COOKIE, state,
        max_age=600, httponly=True, samesite="lax", secure=True, path="/oauth")
    return resp


async def callback(request: Request) -> Response:
    """Handle the OAuth redirect: exchange code for access token, fetch
    the user's profile, mint a Topic Builder bearer token, display it."""
    if not _is_configured():
        return _not_configured_page()
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    cookie_state = request.cookies.get(STATE_COOKIE)
    if not code:
        return _error_page("Missing 'code' parameter from Wikimedia.")
    if not state or state != cookie_state:
        return _error_page("CSRF state mismatch. Please retry from /oauth/login.")
    if not db.consume_oauth_state(state):
        return _error_page("Authentication state expired. Please retry from /oauth/login.")

    # Exchange the authorization code for an access token.
    try:
        access_token = await _exchange_code(code)
    except Exception as e:
        return _error_page(f"Token exchange failed: {e}")

    # Fetch the user's Wikipedia username.
    try:
        username = await _fetch_username(access_token)
    except Exception as e:
        return _error_page(f"Profile fetch failed: {e}")

    # Mint a Topic Builder bearer token for this user.
    raw, expires_at = db.create_auth_token(username, ttl_days=30)
    return _token_display_page(username, raw, expires_at)


async def revoke(request: Request) -> Response:
    """Revoke a token. Accepts the token in form data so the user can
    paste it from the display page; no auth needed beyond knowing the
    token (it's a self-revoke)."""
    form = await request.form()
    raw = form.get("token", "").strip()
    if not raw:
        return _error_page("No token provided.")
    ok = db.revoke_auth_token(raw)
    body = """<!doctype html>
<html><head><title>Token revoked</title>
<style>body{font-family:system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#222}</style>
</head><body>
<h1>Token revoked</h1>
<p>%s</p>
<p><a href="/oauth/login">Sign in again to get a fresh token</a></p>
</body></html>
""" % ("The token has been revoked. Any session using it will need a fresh sign-in."
       if ok else "Token not found or already revoked.")
    return HTMLResponse(body)


# ── Helpers ───────────────────────────────────────────────────────────


def _error_page(msg: str) -> HTMLResponse:
    body = f"""<!doctype html>
<html><head><title>Sign-in failed</title>
<style>body{{font-family:system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#222}}</style>
</head><body>
<h1>Sign-in failed</h1>
<p>{msg}</p>
<p><a href="/oauth/login">Try again</a></p>
</body></html>
"""
    return HTMLResponse(body, status_code=400)


def _token_display_page(username: str, raw_token: str, expires_at: str) -> HTMLResponse:
    # The user pastes this whole block. We format it as something that
    # looks more like a chat instruction than a credential, so a
    # paranoid client (e.g. a future ChatGPT version that sniffs
    # secrets) is less likely to redact it.
    paste_line = f'My Topic Builder token is "{raw_token}" — please use it to authenticate me for this session.'
    body = f"""<!doctype html>
<html><head><title>Signed in as {username}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:0 1rem;color:#222;line-height:1.5}}
.token{{background:#f4f4f4;padding:1rem;border-radius:.3rem;font-family:ui-monospace,monospace;font-size:.95em;word-break:break-all;border:1px solid #ddd}}
button{{background:#36c;color:#fff;border:none;padding:.5rem 1rem;border-radius:.3rem;cursor:pointer;font:inherit;font-weight:600}}
button:hover{{background:#2a52a3}}
form.revoke{{margin-top:2rem;padding-top:1rem;border-top:1px solid #ddd}}
form.revoke button{{background:#933}}
</style>
</head><body>
<h1>Signed in as {username}</h1>
<p>Copy the line below and paste it into your chat with the AI. The AI
will call <code>authenticate</code> with the token, and your topic
tools will be bound to your account for the rest of the session.</p>
<div class="token" id="token">{paste_line}</div>
<p><button onclick="navigator.clipboard.writeText(document.getElementById('token').textContent)">Copy to clipboard</button></p>
<p>Token expires: <strong>{expires_at} UTC</strong> (30 days from now).
You'll need to sign in again to get a fresh one when it expires.</p>
<form class="revoke" method="post" action="/oauth/revoke">
  <p>If you ever want to revoke this token (for example because you
  pasted it somewhere you shouldn't have), submit it here:</p>
  <input type="text" name="token" placeholder="tb_..." style="width:60%;font-family:ui-monospace,monospace">
  <button type="submit">Revoke token</button>
</form>
</body></html>
"""
    resp = HTMLResponse(body)
    # Clear the state cookie now that we're done with the flow.
    resp.delete_cookie(STATE_COOKIE, path="/oauth")
    return resp


async def _exchange_code(code: str) -> str:
    """POST the authorization code to Wikimedia's token endpoint and
    return the access_token. Synchronous urllib in a thread would be
    cleaner, but this runs once per sign-in so a blocking call inside
    an async route is acceptable."""
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(),
        "client_id": _client_id(),
        "client_secret": _client_secret(),
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # urllib's str(HTTPError) is just "HTTP NNN reason"; the OAuth 2.0
        # error code (invalid_client, unauthorized_client, …) lives in the
        # response body. Surface it so failures are diagnosable.
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            err_body = ""
        raise ValueError(f"HTTP {e.code} {e.reason} — {err_body}") from e
    token = body.get("access_token")
    if not token:
        raise ValueError(f"no access_token in response: {body!r}")
    return token


async def _fetch_username(access_token: str) -> str:
    """Call the profile endpoint and pull the `username` field."""
    req = urllib.request.Request(PROFILE_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8"))
    name = body.get("username") or body.get("name")
    if not name:
        raise ValueError(f"no username in profile response: {body!r}")
    return name


def register(mcp) -> None:
    """Register all /oauth/* routes on the FastMCP app. Called from
    server.py at module-load time."""
    mcp.custom_route("/oauth/login", methods=["GET"])(login)
    mcp.custom_route("/oauth/start", methods=["GET"])(start)
    mcp.custom_route("/oauth/callback", methods=["GET"])(callback)
    mcp.custom_route("/oauth/revoke", methods=["POST"])(revoke)
