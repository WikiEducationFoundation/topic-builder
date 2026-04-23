"""Wikipedia Topic Builder MCP Server.

Provides tools for exploring Wikipedia's content structure to build
comprehensive article lists for any topic.
"""

import csv
import html.parser
import json
import collections
import datetime
import logging
import os
import re
import threading
import time
import urllib.parse
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

from wikipedia_api import (
    api_query, api_query_all, api_get, normalize_title, wiki_api_url,
    get_rate_limit_stats, fetch_short_descriptions,
    reset_call_counters, get_call_counters,
)
import db

# ── Usage logging ──────────────────────────────────────────────────────────

LOG_DIR = os.environ.get("LOG_DIR", "/opt/topic-builder/logs")
os.makedirs(LOG_DIR, exist_ok=True)

usage_logger = logging.getLogger("usage")
usage_logger.setLevel(logging.INFO)
usage_handler = logging.FileHandler(os.path.join(LOG_DIR, "usage.jsonl"))
usage_handler.setFormatter(logging.Formatter("%(message)s"))
usage_logger.addHandler(usage_handler)

# Per-session current topic. Each MCP session (one client connection) has its
# own "current topic" so concurrent clients don't clobber each other's state.
# Keyed by id(ctx.session); value is (topic_id, topic_name, wiki).
_session_topics: dict[int, tuple[int, str, str]] = {}
_session_lock = threading.Lock()


def _session_key(ctx: Context) -> int:
    return id(ctx.session)


def _get_topic(ctx: Context) -> tuple[int | None, str, str]:
    with _session_lock:
        return _session_topics.get(_session_key(ctx), (None, "", "en"))


def _set_topic(ctx: Context, topic_id: int, name: str, wiki: str = "en") -> None:
    with _session_lock:
        _session_topics[_session_key(ctx)] = (topic_id, name, wiki)


def _start_call() -> float:
    """Mark the start of a tool invocation: zero per-call counters, return a
    monotonic timestamp. Every tool that calls log_usage should call this at
    entry; log_usage reads the counters + diffs the timestamp to record
    elapsed_ms, wikipedia_api_calls, and rate_limit_hits_this_call."""
    reset_call_counters()
    return time.perf_counter()


def log_usage(ctx: Context, tool_name: str, params: dict | None = None,
              result_summary: str = "", start_time: float | None = None,
              timed_out: bool = False, note: str = ""):
    """Append a usage log entry. Pass start_time from _start_call() at tool
    entry to attach elapsed_ms + per-call cost fields (wikipedia_api_calls,
    rate_limit_hits_this_call). timed_out is a contract for future tools that
    return partial results on a cooperative budget (Stage 3); current tools
    pass False. note is an optional AI-provided observation captured at the
    moment of the call."""
    topic_id, topic_name, wiki = _get_topic(ctx)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "topic": topic_name or "(none)",
        "wiki": wiki,
        "tool": tool_name,
    }
    if topic_id:
        status = db.get_status(topic_id)
        entry["articles_count"] = status['total_articles']
    if params:
        entry["params"] = {k: v for k, v in params.items()
                          if not isinstance(v, (list, dict)) or len(str(v)) < 200}
    if result_summary:
        entry["result"] = result_summary
    if start_time is not None:
        entry["elapsed_ms"] = int((time.perf_counter() - start_time) * 1000)
    counters = get_call_counters()
    entry["wikipedia_api_calls"] = counters['wikipedia_api_calls']
    entry["rate_limit_hits_this_call"] = counters['rate_limit_hits_this_call']
    entry["timed_out"] = timed_out
    if note:
        entry["note"] = note
    usage_logger.info(json.dumps(entry, ensure_ascii=False))


# Server instructions are maintained as Markdown in server_instructions.md
# for readability and clean diffs. Edit that file to change AI guidance;
# the running process reads it at startup, so a deploy + restart picks up
# any change. If the file is missing, fall back to a minimal stub so the
# server still boots (should never happen in a real deploy).
_INSTRUCTIONS_PATH = Path(__file__).parent / "server_instructions.md"
try:
    SERVER_INSTRUCTIONS = _INSTRUCTIONS_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    SERVER_INSTRUCTIONS = (
        "You are a Wikipedia topic mapping assistant. "
        "server_instructions.md is missing — running with a minimal stub."
    )

mcp = FastMCP(
    "Wikipedia Topic Builder",
    instructions=SERVER_INSTRUCTIONS,
)


def _require_topic(ctx: Context, topic_name: str | None = None) -> tuple[int | None, str, str | None]:
    """Resolve the topic for this call. Returns (topic_id, wiki, error).

    If topic_name is passed explicitly (for stateless clients like ChatGPT that
    don't persist MCP sessions), look it up by name — creating as enwiki if
    missing — and bind it to this session. Otherwise fall back to the
    session's current topic (set by start_topic). `wiki` defaults to 'en' if
    no topic is active.
    """
    if topic_name:
        tid, canonical, wiki = db.get_topic_by_name(topic_name)
        if tid is None:
            tid, _, _, wiki = db.create_or_get_topic(topic_name)
            canonical = topic_name
        _set_topic(ctx, tid, canonical, wiki)
        return tid, wiki, None

    tid, _, wiki = _get_topic(ctx)
    if not tid:
        return None, "en", (
            "No active topic. Call start_topic first, or pass topic=<name> to this tool. "
            "If your MCP client doesn't persist sessions between tool calls (e.g. ChatGPT), "
            "pass topic=<name> on every call."
        )
    return tid, wiki, None


def _resolve_wiki(ctx: Context, wiki: str | None = None, topic_name: str | None = None) -> str:
    """Pick the wiki for a recon tool call (tools that aren't topic-scoped
    but still need to query Wikipedia). Resolution order:
      1. explicit `wiki` parameter
      2. wiki of the topic passed as `topic_name`
      3. wiki of the session's current topic
      4. 'en' default
    """
    if wiki:
        return wiki
    if topic_name:
        _, _, w = db.get_topic_by_name(topic_name)
        if w:
            return w
    _, _, session_wiki = _get_topic(ctx)
    return session_wiki or 'en'


# ── Topic management ───────────────────────────────────────────────────────

@mcp.tool()
def start_topic(name: str, wiki: str = "en", fresh: bool = False,
                note: str = "", ctx: Context = None) -> str:
    """Start a new topic build or resume an existing one with the same name.
    Topics are persisted — if a topic with this name already exists, it will
    be resumed with all its articles intact UNLESS you pass fresh=True.

    A topic is bound to a specific Wikipedia language edition at creation
    time. Every subsequent tool call for this topic queries that wiki. Use a
    non-English wiki when the user wants to build a list of articles that
    live on (say) German or Spanish Wikipedia — titles, categories, and
    descriptions all come from the chosen wiki.

    Args:
        name: The topic name (e.g., "climate change", "Kochutensilien").
        wiki: Wikipedia language code (e.g., "en", "de", "es", "fr", "ja").
              Defaults to "en". Ignored when resuming an existing topic —
              the stored wiki wins so articles and pulls stay consistent.
        fresh: If True and the topic already exists, wipe all its articles
               before starting. Use this when the user asks to "start over"
               or "start fresh" on an existing topic. Defaults to False.
        note: Optional free-text observation to attach to this call's log
              entry. Use for zero-ceremony mid-flow reflection: surprise,
              friction, unexpected cost, unusual seed — the stuff worth
              remembering later. Empty by default; leave blank unless you
              have something specific to capture.
    """
    _start = _start_call()
    topic_id, is_new, article_count, canonical_wiki = db.create_or_get_topic(name, wiki=wiki)
    _set_topic(ctx, topic_id, name, canonical_wiki)

    if is_new:
        log_usage(ctx, "start_topic", {"name": name, "wiki": canonical_wiki, "is_new": True},
                  start_time=_start, note=note)
        return (f"Started new topic build: '{name}' on {canonical_wiki}.wikipedia.org. "
                f"Working list is empty.")

    wiki_mismatch_note = ""
    if wiki and wiki != canonical_wiki:
        wiki_mismatch_note = (
            f" (NOTE: you passed wiki='{wiki}' but this topic was created on "
            f"'{canonical_wiki}.wikipedia.org' and is locked to it. If you want a "
            f"different wiki, start a new topic under a different name.)"
        )

    if fresh:
        db.replace_all_articles(topic_id, {})
        log_usage(ctx, "start_topic", {"name": name, "wiki": canonical_wiki, "fresh": True},
                  f"cleared {article_count} articles", start_time=_start, note=note)
        return (f"Resumed existing topic '{name}' on {canonical_wiki}.wikipedia.org and "
                f"cleared its {article_count} previous articles (fresh=True). Working "
                f"list is now empty.{wiki_mismatch_note}")

    log_usage(ctx, "start_topic", {"name": name, "wiki": canonical_wiki, "is_new": False},
              start_time=_start, note=note)
    return (f"Resumed existing topic: '{name}' on {canonical_wiki}.wikipedia.org. Working "
            f"list has {article_count} articles. If you want to start over with a "
            f"fresh empty list instead, call reset_topic now (or re-call start_topic "
            f"with fresh=True).{wiki_mismatch_note}")


