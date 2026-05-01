"""Server-to-server JSON endpoint that delivers a frozen IV package.

Mounted on the FastMCP Starlette app via @mcp.custom_route in server.py.
The /packages/<handle> route is public (no auth beyond handle
unguessability — the handle is a capability) and returns the snapshot
config + article list created by publish_topic. Impact Visualizer
fetches this URL after the user clicks Import on its preview page.

Responses:
  200 — JSON package; consumed_at marked on first hit (multi-use, so
        IV can retry on transient failures, but only the first fetch
        records consumed_at).
  404 — unknown, expired, or bad-prefix handles all return the same
        body. The reason rides on the JSONL log line, not the
        response — no enumeration distinction.
"""

from __future__ import annotations

import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import db


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    return getattr(request.client, "host", "") or ""


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _not_found(request: Request, handle: str, *, reason: str) -> Response:
    db.append_package_event({
        "event": "fetch",
        "handle": handle,
        "ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent", ""),
        "status": 404,
        "reason": reason,
        "ts": _now_iso(),
    })
    return JSONResponse({"error": "not found"}, status_code=404)


async def get_package(request: Request) -> Response:
    handle = request.path_params.get("handle", "")
    if not handle.startswith("tbp_"):
        return _not_found(request, handle, reason="bad_prefix")

    pkg = db.get_iv_package(handle)
    if not pkg:
        return _not_found(request, handle, reason="missing")

    now_iso = _now_iso()
    # SQLite's datetime('now') format is 'YYYY-MM-DD HH:MM:SS' (UTC, no
    # tz suffix); compare lexicographically against the same shape.
    sqlite_now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S")
    if pkg["expires_at"] < sqlite_now:
        return _not_found(request, handle, reason="expired")

    consumed_first_time = db.mark_iv_package_consumed(handle)

    body = {
        "handle": pkg["handle"],
        "schema_version": pkg["schema_version"],
        "config": pkg["config"],
        "articles": pkg["articles"],
        "article_count": len(pkg["articles"]),
        "source_topic": pkg["source_topic"],
        "created_at": pkg["created_at"],
        "consumed_at": pkg["consumed_at"] or sqlite_now,
    }
    db.append_package_event({
        "event": "fetch",
        "handle": handle,
        "ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent", ""),
        "status": 200,
        "consumed_first_time": consumed_first_time,
        "ts": now_iso,
    })
    return JSONResponse(body)


def register(mcp) -> None:
    """Register the /packages/<handle> route on the FastMCP app.
    Called from server.py at module-load time."""
    mcp.custom_route("/packages/{handle}", methods=["GET"])(get_package)
