"""HTML pages for signed-in users.

Currently mounts two routes on the FastMCP Starlette app:

  GET /topics                       — list the caller's owned topics with
                                       per-topic on-demand CSV download links.
  GET /topics/<slug>/download.csv   — auth + ownership check, regenerate
                                       the topic's CSV via csv_export, then
                                       302 to /exports/<filename> for nginx
                                       to serve.

Authentication uses a `tb_session` cookie (the same `tb_<hex>` bearer
token shown on /oauth/callback). If the cookie is missing or the token
is expired/revoked, the user is bounced to /oauth/login.
"""

from __future__ import annotations

import datetime
import html
import os

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

import csv_export
import db
from oauth import SESSION_COOKIE


def _authenticated_username(request: Request) -> str | None:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    info = db.lookup_auth_token(raw)
    return info["username"] if info else None


# ── Route: /topics ────────────────────────────────────────────────────


async def topics_index(request: Request) -> Response:
    username = _authenticated_username(request)
    if not username:
        return RedirectResponse("/oauth/login", status_code=302)

    rows = db.list_topics_for(username)
    owned = [r for r in rows if r.get("mine")]
    return HTMLResponse(_render_index_page(username, owned))


# ── Route: /topics/<slug>/download.csv ────────────────────────────────


async def topics_download(request: Request) -> Response:
    username = _authenticated_username(request)
    if not username:
        return RedirectResponse("/oauth/login", status_code=302)

    slug = request.path_params.get("slug", "")
    if not slug:
        return _error_page("Missing topic slug.", status=400)

    # Look up by slug. get_topic_by_name re-slugifies its argument and
    # matches against the slug column, so feeding it a slug works
    # (slugify is idempotent over already-slugified strings).
    topic_id, canonical_name, wiki = db.get_topic_by_name(slug)
    if topic_id is None:
        return _error_page(f"No topic named {slug!r}.", status=404)

    owner, _visibility = db.get_topic_acl(topic_id)
    if db.normalize_username(owner) != db.normalize_username(username):
        return _error_page(
            "You can only download CSVs for topics you own.", status=403)

    enriched = request.query_params.get("enriched", "0").lower() in ("1", "true", "yes")

    try:
        result = csv_export.write_topic_csv(
            topic_id, canonical_name, wiki, enriched=enriched)
    except Exception as e:  # pragma: no cover — defensive: surface errors
        return _error_page(f"Export failed: {e}", status=500)

    # Redirect to the static-served file. nginx adds Content-Disposition:
    # attachment for /exports/, so the browser will save rather than open.
    return RedirectResponse(f"/exports/{result['filename']}", status_code=302)


# ── HTML rendering ────────────────────────────────────────────────────