@mcp.tool()
def reset_topic(note: str = "", topic: str | None = None, ctx: Context = None) -> str:
    """Clear all articles from the current topic and start over.
    The topic itself is kept (so the name is preserved), but all articles,
    scores, and sources are wiped.

    Args:
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session (e.g. ChatGPT); otherwise uses the session's
               current topic.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name, _ = _get_topic(ctx)
    all_articles = db.get_all_articles_dict(topic_id)
    count = len(all_articles)
    db.replace_all_articles(topic_id, {})
    log_usage(ctx, "reset_topic", {}, f"cleared {count} articles",
              start_time=_start, note=note)
    return f"Reset topic '{topic_name}'. Removed all {count} articles. Working list is now empty."


@mcp.tool()
def list_topics() -> str:
    """List all existing topics that can be resumed."""
    topics = db.list_topics()
    if not topics:
        return "No topics found. Use start_topic to create one."
    return json.dumps(topics, indent=2, default=str)


@mcp.tool()
def resume_topic(name: str, ctx: Context = None) -> str:
    """Resume an existing topic build.

    Args:
        name: The topic name to resume
    """
    return start_topic(name, ctx=ctx)


@mcp.tool()
def get_status(topic: str | None = None, ctx: Context = None) -> str:
    """Get current status of the topic build: article count, score distribution, source breakdown.

    Args:
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name, _ = _get_topic(ctx)
    status = db.get_status(topic_id)
    status['topic'] = topic_name
    status['rate_limits'] = get_rate_limit_stats()
    return json.dumps(status, indent=2, default=str)


# ── Reconnaissance tools ──────────────────────────────────────────────────

