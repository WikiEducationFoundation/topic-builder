"""Wikipedia Topic Builder MCP Server.

Provides tools for exploring Wikipedia's content structure to build
comprehensive article lists for any topic.
"""

import json
import collections
import datetime
import logging
import os
import re
import threading
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

from wikipedia_api import (
    api_query, api_query_all, api_get, normalize_title, WIKIPEDIA_API,
    get_rate_limit_stats,
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
# Keyed by id(ctx.session); value is (topic_id, topic_name).
_session_topics: dict[int, tuple[int, str]] = {}
_session_lock = threading.Lock()


def _session_key(ctx: Context) -> int:
    return id(ctx.session)


def _get_topic(ctx: Context) -> tuple[int | None, str]:
    with _session_lock:
        return _session_topics.get(_session_key(ctx), (None, ""))


def _set_topic(ctx: Context, topic_id: int, name: str) -> None:
    with _session_lock:
        _session_topics[_session_key(ctx)] = (topic_id, name)


def log_usage(ctx: Context, tool_name: str, params: dict | None = None, result_summary: str = ""):
    topic_id, topic_name = _get_topic(ctx)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "topic": topic_name or "(none)",
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


def _require_topic(ctx: Context, topic_name: str | None = None) -> tuple[int | None, str | None]:
    """Resolve the topic for this call. Returns (topic_id, error).

    If topic_name is passed explicitly (for stateless clients like ChatGPT that
    don't persist MCP sessions), look it up by name — creating if missing — and
    bind it to this session. Otherwise fall back to the session's current topic
    (set by start_topic).
    """
    if topic_name:
        tid, canonical = db.get_topic_by_name(topic_name)
        if tid is None:
            tid, _, _ = db.create_or_get_topic(topic_name)
            canonical = topic_name
        _set_topic(ctx, tid, canonical)
        return tid, None

    tid, _ = _get_topic(ctx)
    if not tid:
        return None, (
            "No active topic. Call start_topic first, or pass topic=<name> to this tool. "
            "If your MCP client doesn't persist sessions between tool calls (e.g. ChatGPT), "
            "pass topic=<name> on every call."
        )
    return tid, None


# ── Topic management ───────────────────────────────────────────────────────

@mcp.tool()
def start_topic(name: str, fresh: bool = False, ctx: Context = None) -> str:
    """Start a new topic build or resume an existing one with the same name.
    Topics are persisted — if a topic with this name already exists, it will
    be resumed with all its articles intact UNLESS you pass fresh=True.

    Args:
        name: The topic name (e.g., "climate change", "women in STEM")
        fresh: If True and the topic already exists, wipe all its articles
               before starting. Use this when the user asks to "start over"
               or "start fresh" on an existing topic. Defaults to False.
    """
    topic_id, is_new, article_count = db.create_or_get_topic(name)
    _set_topic(ctx, topic_id, name)

    if is_new:
        log_usage(ctx, "start_topic", {"name": name, "is_new": True})
        return f"Started new topic build: '{name}'. Working list is empty."

    if fresh:
        db.replace_all_articles(topic_id, {})
        log_usage(ctx, "start_topic", {"name": name, "fresh": True},
                  f"cleared {article_count} articles")
        return (f"Resumed existing topic '{name}' and cleared its {article_count} "
                f"previous articles (fresh=True). Working list is now empty.")

    log_usage(ctx, "start_topic", {"name": name, "is_new": False})
    return (f"Resumed existing topic: '{name}'. Working list has {article_count} articles. "
            f"If you want to start over with a fresh empty list instead, call "
            f"reset_topic now (or re-call start_topic with fresh=True).")


@mcp.tool()
def reset_topic(topic: str | None = None, ctx: Context = None) -> str:
    """Clear all articles from the current topic and start over.
    The topic itself is kept (so the name is preserved), but all articles,
    scores, and sources are wiped.

    Args:
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session (e.g. ChatGPT); otherwise uses the session's
               current topic.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name = _get_topic(ctx)
    all_articles = db.get_all_articles_dict(topic_id)
    count = len(all_articles)
    db.replace_all_articles(topic_id, {})
    log_usage(ctx, "reset_topic", {}, f"cleared {count} articles")
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
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name = _get_topic(ctx)
    status = db.get_status(topic_id)
    status['topic'] = topic_name
    status['rate_limits'] = get_rate_limit_stats()
    return json.dumps(status, indent=2, default=str)


# ── Reconnaissance tools ──────────────────────────────────────────────────

@mcp.tool()
def survey_categories(category: str, depth: int = 2, count_articles: bool = False, ctx: Context = None) -> str:
    """Survey the subcategory tree of a Wikipedia category WITHOUT collecting articles.
    Use this first to understand how Wikipedia organizes a topic before committing to a pull.

    Args:
        category: Category name without "Category:" prefix (e.g., "Climate change")
        depth: How deep to survey (default 2, max 4)
        count_articles: If True, also count total articles across all categories (slower but helps gauge size before pulling)
    """
    depth = min(depth, 4)
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
            for item in api_query_all(params, 'categorymembers'):
                title = item['title']
                if title.startswith('Category:'):
                    title = title[len('Category:'):]
                if title not in visited:
                    visited.add(title)
                    by_depth[d + 1].append(title)
                    queue.append((title, d + 1))

    result = {
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
            for _ in api_query_all(params, 'categorymembers', max_items=50000):
                total_articles += 1
        result['estimated_total_articles'] = total_articles
        if total_articles > 2000:
            result['warning'] = f'This tree contains ~{total_articles} articles. Consider pulling specific subcategories rather than the whole tree.'

    log_usage(ctx, "survey_categories", {"category": category, "depth": depth}, f"{len(visited)} categories")
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def check_wikiproject(project_name: str) -> str:
    """Check whether a given WikiProject exists on Wikipedia. WikiProjects
    tag articles with assessment banners — if one exists for the topic, it's
    usually the best single source of tagged articles.

    Args:
        project_name: the WikiProject's own name, which is often not identical
            to the topic name. For the topic "Climate change" the project
            happens to also be "Climate change", but for "Hispanic and Latino
            people in STEM" it might be "Latino and Hispanic Americans" or
            "Science". Guess likely names and probe.
    """
    template_title = f"Template:WikiProject {project_name}"
    params = {'titles': template_title, 'prop': 'info'}
    data = api_query(params)
    exists = False
    if 'query' in data and 'pages' in data['query']:
        for page in data['query']['pages']:
            if not page.get('missing', False):
                exists = True

    return json.dumps({
        'project': project_name,
        'template': template_title,
        'exists': exists,
        'note': 'Use get_wikiproject_articles to fetch all tagged articles' if exists else 'No WikiProject found'
    })


@mcp.tool()
def find_list_pages(subject: str) -> str:
    """Search for Index/List/Outline/Glossary pages about a subject.

    Args:
        subject: Subject to search for (free text, e.g. "climate change")
    """
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
        for item in api_query_all(params, 'search', max_items=20):
            pages.append(item['title'])

    return json.dumps({
        'subject': subject,
        'list_pages': pages,
        'count': len(pages),
    }, indent=2)


# ── Gathering tools ───────────────────────────────────────────────────────

@mcp.tool()
def get_wikiproject_articles(project_name: str, max_articles: int = 50000,
                              topic: str | None = None, ctx: Context = None) -> str:
    """Get all articles tagged by a WikiProject. Adds them to the working list
    with source 'wikiproject'.

    Args:
        project_name: WikiProject name (e.g., "Climate change")
        max_articles: Maximum articles to fetch (default 50000)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
    for item in api_query_all(params, 'embeddedin', max_items=max_articles):
        title = item['title']
        if title.startswith('Talk:'):
            title = title[len('Talk:'):]
        title = normalize_title(title)
        articles.append(title)

    source_label = f"wikiproject:{project_name}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "get_wikiproject_articles", {"project": project_name}, f"{len(articles)} articles")
    return json.dumps({
        'project': project_name,
        'articles_found': len(articles),
        'new_articles_added': added,
        'existing_updated': updated,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def get_category_articles(category: str, depth: int = 3, exclude: list[str] | None = None,
                          max_articles: int = 50000,
                          topic: str | None = None, ctx: Context = None) -> str:
    """Crawl a category tree and collect all articles. Adds them to the working list
    with source 'category'.

    Args:
        category: Category name without "Category:" prefix
        depth: Maximum depth to crawl (default 3, max 5)
        exclude: Category names to skip (prune entire branches)
        max_articles: Maximum articles to collect (default 50000)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    depth = min(depth, 5)
    exclude_set = set(exclude or [])
    articles = set()
    visited_cats = set()

    queue = collections.deque([(category, 0)])
    visited_cats.add(category)

    while queue and len(articles) < max_articles:
        cat, d = queue.popleft()

        params = {
            'list': 'categorymembers',
            'cmtitle': f'Category:{cat}',
            'cmtype': 'page',
            'cmnamespace': '0',
            'cmlimit': '500',
        }
        for item in api_query_all(params, 'categorymembers'):
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
            for item in api_query_all(params, 'categorymembers'):
                subcat = item['title']
                if subcat.startswith('Category:'):
                    subcat = subcat[len('Category:'):]
                if subcat not in visited_cats and subcat not in exclude_set:
                    visited_cats.add(subcat)
                    queue.append((subcat, d + 1))

    source_label = f"category:{category}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    result = {
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
    _, topic_name = _get_topic(ctx)
    if added > 500 and topic_name:
        STOPWORDS = {"a", "an", "and", "of", "in", "on", "for", "to", "the", "by"}
        cat_words = {w for w in re.findall(r"\w+", category.lower()) if w not in STOPWORDS}
        topic_words = {w for w in re.findall(r"\w+", topic_name.lower()) if w not in STOPWORDS}
        if cat_words and topic_words and not (cat_words & topic_words):
            result['warning'] = (
                f"This pull added {added} articles and the category '{category}' "
                f"has no word-level overlap with the topic '{topic_name}'. "
                f"It may be too broad or off-scope. If most of it turns out to be "
                f"noise, use remove_by_source(\"{source_label}\", "
                f"keep_if_other_sources=True) to drop everything that isn't also "
                f"found via a more on-topic source."
            )

    log_usage(ctx, "get_category_articles", {"category": category, "depth": depth}, f"{len(articles)} articles, {len(visited_cats)} categories")
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def harvest_list_page(title: str, topic: str | None = None, ctx: Context = None) -> str:
    """Extract all article links from a List/Index/Glossary page. Adds them
    to the working list with source 'list_page'.

    Args:
        title: Page title (e.g., "Index of climate change articles")
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

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
        data = api_get(WIKIPEDIA_API, params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                for link in page.get('links', []):
                    links.append(normalize_title(link['title']))
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break

    source_label = f"list_page:{title}"
    batch = [(t, source_label, None) for t in links]
    added, updated = db.add_articles(topic_id, batch)

    return json.dumps({
        'source_page': title,
        'links_found': len(links),
        'new_articles_added': added,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'note': f'To undo this harvest, use: remove_by_source("{source_label}")',
    }, indent=2)


@mcp.tool()
def search_articles(query: str, limit: int = 500,
                    topic: str | None = None, ctx: Context = None) -> str:
    """Search Wikipedia using CirrusSearch. Supports operators like intitle:,
    morelike:, hastemplate:, incategory:. Adds results to working list with source 'search'.

    Args:
        query: Search query (e.g., 'intitle:"climate change"', 'morelike:Effects of climate change')
        limit: Maximum results (default 500)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
    for item in api_query_all(params, 'search', max_items=limit):
        results.append(item['title'])

    batch = [(title, 'search', None) for title in results]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "search_articles", {"query": query}, f"{len(results)} results")
    return json.dumps({
        'query': query,
        'results_found': len(results),
        'new_articles_added': added,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def search_similar(seed_article: str, limit: int = 50,
                   topic: str | None = None, ctx: Context = None) -> str:
    """Find articles similar to a given article using CirrusSearch morelike:.
    Great for finding thematic clusters the other strategies miss.

    Args:
        seed_article: Article title to find similar articles to
        limit: Maximum results (default 50)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    return search_articles(f'morelike:{seed_article}', limit=limit, topic=topic, ctx=ctx)


# ── Scoring tools ─────────────────────────────────────────────────────────

@mcp.tool()
def score_by_extract(titles: list[str] | None = None, unscored_batch: bool = False,
                     batch_size: int = 50,
                     topic: str | None = None, ctx: Context = None) -> str:
    """Fetch article extracts (first 5 sentences) from Wikipedia for scoring.
    Returns the extracts so you can judge relevance on a 1-10 scale.

    Args:
        titles: Specific titles to score. If None and unscored_batch=True, fetches unscored articles.
        unscored_batch: If True and titles is None, fetch a batch of unscored articles
        batch_size: How many articles to fetch (default 50, max 50)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
    data = api_query(params)

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

    return json.dumps({
        'articles': results,
        'count': len(results),
        'note': 'Score each article 1-10 for topic relevance, then use set_scores to save.',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def set_scores(scores: dict[str, int],
               topic: str | None = None, ctx: Context = None) -> str:
    """Set relevance scores for articles. Scores should be 1-10.

    Args:
        scores: Dict mapping article title to score (e.g., {"Article Name": 8, "Other Article": 3})
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    updated = db.set_scores(topic_id, scores)
    return f"Updated scores for {updated} articles."


@mcp.tool()
def auto_score_by_title(threshold: int = 7,
                        topic: str | None = None, ctx: Context = None) -> str:
    """Quick title-based scoring pass for obvious cases. Articles with clear topic
    keywords in the title get auto-scored.

    Args:
        threshold: Score to assign to keyword-matched articles (default 7)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name = _get_topic(ctx)
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
    return f"Auto-scored {len(scores)} articles containing '{topic_phrase}' in title. ~{unscored} still unscored."


@mcp.tool()
def score_all_unscored(score: int = 8,
                       topic: str | None = None, ctx: Context = None) -> str:
    """Set a score for ALL currently unscored articles in one operation.
    Use this after you've already pruned the list down to on-topic articles
    and just need to mark everything as scored for export.

    Args:
        score: Score to assign to all unscored articles (default 8)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    scores = {title: score for title, article in all_articles.items()
              if article.get('score') is None}

    if scores:
        db.set_scores(topic_id, scores)

    return f"Scored {len(scores)} previously unscored articles at {score}. All articles are now scored."


# ── Edge browsing ─────────────────────────────────────────────────────────

@mcp.tool()
def browse_edges(seed_titles: list[str], min_links: int = 3,
                 topic: str | None = None, ctx: Context = None) -> str:
    """Browse outgoing links from seed articles to find related articles not yet
    in the working list. Articles linked by multiple seeds are most likely relevant.

    Args:
        seed_titles: Articles to browse from (pick peripheral/edge articles for best results)
        min_links: Minimum seed articles that must link to a candidate (default 3)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
            data = api_get(WIKIPEDIA_API, params)
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

    return json.dumps({
        'seeds_browsed': len(seed_titles),
        'candidates': [{'title': t, 'linked_by': c} for t, c in candidates[:100]],
        'total_candidates': len(candidates),
        'note': 'Use add_articles to add relevant candidates, or score_by_extract to investigate.',
    }, indent=2, ensure_ascii=False)


# ── List management ───────────────────────────────────────────────────────

@mcp.tool()
def list_sources(topic: str | None = None, ctx: Context = None) -> str:
    """List every source label currently attached to articles in the working list,
    with counts. Call this before remove_by_source to see exactly what labels
    you can target. Each gather tool (get_category_articles, get_wikiproject_articles,
    harvest_list_page, search_articles) records a specific source label like
    "category:Cognition" or "wikiproject:Climate change".

    Args:
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    counts = collections.Counter()
    for article in all_articles.values():
        for s in article.get('sources', []):
            counts[s] += 1

    sources = [{'source': s, 'count': c} for s, c in counts.most_common()]
    return json.dumps({
        'sources': sources,
        'total_distinct_sources': len(sources),
        'note': ('To drop a noisy source while keeping articles that also appear '
                 'under another source, use remove_by_source(source, '
                 'keep_if_other_sources=True). To drop a source entirely, set '
                 'keep_if_other_sources=False.'),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def add_articles(titles: list[str], source: str = "manual", score: int | None = None,
                 topic: str | None = None, ctx: Context = None) -> str:
    """Add articles to the working list. Use this when you want to add articles
    you've discovered or identified yourself, outside of the other gather tools.

    Args:
        titles: Article titles to add
        source: Source label (e.g., "manual", "edge_browse", "search")
        score: Optional relevance score to assign (1-10)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    batch = [(normalize_title(t), source, score) for t in titles]
    added, updated = db.add_articles(topic_id, batch)
    total = db.get_status(topic_id)['total_articles']
    return f"Added {added} new articles, updated {updated} (source: {source}). Total: {total}"


@mcp.tool()
def get_articles_by_source(source: str, exclude_sources: list[str] | None = None,
                           limit: int = 100, offset: int = 0,
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
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
        matches.append(title)

    total = len(matches)
    page = matches[offset:offset + limit]

    return json.dumps({
        'source': source,
        'excluding': sorted(exclude) if exclude else None,
        'titles': page,
        'showing': f"{offset + 1}-{offset + len(page)} of {total}",
        'total_matching': total,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def remove_articles(titles: list[str],
                    topic: str | None = None, ctx: Context = None) -> str:
    """Remove articles from the working list.

    Args:
        titles: Article titles to remove
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    removed = db.remove_articles(topic_id, titles)
    total = db.get_status(topic_id)['total_articles']
    return f"Removed {removed} articles. Total: {total}"


@mcp.tool()
def remove_by_source(source: str, keep_if_other_sources: bool = True, dry_run: bool = True,
                     topic: str | None = None, ctx: Context = None) -> str:
    """Remove all articles that came from a specific source. Use this to undo a bad
    category pull or noisy list harvest.

    Args:
        source: Source label to remove (e.g., "category:Learning methods", "list_page:List of printmakers")
        keep_if_other_sources: If True (default), keep articles that also have OTHER sources.
                               If False, remove all articles with this source regardless.
        dry_run: If True (default), preview what would be removed without actually removing.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)

    to_remove = []
    to_keep = []
    for title, article in all_articles.items():
        sources = article.get('sources', [])
        if source not in sources:
            continue
        other_sources = [s for s in sources if s != source]
        if keep_if_other_sources and other_sources:
            to_keep.append(title)
        else:
            to_remove.append(title)

    if dry_run:
        return json.dumps({
            'source': source,
            'would_remove': len(to_remove),
            'would_keep_(other_sources)': len(to_keep),
            'sample_remove': to_remove[:20],
            'sample_keep': to_keep[:10],
            'note': 'Set dry_run=False to actually remove.',
        }, indent=2, ensure_ascii=False)

    removed = db.remove_articles(topic_id, to_remove)
    # Also strip this source from articles we kept
    if to_keep:
        for title in to_keep:
            article = all_articles[title]
            new_sources = [s for s in article['sources'] if s != source]
            db.update_article_sources(topic_id, title, new_sources)

    total = db.get_status(topic_id)['total_articles']
    return f"Removed {removed} articles from source '{source}' (kept {len(to_keep)} that had other sources). Total: {total}"


@mcp.tool()
def remove_by_pattern(pattern: str, below_score: int | None = None, source: str | None = None,
                      dry_run: bool = True,
                      topic: str | None = None, ctx: Context = None) -> str:
    """Remove articles matching a pattern (case-insensitive substring match on title).
    Use dry_run=True first to preview what would be removed.

    Args:
        pattern: Substring to match in article titles (case-insensitive)
        below_score: Only remove articles with score below this value (or unscored)
        source: Only remove articles from this source
        dry_run: If True (default), just preview — don't actually remove
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    if not pattern or len(pattern.strip()) < 2:
        return ("Pattern must be at least 2 characters. An empty or trivial pattern "
                "would match every article — if you want to clear a whole source, use "
                "remove_by_source instead, or reset_topic to clear the entire working list.")

    all_articles = db.get_all_articles_dict(topic_id)
    pattern_lower = pattern.lower()

    matches = []
    for title, article in all_articles.items():
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

    if dry_run:
        return json.dumps({
            'pattern': pattern,
            'would_remove': len(matches),
            'sample': matches[:30],
            'note': 'Set dry_run=False to actually remove these articles.',
        }, indent=2, ensure_ascii=False)

    removed = db.remove_articles(topic_id, matches)
    total = db.get_status(topic_id)['total_articles']
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
    topic_id, err = _require_topic(ctx, topic)
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
                    remove_lists: bool = True,
                    topic: str | None = None, ctx: Context = None) -> str:
    """Clean up the working list: resolve redirects, remove disambiguation pages,
    remove list/index pages.

    Args:
        resolve_redirects: Resolve redirect titles to canonical titles
        remove_disambig: Remove disambiguation pages
        remove_lists: Remove "List of...", "Index of...", etc.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
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
            data = api_query(params)
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
            data = api_query(params)
            if 'query' in data and 'pages' in data['query']:
                for page in data['query']['pages']:
                    if 'pageprops' in page and 'disambiguation' in page['pageprops']:
                        disambig.add(normalize_title(page['title']))
        for t in disambig:
            all_articles.pop(t, None)
        stats['disambig_removed'] = len(disambig)

    # Remove list pages
    if remove_lists:
        list_pages = [t for t in all_articles if t.lower().startswith(
            ('list of ', 'lists of ', 'index of ', 'outline of '))]
        for t in list_pages:
            del all_articles[t]
        stats['lists_removed'] = len(list_pages)

    stats['final'] = len(all_articles)

    # Write back to DB
    db.replace_all_articles(topic_id, all_articles)

    return json.dumps(stats, indent=2)


@mcp.tool()
def export_csv(min_score: int = 0, scored_only: bool = False,
               topic: str | None = None, ctx: Context = None) -> str:
    """Export the final article list as a downloadable CSV file.

    Returns a download link — give this URL to the user so they can download the CSV directly.

    Args:
        min_score: Minimum score to include (default 0 = export all articles).
                   Set to 7 to export only scored-and-relevant articles.
        scored_only: If True, only export articles that have been scored. Default False.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, err = _require_topic(ctx, topic)
    if err:
        return err

    _, topic_name = _get_topic(ctx)
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

    lines = []
    for title in titles:
        if ',' in title:
            lines.append(f'"{title}"')
        else:
            lines.append(title)

    csv_content = '\n'.join(lines) + '\n'

    # Save to a downloadable file
    slug = topic_name.lower().replace(' ', '_').replace("'", '').replace('"', '')
    export_dir = os.path.join(os.environ.get("EXPORT_DIR", "/opt/topic-builder/exports"))
    os.makedirs(export_dir, exist_ok=True)
    filename = f"topic-articles-{slug}.csv"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(csv_content)

    download_url = f"https://topic-builder.wikiedu.org/exports/{filename}"

    log_usage(ctx, "export_csv", {"min_score": min_score}, f"{len(titles)} articles exported")
    return json.dumps({
        'article_count': len(titles),
        'min_score': min_score,
        'download_url': download_url,
        'filename': filename,
        'note': 'Give the user the download link above. The CSV has one article title per line, ready for the Impact Visualizer.',
    }, indent=2, ensure_ascii=False)


# ── Feedback ──────────────────────────────────────────────────────────────

@mcp.tool()
def submit_feedback(summary: str, what_worked: str = "", what_didnt: str = "",
                    missed_strategies: str = "",
                    rating: int | None = None,
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
        topic: The topic name this feedback is about. Pass explicitly if your
               client doesn't maintain an MCP session.
    """
    tid, name = _get_topic(ctx)
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
                lookup_id, _ = db.get_topic_by_name(topic)
            if lookup_id:
                status = db.get_status(lookup_id)
                entry["articles_count"] = status["total_articles"]
                entry["scored_count"] = status["scored"]
        except Exception:
            pass

    db.append_feedback(entry)
    log_usage(ctx, "submit_feedback", {"topic": resolved_topic, "rating": rating},
              f"feedback recorded ({len(summary)} chars)")
    return ("Thanks — feedback recorded. The Wiki Education team will review it. "
            "Tell the user their feedback was submitted.")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