def _render_index_page(username: str, topics: list[dict]) -> str:
    user_safe = html.escape(username)
    if not topics:
        body = (
            '<p class="empty">You don\'t own any topics yet. Connect Topic '
            'Builder in your AI client and start a topic — once it\'s '
            'saved, it\'ll show up here.</p>'
        )
    else:
        rows_html = "\n".join(_render_topic_row(t) for t in topics)
        body = f"""<table class="topics">
<thead><tr>
<th>Topic</th><th>Wiki</th><th class="num">Articles</th>
<th>Visibility</th><th>Updated</th>
<th>Simple CSV</th><th>Enriched CSV</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>"""

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="UTF-8">
<title>My topics &mdash; Topic Builder</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:64rem;margin:2.5rem auto;padding:0 1.25rem;color:#2c2c2c;line-height:1.5}}
h1{{font-weight:400;color:#5248af;margin:0 0 .25rem;font-size:2rem}}
.user{{color:#6a6a6a;margin:0 0 2rem}}
.user a{{color:#5248af}}
.empty{{color:#6a6a6a;font-style:italic;background:#fafafa;border:1px solid #e2e2e2;padding:1rem 1.25rem;border-radius:3px}}
table.topics{{border-collapse:collapse;width:100%;font-size:.95em}}
table.topics th,table.topics td{{padding:.55rem .75rem;text-align:left;border-bottom:1px solid #ececec;vertical-align:top}}
table.topics th{{font-weight:600;color:#444;background:#fafafa;border-bottom:1px solid #d4d4d4;font-size:.85em;text-transform:uppercase;letter-spacing:.04em}}
table.topics td.num,table.topics th.num{{text-align:right;font-variant-numeric:tabular-nums}}
table.topics .name{{font-weight:600;color:#2c2c2c}}
table.topics .updated{{color:#6a6a6a;font-size:.88em;font-variant-numeric:tabular-nums}}
.viz{{display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;padding:2px 7px;border-radius:3px;border:1px solid transparent}}
.viz-private{{background:#eef0fa;color:#3a3a8a;border-color:#d8dcee}}
.viz-public_read{{background:#fff4dc;color:#8a6a1f;border-color:#f1dfb2}}
.viz-public_edit{{background:#e3f4ec;color:#368e76;border-color:#cde7dc}}
.dl a{{color:#5248af;font-weight:600;text-decoration:none}}
.dl a:hover{{text-decoration:underline}}
.dl .meta{{display:block;color:#878787;font-size:.78em;margin-top:1px;font-variant-numeric:tabular-nums}}
.dl .stale{{color:#a36a1f}}
nav.crumbs{{margin-bottom:1.25rem;font-size:.9em;color:#6a6a6a}}
nav.crumbs a{{color:#5248af;text-decoration:none}}
nav.crumbs a:hover{{text-decoration:underline}}
</style>
</head><body>
<nav class="crumbs"><a href="/">Topic Builder</a> &rsaquo; My topics</nav>
<h1>My topics</h1>
<p class="user">Signed in as <strong>{user_safe}</strong>. Each download link regenerates the CSV from the current corpus before serving.</p>
{body}
</body></html>
"""


def _render_topic_row(t: dict) -> str:
    slug = t["slug"]
    name = html.escape(t.get("name") or slug)
    wiki = html.escape(t.get("wiki") or "en")
    count = t.get("article_count") or 0
    visibility = t.get("visibility") or "private"
    viz_safe = html.escape(visibility)
    updated_at = t.get("updated_at") or ""
    updated_dt = _parse_sqlite_dt(updated_at)
    updated_display = html.escape(_short_dt(updated_dt) if updated_dt else updated_at)

    simple_cell = _download_cell(slug, updated_dt, enriched=False)
    enriched_cell = _download_cell(slug, updated_dt, enriched=True)

    return f"""<tr>
<td class="name">{name}</td>
<td>{wiki}</td>
<td class="num">{count}</td>
<td><span class="viz viz-{viz_safe}">{viz_safe}</span></td>
<td class="updated">{updated_display}</td>
<td class="dl">{simple_cell}</td>
<td class="dl">{enriched_cell}</td>
</tr>"""


def _download_cell(slug: str, topic_updated: datetime.datetime | None, *,
                   enriched: bool) -> str:
    flag = "1" if enriched else "0"
    safe_slug = html.escape(slug)
    href = f"/topics/{safe_slug}/download.csv?enriched={flag}"
    label = "Enriched" if enriched else "Simple"
    link = f'<a href="{href}">Download {label}</a>'

    filename = csv_export.csv_filename(slug, enriched=enriched)
    fpath = os.path.join(csv_export.export_dir(), filename)
    if not os.path.exists(fpath):
        return f'{link}<span class="meta">never generated</span>'
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(fpath), tz=datetime.timezone.utc)
    stale = topic_updated is not None and topic_updated > mtime
    klass = ' class="meta stale"' if stale else ' class="meta"'
    suffix = " (stale)" if stale else ""
    return f'{link}<span{klass}>last: {html.escape(_short_dt(mtime))}{suffix}</span>'


# ── Time helpers ──────────────────────────────────────────────────────


def _parse_sqlite_dt(s: str) -> datetime.datetime | None:
    if not s:
        return None
    s = s.split(".", 1)[0]  # drop fractional seconds if any
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc)
    except ValueError:
        try:
            return datetime.datetime.fromisoformat(s).replace(
                tzinfo=datetime.timezone.utc)
        except ValueError:
            return None


def _short_dt(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ── Misc ──────────────────────────────────────────────────────────────


def _error_page(msg: str, *, status: int = 400) -> HTMLResponse:
    body = f"""<!doctype html>
<html><head><title>Error &mdash; Topic Builder</title>
<style>body{{font-family:system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#222;line-height:1.5}}</style>
</head><body>
<h1>Something went wrong</h1>
<p>{html.escape(msg)}</p>
<p><a href="/topics">Back to my topics</a></p>
</body></html>
"""
    return HTMLResponse(body, status_code=status)


def register(mcp) -> None:
    """Register /topics + /topics/<slug>/download.csv on the FastMCP app."""
    mcp.custom_route("/topics", methods=["GET"])(topics_index)
    mcp.custom_route(
        "/topics/{slug}/download.csv", methods=["GET"])(topics_download)