@mcp.tool()
def survey_categories(category: str, depth: int = 2, count_articles: bool = False,
                      wiki: str | None = None, note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Survey the subcategory tree of a Wikipedia category WITHOUT collecting articles.
    Use this first to understand how Wikipedia organizes a topic before committing to a pull.

    Args:
        category: Category name without "Category:" prefix. On non-English
                  wikis, pass the category name in that wiki's language
                  (e.g. "Küchengerät" on dewiki).
        depth: How deep to survey (default 2, max 4)
        count_articles: If True, also count total articles across all categories (slower but helps gauge size before pulling)
        wiki: Wikipedia language code to query. Defaults to the active topic's
              wiki, or "en" if no topic is active.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name to infer the wiki from.
    """
    _start = _start_call()
    depth = min(depth, 4)
    wiki = _resolve_wiki(ctx, wiki, topic)
    visited = set()
    by_depth = collections.defaultdict(list)

    queue = collections.deque([(category, 0)])
    visited.add(category)
    by_depth[0].append(category)

    while queue:
        cat, d = queue.popleft()
        if d < depth:
            params = {
                'list': 'categorymembers',
                'cmtitle': f'Category:{cat}',
                'cmtype': 'subcat',
                'cmlimit': '500',
            }
            for item in api_query_all(params, 'categorymembers', wiki=wiki):
                title = item['title']
                if title.startswith('Category:'):
                    title = title[len('Category:'):]
                if title not in visited:
                    visited.add(title)
                    by_depth[d + 1].append(title)
                    queue.append((title, d + 1))

    result = {
        'wiki': wiki,
        'root_category': category,
        'depth_surveyed': depth,
        'total_categories': len(visited),
        'categories_by_depth': {str(d): sorted(cats) for d, cats in sorted(by_depth.items())},
    }

    # Optionally count articles to help gauge size
    if count_articles:
        total_articles = 0
        for cat in visited:
            params = {
                'list': 'categorymembers',
                'cmtitle': f'Category:{cat}',
                'cmtype': 'page',
                'cmnamespace': '0',
                'cmlimit': '500',
            }
            for _ in api_query_all(params, 'categorymembers', max_items=50000, wiki=wiki):
                total_articles += 1
        result['estimated_total_articles'] = total_articles
        if total_articles > 2000:
            result['warning'] = f'This tree contains ~{total_articles} articles. Consider pulling specific subcategories rather than the whole tree.'

    # If the root category came back with no subcategories AND no article count
    # was asked for, that usually means the category name doesn't exist on this
    # wiki — most often because the user meant a different wiki.
    if len(visited) == 1 and not count_articles:
        result['hint'] = (
            f"No subcategories found under 'Category:{category}' on "
            f"{wiki}.wikipedia.org. Either the category is a leaf, or it "
            f"doesn't exist on this wiki. Verify the exact category name on "
            f"{wiki}.wikipedia.org, or check that you're on the intended wiki."
        )

    log_usage(ctx, "survey_categories", {"category": category, "depth": depth, "wiki": wiki},
              f"{len(visited)} categories", start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def check_wikiproject(project_name: str, wiki: str | None = None,
                      note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Check whether a given WikiProject exists on Wikipedia. WikiProjects
    tag articles with assessment banners — if one exists for the topic, it's
    usually the best single source of tagged articles.

    WikiProjects are an English-Wikipedia convention. Most other language
    editions don't maintain them in the same form (no Template:WikiProject
    namespace), so on non-enwiki topics this tool will almost always report
    exists=False — fall back to category and search strategies instead.

    Args:
        project_name: the WikiProject's own name, which is often not identical
            to the topic name. For the topic "Climate change" the project
            happens to also be "Climate change", but for "Hispanic and Latino
            people in STEM" it might be "Latino and Hispanic Americans" or
            "Science". Guess likely names and probe.
        wiki: Wikipedia language code to query. Defaults to the active topic's
              wiki, or "en" if no topic is active.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name to infer the wiki from.
    """
    _start = _start_call()
    wiki = _resolve_wiki(ctx, wiki, topic)
    template_title = f"Template:WikiProject {project_name}"
    params = {'titles': template_title, 'prop': 'info'}
    data = api_query(params, wiki=wiki)
    exists = False
    if 'query' in data and 'pages' in data['query']:
        for page in data['query']['pages']:
            if not page.get('missing', False):
                exists = True

    result = {
        'wiki': wiki,
        'project': project_name,
        'template': template_title,
        'exists': exists,
        'note': 'Use get_wikiproject_articles to fetch all tagged articles' if exists else 'No WikiProject found'
    }
    if wiki != 'en':
        result['warning'] = (
            f"WikiProjects are an enwiki convention and rarely exist on "
            f"{wiki}.wikipedia.org. This check is likely uninformative — "
            f"rely on categories and search instead."
        )
    log_usage(ctx, "check_wikiproject", {"project": project_name, "wiki": wiki},
              f"exists={exists}", start_time=_start, note=note)
    return json.dumps(result)


@mcp.tool()
def find_list_pages(subject: str, wiki: str | None = None,
                    note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Search for Index/List/Outline/Glossary pages about a subject.

    The "Index of", "List of", "Outline of", "Glossary of" prefixes are
    English-specific. On non-enwiki topics this tool almost always returns
    zero results — other-language wikis use different conventions (e.g.
    "Liste der …" on dewiki, "Lista de …" on eswiki). If you're on a
    non-enwiki topic and need list-style pages, use search_articles with
    intitle: and the appropriate prefix for that wiki.

    Args:
        subject: Subject to search for (free text, e.g. "climate change")
        wiki: Wikipedia language code to query. Defaults to the active topic's
              wiki, or "en" if no topic is active.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name to infer the wiki from.
    """
    _start = _start_call()
    wiki = _resolve_wiki(ctx, wiki, topic)
    pages = []
    for prefix in ['Index of', 'List of', 'Outline of', 'Glossary of']:
        params = {
            'list': 'search',
            'srsearch': f'intitle:"{prefix}" intitle:"{subject}"',
            'srnamespace': '0',
            'srlimit': '20',
            'srinfo': '',
            'srprop': '',
        }
        for item in api_query_all(params, 'search', max_items=20, wiki=wiki):
            pages.append(item['title'])

    result = {
        'wiki': wiki,
        'subject': subject,
        'list_pages': pages,
        'count': len(pages),
    }
    if wiki != 'en' and not pages:
        result['hint'] = (
            f"No results on {wiki}.wikipedia.org — the prefixes used here "
            f"('Index of', 'List of', …) are English-specific. Try "
            f"search_articles with the list-page prefix native to this wiki."
        )
    log_usage(ctx, "find_list_pages", {"subject": subject, "wiki": wiki},
              f"{len(pages)} pages", start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── Gathering tools ───────────────────────────────────────────────────────

@mcp.tool()
def get_wikiproject_articles(project_name: str, max_articles: int = 50000,
                              note: str = "",
                              topic: str | None = None, ctx: Context = None) -> str:
    """Get all articles tagged by a WikiProject. Adds them to the working list
    with source 'wikiproject'. WikiProjects are an enwiki convention — this
    tool returns few/no articles on non-English wikis.

    Args:
        project_name: WikiProject name (e.g., "Climate change")
        max_articles: Maximum articles to fetch (default 50000)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    template_title = f"Template:WikiProject {project_name}"
    params = {
        'list': 'embeddedin',
        'eititle': template_title,
        'einamespace': '1',
        'eilimit': '500',
    }

    articles = []
    for item in api_query_all(params, 'embeddedin', max_items=max_articles, wiki=wiki):
        title = item['title']
        if title.startswith('Talk:'):
            title = title[len('Talk:'):]
        title = normalize_title(title)
        articles.append(title)

    source_label = f"wikiproject:{project_name}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "get_wikiproject_articles", {"project": project_name, "wiki": wiki},
              f"{len(articles)} articles", start_time=_start, note=note)
    result = {
        'wiki': wiki,
        'project': project_name,
        'articles_found': len(articles),
        'new_articles_added': added,
        'existing_updated': updated,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
    }
    if wiki != 'en' and len(articles) == 0:
        result['hint'] = (
            f"WikiProjects are rare outside enwiki — {wiki}.wikipedia.org "
            f"probably doesn't tag articles this way. Use categories and "
            f"search_articles instead."
        )
    return json.dumps(result, indent=2, ensure_ascii=False)


def _walk_category_tree(category: str, depth: int, exclude_set: set[str],
                        max_articles: int, wiki: str) -> tuple[set[str], set[str]]:
    """Breadth-first walk of a Wikipedia category tree. Returns (articles,
    visited_cats) — mainspace titles collected from every category visited,
    and the set of category names traversed. Shared between
    get_category_articles and preview_category_pull."""
    articles: set[str] = set()
    visited_cats: set[str] = set()
    visited_cats.add(category)

    queue = collections.deque([(category, 0)])
    while queue and len(articles) < max_articles:
        cat, d = queue.popleft()

        params = {
            'list': 'categorymembers',
            'cmtitle': f'Category:{cat}',
            'cmtype': 'page',
            'cmnamespace': '0',
            'cmlimit': '500',
        }
        for item in api_query_all(params, 'categorymembers', wiki=wiki):
            title = normalize_title(item['title'])
            articles.add(title)
            if len(articles) >= max_articles:
                break

        if d < depth:
            params = {
                'list': 'categorymembers',
                'cmtitle': f'Category:{cat}',
                'cmtype': 'subcat',
                'cmlimit': '500',
            }
            for item in api_query_all(params, 'categorymembers', wiki=wiki):
                subcat = item['title']
                if subcat.startswith('Category:'):
                    subcat = subcat[len('Category:'):]
                if subcat not in visited_cats and subcat not in exclude_set:
                    visited_cats.add(subcat)
                    queue.append((subcat, d + 1))

    return articles, visited_cats


def _scope_drift_warning(category: str, topic_name: str,
                         source_label: str, count: int) -> str | None:
    """Return a scope-drift warning string when a big category pull has no
    word-level overlap with the topic name (e.g. topic='orchids' pulling
    category='Cognition'). None when the pull is OK."""
    if count <= 500 or not topic_name:
        return None
    stopwords = {"a", "an", "and", "of", "in", "on", "for", "to", "the", "by"}
    cat_words = {w for w in re.findall(r"\w+", category.lower()) if w not in stopwords}
    topic_words = {w for w in re.findall(r"\w+", topic_name.lower()) if w not in stopwords}
    if cat_words and topic_words and not (cat_words & topic_words):
        return (
            f"This pull added {count} articles and the category '{category}' "
            f"has no word-level overlap with the topic '{topic_name}'. "
            f"It may be too broad or off-scope. If most of it turns out to be "
            f"noise, use remove_by_source(\"{source_label}\", "
            f"keep_if_other_sources=True) to drop everything that isn't also "
            f"found via a more on-topic source."
        )
    return None


@mcp.tool()
def get_category_articles(category: str, depth: int = 3, exclude: list[str] | None = None,
                          max_articles: int = 50000, note: str = "",
                          topic: str | None = None, ctx: Context = None) -> str:
    """Crawl a category tree and collect all articles. Adds them to the working list
    with source 'category'.

    Args:
        category: Category name without "Category:" prefix
        depth: Maximum depth to crawl (default 3, max 5)
        exclude: Category names to skip (prune entire branches)
        max_articles: Maximum articles to collect (default 50000)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    depth = min(depth, 5)
    exclude_set = set(exclude or [])
    articles, visited_cats = _walk_category_tree(
        category, depth, exclude_set, max_articles, wiki)

    source_label = f"category:{category}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    result = {
        'wiki': wiki,
        'root_category': category,
        'depth': depth,
        'excluded': sorted(exclude_set),
        'articles_found': len(articles),
        'categories_visited': len(visited_cats),
        'new_articles_added': added,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'note': f'To undo this pull, use: remove_by_source("{source_label}")',
    }

    # Noisy-pull warning: large pull with no word-level overlap between the
    # category name and the topic name is a strong signal of scope drift
    # (e.g. topic="educational psychology", category="Cognition").
    _, topic_name, _ = _get_topic(ctx)
    warning = _scope_drift_warning(category, topic_name, source_label, added)
    if warning:
        result['warning'] = warning

    log_usage(ctx, "get_category_articles", {"category": category, "depth": depth, "wiki": wiki},
              f"{len(articles)} articles, {len(visited_cats)} categories",
              start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def preview_category_pull(category: str, depth: int = 3,
                          exclude: list[str] | None = None,
                          max_articles: int = 50000,
                          sample_size: int = 50,
                          note: str = "",
                          topic: str | None = None,
                          ctx: Context = None) -> str:
    """Dry-run of get_category_articles. Walks the category tree and reports
    article / category counts + a sampled preview with descriptions WITHOUT
    committing anything. Use when you want to gauge the shape of a subtree
    before deciding whether to pull it, or when a `survey_categories`
    warning flagged the tree as potentially oversized.

    Args:
        category: Category name without "Category:" prefix
        depth: Maximum depth to crawl (default 3, max 5)
        exclude: Category names to skip (prune entire branches)
        max_articles: Upper bound on articles to enumerate during preview.
                      Same semantics as get_category_articles.
        sample_size: How many titles to return in the sample (default 50).
                     Descriptions are only fetched for the sample.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    depth = min(depth, 5)
    exclude_set = set(exclude or [])
    articles_set, visited_cats = _walk_category_tree(
        category, depth, exclude_set, max_articles, wiki)

    articles = sorted(articles_set)
    existing = db.get_all_titles(topic_id)
    new_count = sum(1 for t in articles if t not in existing)
    overlap_count = len(articles) - new_count

    sample_titles = articles[:max(0, sample_size)]
    descriptions = fetch_short_descriptions(sample_titles, wiki=wiki) if sample_titles else {}
    sample = [
        {
            'title': t,
            'description': descriptions.get(t, ''),
            'already_in_topic': t in existing,
        }
        for t in sample_titles
    ]

    would_be_source_label = f"category:{category}"
    result = {
        'wiki': wiki,
        'root_category': category,
        'depth': depth,
        'excluded': sorted(exclude_set),
        'total_articles': len(articles),
        'categories_visited': len(visited_cats),
        'new_to_topic': new_count,
        'already_in_topic': overlap_count,
        'sample': sample,
        'would_be_source_label': would_be_source_label,
        'note': (
            'Nothing added to the working list. Review the sample + counts, '
            'then call get_category_articles(category) to commit, or pass '
            'exclude=[...] to prune branches first. Skip entirely if the '
            'subtree is too broad.'
        ),
    }

    _, topic_name, _ = _get_topic(ctx)
    warning = _scope_drift_warning(category, topic_name, would_be_source_label, new_count)
    if warning:
        result['warning'] = warning

    log_usage(ctx, "preview_category_pull",
              {"category": category, "depth": depth, "wiki": wiki,
               "sample_size": sample_size},
              f"{len(articles)} articles ({new_count} new), {len(visited_cats)} categories",
              start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


_MAIN_CONTENT_EXCLUDED_CLASSES = {
    'navbox', 'navbox-styles', 'sidebar', 'sidebar-content',
    'infobox', 'metadata', 'reflist', 'references',
    'mw-editsection', 'catlinks', 'toc', 'thumbcaption',
    'hatnote', 'dablink', 'shortdescription', 'noprint',
    'mw-references-wrap',
}
_MAIN_CONTENT_EXCLUDED_SECTION_IDS = {
    'See_also', 'External_links', 'References', 'Further_reading',
    'Notes', 'Bibliography', 'Sources', 'Citations', 'Footnotes',
}


_VOID_ELEMENTS = {
    'br', 'img', 'hr', 'input', 'meta', 'link', 'area', 'base',
    'col', 'embed', 'source', 'track', 'wbr', 'param',
}


class _MainContentLinkExtractor(html.parser.HTMLParser):
    """Walk a Wikipedia-rendered HTML fragment and collect <a href> targets
    pointing to mainspace articles, excluding anything under navbox/sidebar/
    reflist/etc. or past a See_also/External_links/References heading.

    Uses a proper tag stack so end-tags only pop their matching open element
    — naively counting depth by any endtag would let an <a></a> inside a
    navbox prematurely exit the excluded region, which was the initial bug."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._seen = set()
        self._stack = []  # list of (tag, is_excluded)
        self._excluded_depth = 0
        self._past_excluded_heading = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        classes = set(attr_dict.get('class', '').split()) if attr_dict.get('class') else set()
        is_excluded = bool(classes & _MAIN_CONTENT_EXCLUDED_CLASSES)

        if tag not in _VOID_ELEMENTS:
            self._stack.append((tag, is_excluded))
            if is_excluded:
                self._excluded_depth += 1
                return

        if self._excluded_depth > 0:
            return
        # Headings use the heading element's own id OR a nested
        # <span class="mw-headline" id="Section_Name"> depending on skin.
        if tag in ('h2', 'h3', 'h4', 'span'):
            elem_id = attr_dict.get('id', '')
            if elem_id in _MAIN_CONTENT_EXCLUDED_SECTION_IDS:
                self._past_excluded_heading = True
                return
        if self._past_excluded_heading:
            return
        if tag == 'a':
            # Prefer the title="..." attribute — MediaWiki sets it to the
            # target page title for both blue links (<a href="/wiki/X">) and
            # red links (<a href="/w/index.php?title=X&redlink=1"> — which
            # would be filtered out if we matched on href alone). For
            # redlinks the title attribute ends with " (page does not
            # exist)"; strip that suffix.
            link_title = attr_dict.get('title', '').strip()
            href = attr_dict.get('href', '')
            # Only consider anchors that look like wiki links (internal
            # links have either /wiki/ or /w/index.php?title=).
            is_wiki_link = (href.startswith('/wiki/')
                            or '/w/index.php?title=' in href)
            if not is_wiki_link or not link_title:
                return
            if link_title.endswith(' (page does not exist)'):
                link_title = link_title[:-len(' (page does not exist)')].strip()
            # mainspace only — skip namespaced pages (File:, Category:, etc.)
            if ':' in link_title:
                return
            if link_title in self._seen:
                return
            self._seen.add(link_title)
            self.links.append(link_title)

    def handle_endtag(self, tag):
        # Pop the matching open tag. Real-world Wikipedia HTML has some
        # unclosed <p> / <li> / <img> etc., so seek backward for the match
        # and discard anything above it as malformed.
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                popped = self._stack[i:]
                self._stack = self._stack[:i]
                for _, was_excl in popped:
                    if was_excl:
                        self._excluded_depth -= 1
                return


def _fetch_list_page_links(title: str, wiki: str,
                           main_content_only: bool) -> tuple[list[str], bool]:
    """Fetch mainspace links from a list/outline page.

    Returns (links, main_content_only_actual). The second return reflects
    whether the HTML parse path succeeded — when `main_content_only=True`
    but the page's HTML came back empty (missing page, parse error), we
    fall back to prop=links and return the second value as False so the
    caller can surface that to the user."""
    if main_content_only:
        parse_params = {
            'action': 'parse',
            'page': title,
            'prop': 'text',
            'format': 'json',
            'formatversion': '2',
            'redirects': '1',
            'disabletoc': '1',
            'disableeditsection': '1',
        }
        data = api_get(wiki_api_url(wiki), parse_params)
        html_text = data.get('parse', {}).get('text', '')
        if html_text:
            extractor = _MainContentLinkExtractor()
            extractor.feed(html_text)
            return [normalize_title(t) for t in extractor.links], True
        main_content_only = False

    params = {
        'action': 'query',
        'titles': title,
        'prop': 'links',
        'plnamespace': '0',
        'pllimit': '500',
        'format': 'json',
        'formatversion': '2',
    }
    links = []
    while True:
        data = api_get(wiki_api_url(wiki), params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                for link in page.get('links', []):
                    links.append(normalize_title(link['title']))
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break
    return links, False


@mcp.tool()
def harvest_list_page(title: str, main_content_only: bool = True,
                      note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Extract article links from a List/Index/Glossary page. Adds them
    to the working list with source 'list_page'.

    Args:
        title: Page title (e.g., "Index of climate change articles")
        main_content_only: If True (default), parse the rendered HTML and
            collect links only from the article body — skipping navboxes,
            sidebars, infoboxes, reference lists, and anything past a
            "See also" / "External links" / "References" heading. This is
            the right default for List/Index/Outline pages where navbox
            noise routinely dominates the link count (68% in one observed
            orchids case). Set False to fall back to the raw `prop=links`
            API, which returns every mainspace link on the page including
            navigation chrome — useful for "Outline of …" pages whose
            curated content lives in navigation templates, or for broad
            category-like list pages.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    links, used_html = _fetch_list_page_links(title, wiki, main_content_only)

    source_label = f"list_page:{title}"
    batch = [(t, source_label, None) for t in links]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "harvest_list_page",
              {"title": title, "wiki": wiki, "main_content_only": used_html},
              f"{len(links)} links, {added} new", start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'source_page': title,
        'main_content_only': used_html,
        'links_found': len(links),
        'new_articles_added': added,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'note': (
            f'To undo this harvest, use: remove_by_source("{source_label}"). '
            f'Pass main_content_only=False if you want the raw link set '
            f'including navboxes and navigation chrome. Use '
            f'preview_harvest_list_page first if you want to inspect before '
            f'committing.'
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def preview_harvest_list_page(title: str, sample_size: int = 50,
                              main_content_only: bool = True,
                              note: str = "",
                              topic: str | None = None,
                              ctx: Context = None) -> str:
    """Dry-run of harvest_list_page. Fetches the page's links but does NOT
    add anything to the working list. Returns the link count, new-vs-
    already-in-topic counts, and a sample of titles + Wikidata short
    descriptions so the AI/user can inspect before committing.

    Good for list pages you're not sure about — especially geographic or
    biodiversity lists where navbox contamination is common even with
    `main_content_only=True`, or "Outline of …" pages where you want to
    know up front whether the curated content lives in navboxes.

    Args:
        title: Page title (e.g., "List of orchid genera").
        sample_size: How many titles to return in the sample (default 50).
                     Only the sample pays for description fetches; the
                     full link list is cheap.
        main_content_only: Same semantics as harvest_list_page. Default True.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    links, used_html = _fetch_list_page_links(title, wiki, main_content_only)
    existing = db.get_all_titles(topic_id)
    new_count = sum(1 for t in links if t not in existing)
    overlap_count = len(links) - new_count

    sample_titles = links[:max(0, sample_size)]
    descriptions = fetch_short_descriptions(sample_titles, wiki=wiki) if sample_titles else {}
    sample = [
        {
            'title': t,
            'description': descriptions.get(t, ''),
            'already_in_topic': t in existing,
        }
        for t in sample_titles
    ]

    would_be_source_label = f"list_page:{title}"
    log_usage(ctx, "preview_harvest_list_page",
              {"title": title, "wiki": wiki, "main_content_only": used_html,
               "sample_size": sample_size},
              f"{len(links)} links ({new_count} new)",
              start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'source_page': title,
        'main_content_only': used_html,
        'total_links': len(links),
        'new_to_topic': new_count,
        'already_in_topic': overlap_count,
        'sample': sample,
        'would_be_source_label': would_be_source_label,
        'note': (
            'Nothing added to the working list. Review the sample, then '
            'call harvest_list_page(title) to commit, or skip entirely '
            'if the preview looks noisy. Pass main_content_only=False to '
            'see the raw prop=links set including navigation chrome.'
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def search_articles(query: str, limit: int = 500, note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Search Wikipedia using CirrusSearch. Supports operators like intitle:,
    morelike:, hastemplate:, incategory:. Adds results to working list with source 'search'.

    Args:
        query: Search query (e.g., 'intitle:"climate change"', 'morelike:Effects of climate change')
        limit: Maximum results (default 500)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    params = {
        'list': 'search',
        'srsearch': query,
        'srnamespace': '0',
        'srlimit': str(min(limit, 500)),
        'srinfo': '',
        'srprop': '',
    }

    results = []
    for item in api_query_all(params, 'search', max_items=limit, wiki=wiki):
        results.append(item['title'])

    # Tag with the specific query so remove_by_source / get_articles_by_source
    # can target one bad pull without blanket-touching all search-added articles.
    # Use prefix_match=True on remove_by_source to clear a family of queries
    # (e.g. "search:morelike:" drops every similarity pull at once).
    source_label = f"search:{query}"
    batch = [(title, source_label, None) for title in results]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "search_articles", {"query": query, "wiki": wiki},
              f"{len(results)} results", start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'query': query,
        'source_label': source_label,
        'results_found': len(results),
        'new_articles_added': added,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'note': f'To undo this pull, use: remove_by_source("{source_label}")',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def search_similar(seed_article: str, limit: int = 50, note: str = "",
                   topic: str | None = None, ctx: Context = None) -> str:
    """Find articles similar to a given article using CirrusSearch morelike:.
    Great for finding thematic clusters the other strategies miss.

    Args:
        seed_article: Article title to find similar articles to
        limit: Maximum results (default 50)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    return search_articles(f'morelike:{seed_article}', limit=limit, note=note,
                           topic=topic, ctx=ctx)


@mcp.tool()
def preview_search(query: str, limit: int = 50, note: str = "",
                   topic: str | None = None, ctx: Context = None) -> str:
    """Run a Wikipedia search and return titles + short descriptions WITHOUT
    adding anything to the working list. Use this before committing broad
    searches (morelike:, keyword searches without a demographic anchor) — the
    AI/user can review titles+descriptions and then commit a filtered subset
    via add_articles(titles=[...]), or skip entirely if the query was noisy.

    Each previewed result is flagged `already_in_topic: true` if the title
    is already in the working list, so the AI can focus on what's new.

    Args:
        query: Same syntax as search_articles (intitle:, morelike:,
               incategory:, hastemplate:, etc.)
        limit: Max results to preview (default 50, capped at 100).
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an
               MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    limit = min(limit, 100)
    params = {
        'list': 'search',
        'srsearch': query,
        'srnamespace': '0',
        'srlimit': str(limit),
        'srinfo': '',
        'srprop': '',
    }

    titles = []
    for item in api_query_all(params, 'search', max_items=limit, wiki=wiki):
        titles.append(item['title'])

    if not titles:
        return json.dumps({
            'wiki': wiki,
            'query': query,
            'results_found': 0,
            'results': [],
        }, indent=2, ensure_ascii=False)

    descriptions = fetch_short_descriptions(titles, wiki=wiki)
    existing = db.get_all_titles(topic_id)

    results = []
    new_count = 0
    for t in titles:
        in_topic = t in existing
        if not in_topic:
            new_count += 1
        results.append({
            'title': t,
            'description': descriptions.get(t, ''),
            'already_in_topic': in_topic,
        })

    log_usage(ctx, "preview_search", {"query": query, "limit": limit, "wiki": wiki},
              f"{len(titles)} results ({new_count} new)",
              start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'query': query,
        'results_found': len(titles),
        'new_to_topic': new_count,
        'already_in_topic': len(titles) - new_count,
        'results': results,
        'note': ('Nothing added to the working list. Review the titles + '
                 'descriptions, then call add_articles(titles=[...]) with a '
                 'filtered subset. Skip entirely if the query is too noisy.'),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def preview_similar(seed_article: str, limit: int = 50, note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Read-only preview of morelike: results for a seed article. Returns
    titles + descriptions + already_in_topic flags WITHOUT adding anything
    to the working list. Use this before `search_similar` — the AI/user can
    review and then commit a filtered subset via add_articles, or skip
    entirely if the seed turned out to be a bad choice.

    `search_similar` pulls are especially prone to noise when the seed is a
    biographical hub (a polymath's filmography, a politically-prominent
    figure's broad edges) or when the seed is a novel/film whose adaptation
    has its own strong edge graph. Preview first, commit second.

    Args:
        seed_article: Article title to find similar articles to.
        limit: Max results to preview (default 50, capped at 100 by
               preview_search).
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    return preview_search(f'morelike:{seed_article}', limit=limit, note=note,
                          topic=topic, ctx=ctx)


# ── Review aids ───────────────────────────────────────────────────────────

@mcp.tool()
def fetch_descriptions(limit: int = 500, note: str = "",
                       topic: str | None = None, ctx: Context = None) -> str:
    """Fetch Wikidata short descriptions for articles in the current topic
    that don't have one yet, and persist them. Descriptions show up in
    get_articles / get_articles_by_source output so the AI or user can judge
    relevance while paging or reviewing a source. export_csv also reuses them.

    Batches of 50 titles per API call. An article with no short-desc on
    Wikipedia is stored as an empty string (so we don't re-ask next time).

    Args:
        limit: Max titles to fetch in this call (default 500). If more
               articles are undescribed afterward, call again to continue.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an
               MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    titles = db.get_undescribed_titles(topic_id, limit=limit)
    if not titles:
        return json.dumps({
            'fetched': 0,
            'remaining_undescribed': 0,
            'note': 'All articles in this topic already have descriptions (or were checked).',
        }, indent=2, ensure_ascii=False)

    desc_map = fetch_short_descriptions(titles, wiki=wiki)
    db.set_descriptions(topic_id, desc_map)

    non_empty = sum(1 for v in desc_map.values() if v)
    remaining = db.count_undescribed(topic_id)

    log_usage(ctx, "fetch_descriptions", {"limit": limit},
              f"fetched {len(titles)} ({non_empty} non-empty), {remaining} still undescribed",
              start_time=_start, note=note)
    return json.dumps({
        'fetched': len(titles),
        'non_empty': non_empty,
        'remaining_undescribed': remaining,
        'note': ('Descriptions now available in get_articles / get_articles_by_source / export_csv. '
                 'Call fetch_descriptions again to continue.' if remaining
                 else 'All articles in this topic now have descriptions (or were checked).'),
    }, indent=2, ensure_ascii=False)


# ── Scoring tools ─────────────────────────────────────────────────────────

@mcp.tool()
def score_by_extract(titles: list[str] | None = None, unscored_batch: bool = False,
                     batch_size: int = 50, note: str = "",
                     topic: str | None = None, ctx: Context = None) -> str:
    """Fetch article extracts (first 5 sentences) from Wikipedia for scoring.
    Returns the extracts so you can judge relevance on a 1-10 scale.

    Args:
        titles: Specific titles to score. If None and unscored_batch=True, fetches unscored articles.
        unscored_batch: If True and titles is None, fetch a batch of unscored articles
        batch_size: How many articles to fetch (default 50, max 50)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    batch_size = min(batch_size, 50)

    if titles:
        to_score = titles[:batch_size]
    elif unscored_batch:
        articles, _ = db.get_articles(topic_id, unscored_only=True, limit=batch_size)
        to_score = [a['title'] for a in articles]
    else:
        return "Provide titles or set unscored_batch=True"

    if not to_score:
        return "No articles to score."

    params = {
        'titles': '|'.join(to_score),
        'prop': 'extracts',
        'exintro': 'true',
        'explaintext': 'true',
        'exsentences': '5',
    }
    data = api_query(params, wiki=wiki)

    extracts = {}
    if 'query' in data and 'pages' in data['query']:
        for page in data['query']['pages']:
            if not page.get('missing', False):
                extracts[normalize_title(page['title'])] = page.get('extract', '')

    all_articles = db.get_all_articles_dict(topic_id)
    results = []
    for title in to_score:
        extract = extracts.get(title, '')
        article = all_articles.get(title, {})
        results.append({
            'title': title,
            'extract': extract[:500] if extract else '(no extract available)',
            'sources': article.get('sources', []),
            'current_score': article.get('score'),
        })

    log_usage(ctx, "score_by_extract",
              {"batch_size": batch_size, "unscored_batch": unscored_batch,
               "titles_count": len(titles) if titles else 0},
              f"{len(results)} extracts", start_time=_start, note=note)
    return json.dumps({
        'articles': results,
        'count': len(results),
        'note': 'Score each article 1-10 for topic relevance, then use set_scores to save.',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def set_scores(scores: dict[str, int], note: str = "",
               topic: str | None = None, ctx: Context = None) -> str:
    """Set relevance scores for articles. Scores should be 1-10.

    Args:
        scores: Dict mapping article title to score (e.g., {"Article Name": 8, "Other Article": 3})
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    updated = db.set_scores(topic_id, scores)
    log_usage(ctx, "set_scores", {"scores_count": len(scores)},
              f"updated {updated}", start_time=_start, note=note)
    return f"Updated scores for {updated} articles."


@mcp.tool()
def auto_score_by_title(threshold: int = 7, note: str = "",
                        topic: str | None = None, ctx: Context = None) -> str:
    """Quick title-based scoring pass for obvious cases. Articles with clear topic
    keywords in the title get auto-scored.

    Args:
        threshold: Score to assign to keyword-matched articles (default 7)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name, _ = _get_topic(ctx)
    topic_phrase = topic_name.lower()
    all_articles = db.get_all_articles_dict(topic_id)

    scores = {}
    for title, article in all_articles.items():
        if article.get('score') is not None:
            continue
        if topic_phrase in title.lower():
            scores[title] = min(threshold + 2, 10)

    if scores:
        db.set_scores(topic_id, scores)

    unscored = sum(1 for a in all_articles.values() if a.get('score') is None) - len(scores)
    log_usage(ctx, "auto_score_by_title", {"threshold": threshold, "phrase": topic_phrase},
              f"scored {len(scores)}, {unscored} still unscored",
              start_time=_start, note=note)
    return f"Auto-scored {len(scores)} articles containing '{topic_phrase}' in title. ~{unscored} still unscored."


@mcp.tool()
def auto_score_by_description(
    required_any: dict[str, list[str]],
    disqualifying: list[str] | None = None,
    overwrite_scored: bool = False,
    dry_run: bool = True,
    note: str = "",
    topic: str | None = None, ctx: Context = None,
) -> str:
    """Auto-score articles as 0 ("irrelevant") when their Wikidata short
    description clearly disqualifies them. Use this after fetch_descriptions
    to eliminate obvious noise without manual review, leaving a much smaller
    ambiguous set to look at by hand.

    TWO FAILURE MODES TO WATCH FOR:

    1. Implicit-axis leakage. If the topic is intersectional and one axis
       is often NOT stated in Wikipedia's shortdesc ("American
       neuroscientist" for a Mexican-American scientist, where the shortdesc
       elides the ethnicity), requiring that axis cuts genuine topic members.
       Prefer to only require axes that shortdescs reliably contain, or run
       with disqualifying markers alone and keep axes off. The tool surfaces
       a warning when axes dominate the cut.
    2. Over-broad markers. A marker like "artist" matches "martial artist";
       "poll" matches "polling". Matching uses word boundaries to mitigate
       this but not every case is safe — review samples_by_reason on the
       dry-run before applying.

    `required_any` is a dict of labeled axes. For each axis, the description
    must match at least one marker from that axis's list. An article missing
    a match on ANY axis is scored 0. Axis labels appear in the breakdown so
    the AI can present cuts to the user in plain language (e.g. "450 had no
    profession marker" rather than "axis 2"). Pass an empty dict to rely on
    disqualifying markers alone (the safest mode).

    `disqualifying` markers score the article 0 regardless of axis matches.
    These tend to be the safest cutter for intersectional topics because
    off-scope professions (actor, musician, footballer, politician) are
    usually explicit in the shortdesc.

    Matching is case-insensitive and word-boundary. Descriptions are
    pre-normalized so hyphens become spaces ("Mexican-American chemist"
    matches marker "mexican american" or "american").

    Only writes score=0 — never positives. "Has matching markers" is
    necessary but not sufficient evidence of relevance (e.g. Brazilian-
    American physicists may or may not count depending on the user's
    Latin/Hispanic scope). Positive scoring stays with humans.

    Args:
        required_any: Labeled axes, each a list of markers. Example for
            "Hispanic/Latino people in STEM":
              {
                "demographic": ["hispanic","latino","latina","mexican",
                                "puerto rican","cuban","colombian", ...],
                "profession":  ["scientist","physicist","chemist","engineer",
                                "mathematician","astronaut","inventor", ...],
              }
        disqualifying: Markers that force score=0 regardless, e.g.
                       ["actor","musician","footballer","politician"].
        overwrite_scored: If False (default), skip articles that already
            have a score — don't clobber human judgment. If True, apply 0
            even to articles with existing non-zero scores when they hit
            disqualifying criteria.
        dry_run: If True (default), preview counts + samples without
                 applying. Set False to apply the score=0 writes.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.

    Articles with NULL descriptions (not yet fetched) are skipped, not
    auto-zeroed — run fetch_descriptions first to include them.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    disqualifying = disqualifying or []
    if not required_any and not disqualifying:
        return json.dumps({
            'error': 'Provide required_any axes and/or disqualifying markers.',
        })

    def _compile(markers):
        return [(m, re.compile(r'\b' + re.escape(m.lower()) + r'\b'))
                for m in markers]

    axis_patterns = {name: _compile(markers) for name, markers in required_any.items()}
    disqual_patterns = _compile(disqualifying)

    all_articles = db.get_all_articles_dict(topic_id)

    would_zero = []  # (title, desc, reason)
    survivors = []   # (title, desc)
    skipped_already_scored = 0
    skipped_no_description = 0
    reason_counts = collections.Counter()

    for title, article in all_articles.items():
        score = article.get('score')
        if score is not None and not overwrite_scored:
            skipped_already_scored += 1
            continue
        desc = article.get('description')
        if desc is None:
            skipped_no_description += 1
            continue

        desc_norm = desc.lower().replace('-', ' ')

        # Disqualifying markers take priority (clearer reason string).
        disqual_hit = next((m for m, pat in disqual_patterns
                            if pat.search(desc_norm)), None)
        if disqual_hit:
            reason = f'disqualifying:{disqual_hit}'
            would_zero.append((title, desc, reason))
            reason_counts[reason] += 1
            continue

        # Axis check: missing a match on any axis → 0.
        missing_axis = None
        for axis_name, patterns in axis_patterns.items():
            if not any(pat.search(desc_norm) for _, pat in patterns):
                missing_axis = axis_name
                break
        if missing_axis:
            reason = f'missing_{missing_axis}'
            would_zero.append((title, desc, reason))
            reason_counts[reason] += 1
        else:
            survivors.append((title, desc))

    if not dry_run and would_zero:
        db.set_scores(topic_id, {t: 0 for t, _, _ in would_zero})
        log_usage(ctx, "auto_score_by_description",
                  {"axes": list(required_any.keys()),
                   "disqualifying_count": len(disqualifying)},
                  f"scored 0: {len(would_zero)}",
                  start_time=_start, note=note)
    elif dry_run:
        log_usage(ctx, "auto_score_by_description",
                  {"axes": list(required_any.keys()),
                   "disqualifying_count": len(disqualifying),
                   "dry_run": True},
                  f"would score 0: {len(would_zero)}",
                  start_time=_start, note=note)

    # Group samples by reason (up to 5 each) so the AI/user can spot patterns:
    # e.g. if "missing_demographic: 1300" is accompanied by samples like
    # "American neuroscientist" / "American engineer" / "American chemist",
    # the axis is probably cutting through legitimate members whose shortdesc
    # omits the demographic qualifier — a signal to drop that axis.
    samples_by_reason = {}
    for t, d, r in would_zero:
        samples_by_reason.setdefault(r, [])
        if len(samples_by_reason[r]) < 5:
            samples_by_reason[r].append({'title': t, 'description': d})

    result = {
        'dry_run': dry_run,
        ('would_score_zero' if dry_run else 'scored_zero'): len(would_zero),
        'skipped_already_scored': skipped_already_scored,
        'skipped_no_description': skipped_no_description,
        'survivors_unscored': len(survivors),
        'breakdown_by_reason': dict(reason_counts.most_common()),
        'samples_by_reason': samples_by_reason,
        'sample_survivors_unscored': [
            {'title': t, 'description': d} for t, d in survivors[:10]
        ],
        'note': ('Set dry_run=False to apply the score=0 writes.' if dry_run
                 else 'Scores applied. Sample survivors above still need review.'),
    }
    if skipped_no_description:
        result['hint'] = (f'{skipped_no_description} articles have no '
                          'description yet; call fetch_descriptions to include '
                          'them in the next pass.')
    # Warn when axes dominate — a common failure mode for intersectional
    # topics where one axis (typically demographic) is often implicit in
    # Wikipedia shortdescs ("American scientist" for a Mexican-American).
    axis_cuts = sum(v for k, v in reason_counts.items() if k.startswith('missing_'))
    if axis_cuts and axis_cuts > 2 * len(survivors) and axis_cuts > 200:
        result['warning'] = (
            'Axes are doing most of the cutting. If the missing-axis samples '
            'look like genuine topic members whose description just omits that '
            'axis (e.g. "American scientist" with no ethnic qualifier), the '
            'axis is too strict — Wikipedia shortdescs often elide implicit '
            'identity. Consider dropping that axis and relying on '
            'disqualifying markers only, or tighten the axis to markers the '
            'description would reliably contain.'
        )
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def score_all_unscored(score: int = 8, note: str = "",
                       topic: str | None = None, ctx: Context = None) -> str:
    """Set a score for ALL currently unscored articles in one operation.
    Use this after you've already pruned the list down to on-topic articles
    and just need to mark everything as scored for export.

    Args:
        score: Score to assign to all unscored articles (default 8)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    scores = {title: score for title, article in all_articles.items()
              if article.get('score') is None}

    if scores:
        db.set_scores(topic_id, scores)

    log_usage(ctx, "score_all_unscored", {"score": score},
              f"scored {len(scores)}", start_time=_start, note=note)
    return f"Scored {len(scores)} previously unscored articles at {score}. All articles are now scored."


# ── Edge browsing ─────────────────────────────────────────────────────────

@mcp.tool()
def browse_edges(seed_titles: list[str], min_links: int = 3, note: str = "",
                 topic: str | None = None, ctx: Context = None) -> str:
    """Browse outgoing links from seed articles to find related articles not yet
    in the working list. Articles linked by multiple seeds are most likely relevant.

    Args:
        seed_titles: Articles to browse from (pick peripheral/edge articles for best results)
        min_links: Minimum seed articles that must link to a candidate (default 3)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    link_counts = collections.Counter()
    existing = db.get_all_titles(topic_id)

    for seed in seed_titles:
        params = {
            'action': 'query',
            'titles': seed,
            'prop': 'links',
            'plnamespace': '0',
            'pllimit': '500',
            'format': 'json',
            'formatversion': '2',
        }
        while True:
            data = api_get(wiki_api_url(wiki), params)
            if 'query' in data and 'pages' in data['query']:
                for page in data['query']['pages']:
                    for link in page.get('links', []):
                        t = normalize_title(link['title'])
                        if t not in existing:
                            link_counts[t] += 1
            if 'continue' in data:
                params.update(data['continue'])
            else:
                break

    candidates = [(t, c) for t, c in link_counts.most_common() if c >= min_links]

    log_usage(ctx, "browse_edges",
              {"seeds": len(seed_titles), "min_links": min_links, "wiki": wiki},
              f"{len(candidates)} candidates", start_time=_start, note=note)
    return json.dumps({
        'seeds_browsed': len(seed_titles),
        'candidates': [{'title': t, 'linked_by': c} for t, c in candidates[:100]],
        'total_candidates': len(candidates),
        'note': 'Use add_articles to add relevant candidates, or score_by_extract to investigate.',
    }, indent=2, ensure_ascii=False)


# ── List management ───────────────────────────────────────────────────────

@mcp.tool()
def list_sources(note: str = "", topic: str | None = None, ctx: Context = None) -> str:
    """List every source label currently attached to articles in the working list,
    with counts. Call this before remove_by_source to see exactly what labels
    you can target. Each gather tool records a specific source label:
    "category:Cognition", "wikiproject:Climate change", "list_page:List of X",
    "search:morelike:Mario Molina", "search:incategory:American women chemists".

    Args:
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    counts = collections.Counter()
    for article in all_articles.values():
        for s in article.get('sources', []):
            counts[s] += 1

    sources = [{'source': s, 'count': c} for s, c in counts.most_common()]
    log_usage(ctx, "list_sources", {}, f"{len(sources)} sources",
              start_time=_start, note=note)
    return json.dumps({
        'sources': sources,
        'total_distinct_sources': len(sources),
        'note': ('To drop a noisy pull while keeping articles that also appear '
                 'under another source, use remove_by_source(source, '
                 'keep_if_other_sources=True). To drop a family of labels at '
                 'once (e.g. every morelike: search), use '
                 'remove_by_source("search:morelike:", prefix_match=True).'),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def add_articles(titles: list[str], source: str = "manual", score: int | None = None,
                 note: str = "",
                 topic: str | None = None, ctx: Context = None) -> str:
    """Add articles to the working list. Use this when you want to add articles
    you've discovered or identified yourself, outside of the other gather tools.

    Args:
        titles: Article titles to add
        source: Source label. For hand-curated additions prefer 'manual:<context>'
                over bare 'manual' — e.g. 'manual:veitch-cluster',
                'manual:cross-wiki-reconciliation-nl'. The <context> makes the
                audit trail self-describing and enables selective undo via
                remove_by_source. Bare 'manual' works but loses provenance.
        score: Optional relevance score to assign (1-10)
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    batch = [(normalize_title(t), source, score) for t in titles]
    added, updated = db.add_articles(topic_id, batch)
    total = db.get_status(topic_id)['total_articles']
    log_usage(ctx, "add_articles",
              {"source": source, "titles_count": len(titles), "score": score},
              f"added {added}, updated {updated}", start_time=_start, note=note)
    return f"Added {added} new articles, updated {updated} (source: {source}). Total: {total}"


@mcp.tool()
def get_articles_by_source(source: str, exclude_sources: list[str] | None = None,
                           limit: int = 100, offset: int = 0, note: str = "",
                           topic: str | None = None, ctx: Context = None) -> str:
    """Get articles that came from a specific source, optionally excluding articles
    that also came from other sources. Useful for reviewing noisy sources like list page harvests.

    For example: get_articles_by_source("list_page", exclude_sources=["category", "wikiproject"])
    returns articles ONLY found via list pages — the ones most likely to be noise.

    Args:
        source: Source to filter by (e.g., "list_page", "category", "wikiproject", "search")
        exclude_sources: If set, exclude articles that also have any of these sources
        limit: Max articles to return (default 100)
        offset: Pagination offset
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    exclude = set(exclude_sources or [])

    matches = []
    for title, article in sorted(all_articles.items()):
        sources = article.get('sources', [])
        if source not in sources:
            continue
        if exclude and any(s in exclude for s in sources):
            continue
        matches.append({'title': title, 'description': article.get('description') or ''})

    total = len(matches)
    page = matches[offset:offset + limit]

    log_usage(ctx, "get_articles_by_source",
              {"source": source, "exclude_sources": exclude_sources,
               "limit": limit, "offset": offset},
              f"{total} matches", start_time=_start, note=note)
    return json.dumps({
        'source': source,
        'excluding': sorted(exclude) if exclude else None,
        'articles': page,
        'showing': f"{offset + 1}-{offset + len(page)} of {total}",
        'total_matching': total,
        'note': 'Descriptions come from stored Wikidata short-descs. Call fetch_descriptions if they are blank and you want them populated.',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def remove_articles(titles: list[str], note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Remove articles from the working list.

    Args:
        titles: Article titles to remove
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    removed = db.remove_articles(topic_id, titles)
    total = db.get_status(topic_id)['total_articles']
    log_usage(ctx, "remove_articles", {"titles_count": len(titles)},
              f"removed {removed}", start_time=_start, note=note)
    return f"Removed {removed} articles. Total: {total}"


@mcp.tool()
def remove_by_source(source: str, keep_if_other_sources: bool = True,
                     prefix_match: bool = False, dry_run: bool = True,
                     note: str = "",
                     topic: str | None = None, ctx: Context = None) -> str:
    """Remove all articles that came from a specific source. Use this to undo a bad
    category pull, noisy list harvest, or noisy search query.

    With prefix_match=True, matches every source label starting with the given
    string — e.g. `remove_by_source("search:morelike:", prefix_match=True)`
    clears every similarity search at once, and `remove_by_source("search:",
    prefix_match=True)` clears everything that came via search_articles.

    Args:
        source: Source label to remove (e.g., "category:Learning methods",
                "list_page:List of printmakers", "search:morelike:Mario Molina").
                With prefix_match=True, any source label starting with this
                string is matched.
        keep_if_other_sources: If True (default), keep articles that also have OTHER sources
                               (under the matched label, or any non-matching label).
                               If False, remove all matching articles regardless.
        prefix_match: If True, match source labels that START WITH `source`.
                      Default False (exact match).
        dry_run: If True (default), preview what would be removed without actually removing.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)

    def matches(s: str) -> bool:
        return s.startswith(source) if prefix_match else s == source

    to_remove = []
    to_keep = []
    matched_labels = set()  # for reporting
    for title, article in all_articles.items():
        sources = article.get('sources', [])
        article_matches = [s for s in sources if matches(s)]
        if not article_matches:
            continue
        matched_labels.update(article_matches)
        other_sources = [s for s in sources if s not in article_matches]
        if keep_if_other_sources and other_sources:
            to_keep.append(title)
        else:
            to_remove.append(title)

    if dry_run:
        log_usage(ctx, "remove_by_source",
                  {"source": source, "prefix_match": prefix_match,
                   "keep_if_other_sources": keep_if_other_sources, "dry_run": True},
                  f"would remove {len(to_remove)}, keep {len(to_keep)}",
                  start_time=_start, note=note)
        return json.dumps({
            'source': source,
            'prefix_match': prefix_match,
            'matched_labels': sorted(matched_labels),
            'would_remove': len(to_remove),
            'would_keep_(other_sources)': len(to_keep),
            'sample_remove': to_remove[:20],
            'sample_keep': to_keep[:10],
            'note': 'Set dry_run=False to actually remove.',
        }, indent=2, ensure_ascii=False)

    removed = db.remove_articles(topic_id, to_remove)
    # Also strip matching sources from articles we kept
    if to_keep:
        for title in to_keep:
            article = all_articles[title]
            new_sources = [s for s in article['sources'] if not matches(s)]
            db.update_article_sources(topic_id, title, new_sources)

    total = db.get_status(topic_id)['total_articles']
    desc = f"{len(matched_labels)} source label(s)" if prefix_match else f"source '{source}'"
    log_usage(ctx, "remove_by_source",
              {"source": source, "prefix_match": prefix_match,
               "keep_if_other_sources": keep_if_other_sources},
              f"removed {removed}, kept {len(to_keep)}",
              start_time=_start, note=note)
    return f"Removed {removed} articles from {desc} (kept {len(to_keep)} that had other sources). Total: {total}"


@mcp.tool()
def remove_by_pattern(pattern: str, below_score: int | None = None, source: str | None = None,
                      match_description: bool = False,
                      dry_run: bool = True, note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Remove articles matching a pattern (case-insensitive substring match).
    Matches against the title by default; set match_description=True to match
    against each article's stored short description instead (call
    fetch_descriptions first). Use dry_run=True to preview.

    Args:
        pattern: Substring to match (case-insensitive)
        below_score: Only remove articles with score below this value (or unscored)
        source: Only remove articles from this source
        match_description: If True, match pattern against the description field
                           rather than the title. Articles with no description
                           never match in this mode. Default False.
        dry_run: If True (default), just preview — don't actually remove
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    if not pattern or len(pattern.strip()) < 2:
        return ("Pattern must be at least 2 characters. An empty or trivial pattern "
                "would match every article — if you want to clear a whole source, use "
                "remove_by_source instead, or reset_topic to clear the entire working list.")

    all_articles = db.get_all_articles_dict(topic_id)
    pattern_lower = pattern.lower()

    matches = []
    sample_preview = []
    for title, article in all_articles.items():
        if match_description:
            desc = article.get('description') or ''
            if not desc or pattern_lower not in desc.lower():
                continue
        else:
            if pattern_lower not in title.lower():
                continue
        if below_score is not None:
            score = article.get('score')
            if score is not None and score >= below_score:
                continue
        if source is not None:
            if source not in article.get('sources', []):
                continue
        matches.append(title)
        if len(sample_preview) < 30:
            # Include description in the preview when matching by description,
            # so the AI/user can sanity-check what's about to be cut.
            if match_description:
                sample_preview.append({'title': title, 'description': article.get('description') or ''})
            else:
                sample_preview.append(title)

    if dry_run:
        log_usage(ctx, "remove_by_pattern",
                  {"pattern": pattern, "below_score": below_score,
                   "source": source, "match_description": match_description,
                   "dry_run": True},
                  f"would remove {len(matches)}",
                  start_time=_start, note=note)
        return json.dumps({
            'pattern': pattern,
            'match_description': match_description,
            'would_remove': len(matches),
            'sample': sample_preview,
            'note': 'Set dry_run=False to actually remove these articles.',
        }, indent=2, ensure_ascii=False)

    removed = db.remove_articles(topic_id, matches)
    total = db.get_status(topic_id)['total_articles']
    log_usage(ctx, "remove_by_pattern",
              {"pattern": pattern, "below_score": below_score,
               "source": source, "match_description": match_description},
              f"removed {removed}", start_time=_start, note=note)
    return f"Removed {removed} articles matching '{pattern}'. Total: {total}"


@mcp.tool()
def get_articles(min_score: int | None = None, max_score: int | None = None,
                 source: str | None = None, unscored_only: bool = False,
                 titles_only: bool = False,
                 limit: int = 100, offset: int = 0,
                 topic: str | None = None, ctx: Context = None) -> str:
    """Get articles from the working list with optional filters.

    Args:
        min_score: Minimum score filter
        max_score: Maximum score filter
        source: Filter by source (e.g., "wikiproject", "category", "search")
        unscored_only: Only return articles without a score
        titles_only: If True, return just titles (saves tokens). Default False.
        limit: Max articles to return (default 100)
        offset: Skip this many articles (for pagination)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    articles, total = db.get_articles(
        topic_id, min_score=min_score, max_score=max_score,
        source=source, unscored_only=unscored_only, limit=limit, offset=offset
    )

    if titles_only:
        return json.dumps({
            'titles': [a['title'] for a in articles],
            'showing': f"{offset + 1}-{offset + len(articles)} of {total}",
            'total_matching': total,
        }, indent=2, ensure_ascii=False)

    return json.dumps({
        'articles': articles,
        'showing': f"{offset + 1}-{offset + len(articles)} of {total}",
        'total_matching': total,
    }, indent=2, ensure_ascii=False)


# ── Cleanup and export ────────────────────────────────────────────────────

@mcp.tool()
def filter_articles(resolve_redirects: bool = True, remove_disambig: bool = True,
                    remove_lists: bool = True, note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Clean up the working list: resolve redirects, remove disambiguation pages,
    remove list/index pages.

    Args:
        resolve_redirects: Resolve redirect titles to canonical titles
        remove_disambig: Remove disambiguation pages
        remove_lists: Remove "List of...", "Index of...", etc.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    stats = {'before': len(all_articles)}

    # Resolve redirects
    if resolve_redirects:
        titles = list(all_articles.keys())
        redirect_map = {}
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            params = {'titles': '|'.join(batch), 'redirects': '1'}
            data = api_query(params, wiki=wiki)
            if 'query' in data:
                for r in data['query'].get('redirects', []):
                    redirect_map[r['from']] = r['to']
                for n in data['query'].get('normalized', []):
                    redirect_map[n['from']] = n['to']

        new_articles = {}
        redirected = 0
        for title, article in all_articles.items():
            resolved = title
            for _ in range(5):
                if resolved in redirect_map:
                    resolved = redirect_map[resolved]
                else:
                    break
            resolved = normalize_title(resolved)
            if resolved != title:
                redirected += 1
                # Title changed — the stored description was for the old title
                # and may be stale. Invalidate so fetch_descriptions refreshes it.
                article = {**article, 'description': None}
            if resolved not in new_articles:
                new_articles[resolved] = article
            else:
                for s in article.get('sources', []):
                    if s not in new_articles[resolved]['sources']:
                        new_articles[resolved]['sources'].append(s)
                if article.get('score') and (not new_articles[resolved].get('score') or
                        article['score'] > new_articles[resolved]['score']):
                    new_articles[resolved]['score'] = article['score']

        all_articles = new_articles
        stats['redirects_resolved'] = redirected
        stats['after_redirects'] = len(all_articles)

    # Remove disambiguation pages
    if remove_disambig:
        titles = list(all_articles.keys())
        disambig = set()
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            params = {'titles': '|'.join(batch), 'prop': 'pageprops', 'ppprop': 'disambiguation'}
            data = api_query(params, wiki=wiki)
            if 'query' in data and 'pages' in data['query']:
                for page in data['query']['pages']:
                    if 'pageprops' in page and 'disambiguation' in page['pageprops']:
                        disambig.add(normalize_title(page['title']))
        for t in disambig:
            all_articles.pop(t, None)
        stats['disambig_removed'] = len(disambig)

    # Remove list pages and year-prefixed meta pages. The latter catches
    # "2020 in Colombia", "2006 FIFA World Cup squads", "2021 deaths in …"
    # style titles that routinely slip through search pulls for biography
    # topics. Legitimate biographies rarely start with a 4-digit year.
    if remove_lists:
        list_pages = [t for t in all_articles if t.lower().startswith(
            ('list of ', 'lists of ', 'index of ', 'outline of '))]
        meta_pages = [t for t in all_articles if re.match(r'^\d{4}\s', t)]
        dropped = set(list_pages) | set(meta_pages)
        for t in dropped:
            del all_articles[t]
        stats['lists_removed'] = len(list_pages)
        stats['meta_pages_removed'] = len(meta_pages)

    stats['final'] = len(all_articles)

    # Write back to DB
    db.replace_all_articles(topic_id, all_articles)

    log_usage(ctx, "filter_articles",
              {"resolve_redirects": resolve_redirects, "remove_disambig": remove_disambig,
               "remove_lists": remove_lists},
              f"{stats['before']} → {stats['final']}", start_time=_start, note=note)
    return json.dumps(stats, indent=2)


@mcp.tool()
def export_csv(min_score: int = 0, scored_only: bool = False, note: str = "",
               topic: str | None = None, ctx: Context = None) -> str:
    """Export the final article list as a downloadable CSV file.

    Returns a download link — give this URL to the user so they can download the CSV directly.

    Args:
        min_score: Minimum score to include (default 0 = export all articles).
                   Set to 7 to export only scored-and-relevant articles.
        scored_only: If True, only export articles that have been scored. Default False.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name, _ = _get_topic(ctx)
    all_articles = db.get_all_articles_dict(topic_id)

    titles = []
    for title, article in sorted(all_articles.items()):
        score = article.get('score')

        if scored_only and score is None:
            continue
        if score is not None and score < min_score:
            continue
        # If min_score > 0 and article is unscored, skip it
        if min_score > 0 and score is None:
            continue

        titles.append(title)

    # Use stored descriptions from the DB where available; fetch any that
    # are still NULL (not-yet-fetched) and persist them for next time.
    # Empty-string description = "no short-desc exists for this page" — use as-is.
    descriptions = {}
    missing = []
    for title in titles:
        stored = all_articles.get(title, {}).get('description')
        if stored is None:
            missing.append(title)
        else:
            descriptions[title] = stored
    if missing:
        fetched = fetch_short_descriptions(missing, wiki=wiki)
        db.set_descriptions(topic_id, fetched)
        descriptions.update(fetched)

    # Save to a downloadable file. utf-8-sig prepends a BOM so Excel detects
    # UTF-8 (otherwise accented characters get mojibaked to Windows-1252).
    # csv.writer with newline='' emits RFC-4180 CRLF line endings and handles
    # quote escaping for titles containing commas, quotes, or newlines.
    slug = topic_name.lower().replace(' ', '_').replace("'", '').replace('"', '')
    export_dir = os.path.join(os.environ.get("EXPORT_DIR", "/opt/topic-builder/exports"))
    os.makedirs(export_dir, exist_ok=True)
    filename = f"topic-articles-{slug}.csv"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        for title in titles:
            writer.writerow([title, descriptions.get(title, '')])

    download_url = f"https://topic-builder.wikiedu.org/exports/{filename}"

    log_usage(ctx, "export_csv", {"min_score": min_score, "scored_only": scored_only, "wiki": wiki},
              f"{len(titles)} articles exported", start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'article_count': len(titles),
        'min_score': min_score,
        'download_url': download_url,
        'filename': filename,
        'note': (
            f'Give the user the download link above. The CSV has two columns '
            f'per row: article title and a Wikidata short description (empty '
            f'if none). Titles refer to articles on {wiki}.wikipedia.org — '
            f'pass the same wiki to Impact Visualizer on import.'
        ),
    }, indent=2, ensure_ascii=False)


# ── Feedback ──────────────────────────────────────────────────────────────

@mcp.tool()
def submit_feedback(summary: str, what_worked: str = "", what_didnt: str = "",
                    missed_strategies: str = "",
                    rating: int | None = None, note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Submit a brief retrospective on this topic-building session so the
    Wiki Education team can improve the tool. Offer to call this at the end
    of a session (before or after export_csv), or whenever the user signals
    they're done. Don't call it without the user's okay.

    Args:
        summary: 2-5 sentence plain-language account of how the session went —
                 topic, final article count, overall flow.
        what_worked: What helped — tools that were effective, strategies that
                     fit this topic, places the AI/user collaboration felt smooth.
        what_didnt: Pain points — missing tools, confusing output, noisy sources,
                    places the AI got stuck or had to work around the API.
                    Be specific; this is the most useful field for us.
        missed_strategies: Other ways the user (or you) thought of for identifying
                           articles that the current tools didn't support well.
                           Wikidata / SPARQL queries, PetScan compound queries,
                           reading lists, awards, author bibliographies, non-English
                           wikis, academic databases — anything you wanted to reach
                           for but couldn't. This is how we decide what tool to
                           build next. Empty string if nothing came up.
        rating: Optional 1-10 rating of the overall experience.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: The topic name this feedback is about. Pass explicitly if your
               client doesn't maintain an MCP session.
    """
    _start = _start_call()
    tid, name, _ = _get_topic(ctx)
    resolved_topic = topic or name or "(unknown)"

    client_id = None
    try:
        client_id = ctx.client_id
    except Exception:
        pass

    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "topic": resolved_topic,
        "client_id": client_id,
        "rating": rating,
        "summary": summary,
        "what_worked": what_worked,
        "what_didnt": what_didnt,
        "missed_strategies": missed_strategies,
    }
    if tid or topic:
        try:
            lookup_id = tid
            if not lookup_id and topic:
                lookup_id, _, _ = db.get_topic_by_name(topic)
            if lookup_id:
                status = db.get_status(lookup_id)
                entry["articles_count"] = status["total_articles"]
                entry["scored_count"] = status["scored"]
        except Exception:
            pass

    db.append_feedback(entry)
    log_usage(ctx, "submit_feedback", {"topic": resolved_topic, "rating": rating},
              f"feedback recorded ({len(summary)} chars)",
              start_time=_start, note=note)
    return ("Thanks — feedback recorded. The Wiki Education team will review it. "
            "Tell the user their feedback was submitted.")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
