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
import unicodedata
import urllib.parse
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

from wikipedia_api import (
    api_query, api_query_all, api_get, normalize_title, wiki_api_url,
    get_rate_limit_stats, fetch_short_descriptions,
    fetch_descriptions_with_fallback, fetch_wikidata_qids,
    fetch_article_leads as _fetch_article_leads,
    resolve_redirects as _resolve_redirects,
    apply_redirect_map as _apply_redirect_map,
    reset_call_counters, get_call_counters,
    wikidata_sparql as _wikidata_sparql,
    wikidata_entities_by_property as _wikidata_entities_by_property,
    wikidata_search_entity as _wikidata_search_entity,
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
# Per-session count of bare `add_articles(source="manual", ...)` calls, used
# to emit a one-shot nudge on the second such call (see 2.1 manual:<label>
# convention). Labeled `manual:<context>` calls don't count here.
_session_bare_manual_counts: dict[int, int] = collections.defaultdict(int)
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
def set_topic_rubric(rubric: str, note: str = "",
                     topic: str | None = None, ctx: Context = None) -> str:
    """Persist a centrality rubric for the active topic. Call this AFTER
    confirming scope with the user, BEFORE any gather call — the rubric
    is the authoritative scope statement and frames all later review.

    A rubric is a short prose statement (typically a few sentences per
    section) of how centrality is decided for THIS topic. Structure it
    in three parts:
      * CENTRAL — the core membership criterion. What's essentially
        "about" this topic. Gets score 8-10.
      * PERIPHERAL — adjacent articles that touch the topic without
        being about it. Gets score 3-5.
      * OUT — related-but-not-in-scope. Should be rejected, not added.

    The rubric is shape-agnostic: it works equally well for topics with
    rich structural sources (categories + Wikidata + list pages all
    agree) and for topics where every tool is marginal and you're
    reasoning mostly from domain knowledge.

    Idempotent. Call again with revised text to update; the whole
    rubric is overwritten. When scope drifts mid-build, stop, update
    the rubric, then proceed.

    Args:
        rubric: Prose rubric. Recommended ~100–500 chars across the
                three sections — enough to be unambiguous without
                becoming a policy document.
        note: Optional free-text observation for this call's log entry.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session; otherwise uses the session's current topic.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    prior = db.get_topic_rubric(topic_id)
    db.set_topic_rubric(topic_id, rubric)
    _, topic_name, _ = _get_topic(ctx)

    log_usage(ctx, "set_topic_rubric",
              {"rubric_chars": len(rubric), "had_prior": bool(prior)},
              f"rubric set ({len(rubric)} chars, "
              f"{'revised' if prior else 'initial'})",
              start_time=_start, note=note)
    return json.dumps({
        'topic': topic_name,
        'rubric': rubric,
        'rubric_chars': len(rubric),
        'was_revision': bool(prior),
        'note': (
            'Rubric persisted. Reference it during every review step: '
            'classify each candidate as CENTRAL / PERIPHERAL / OUT. '
            'Revise via set_topic_rubric again if a scope wrinkle surfaces.'
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def get_topic_rubric(topic: str | None = None, ctx: Context = None) -> str:
    """Read the centrality rubric for the active topic. Returns empty
    string if no rubric has been set yet.

    Useful across stateless tool-call sessions, during resume, or at
    wrap-up before export to sanity-check the rubric still matches
    the corpus.

    Args:
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session; otherwise uses the session's current topic.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    rubric = db.get_topic_rubric(topic_id)
    _, topic_name, _ = _get_topic(ctx)
    return json.dumps({
        'topic': topic_name,
        'rubric': rubric,
        'rubric_chars': len(rubric),
        'has_rubric': bool(rubric),
        'note': (
            'Write or revise via set_topic_rubric.'
            if not rubric else
            'Apply this rubric when reviewing, scoring, or spot-checking. '
            'CENTRAL ≈ 8–10, PERIPHERAL ≈ 3–5, OUT → reject.'
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def list_topics() -> str:
    """List all existing topics that can be resumed."""
    topics = db.list_topics()
    if not topics:
        return "No topics found. Use start_topic to create one."
    return json.dumps(topics, indent=2, default=str)


def _feedback_nudge_for_resume(topic_name: str,
                               max_lines: int = 20000,
                               gap_hours: int = 24,
                               min_prior_calls: int = 5) -> str | None:
    """On resume, check whether this topic's previous session ended > N
    hours ago without a submit_feedback call. If so, return a nudge
    string; otherwise return None. The nudge is surfaced to the AI only
    once per gap — if the user kept working after a previous resume, the
    "last tool call" timestamp advances and the gap check stops firing."""
    log_path = os.path.join(LOG_DIR, 'usage.jsonl')
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
    except Exception:
        return None

    topic_entries = []
    for line in lines[-max_lines:]:
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get('topic') == topic_name:
            topic_entries.append(entry)
    # Consider only non-resume tool calls for the "last activity" anchor —
    # a prior resume doesn't count as real work. submit_feedback also
    # doesn't anchor activity (we specifically want to know if feedback
    # was given between the prior session and this resume).
    anchor_entries = [e for e in topic_entries
                      if e.get('tool') not in ('resume_topic', 'start_topic',
                                               'submit_feedback')]
    if len(anchor_entries) < min_prior_calls:
        return None
    last_anchor = anchor_entries[-1]
    try:
        last_ts = datetime.datetime.fromisoformat(
            last_anchor['ts'].replace('Z', '+00:00'))
    except Exception:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    hours_since = (now - last_ts).total_seconds() / 3600
    if hours_since < gap_hours:
        return None
    # Any submit_feedback after the anchor? If so, no nudge.
    for e in topic_entries:
        if e.get('tool') == 'submit_feedback' and e.get('ts', '') > last_anchor.get('ts', ''):
            return None

    return (
        f"Heads up: your last session on this topic ran {hours_since:.0f} hours "
        f"ago and ended without submit_feedback. If anything from that session "
        f"felt friction-heavy — tools that misbehaved, surprises, approaches "
        f"that worked well — this is a good moment to call submit_feedback "
        f"before continuing. The user can decline; don't call it unprompted."
    )


@mcp.tool()
def resume_topic(name: str, ctx: Context = None) -> str:
    """Resume an existing topic build. If this resume follows a gap of
    more than 24 hours since the last tool call on this topic AND no
    submit_feedback was recorded in the interim AND the prior session
    had ≥5 tool calls, the response surfaces a `feedback_nudge` field
    — a gentle prompt to consider capturing retrospective feedback
    before diving back in.

    Args:
        name: The topic name to resume
    """
    resumed = start_topic(name, ctx=ctx)
    nudge = _feedback_nudge_for_resume(name)
    if nudge:
        return json.dumps({
            'resumed': resumed,
            'feedback_nudge': nudge,
        }, indent=2, ensure_ascii=False)
    return resumed


def _topic_cost_summary(topic_name: str, max_lines: int = 20000) -> dict | None:
    """Aggregate per-topic cost from usage.jsonl: lifetime Wikipedia API
    calls, rate-limit hits, timeouts, and a recent-heavy-calls tail.

    Scans at most `max_lines` from the end of the log to bound work even
    on a very large file. Returns None if the log is unreadable — caller
    should treat absence as "no historical cost data yet"."""
    log_path = os.path.join(LOG_DIR, 'usage.jsonl')
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
    except Exception:
        return None

    lifetime_api = 0
    lifetime_timeouts = 0
    rate_limit_hits = 0
    tool_calls = 0
    heavy_calls: list[dict] = []
    for line in lines[-max_lines:]:
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get('topic') != topic_name:
            continue
        tool_calls += 1
        api = entry.get('wikipedia_api_calls', 0) or 0
        elapsed = entry.get('elapsed_ms', 0) or 0
        timed_out = bool(entry.get('timed_out'))
        rate_hits = entry.get('rate_limit_hits_this_call', 0) or 0
        lifetime_api += api
        rate_limit_hits += rate_hits
        if timed_out:
            lifetime_timeouts += 1
        if api > 500 or elapsed > 30000 or timed_out:
            heavy_calls.append({
                'ts': entry.get('ts'),
                'tool': entry.get('tool'),
                'elapsed_ms': elapsed,
                'wikipedia_api_calls': api,
                'timed_out': timed_out,
            })

    heavy_calls.sort(key=lambda e: e.get('ts') or '', reverse=True)
    return {
        'logged_tool_calls': tool_calls,
        'lifetime_wikipedia_api_calls': lifetime_api,
        'lifetime_timeouts': lifetime_timeouts,
        'rate_limit_hits_total': rate_limit_hits,
        'recent_heavy_calls': heavy_calls[:10],
    }


@mcp.tool()
def get_status(topic: str | None = None, ctx: Context = None) -> str:
    """Get current status of the topic build: article count, score
    distribution, source breakdown, and a per-topic cost summary
    aggregated from the usage log (lifetime Wikipedia API calls, timeouts,
    rate-limit hits, recent heavy calls). Useful to check "is this topic
    being a good Wikimedia citizen?" and to spot tools that routinely
    overrun.

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
    cost_summary = _topic_cost_summary(topic_name)
    if cost_summary:
        status['cost_summary'] = cost_summary
    return json.dumps(status, indent=2, default=str)


@mcp.tool()
def describe_topic(top_first_words_limit: int = 20,
                   note: str = "",
                   topic: str | None = None, ctx: Context = None) -> str:
    """Shape-of-corpus overview for the current topic. Returns title
    length distribution, most-common first words, count of articles
    without descriptions, suspicious-pattern counts (year-prefixed,
    all-caps, very-short titles), and source-shape stats (single-source
    vs multi-source articles). Useful mid-flow to catch contamination
    you'd otherwise only notice by paging `get_articles`.

    Think of it as `DataFrame.describe()` for a topic. Everything runs
    in-process against the current working list — no Wikipedia API
    calls, sub-second even on 20K-article topics.

    Args:
        top_first_words_limit: How many entries to return in
                               `top_first_words` (default 20). Useful
                               for spotting dominant genera in a
                               taxonomy topic.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    total = len(all_articles)

    length_dist: dict[str, int] = collections.Counter()
    first_words: collections.Counter[str] = collections.Counter()
    no_desc = 0
    year_or_date = 0
    all_caps = 0
    one_word = 0
    very_short = 0
    source_counts: collections.Counter[str] = collections.Counter()
    single_source = 0
    multi_source = 0

    year_prefix = re.compile(r'^\d{4}\b')
    for title, article in all_articles.items():
        words = title.split()
        if not words:
            continue
        nwords = len(words)
        bucket = f'{nwords}_word' + ('' if nwords == 1 else 's')
        length_dist[bucket] += 1
        first_words[words[0]] += 1
        if article.get('description') is None:
            no_desc += 1
        if year_prefix.match(title):
            year_or_date += 1
        # All-caps detection: multi-char alpha-only title that's all uppercase.
        letters_only = ''.join(c for c in title if c.isalpha())
        if len(letters_only) > 2 and letters_only == letters_only.upper():
            all_caps += 1
        if nwords == 1:
            one_word += 1
        if len(title) <= 3:
            very_short += 1
        sources = article.get('sources') or []
        for s in sources:
            source_counts[s] += 1
        if len(sources) == 1:
            single_source += 1
        elif len(sources) > 1:
            multi_source += 1

    sorted_length_dist = dict(sorted(
        length_dist.items(),
        key=lambda kv: int(kv[0].split('_')[0])
    ))

    result = {
        'topic': _get_topic(ctx)[1],
        'total_articles': total,
        'title_length_distribution': sorted_length_dist,
        'top_first_words': [
            {'word': w, 'count': c}
            for w, c in first_words.most_common(top_first_words_limit)
        ],
        'articles_without_description': no_desc,
        'suspicious_patterns': {
            'year_or_date_titles': year_or_date,
            'all_caps_titles': all_caps,
            'one_word_titles': one_word,
            'very_short_titles': very_short,
        },
        'source_shape': {
            'total_sources': len(source_counts),
            'articles_with_single_source': single_source,
            'articles_with_multiple_sources': multi_source,
        },
        'centrality_rubric': db.get_topic_rubric(topic_id),
    }
    if not result['centrality_rubric']:
        result['rubric_reminder'] = (
            'No centrality rubric set for this topic yet. After scope '
            'confirmation with the user, draft one and save via '
            'set_topic_rubric — CENTRAL / PERIPHERAL / OUT. The rubric '
            'frames all later review and is exported alongside the CSV.'
        )
    log_usage(ctx, "describe_topic",
              {"top_first_words_limit": top_first_words_limit},
              f"{total} articles", start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


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
    project_page_title = f"Wikipedia:WikiProject {project_name}"
    # Probe both the template namespace AND the Wikipedia: namespace page —
    # `find_wikiprojects` uses prefixsearch on the Wikipedia: namespace so
    # it can report a project candidate whose template never existed (or
    # was merged/renamed). Returning both signals lets the AI tell "truly
    # no WikiProject" from "project page exists but template is missing".
    params = {'titles': f'{template_title}|{project_page_title}',
              'prop': 'info'}
    data = api_query(params, wiki=wiki)
    template_exists = False
    project_page_exists = False
    if 'query' in data and 'pages' in data['query']:
        for page in data['query']['pages']:
            if page.get('missing', False):
                continue
            t = page.get('title', '')
            if t == template_title:
                template_exists = True
            elif t == project_page_title:
                project_page_exists = True

    # `exists` stays as the practical "can I call get_wikiproject_articles
    # on this project?" signal — which needs the template to be tagging
    # articles. Historical callers that just read `exists` keep working.
    exists = template_exists
    result = {
        'wiki': wiki,
        'project': project_name,
        'template': template_title,
        'template_exists': template_exists,
        'project_page': project_page_title,
        'project_page_exists': project_page_exists,
        'exists': exists,
    }
    if template_exists:
        result['note'] = 'Use get_wikiproject_articles to fetch all tagged articles'
    elif project_page_exists:
        result['note'] = (
            'Project PAGE exists but the template does not — `find_wikiprojects` '
            'may list this as a candidate, but `get_wikiproject_articles` will '
            'return nothing because there are no template-tagged articles. Try '
            'a renamed / merged variant of the project name, or fall back to '
            'categories + search.'
        )
    else:
        result['note'] = 'No WikiProject found'
    if wiki != 'en':
        result['warning'] = (
            f"WikiProjects are an enwiki convention and rarely exist on "
            f"{wiki}.wikipedia.org. This check is likely uninformative — "
            f"rely on categories and search instead."
        )
    log_usage(ctx, "check_wikiproject", {"project": project_name, "wiki": wiki},
              f"template_exists={template_exists} project_page_exists={project_page_exists}",
              start_time=_start, note=note)
    return json.dumps(result)


@mcp.tool()
def find_wikiprojects(keywords: list[str], limit: int = 20,
                      note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Discover enwiki WikiProjects whose names contain any of the given
    keywords. Use this BEFORE `check_wikiproject` when you're not sure of
    the exact project name — avoids the "I tried WikiProject Plants, it
    was too broad, so I skipped WikiProjects" failure mode (observed in
    orchids, which has a dedicated WikiProject Orchids).

    Enwiki-only by design. WikiProjects are a Wikipedia-English convention
    and rarely exist on other wikis — on non-en topics, skip this tool
    entirely and rely on categories + search_articles.

    Args:
        keywords: List of keyword strings. For each, the tool prefix-
                  searches the Wikipedia: namespace for "WikiProject <kw>"
                  (e.g. ["Orchid", "Plants", "Botany"] → finds WikiProject
                  Orchids, WikiProject Plants, WikiProject Botany).
        limit: Max results per keyword (default 20, hard-capped at 50).
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name (used only to log context; the tool
               always queries enwiki regardless of the topic's wiki).
    """
    _start = _start_call()
    if not keywords:
        return json.dumps({
            'error': 'Pass at least one keyword. Try broad terms from the '
                     'topic name plus domain-specific guesses.',
        })
    limit = min(limit, 50)

    found: dict[str, set[str]] = {}
    for kw in keywords:
        params = {
            'list': 'prefixsearch',
            'pssearch': f'WikiProject {kw}',
            'psnamespace': '4',  # Wikipedia: namespace
            'pslimit': str(limit),
        }
        data = api_query(params, wiki='en')
        for item in data.get('query', {}).get('prefixsearch', []):
            title = item.get('title', '')
            if title.startswith('Wikipedia:WikiProject '):
                proj_name = title[len('Wikipedia:WikiProject '):]
                # Skip task-force / subpage noise — project subpages have
                # slashes in their titles (e.g. "WikiProject Orchids/Tasks").
                if '/' in proj_name:
                    continue
                found.setdefault(proj_name, set()).add(kw)

    projects = [
        {
            'project': name,
            'matched_keywords': sorted(kws),
            'template': f'Template:WikiProject {name}',
        }
        for name, kws in sorted(found.items())
    ]

    log_usage(ctx, "find_wikiprojects", {"keywords": keywords, "limit": limit},
              f"{len(projects)} projects", start_time=_start, note=note)
    return json.dumps({
        'wiki': 'en',
        'keywords': keywords,
        'found': len(projects),
        'projects': projects,
        'note': (
            'Call check_wikiproject(<project>) to confirm the template '
            'exists, or get_wikiproject_articles(<project>) to pull every '
            'tagged article. If this returned nothing, broaden the '
            'keywords — include domain synonyms and adjacent concepts '
            '(e.g. for "orchids" try also "Plants", "Botany", "Gardening").'
        ),
    }, indent=2, ensure_ascii=False)


_LIST_PAGE_PREFIXES = [
    'Index of', 'List of', 'Lists of', 'Outline of', 'Glossary of',
    'Timeline of', 'Bibliography of',
]
_LIST_PAGE_SUFFIXES = [
    'in popular culture', 'in fiction', 'filmography', 'discography',
    'anniversaries', 'by country', 'by year',
]


def _extract_topic_qualifier(topic_name: str | None) -> str:
    """Pull the parenthetical qualifier from a topic name.
    'Symbolism (art movement)' -> 'art movement'. Empty if none."""
    if not topic_name:
        return ''
    m = re.search(r'\(([^)]+)\)\s*$', topic_name)
    return m.group(1).strip() if m else ''


@mcp.tool()
def find_list_pages(subject: str, wiki: str | None = None,
                    note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Search for list-shaped Wikipedia pages about a subject — "List of X",
    "Index of X", "Outline of X", "Glossary of X", "Timeline of X",
    "Bibliography of X", plus suffix-shaped patterns like "X in popular
    culture", "X filmography", "X discography".

    Subject matching is relevance-ranked free text rather than a strict
    phrase — strict phrase match misses "List of Korean dramas" when the
    topic name is "Korean television dramas" (the canonical list drops
    one token). Dropping the phrase quote lets CirrusSearch relevance-
    rank candidates instead.

    Disambiguation filter: if the active topic (or passed-in `topic`) has
    a parenthetical qualifier like "Symbolism (art movement)", candidates
    are filtered to those whose shortdesc or title contains the
    qualifier's tokens. This prevents homonym bleed — e.g. a bare
    `find_list_pages("Symbolism")` otherwise returns semiotic/religious
    list pages along with the art-movement ones.

    The prefix/suffix patterns are English-specific. On non-enwiki topics
    the tool typically returns zero results — other-language wikis use
    different conventions (e.g. "Liste der …" on dewiki). Use
    search_articles with the wiki-native prefix for non-enwiki.

    When `find_list_pages` returns 0 or only irrelevant hits, the
    topic's OWN main article often functions as the canonical list
    page (e.g. an award article with a year-by-year winners table,
    or a concept article with an enumeration of subtypes) — harvest
    it directly via harvest_list_page.

    Args:
        subject: Subject to search for (free text, e.g. "Apollo 11")
        wiki: Wikipedia language code to query. Defaults to the active
              topic's wiki, or "en" if no topic is active.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name to infer the wiki / qualifier from.
    """
    _start = _start_call()
    wiki = _resolve_wiki(ctx, wiki, topic)

    candidates: dict[str, set[str]] = {}  # title -> matched pattern labels

    # Prefix patterns: `intitle:"<prefix>"` + subject as free text.
    # Confirm the returned title actually starts with the prefix — CirrusSearch
    # intitle: allows partial matches and we only want true "X of Y" shape.
    for prefix in _LIST_PAGE_PREFIXES:
        params = {
            'list': 'search',
            'srsearch': f'intitle:"{prefix}" {subject}',
            'srnamespace': '0', 'srlimit': '20', 'srinfo': '', 'srprop': '',
        }
        for item in api_query_all(params, 'search', max_items=20, wiki=wiki):
            t = item['title']
            if t.startswith(prefix + ' '):
                candidates.setdefault(t, set()).add(prefix)

    # Suffix patterns: title must actually contain the suffix.
    for suffix in _LIST_PAGE_SUFFIXES:
        params = {
            'list': 'search',
            'srsearch': f'intitle:"{suffix}" {subject}',
            'srnamespace': '0', 'srlimit': '20', 'srinfo': '', 'srprop': '',
        }
        for item in api_query_all(params, 'search', max_items=20, wiki=wiki):
            t = item['title']
            if suffix.lower() in t.lower():
                candidates.setdefault(t, set()).add(suffix)

    all_candidates = sorted(candidates.keys())

    # Resolve the active topic name for the disambiguation filter. Prefer
    # the explicit `topic` argument; fall back to the session's current topic.
    active_topic_name = topic or ''
    if not active_topic_name and ctx is not None:
        _tid, tname, _twiki = _get_topic(ctx)
        if tname:
            active_topic_name = tname
    qualifier = _extract_topic_qualifier(active_topic_name)

    # Token-based relevance filter. Without this, the widened prefix/suffix
    # search returns "generic soup" for any topic whose canonical article
    # has no parenthetical qualifier — e.g. `Mountains of Kyrgyzstan` hit
    # 61 candidates in a Codex dogfood run, including timelines of Kyrgyz
    # history and outlines of geography, with only the one useful mountain
    # list buried inside. The filter always uses `subject` tokens as a
    # minimum relevance check; when the topic also supplies a qualifier,
    # its tokens extend the accept set.
    filter_note = None
    filter_tokens = {t.lower() for t in re.findall(r"\w+", subject) if len(t) > 2}
    if qualifier:
        filter_tokens |= {t.lower() for t in re.findall(r"\w+", qualifier) if len(t) > 2}
    # Never filter on just {'list','of','index'} — common English words
    # borrowed from the subject would match every candidate.
    _STOPWORDS = {'list', 'lists', 'index', 'outline', 'glossary',
                  'timeline', 'bibliography', 'filmography', 'discography',
                  'the', 'and', 'for', 'with', 'from', 'into'}
    filter_tokens -= _STOPWORDS

    if filter_tokens and all_candidates:
        descs = fetch_short_descriptions(all_candidates, wiki=wiki)
        kept = []
        dropped = []
        for title in all_candidates:
            d = (descs.get(title) or '').lower()
            t_lower = title.lower()
            matched = any(tok in d or tok in t_lower for tok in filter_tokens)
            if matched:
                kept.append(title)
            else:
                dropped.append(title)
        filtered = kept
        if dropped:
            filter_note = (
                f"Filtered {len(dropped)} candidate(s) whose shortdesc and "
                f"title didn't match any relevance token from "
                f"{sorted(filter_tokens)} (derived from subject"
                f"{' and topic qualifier' if qualifier else ''}). "
                f"Dropped sample: {dropped[:5]}"
            )
    else:
        filtered = all_candidates

    result = {
        'wiki': wiki,
        'subject': subject,
        'active_topic': active_topic_name,
        'qualifier': qualifier,
        'list_pages': filtered,
        'count': len(filtered),
        'total_candidates_before_filter': len(all_candidates),
        'matched_patterns': {t: sorted(candidates[t]) for t in filtered},
    }
    if filter_note:
        result['disambiguation_filter_note'] = filter_note
    if wiki != 'en' and not all_candidates:
        result['hint'] = (
            f"No results on {wiki}.wikipedia.org — the prefixes / suffixes "
            f"used here ('List of', 'Index of', 'in popular culture', …) "
            f"are English-specific. Try search_articles with the list-page "
            f"prefix native to this wiki."
        )
    log_usage(ctx, "find_list_pages", {"subject": subject, "wiki": wiki},
              f"{len(filtered)} pages (of {len(all_candidates)} candidates)",
              start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── Wikidata ──────────────────────────────────────────────────────────────

@mcp.tool()
def wikidata_search_entity(term: str, entity_type: str = "item",
                           language: str = "en", limit: int = 10,
                           note: str = "",
                           topic: str | None = None,
                           ctx: Context = None) -> str:
    """Search Wikidata for candidate entities (or properties) matching a
    label or description. **Call this FIRST** when you need a QID for a
    concept — guessing QIDs is error-prone (e.g. Q27868 looks like it
    should be Bulbophyllum but is the Eacles moth genus). Returns up
    to `limit` candidates with QID + label + description + aliases;
    pick the best one for downstream `wikidata_entities_by_property`.

    Also works for properties — pass `entity_type="property"` to find
    P-IDs by name (e.g. `wikidata_search_entity("parent taxon",
    entity_type="property")` returns P171).

    Fast (~100ms, single API call to wbsearchentities). Independent of
    any topic's wiki — `language` controls the search language, not a
    sitelink destination.

    Args:
        term: Label or description text to search for.
        entity_type: "item" (Q-IDs, default) or "property" (P-IDs).
        language: Search language (default "en"). Uses whichever
                  language's labels/aliases to match against.
        limit: Max candidates (default 10, capped at 50).
        note: Optional free-text observation for this call's log entry.
        topic: Optional topic name (for log context only).
    """
    _start = _start_call()
    try:
        rows = _wikidata_search_entity(term, language=language,
                                       entity_type=entity_type, limit=limit)
    except ValueError as e:
        return json.dumps({'error': str(e)}, indent=2)
    except Exception as e:
        return json.dumps({
            'error': f'Wikidata search failed: {type(e).__name__}: {e}',
        }, indent=2)

    log_usage(ctx, "wikidata_search_entity",
              {"term": term, "entity_type": entity_type,
               "language": language, "limit": limit},
              f"{len(rows)} candidates", start_time=_start, note=note)
    return json.dumps({
        'term': term,
        'entity_type': entity_type,
        'language': language,
        'total': len(rows),
        'candidates': rows,
        'note': (
            'Pick the QID whose description best matches your concept, '
            'then pass it to wikidata_entities_by_property. When multiple '
            'candidates look plausible (common for polysemous terms) the '
            'description + aliases disambiguate.'
        ),
    }, indent=2, ensure_ascii=False)


# Response-size thresholds for Wikidata tools. Both dogfood sessions hit
# MCP-transport overflow on 300-row SPARQL responses: Lakes of Finland at
# 52kb (wikidata_query with labels), Symbolism at 85kb
# (wikidata_entities_by_property). Setting 40kb as the auto-trim trigger
# keeps responses well under any observed overflow point. Bytes are a
# rough char count on compact-JSON serialization.
_WIKIDATA_RESPONSE_SOFT_LIMIT = 40_000


def _json_size(obj) -> int:
    """Approximate byte size of `obj` serialized as compact JSON. Skips
    indent whitespace for speed; the value is indicative, not exact."""
    return len(json.dumps(obj, separators=(',', ':'), ensure_ascii=False))


@mcp.tool()
def wikidata_entities_by_property(property_id: str, value_qid: str,
                                  wiki: str | None = None,
                                  limit: int = 500,
                                  note: str = "",
                                  topic: str | None = None,
                                  ctx: Context = None) -> str:
    """Find Wikidata entities whose `property_id` links to `value_qid`, and
    return each one's QID, label, sitelink title in the requested wiki,
    and Wikidata description. Common use: "all entities whose parent taxon
    is Orchidaceae" = `wikidata_entities_by_property("P171", "Q25308")`.

    This is canonical ground truth that categories + search can miss. It
    is particularly good for:
      * Biological taxonomy: `P171` (parent taxon) + a genus/family QID
      * Field-of-work / occupation joins: `P101` (field of work) +
        a discipline QID for biographies a WikiProject missed
      * Class membership: `P31` (instance of) + class QID for enumerating
        members of a well-defined class

    Does NOT add anything to the working list — review the result, then
    call add_articles with the titles you want. Each row includes:
      * `title` — sitelink on the requested wiki (empty if none)
      * `has_sitelink_on_wiki` — boolean convenience mirror of `bool(title)`
      * `sitelink_count` — total number of sitelinks this entity has
        across ALL wikis. Distinguishes the two "empty title" cases:
        `sitelink_count > 0` = the entity has articles on other wikis
        but not this one (translation candidate, or missing sitelink
        metadata for an enwiki article that actually exists — worth
        probing via `preview_search` on the label); `sitelink_count == 0`
        = the entity has no article on any wiki (genuine Wikidata-only
        entity, probably a real gap).
    Run fetch_descriptions after committing to get Wikipedia descriptions;
    the Wikidata description here is separate.

    Args:
        property_id: Wikidata property (e.g. "P171" for parent taxon).
                     Must start with "P".
        value_qid:   Wikidata entity (e.g. "Q25308" for Orchidaceae).
                     Must start with "Q". For literal-valued properties,
                     use wikidata_sparql directly.
        wiki:        Wikipedia language code to resolve sitelinks + labels
                     + description against. Defaults to the active topic's
                     wiki, or "en".
        limit:       Max rows (default 500, hard-capped at 10000).
        note:        Optional free-text observation for this call's log
                     entry. Use for mid-flow reflection; empty by default.
        topic:       Optional topic name to infer the wiki from.
    """
    _start = _start_call()
    wiki = _resolve_wiki(ctx, wiki, topic)
    try:
        rows = _wikidata_entities_by_property(
            property_id, value_qid, wiki=wiki, limit=limit)
    except ValueError as e:
        return json.dumps({'error': str(e)}, indent=2)
    except Exception as e:
        return json.dumps({
            'error': f'Wikidata query failed: {type(e).__name__}: {e}',
            'hint': 'Check property/value QIDs are valid, or drop to '
                    'wikidata_sparql for a diagnostic query.',
        }, indent=2)

    with_title = sum(1 for r in rows if r.get('title'))
    response = {
        'wiki': wiki,
        'property': property_id,
        'value': value_qid,
        'total': len(rows),
        'entities_with_sitelink': with_title,
        'entities_without_sitelink': len(rows) - with_title,
        'entities': rows,
        'note': (
            f'Review the results. To commit the ones with a {wiki}wiki '
            f'sitelink as topic members, extract their titles and call '
            f'add_articles(titles=[...], source="wikidata:{property_id}={value_qid}"). '
            f'Entities without a sitelink have no article on {wiki}.wikipedia.org '
            f'yet — they are typically translation candidates, not add candidates.'
        ),
    }
    # Auto-trim on overflow — drop label + description, keep structural
    # fields (qid, title, has_sitelink_on_wiki, sitelink_count). Observed
    # to cut ~300-row responses from 85kb to ~15kb while preserving the
    # fields needed to decide what to commit. Dogfood: Symbolism.
    raw_size = _json_size(response)
    if raw_size > _WIKIDATA_RESPONSE_SOFT_LIMIT:
        trimmed_rows = [
            {k: v for k, v in r.items() if k not in ('label', 'description')}
            for r in rows
        ]
        response['entities'] = trimmed_rows
        response['auto_trimmed'] = {
            'reason': (
                f'full response was {raw_size} bytes, above the '
                f'{_WIKIDATA_RESPONSE_SOFT_LIMIT}-byte soft limit; auto-'
                f'dropped per-entity `label` and `description` to keep '
                f'the shape usable.'
            ),
            'dropped_fields': ['label', 'description'],
            'trimmed_size': _json_size(response),
            'to_get_full_fields': (
                'Pass a smaller `limit=`, or use `wikidata_query` with a '
                'narrower SELECT projection (e.g. drop `?itemLabel` and '
                '`?description`) if you only need some of the fields.'
            ),
        }
    log_usage(ctx, "wikidata_entities_by_property",
              {"property": property_id, "value": value_qid,
               "wiki": wiki, "limit": limit},
              f"{len(rows)} entities, {with_title} on {wiki}"
              f"{' [auto-trimmed]' if raw_size > _WIKIDATA_RESPONSE_SOFT_LIMIT else ''}",
              start_time=_start, note=note)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
def wikidata_query(sparql: str, note: str = "",
                   topic: str | None = None, ctx: Context = None) -> str:
    """Run a raw SPARQL query against query.wikidata.org. Use this only
    when `wikidata_entities_by_property` can't express what you need —
    compound joins, property paths, aggregates, literal-valued
    properties, multi-hop traversals.

    Returns simplified binding rows: each row is a dict keyed by SELECT
    variable name. Entity URIs are reduced to bare QIDs (`Q25308` not
    the full URL) so the AI can use them directly.

    Cost: Wikidata has a 60s per-query hard cap and stricter rate limits
    than per-wiki api.php. Expensive queries block future calls until
    the server relaxes. A 1-hour in-process cache deduplicates repeated
    queries within a session.

    Good hygiene:
      * Always include a LIMIT. Unlimited queries on broad classes
        (e.g. every P31=Q5 person) will time out.
      * Prefer labels via `SERVICE wikibase:label { bd:serviceParam
        wikibase:language "en,<wiki>". }` — cheap.
      * For entity lookups, prefer the `wdt:` predicate (truthy,
        single-value) over `p:` + `ps:` (statement reification).

    Args:
        sparql: SPARQL query text (SELECT / ASK / CONSTRUCT all work,
                SELECT most useful here).
        note:   Optional free-text observation for this call's log entry.
        topic:  Optional topic name (used only for log context; the
                query itself is wiki-agnostic).
    """
    _start = _start_call()
    try:
        rows = _wikidata_sparql(sparql)
    except Exception as e:
        return json.dumps({
            'error': f'SPARQL query failed: {type(e).__name__}: {e}',
            'hint': 'Verify syntax at query.wikidata.org. Expensive or '
                    'malformed queries are rejected.',
        }, indent=2)
    response = {'rows': rows, 'total': len(rows)}
    # Auto-truncate on overflow. The caller controls the SELECT so we
    # can't know which fields to drop — truncate row count instead and
    # tell them to narrow the projection. Proportional truncation from
    # the observed-size ratio gives a reasonable first guess; the AI
    # can rerun with a tighter SELECT or lower LIMIT.
    # Dogfood evidence: Lakes of Finland (330 rows × label = 52kb).
    raw_size = _json_size(response)
    truncated = False
    if raw_size > _WIKIDATA_RESPONSE_SOFT_LIMIT and rows:
        # Proportional estimate + verify-and-tighten. Per-row size varies,
        # and a pure proportional target often overshoots by a few hundred
        # bytes. Halve the target up to 3 times if still over.
        target_count = max(10,
            (len(rows) * _WIKIDATA_RESPONSE_SOFT_LIMIT * 8) // (raw_size * 10))
        for _ in range(3):
            candidate = {**response, 'rows': rows[:target_count],
                         'total': len(rows), 'returned_rows': target_count}
            if _json_size(candidate) <= _WIKIDATA_RESPONSE_SOFT_LIMIT:
                break
            target_count = max(10, target_count // 2)
        if target_count < len(rows):
            response['rows'] = rows[:target_count]
            response['returned_rows'] = target_count
            response['auto_truncated'] = {
                'reason': (
                    f'full response was {raw_size} bytes, above the '
                    f'{_WIKIDATA_RESPONSE_SOFT_LIMIT}-byte soft limit; '
                    f'truncated to first {target_count} of {len(rows)} rows.'
                ),
                'total_rows_from_sparql': len(rows),
                'guidance': (
                    'Narrow your SELECT projection (drop `?itemLabel` / '
                    'description variables — SPARQL `SERVICE wikibase:label` '
                    'is often the biggest cost), or add a tighter WHERE '
                    'filter and a `LIMIT` so the full result fits. Rows '
                    'beyond this truncation are not stored anywhere and '
                    'will be lost unless you re-query.'
                ),
            }
            truncated = True
    result_summary = f"{len(rows)} rows"
    if truncated:
        result_summary += f" [auto-truncated to {len(response['rows'])}]"
    log_usage(ctx, "wikidata_query",
              {"query_length": len(sparql)},
              result_summary,
              start_time=_start, note=note)
    return json.dumps(response, indent=2, ensure_ascii=False)


@mcp.tool()
def resolve_qids(limit: int = 2000, time_budget_s: int = 60,
                 note: str = "",
                 topic: str | None = None, ctx: Context = None) -> str:
    """Backfill Wikidata QIDs for articles in this topic that haven't
    been resolved yet. Uses the pageprops API (1 call per 50 titles) —
    cheap and idempotent: NULL `wikidata_qid` rows get populated, rows
    already resolved are skipped.

    Articles with no QID on Wikipedia (redirects, disambig pages,
    brand-new articles) are marked resolved-but-empty so we don't
    re-ask next time.

    Once resolved, QIDs enable cross-wiki tooling (Stage 5's
    cross_wiki_diff, completeness_check, resolve_category) and show up
    in `export_csv(enriched=True)` output.

    Auto-loops internally with a wall-clock budget; one call on a fresh
    18K-article topic takes ~360 API calls / ~90 seconds. On budget
    exhaustion returns partial progress + `remaining` count so you can
    call again.

    Args:
        limit: Max titles to resolve per internal batch (default 2000).
        time_budget_s: Wall-clock budget (default 60s).
        note:  Optional free-text observation for this call's log entry.
        topic: Optional topic name.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    deadline = time.monotonic() + max(1, time_budget_s)
    total_resolved = 0
    with_qid = 0
    batches = 0
    hit_budget = False

    while True:
        if time.monotonic() >= deadline:
            hit_budget = True
            break
        titles = db.get_unresolved_qid_titles(topic_id, limit=limit)
        if not titles:
            break
        qid_map = fetch_wikidata_qids(titles, wiki=wiki)
        db.set_wikidata_qids(topic_id, qid_map)
        total_resolved += len(titles)
        with_qid += sum(1 for v in qid_map.values() if v)
        batches += 1

    remaining = db.count_unresolved_qids(topic_id)
    log_usage(ctx, "resolve_qids",
              {"limit": limit, "time_budget_s": time_budget_s, "wiki": wiki},
              f"resolved {total_resolved} ({with_qid} with QID), "
              f"{remaining} remaining"
              f"{' (budget exhausted)' if hit_budget else ''}",
              start_time=_start, note=note)
    return json.dumps({
        'resolved': total_resolved,
        'with_qid': with_qid,
        'without_qid': total_resolved - with_qid,
        'remaining': remaining,
        'batches_run': batches,
        'time_budget_exhausted': hit_budget,
        'note': (
            'All articles in this topic now have their QID resolved '
            '(or are marked as having none).' if remaining == 0 else
            f'{remaining} articles still unresolved. Call resolve_qids '
            f'again to continue.'
        ),
    }, indent=2, ensure_ascii=False)


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

    articles, rejected_skipped, rejected_sample = _apply_rejections(topic_id, articles)

    source_label = f"wikiproject:{project_name}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "get_wikiproject_articles", {"project": project_name, "wiki": wiki},
              f"{len(articles)} articles", start_time=_start, note=note)
    result = {
        'wiki': wiki,
        'project': project_name,
        'articles_found': len(articles),
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
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


def _cost_report(start_time: float) -> dict:
    """Summarize wall-time + Wikipedia API cost for a call, optionally
    emitting a soft cost_warning when thresholds are exceeded. Thresholds
    are intentionally rough — they're starting points to be tuned once
    usage.jsonl has enough post-1.1 entries to fit against."""
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    api_calls = get_call_counters()['wikipedia_api_calls']
    report = {
        'elapsed_ms': elapsed_ms,
        'wikipedia_api_calls': api_calls,
    }
    warnings = []
    if api_calls > 2500:
        warnings.append(f'{api_calls} Wikipedia API calls')
    if elapsed_ms > 60000:
        warnings.append(f'{elapsed_ms/1000:.0f}s wall time')
    if warnings:
        report['cost_warning'] = (
            'This call was expensive (' + ', '.join(warnings) + '). '
            'Consider narrowing scope on future pulls: lower depth, '
            'specific subtree via preview_category_pull, narrower '
            'query, or main_content_only=True.'
        )
    return report


def _apply_rejections(topic_id: int, candidates,
                      sample_limit: int = 10
                      ) -> tuple[list[str], int, list[dict]]:
    """Filter out titles that are in the topic's rejection list.

    Returns (kept, rejected_count, rejected_sample):
      * kept — input minus rejected, as a list, order preserved
      * rejected_count — how many candidates were blocked
      * rejected_sample — up to `sample_limit` {title, reason} entries
        so the AI can see WHY those were blocked without a separate
        list_rejections call.

    Every gather tool funnels its candidate set through this helper so
    the rejection surface is uniform (`rejected_skipped` + `rejected_sample`
    in every response) and any future change lands in one place."""
    rejections_map = db.get_rejections_map(topic_id)
    if not rejections_map:
        return list(candidates), 0, []
    kept: list[str] = []
    rejected_titles: list[str] = []
    for t in candidates:
        if t in rejections_map:
            rejected_titles.append(t)
        else:
            kept.append(t)
    sample = [
        {'title': t, 'reason': rejections_map[t]}
        for t in rejected_titles[:sample_limit]
    ]
    return kept, len(rejected_titles), sample


def _walk_category_tree(category: str, depth: int, exclude_set: set[str],
                        max_articles: int, wiki: str,
                        deadline: float | None = None
                        ) -> tuple[set[str], set[str], set[str], bool]:
    """Breadth-first walk of a Wikipedia category tree with optional
    cooperative time budget.

    Returns a 4-tuple:
      * articles — mainspace titles collected.
      * fully_crawled — categories whose article enum AND subcat enum both
        completed. Safe to add to `exclude_set` on a resume call (that
        call will skip descending into them from the root).
      * pending — categories dequeued but not yet processed when the
        deadline fired. Empty when `timed_out` is False.
      * timed_out — True iff `deadline` was set and the budget was
        exhausted mid-walk. Callers should surface this to the AI so
        it can decide whether to resume with the exclude= idiom or
        narrow scope.

    `deadline` is a `time.monotonic()`-scale wall-clock cutoff. When
    None, the walk runs to completion.

    Budget checks happen only between category-units of work (top of
    loop). One category's article + subcat enum is treated as atomic so
    the fully_crawled / pending split is always well-defined."""
    articles: set[str] = set()
    enqueued: set[str] = {category}
    fully_crawled: set[str] = set()

    queue = collections.deque([(category, 0)])
    timed_out = False
    while queue and len(articles) < max_articles:
        if deadline is not None and time.monotonic() >= deadline:
            timed_out = True
            break
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
                if subcat not in enqueued and subcat not in exclude_set:
                    enqueued.add(subcat)
                    queue.append((subcat, d + 1))

        fully_crawled.add(cat)

    pending = {c for c, _ in queue}
    return articles, fully_crawled, pending, timed_out


_TAXONOMY_KEYWORDS = {
    'orchid', 'plant', 'tree', 'flower', 'flora', 'fungus', 'mushroom',
    'alga', 'moss', 'fern', 'grass', 'lichen',
    'bird', 'mammal', 'fish', 'reptile', 'amphibian', 'insect',
    'beetle', 'butterfly', 'moth', 'spider', 'lizard', 'snake',
    'frog', 'crustacean', 'mollusk', 'fauna', 'animal',
    'species', 'genus', 'taxa', 'taxon', 'family',
}
_TAXONOMY_SUFFIXES = ('aceae', 'idae', 'ales', 'phyta', 'ae')


def _looks_taxonomic(topic_name: str, category: str) -> bool:
    """True when a topic + category combination is clearly taxonomic —
    topic name signals biological classification AND the category name
    looks like a Latin-binomial-producing genus (single capitalized
    ASCII word of 3+ chars, e.g. "Bulbophyllum", "Cattleya", "Vanilla").
    In that case the no-word-overlap warning is a near-100% false
    positive and should be suppressed."""
    topic_lower = topic_name.lower()
    has_tax_keyword = any(k in topic_lower for k in _TAXONOMY_KEYWORDS)
    has_tax_suffix = any(w.endswith(_TAXONOMY_SUFFIXES)
                         for w in re.findall(r'\w+', topic_lower))
    is_latin_genus = bool(re.fullmatch(r'[A-Z][a-z]{2,}', category.strip()))
    return (has_tax_keyword or has_tax_suffix) and is_latin_genus


def _scope_drift_warning(category: str, topic_name: str,
                         source_label: str, count: int) -> str | None:
    """Return a scope-drift warning string when a big category pull has no
    word-level overlap with the topic name (e.g. topic='orchids' pulling
    category='Cognition'). None when the pull is OK or when the pull is
    clearly taxonomic (Latin genus name under a biology-flavored topic —
    those are legitimate pulls even though they share zero words)."""
    if count <= 500 or not topic_name:
        return None
    if _looks_taxonomic(topic_name, category):
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
                          max_articles: int = 50000,
                          time_budget_s: int = 240,
                          note: str = "",
                          topic: str | None = None, ctx: Context = None) -> str:
    """Crawl a category tree and collect all articles. Adds them to the
    working list with source 'category'.

    Runs under a cooperative time budget (default 240s, under the MCP
    transport's 300s hard cap). If the walk doesn't finish in time the
    tool returns `timed_out: true` with partial results AND a resume
    hint: `resume_suggestion` tells the AI how to call the tool again
    to continue from where it stopped — typically by passing
    `exclude=[fully-crawled branches]` so the next call skips already-
    covered subtrees.

    Args:
        category: Category name without "Category:" prefix
        depth: Maximum depth to crawl (default 3, max 5)
        exclude: Category names to skip (prune entire branches).
                 On resume, pass the `exclude_suggestion` from the prior
                 timed-out response to skip already-covered subtrees.
        max_articles: Maximum articles to collect (default 50000).
        time_budget_s: Wall-clock budget in seconds (default 240). Set
                       lower for fast probes, higher only if you know
                       the tree is bounded. Above ~280 risks hitting
                       the MCP hard cap (300s).
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
    deadline = time.monotonic() + max(1, time_budget_s)
    articles, fully_crawled, pending, timed_out = _walk_category_tree(
        category, depth, exclude_set, max_articles, wiki, deadline=deadline)

    articles, rejected_skipped, rejected_sample = _apply_rejections(topic_id, articles)

    source_label = f"category:{category}"
    batch = [(title, source_label, None) for title in articles]
    added, updated = db.add_articles(topic_id, batch)

    result = {
        'wiki': wiki,
        'root_category': category,
        'depth': depth,
        'excluded': sorted(exclude_set),
        'articles_found': len(articles),
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
        'categories_fully_crawled': len(fully_crawled),
        'categories_pending': len(pending),
        'new_articles_added': added,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'timed_out': timed_out,
        'note': f'To undo this pull, use: remove_by_source("{source_label}")',
    }

    if timed_out:
        # Merge old excludes + newly-fully-crawled so the AI can pass
        # one clean exclude list on resume. Cap pending_branches sample
        # for readability on 300+-subcategory trees.
        exclude_suggestion = sorted(exclude_set | fully_crawled)
        result['resume_suggestion'] = {
            'note': (
                'Budget exhausted mid-walk. Call get_category_articles again '
                f'with exclude=<this list> to skip already-crawled branches. '
                'For deep or flat-and-wide trees, consider lowering depth, '
                'narrowing to a specific subtree, or raising time_budget_s '
                '(max practical ~280s under the MCP 300s hard cap).'
            ),
            'exclude': exclude_suggestion,
            'pending_branches_sample': sorted(pending)[:50],
            'pending_branches_total': len(pending),
        }

    # Noisy-pull warning: large pull with no word-level overlap between the
    # category name and the topic name is a strong signal of scope drift
    # (e.g. topic="educational psychology", category="Cognition").
    _, topic_name, _ = _get_topic(ctx)
    warning = _scope_drift_warning(category, topic_name, source_label, added)
    if warning:
        result['warning'] = warning

    result['cost'] = _cost_report(_start)
    log_usage(ctx, "get_category_articles",
              {"category": category, "depth": depth, "wiki": wiki,
               "time_budget_s": time_budget_s},
              f"{len(articles)} articles, {len(fully_crawled)} cats"
              f"{' (timed out)' if timed_out else ''}",
              start_time=_start, timed_out=timed_out, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def preview_category_pull(category: str, depth: int = 3,
                          exclude: list[str] | None = None,
                          max_articles: int = 50000,
                          sample_size: int = 50,
                          time_budget_s: int = 240,
                          note: str = "",
                          topic: str | None = None,
                          ctx: Context = None) -> str:
    """Dry-run of get_category_articles. Walks the category tree and reports
    article / category counts + a sampled preview with descriptions WITHOUT
    committing anything. Use when you want to gauge the shape of a subtree
    before deciding whether to pull it, or when a `survey_categories`
    warning flagged the tree as potentially oversized.

    Honors the same cooperative time budget as get_category_articles and
    returns `timed_out` + a `resume_suggestion` on partial walks — the
    numbers you see are real partials, not "approximately this if we had
    finished."

    Args:
        category: Category name without "Category:" prefix
        depth: Maximum depth to crawl (default 3, max 5)
        exclude: Category names to skip (prune entire branches)
        max_articles: Upper bound on articles to enumerate during preview.
                      Same semantics as get_category_articles.
        sample_size: How many titles to return in the sample (default 50).
                     Descriptions are only fetched for the sample.
        time_budget_s: Wall-clock budget in seconds (default 240).
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
    deadline = time.monotonic() + max(1, time_budget_s)
    articles_set, fully_crawled, pending, timed_out = _walk_category_tree(
        category, depth, exclude_set, max_articles, wiki, deadline=deadline)

    articles = sorted(articles_set)
    existing = db.get_all_titles(topic_id)
    new_count = sum(1 for t in articles if t not in existing)
    overlap_count = len(articles) - new_count

    sample_titles = articles[:max(0, sample_size)]
    descriptions = fetch_descriptions_with_fallback(sample_titles, wiki=wiki) if sample_titles else {}
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
        'categories_fully_crawled': len(fully_crawled),
        'categories_pending': len(pending),
        'new_to_topic': new_count,
        'already_in_topic': overlap_count,
        'sample': sample,
        'would_be_source_label': would_be_source_label,
        'timed_out': timed_out,
        'note': (
            'Nothing added to the working list. Review the sample + counts, '
            'then call get_category_articles(category) to commit, or pass '
            'exclude=[...] to prune branches first. Skip entirely if the '
            'subtree is too broad.'
        ),
    }
    if timed_out:
        result['resume_suggestion'] = {
            'note': (
                'Preview budget exhausted mid-walk — counts above are partial. '
                'To commit the covered portion plus continue, call '
                'get_category_articles with exclude=<this list>, or raise '
                'time_budget_s on this preview to see a fuller picture.'
            ),
            'exclude': sorted(exclude_set | fully_crawled),
            'pending_branches_sample': sorted(pending)[:50],
            'pending_branches_total': len(pending),
        }

    _, topic_name, _ = _get_topic(ctx)
    warning = _scope_drift_warning(category, topic_name, would_be_source_label, new_count)
    if warning:
        result['warning'] = warning

    log_usage(ctx, "preview_category_pull",
              {"category": category, "depth": depth, "wiki": wiki,
               "sample_size": sample_size, "time_budget_s": time_budget_s},
              f"{len(articles)} articles ({new_count} new), "
              f"{len(fully_crawled)} cats"
              f"{' (timed out)' if timed_out else ''}",
              start_time=_start, timed_out=timed_out, note=note)
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
            # Some links (notably image-thumbnail wrappers produced by
            # MediaWiki's parser) carry a caption string in the title
            # attribute while href points at a File:/Category:/etc. page.
            # Trust href for namespace detection, not title — the caption
            # typically has no colon and would sneak past the title-based
            # colon check further down.
            href_title = ''
            if href.startswith('/wiki/'):
                href_title = urllib.parse.unquote(
                    href[len('/wiki/'):]).replace('_', ' ').split('#', 1)[0]
            elif '/w/index.php?title=' in href:
                qs = href.split('/w/index.php?', 1)[1]
                href_title = urllib.parse.unquote(
                    dict(urllib.parse.parse_qsl(qs)).get('title', '')
                ).replace('_', ' ')
            if ':' in href_title:
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
                           main_content_only: bool,
                           deadline: float | None = None,
                           ) -> tuple[list[str], bool, bool]:
    """Fetch mainspace links from a list/outline page.

    Returns (links, main_content_only_actual, timed_out).
    - `main_content_only_actual` reflects whether the HTML parse path
      succeeded — when `main_content_only=True` but the page's HTML came
      back empty (missing page, parse error), we fall back to prop=links
      and return False so the caller can surface that to the user.
    - `timed_out` is True iff the `prop=links` pagination loop hit the
      deadline. The HTML-parse path is a single API call + in-memory
      parse so it never times out meaningfully; this flag only fires on
      the fallback path (or explicit main_content_only=False).

    `deadline` is a time.monotonic()-scale cutoff. None means run to
    completion."""
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
            return [normalize_title(t) for t in extractor.links], True, False
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
    timed_out = False
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            timed_out = True
            break
        data = api_get(wiki_api_url(wiki), params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                for link in page.get('links', []):
                    links.append(normalize_title(link['title']))
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break
    return links, False, timed_out


@mcp.tool()
def harvest_list_page(title: str, main_content_only: bool = True,
                      time_budget_s: int = 240,
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
        time_budget_s: Wall-clock budget in seconds (default 240). The
            HTML-parse path (the default) is always one API call and
            effectively never hits the budget. The prop=links fallback
            path paginates and can time out on pages with tens of
            thousands of links. On timeout, partial links are still
            committed; the AI can retry with `main_content_only=True`.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    deadline = time.monotonic() + max(1, time_budget_s)
    links, used_html, timed_out = _fetch_list_page_links(
        title, wiki, main_content_only, deadline=deadline)

    links, rejected_skipped, rejected_sample = _apply_rejections(topic_id, links)

    source_label = f"list_page:{title}"
    batch = [(t, source_label, None) for t in links]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "harvest_list_page",
              {"title": title, "wiki": wiki, "main_content_only": used_html,
               "time_budget_s": time_budget_s},
              f"{len(links)} links, {added} new"
              f"{' (timed out)' if timed_out else ''}",
              start_time=_start, timed_out=timed_out, note=note)
    result = {
        'wiki': wiki,
        'source_page': title,
        'main_content_only': used_html,
        'links_found': len(links),
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
        'new_articles_added': added,
        'source_label': source_label,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'timed_out': timed_out,
        'cost': _cost_report(_start),
        'note': (
            f'To undo this harvest, use: remove_by_source("{source_label}"). '
            f'Pass main_content_only=False if you want the raw link set '
            f'including navboxes and navigation chrome. Use '
            f'preview_harvest_list_page first if you want to inspect before '
            f'committing.'
        ),
    }
    if timed_out:
        result['resume_suggestion'] = {
            'note': (
                f'Budget exhausted during prop=links pagination. {len(links)} '
                f'links were committed; there may be more on the page. Retry '
                f'with main_content_only=True (single-API-call path, always '
                f'finishes under budget) if that fits your use case — '
                f'otherwise split the list page or raise time_budget_s.'
            ),
        }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def preview_harvest_list_page(title: str, sample_size: int = 50,
                              main_content_only: bool = True,
                              time_budget_s: int = 240,
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
        time_budget_s: Wall-clock budget in seconds (default 240). Same
                       semantics as harvest_list_page — only the prop=links
                       fallback path can time out.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    deadline = time.monotonic() + max(1, time_budget_s)
    links, used_html, timed_out = _fetch_list_page_links(
        title, wiki, main_content_only, deadline=deadline)
    existing = db.get_all_titles(topic_id)
    new_count = sum(1 for t in links if t not in existing)
    overlap_count = len(links) - new_count

    sample_titles = links[:max(0, sample_size)]
    descriptions = fetch_descriptions_with_fallback(sample_titles, wiki=wiki) if sample_titles else {}
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
               "sample_size": sample_size, "time_budget_s": time_budget_s},
              f"{len(links)} links ({new_count} new)"
              f"{' (timed out)' if timed_out else ''}",
              start_time=_start, timed_out=timed_out, note=note)
    return json.dumps({
        'wiki': wiki,
        'source_page': title,
        'main_content_only': used_html,
        'total_links': len(links),
        'new_to_topic': new_count,
        'already_in_topic': overlap_count,
        'sample': sample,
        'would_be_source_label': would_be_source_label,
        'timed_out': timed_out,
        'note': (
            'Nothing added to the working list. Review the sample, then '
            'call harvest_list_page(title) to commit, or skip entirely '
            'if the preview looks noisy. Pass main_content_only=False to '
            'see the raw prop=links set including navigation chrome.'
        ),
    }, indent=2, ensure_ascii=False)


class _AllMainspaceLinkExtractor(html.parser.HTMLParser):
    """Collect every mainspace <a> link in a rendered HTML fragment.

    Unlike `_MainContentLinkExtractor`, does NOT exclude navbox-class or
    sidebar-class subtrees — used for `harvest_navbox` where the entire
    page IS a navbox and filtering those classes would drop everything.
    Carries over the href-based namespace check from the caption-as-title
    fix so image-thumb wrappers don't pollute the link set."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        attr_dict = dict(attrs)
        link_title = attr_dict.get('title', '').strip()
        href = attr_dict.get('href', '')
        is_wiki_link = (href.startswith('/wiki/')
                        or '/w/index.php?title=' in href)
        if not is_wiki_link or not link_title:
            return
        href_title = ''
        if href.startswith('/wiki/'):
            href_title = urllib.parse.unquote(
                href[len('/wiki/'):]).replace('_', ' ').split('#', 1)[0]
        elif '/w/index.php?title=' in href:
            qs = href.split('/w/index.php?', 1)[1]
            href_title = urllib.parse.unquote(
                dict(urllib.parse.parse_qsl(qs)).get('title', '')
            ).replace('_', ' ')
        if ':' in href_title:
            return
        if link_title.endswith(' (page does not exist)'):
            link_title = link_title[:-len(' (page does not exist)')].strip()
        if ':' in link_title:
            return
        if link_title in self._seen:
            return
        self._seen.add(link_title)
        self.links.append(link_title)


@mcp.tool()
def harvest_navbox(template: str, note: str = "",
                   topic: str | None = None, ctx: Context = None) -> str:
    """Extract mainspace article links from a Wikipedia navbox template.

    Navboxes (the horizontal tables at the bottom of Wikipedia articles
    — e.g. `Template:Apollo program`, `Template:tvN series`,
    `Template:Pulitzer Prize for Investigative Reporting`) are
    editor-curated enumerations. They tend to be cleaner and more
    canonical than free-form "List of …" pages, which often collect
    prose-body links alongside the curated entries. Three dogfood
    sessions (Pulitzer, K-drama, Symbolism) specifically asked for a
    navbox-harvest primitive so they could target template-curated
    content directly instead of fishing it out of list-page prose.

    Extracted links are added to the working list with source label
    `navbox:<template-name>`. Undo with `remove_by_source`.

    Args:
        template: Template name, either "Apollo program" (bare) or
                  "Template:Apollo program" (prefixed). Both work.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    # Accept "Template:X" or bare "X". Strip whitespace before the
    # prefix check so "  Template:X  " works like "X".
    bare = template.strip()
    if bare.lower().startswith('template:'):
        bare = bare.split(':', 1)[1].strip()
    if not bare:
        return json.dumps({'error': 'Template name cannot be empty.'}, indent=2)
    page_title = f"Template:{bare}"

    parse_params = {
        'action': 'parse',
        'page': page_title,
        'prop': 'text',
        'format': 'json',
        'formatversion': '2',
        'redirects': '1',
        'disabletoc': '1',
        'disableeditsection': '1',
    }
    data = api_get(wiki_api_url(wiki), parse_params)

    if not isinstance(data, dict) or 'error' in data:
        return json.dumps({
            'wiki': wiki,
            'error': f'Template not found or inaccessible: {page_title}',
            'api_error': (data or {}).get('error') if isinstance(data, dict) else None,
            'hint': (
                f'Check that "{page_title}" exists on {wiki}.wikipedia.org. '
                f'Common mistake: passing a project/portal name (e.g. '
                f'"WikiProject Apollo") — navboxes live in the Template: '
                f'namespace, not the Wikipedia: namespace.'
            ),
        }, indent=2, ensure_ascii=False)

    html_text = data.get('parse', {}).get('text', '')
    if not html_text:
        return json.dumps({
            'wiki': wiki,
            'error': f'Template rendered to empty HTML: {page_title}',
        }, indent=2, ensure_ascii=False)

    extractor = _AllMainspaceLinkExtractor()
    extractor.feed(html_text)
    links = [normalize_title(t) for t in extractor.links]

    links, rejected_skipped, rejected_sample = _apply_rejections(topic_id, links)

    source_label = f"navbox:{bare}"
    batch = [(t, source_label, None) for t in links]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "harvest_navbox",
              {"template": bare, "wiki": wiki},
              f"{len(links)} links, {added} new",
              start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'template': page_title,
        'source_label': source_label,
        'links_extracted': len(links),
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
        'new_articles_added': added,
        'total_in_working_list': db.get_status(topic_id)['total_articles'],
        'note': (
            f'Links added with source="{source_label}". To undo this pull, '
            f'use: remove_by_source("{source_label}"). Navboxes typically '
            f'include a handful of non-article links (category pages, other '
            f'navboxes) that are filtered out here — the count reflects '
            f'mainspace articles only.'
        ),
    }, indent=2, ensure_ascii=False)


def _slugify_for_source_label(query: str, max_length: int = 60) -> str:
    """Slugify a search query for use inside a source label.

    Preserves ':' separators so CirrusSearch operator prefixes stay
    readable (e.g. `morelike:the-orchid-thief`, `intitle:climate-change`).
    Lowercases, strips Latin diacritics, replaces runs of non-word
    characters with '-', collapses, and truncates to `max_length` without
    leaving a trailing '-' or ':'. Unicode letters (CJK, Cyrillic, Arabic,
    etc.) survive intact — dropping them entirely would collapse
    `morelike:牧野富太郎` to `morelike` and lose all seed information on
    non-ASCII seeds.

    Used by `search_articles` / `preview_search` when building the
    `search:<…>` source label. Existing DB rows keep their older
    un-slugified labels."""
    parts = query.split(':')
    slugged_parts = []
    for p in parts:
        normalized = unicodedata.normalize('NFKD', p)
        without_combining = ''.join(c for c in normalized
                                    if not unicodedata.combining(c))
        lower = without_combining.lower()
        # \w with re.UNICODE matches Unicode letters + digits + underscore,
        # so non-ASCII scripts survive; other punctuation / whitespace
        # collapses to '-'.
        slugged = re.sub(r'[^\w]+', '-', lower, flags=re.UNICODE).strip('-_')
        slugged_parts.append(slugged)
    label = ':'.join(slugged_parts).strip(':')
    if len(label) > max_length:
        label = label[:max_length].rstrip('-:_')
    return label or 'unnamed'


def _apply_within_category(query: str, within_category: str | None) -> str:
    """Append an `incategory:"…"` operator when within_category is set.
    CirrusSearch's incategory is single-level (not recursive); this keeps
    the semantics close to a normal full-text search scoped to one
    category's direct members. Use `get_category_articles` for recursive
    walks or combine multiple with `within_category="A|B|C"` (CirrusSearch
    treats `|` as OR in incategory expressions)."""
    if not within_category:
        return query
    # Quote if the category contains spaces. Category titles use underscores
    # in URLs but CirrusSearch accepts either form; quotes are safe.
    return f'{query} incategory:"{within_category}"' if query else f'incategory:"{within_category}"'


_INTITLE_OR_PATTERN = re.compile(
    r'^\s*intitle:"[^"]+"(?:\s+OR\s+intitle:"[^"]+")+\s*$')


def _split_intitle_or_query(query: str) -> list[str] | None:
    """If `query` is a pure compound `intitle:"A" OR intitle:"B" [OR ...]`
    chain, return the titles as a list. Else return None.

    Works around a CirrusSearch quirk where compound intitle-OR queries
    silently return zero results while each single-clause form returns
    matches. Observed across three dogfood sessions. Callers split into
    N separate queries and union the results."""
    if not _INTITLE_OR_PATTERN.match(query):
        return None
    titles = re.findall(r'intitle:"([^"]+)"', query)
    return titles if len(titles) >= 2 else None


def _run_cirrus_search(query: str, within_category: str | None,
                        limit: int, wiki: str) -> tuple[list[str], str]:
    """Run a CirrusSearch query, union-splitting compound intitle-OR
    forms. Returns (title_list, effective_query_note)."""
    scoped_query = _apply_within_category(query, within_category)
    subtitles = _split_intitle_or_query(query)

    if not subtitles:
        params = {
            'list': 'search', 'srsearch': scoped_query,
            'srnamespace': '0', 'srlimit': str(min(limit, 500)),
            'srinfo': '', 'srprop': '',
        }
        titles = [item['title'] for item in
                  api_query_all(params, 'search', max_items=limit, wiki=wiki)]
        return titles, scoped_query

    # Compound intitle-OR: run each clause separately and union.
    seen: set[str] = set()
    titles: list[str] = []
    for sub in subtitles:
        sub_scoped = _apply_within_category(f'intitle:"{sub}"', within_category)
        params = {
            'list': 'search', 'srsearch': sub_scoped,
            'srnamespace': '0', 'srlimit': str(min(limit, 500)),
            'srinfo': '', 'srprop': '',
        }
        for item in api_query_all(params, 'search', max_items=limit, wiki=wiki):
            t = item['title']
            if t not in seen:
                seen.add(t)
                titles.append(t)
            if len(titles) >= limit:
                break
        if len(titles) >= limit:
            break
    note = (f'compound intitle-OR split into {len(subtitles)} separate '
            f'queries (CirrusSearch quirk workaround)')
    return titles, note


@mcp.tool()
def search_articles(query: str, limit: int = 500,
                    within_category: str | None = None,
                    note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Search Wikipedia using CirrusSearch. Supports operators like intitle:,
    morelike:, hastemplate:, incategory:. Adds results to working list with source 'search'.

    Args:
        query: Search query (e.g., 'intitle:"climate change"', 'morelike:Effects of climate change')
        limit: Maximum results (default 500)
        within_category: If set, scope the search to articles that are direct
                         members of this category. Single-level (not recursive)
                         — CirrusSearch's `incategory:` doesn't walk subcats.
                         For multiple categories (union), pass `"A|B|C"`.
                         For a recursive sweep, use `get_category_articles`
                         instead.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    results, scoped_query = _run_cirrus_search(query, within_category, limit, wiki)
    results, rejected_skipped, rejected_sample = _apply_rejections(topic_id, results)

    # Tag with the specific query so remove_by_source / get_articles_by_source
    # can target one bad pull without blanket-touching all search-added
    # articles. Slugify the query so labels are ASCII / lowercase / hyphenated
    # (diacritics stripped, special chars replaced) — keeps list_sources
    # output tractable. Use prefix_match=True on remove_by_source to clear a
    # family of queries (e.g. "search:morelike:" drops every similarity
    # pull at once — the "morelike:" prefix survives slugification).
    source_label = f"search:{_slugify_for_source_label(scoped_query)}"
    batch = [(title, source_label, None) for title in results]
    added, updated = db.add_articles(topic_id, batch)

    log_usage(ctx, "search_articles",
              {"query": query, "within_category": within_category, "wiki": wiki},
              f"{len(results)} results", start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'query': query,
        'within_category': within_category,
        'effective_query': scoped_query,
        'source_label': source_label,
        'results_found': len(results),
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
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
def preview_search(query: str, limit: int = 50,
                   within_category: str | None = None,
                   note: str = "",
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
        within_category: Same semantics as search_articles — scope results
                         to direct members of this category. Single-level
                         (not recursive); for union pass "A|B|C".
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
    titles, scoped_query = _run_cirrus_search(query, within_category, limit, wiki)

    if not titles:
        return json.dumps({
            'wiki': wiki,
            'query': query,
            'within_category': within_category,
            'effective_query': scoped_query,
            'results_found': 0,
            'results': [],
        }, indent=2, ensure_ascii=False)

    descriptions = fetch_descriptions_with_fallback(titles, wiki=wiki)
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

    log_usage(ctx, "preview_search",
              {"query": query, "within_category": within_category,
               "limit": limit, "wiki": wiki},
              f"{len(titles)} results ({new_count} new)",
              start_time=_start, note=note)
    return json.dumps({
        'wiki': wiki,
        'query': query,
        'within_category': within_category,
        'effective_query': scoped_query,
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
def fetch_descriptions(limit: int = 2000, time_budget_s: int = 60,
                       note: str = "",
                       topic: str | None = None, ctx: Context = None) -> str:
    """Fetch short descriptions for articles in the current topic that
    don't have one yet, and persist them. Descriptions show up in
    get_articles / get_articles_by_source output so the AI or user can judge
    relevance while paging or reviewing a source. export_csv also reuses them.

    On **enwiki**, sources the Wikidata short description (comprehensive
    coverage). On **non-en wikis**, first tries Wikidata — which is sparse
    outside English — then falls back to the first sentence of the
    article's REST summary (MediaWiki's `/page/summary/{title}` endpoint).
    The fallback is what makes cross-wiki topic builds usable: zhwiki /
    jawiki / ptwiki previously came back with all-empty descriptions.

    Auto-loops internally: each batch fetches up to `limit` titles, then
    continues with the next undescribed chunk until either the topic is
    fully described or `time_budget_s` is exhausted. One call on a fresh
    topic typically drains the backlog; call again if `remaining_undescribed`
    is non-zero on return.

    An article with no short-desc on Wikipedia (and no REST extract on
    non-en) is stored as an empty string so we don't re-ask next time.

    Args:
        limit: Max titles to fetch per internal batch (default 2000). Tune
               down if you want smaller, more interruptible chunks; up if
               you want to minimize round-trips.
        time_budget_s: Overall wall-clock budget for auto-loop (default 60s).
               When exhausted the tool returns partial results with
               remaining_undescribed set; the AI can call again to continue.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an
               MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    deadline = time.monotonic() + max(1, time_budget_s)
    total_fetched = 0
    total_non_empty = 0
    batches = 0
    hit_budget = False

    while True:
        if time.monotonic() >= deadline:
            hit_budget = True
            break
        titles = db.get_undescribed_titles(topic_id, limit=limit)
        if not titles:
            break
        desc_map = fetch_descriptions_with_fallback(
            titles, wiki=wiki, deadline=deadline)
        # Titles unprobed by the REST fallback (budget exhausted mid-
        # batch) are omitted from desc_map so they stay NULL in the DB
        # and a follow-up call retries them.
        unprobed = [t for t in titles if t not in desc_map]
        db.set_descriptions(topic_id, desc_map)
        total_fetched += len(desc_map)
        total_non_empty += sum(1 for v in desc_map.values() if v)
        batches += 1
        if unprobed:
            # REST fallback ran out of time mid-batch. Treat as budget
            # exhausted so the tool returns now and the AI can call
            # again to continue.
            hit_budget = True
            break

    remaining = db.count_undescribed(topic_id)
    if remaining == 0 and total_fetched == 0:
        log_usage(ctx, "fetch_descriptions",
                  {"limit": limit, "time_budget_s": time_budget_s},
                  "no undescribed articles", start_time=_start, note=note)
        return json.dumps({
            'fetched': 0,
            'remaining_undescribed': 0,
            'note': 'All articles in this topic already have descriptions (or were checked).',
        }, indent=2, ensure_ascii=False)

    log_usage(ctx, "fetch_descriptions",
              {"limit": limit, "time_budget_s": time_budget_s},
              f"fetched {total_fetched} in {batches} batch(es), "
              f"{total_non_empty} non-empty, {remaining} still undescribed"
              f"{' (budget exhausted)' if hit_budget else ''}",
              start_time=_start, note=note)

    if remaining == 0:
        tail = 'All articles in this topic now have descriptions (or were checked).'
    elif hit_budget:
        tail = (f'Time budget ({time_budget_s}s) exhausted with {remaining} still '
                f'undescribed. Call fetch_descriptions again to continue.')
    else:
        tail = (f'{remaining} articles still undescribed — call again if you want '
                f'to continue. (Budget was not exhausted; this can happen if a '
                f'batch returned early.)')

    return json.dumps({
        'fetched': total_fetched,
        'non_empty': total_non_empty,
        'batches_run': batches,
        'remaining_undescribed': remaining,
        'time_budget_exhausted': hit_budget,
        'note': tail,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def fetch_article_leads(titles: list[str], sentences: int = 3,
                        wiki: str | None = None, note: str = "",
                        topic: str | None = None, ctx: Context = None) -> str:
    """Fetch the first N sentences of each article's body (the article's
    *lead*, not the Wikidata shortdesc). Use when a shortdesc looks thin
    or misleading and you need a richer read before scoring, rejecting,
    or accepting a candidate.

    Distinct from `fetch_descriptions`: that tool bulk-fills the persistent
    description column with Wikidata short-descs (plus an enwiki REST
    fallback when they're empty). This tool is a targeted, non-persistent
    probe against the article text itself, for disambiguating ambiguous
    titles. Typical cases — all observed during the 2026-04-23 AA-STEM
    audit — where shortdesc lies and the lead is needed:
      - "American academic" → Gloria Chisum, applied-STEM researcher on
        pilot-vision eyewear.
      - Shortdesc truncated mid-title → William Hallett Greene, first
        Black meteorologist + Signal Corps station chief.
      - "American long jumper" → Meredith Gourdine, who was also a plasma
        physicist and engineer.

    Returns a dict title -> lead text. Empty string for missing pages.
    Batched internally (20 titles per API call — MediaWiki's `exlimit`
    cap when `exsentences` is in use); a 60-title call is 3 round-trips.

    Args:
        titles: List of article titles to fetch leads for. No backlog
                drain — you pass exactly the titles you want.
        sentences: How many sentences of the lead to return per title.
                   Default 3. Capped at 5 (MediaWiki's `exsentences`
                   accepts more but 5 is the useful ceiling for
                   disambiguation; beyond that, use `score_by_extract`
                   or read the article directly).
        wiki: Override the wiki. Defaults to the current topic's wiki
              (from the session or from `topic=`), falling back to 'en'.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Used only to resolve the wiki when
               `wiki` is not set; leads are not attached to topic state.
    """
    _start = _start_call()
    if not isinstance(titles, list) or not titles:
        return "Provide a non-empty list of titles."
    resolved_wiki = _resolve_wiki(ctx, wiki, topic)
    capped_sentences = max(1, min(5, int(sentences)))

    leads = _fetch_article_leads(titles, wiki=resolved_wiki,
                                 sentences=capped_sentences)
    non_empty = sum(1 for v in leads.values() if v)

    log_usage(ctx, "fetch_article_leads",
              {"titles_count": len(titles), "sentences": capped_sentences,
               "wiki": resolved_wiki},
              f"{non_empty}/{len(titles)} non-empty",
              start_time=_start, note=note)

    return json.dumps({
        'wiki': resolved_wiki,
        'sentences': capped_sentences,
        'count': len(leads),
        'non_empty': non_empty,
        'leads': leads,
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
def auto_score_by_keyword(keywords: list[str], score: int = 9,
                          match_description: bool = False,
                          overwrite_scored: bool = False,
                          note: str = "",
                          topic: str | None = None, ctx: Context = None) -> str:
    """Fast-pass scoring for articles whose title (or description, if
    `match_description=True`) contains any of the given keywords. Case-
    insensitive substring match.

    Takes explicit keywords — works on any Wikipedia language edition and
    handles non-English topic names, Latin-binomial taxonomies, and
    compound / suffixed topic names correctly. (This replaces the older
    auto_score_by_title, which did a substring match of the topic name
    against titles — broken for non-en wikis, taxonomic topics, and
    topic-name suffixes like "orchids-pt".)

    Typical use on a non-en topic:
      auto_score_by_keyword(keywords=["orchid", "orchidaceae",
                                      "蘭", "兰", "ラン",
                                      "Bulbophyllum", "Cattleya"])

    Typical use on a biography-heavy topic where scoring by title-match
    is risky (false positives like "martial artist" matching "artist"):
    leave this tool alone and use auto_score_by_description instead.

    Args:
        keywords: Case-insensitive substring keywords. Include
                  language-specific synonyms on non-en wikis, and
                  common-genus names on taxonomy topics.
        score: Score to assign to matched articles (default 9, capped at 10).
        match_description: If True, match against the Wikidata short
                  description as well as the title. Articles with no
                  description are still considered (title-only).
                  Descriptions must be fetched first
                  (fetch_descriptions). Default False.
        overwrite_scored: If False (default), skip articles that already
                  have a score. If True, overwrite.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    if not keywords:
        return json.dumps({
            'error': 'Pass at least one keyword. Use language-appropriate '
                     'terms — e.g. ["orchid","orchidaceae"] on en, '
                     '["ラン","兰","蘭"] on ja/zh wikis, or common genus '
                     'names for taxonomy topics.',
        })

    score = min(max(int(score), 1), 10)
    kws_lower = [k.lower() for k in keywords if k]
    all_articles = db.get_all_articles_dict(topic_id)

    scores: dict[str, int] = {}
    for title, article in all_articles.items():
        if article.get('score') is not None and not overwrite_scored:
            continue
        haystack = title.lower()
        if match_description:
            desc = article.get('description') or ''
            haystack += ' ' + desc.lower()
        if any(kw in haystack for kw in kws_lower):
            scores[title] = score

    if scores:
        db.set_scores(topic_id, scores)

    unscored = sum(1 for a in all_articles.values()
                   if a.get('score') is None) - len(scores)
    log_usage(ctx, "auto_score_by_keyword",
              {"keywords_count": len(kws_lower), "score": score,
               "match_description": match_description},
              f"scored {len(scores)}, {unscored} still unscored",
              start_time=_start, note=note)
    return json.dumps({
        'scored': len(scores),
        'score_applied': score,
        'keywords': keywords,
        'match_description': match_description,
        'still_unscored': unscored,
        'note': 'Set overwrite_scored=True to re-score articles that already have a score.',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def auto_score_by_description(
    required_any: dict[str, list[str]],
    disqualifying: list[str] | None = None,
    overwrite_scored: bool = False,
    dry_run: bool = True,
    note: str = "",
    topic: str | None = None, ctx: Context = None,
) -> str:
    """Reject articles whose Wikidata short description clearly disqualifies
    them from the topic. Use this after fetch_descriptions to eliminate
    obvious noise without manual review, leaving a much smaller ambiguous
    set to look at by hand.

    Rejected articles are removed from the working list AND added to the
    topic's sticky rejection list (so future gathers — another
    search_articles, a later category crawl — won't re-introduce them).
    Each rejection records the specific marker that fired, so the audit
    trail via list_rejections is self-describing.

    (Under the centrality-gradient model: "in-topic" is a binary
    decided by presence in the working list; this tool moves articles
    out of the list based on description-marker evidence. It does NOT
    set score=0 — score now means "topic centrality 1–10," and
    disqualified articles are simply out, not scored-low.)

    TWO FAILURE MODES TO WATCH FOR:

    1. Implicit-axis leakage. If the topic is intersectional and one axis
       is often NOT stated in Wikipedia's shortdesc ("American
       neuroscientist" for a Mexican-American scientist, where the shortdesc
       elides the ethnicity), requiring that axis rejects genuine topic
       members. Prefer to only require axes that shortdescs reliably
       contain, or run with disqualifying markers alone and keep axes
       off. The tool surfaces a warning when axes dominate the cut.
    2. Over-broad markers. A marker like "artist" matches "martial artist";
       "poll" matches "polling". Matching uses word boundaries to mitigate
       this but not every case is safe — review samples_by_reason on the
       dry-run before applying.

    `required_any` is a dict of labeled axes. For each axis, the description
    must match at least one marker from that axis's list. An article missing
    a match on ANY axis is rejected. Axis labels appear in the breakdown so
    the AI can present cuts to the user in plain language (e.g. "450 had no
    profession marker" rather than "axis 2"). Pass an empty dict to rely on
    disqualifying markers alone (the safest mode).

    `disqualifying` markers reject the article regardless of axis matches.
    These tend to be the safest cutter for intersectional topics because
    off-scope professions (actor, musician, footballer, politician) are
    usually explicit in the shortdesc.

    Matching is case-insensitive and word-boundary. Descriptions are
    pre-normalized so hyphens become spaces ("Mexican-American chemist"
    matches marker "mexican american" or "american").

    Only rejects — never marks as in-topic. "Has matching markers" is
    necessary but not sufficient evidence of relevance (e.g. Brazilian-
    American physicists may or may not count depending on the user's
    Latin/Hispanic scope). Inclusion decisions stay with humans.

    Args:
        required_any: Labeled axes, each a list of markers. Example for
            "Hispanic/Latino people in STEM":
              {
                "demographic": ["hispanic","latino","latina","mexican",
                                "puerto rican","cuban","colombian", ...],
                "profession":  ["scientist","physicist","chemist","engineer",
                                "mathematician","astronaut","inventor", ...],
              }
        disqualifying: Markers that reject the article regardless, e.g.
                       ["actor","musician","footballer","politician"].
        overwrite_scored: If False (default), skip articles that already
            have a centrality score — don't undo human judgment. If True,
            reject even already-scored articles when disqualifying
            criteria fire.
        dry_run: If True (default), preview counts + samples without
                 applying. Set False to apply the rejections.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.

    Articles with NULL descriptions (not yet fetched) are skipped —
    run fetch_descriptions first to include them.
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

    to_reject = []  # (title, desc, reason)
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
            to_reject.append((title, desc, reason))
            reason_counts[reason] += 1
            continue

        # Axis check: missing a match on any axis → reject.
        missing_axis = None
        for axis_name, patterns in axis_patterns.items():
            if not any(pat.search(desc_norm) for _, pat in patterns):
                missing_axis = axis_name
                break
        if missing_axis:
            reason = f'missing_{missing_axis}'
            to_reject.append((title, desc, reason))
            reason_counts[reason] += 1
        else:
            survivors.append((title, desc))

    if not dry_run and to_reject:
        # Group by reason to give each rejection its specific audit trail.
        # reject_articles takes a single reason per call, so loop by reason.
        reject_titles = [t for t, _, _ in to_reject]
        by_reason: dict[str, list[str]] = {}
        for t, _, r in to_reject:
            by_reason.setdefault(r, []).append(t)
        for reason, titles_for_reason in by_reason.items():
            db.add_rejections(topic_id, titles_for_reason,
                              f'auto_score_by_description: {reason}')
        # also_remove=True behavior: drop from working list.
        db.remove_articles(topic_id, reject_titles)
        log_usage(ctx, "auto_score_by_description",
                  {"axes": list(required_any.keys()),
                   "disqualifying_count": len(disqualifying)},
                  f"rejected: {len(to_reject)}",
                  start_time=_start, note=note)
    elif dry_run:
        log_usage(ctx, "auto_score_by_description",
                  {"axes": list(required_any.keys()),
                   "disqualifying_count": len(disqualifying),
                   "dry_run": True},
                  f"would reject: {len(to_reject)}",
                  start_time=_start, note=note)

    # Group samples by reason (up to 5 each) so the AI/user can spot patterns:
    # e.g. if "missing_demographic: 1300" is accompanied by samples like
    # "American neuroscientist" / "American engineer" / "American chemist",
    # the axis is probably cutting through legitimate members whose shortdesc
    # omits the demographic qualifier — a signal to drop that axis.
    samples_by_reason = {}
    for t, d, r in to_reject:
        samples_by_reason.setdefault(r, [])
        if len(samples_by_reason[r]) < 5:
            samples_by_reason[r].append({'title': t, 'description': d})

    result = {
        'dry_run': dry_run,
        ('would_reject' if dry_run else 'rejected'): len(to_reject),
        'skipped_already_scored': skipped_already_scored,
        'skipped_no_description': skipped_no_description,
        'survivors': len(survivors),
        'breakdown_by_reason': dict(reason_counts.most_common()),
        'samples_by_reason': samples_by_reason,
        'sample_survivors': [
            {'title': t, 'description': d} for t, d in survivors[:10]
        ],
        'note': ('Set dry_run=False to apply the rejections. '
                 'Rejected titles are added to the topic\'s sticky '
                 'rejection list — future gathers will skip them.'
                 if dry_run
                 else 'Rejections applied. Sample survivors above still '
                      'need review. Use list_rejections to audit.'),
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

    **Prefer leaving articles unscored** under the centrality-gradient
    model: score means "how central to the topic" on a 1–10 scale, and
    NULL is a valid state meaning "in-topic, centrality unevaluated."
    A downstream consumer (Impact Visualizer) can filter on score when
    it's set and treat NULL as "no centrality signal available."
    Blanket-stamping every unscored article at one value collapses that
    signal and is the failure mode the orchids dogfood flagged
    (score_all_unscored(8) as a closing ceremony).

    Legitimate uses:
      * You've reviewed the entire working list, scored the articles you
        care about, and want to deliberately mark the remainder at a
        specific centrality (e.g. "everything else is periphery, 3").
      * A pure-taxonomy topic where all members are equally central and
        a flat score communicates that to IV intentionally.

    If you just want to close out a session for export, call export_csv
    directly — it no longer requires scoring.

    Args:
        score: Score to assign to all unscored articles (default 8).
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

    normalized = [normalize_title(t) for t in titles]
    keep, rejected_skipped, rejected_sample = _apply_rejections(topic_id, normalized)
    batch = [(t, source, score) for t in keep]
    added, updated = db.add_articles(topic_id, batch)
    total = db.get_status(topic_id)['total_articles']
    log_usage(ctx, "add_articles",
              {"source": source, "titles_count": len(titles), "score": score,
               "rejected_skipped": rejected_skipped},
              f"added {added}, updated {updated}", start_time=_start, note=note)

    # In-band nudge: if this is the second+ bare 'manual' call in this
    # session, recommend adopting manual:<context> naming. Fires once per
    # session (counter only ticks up while source is exactly "manual"),
    # so labeled calls don't get nagged.
    hint = None
    if source == 'manual':
        with _session_lock:
            _session_bare_manual_counts[_session_key(ctx)] += 1
            count = _session_bare_manual_counts[_session_key(ctx)]
        if count == 2:
            hint = (
                "You're using bare source='manual' more than once in this session. "
                "Consider switching to source='manual:<context>' — e.g. "
                "'manual:veitch-cluster' or 'manual:cross-wiki-reconciliation-nl'. "
                "The <context> makes the audit trail self-describing and lets you "
                "undo specific hand-curated groups via remove_by_source. "
                "Call list_sources to see the labels currently in use."
            )

    result = {
        'added': added,
        'updated': updated,
        'source': source,
        'rejected_skipped': rejected_skipped,
        'rejected_sample': rejected_sample,
        'total_in_working_list': total,
    }
    if hint:
        result['label_hint'] = hint
    return json.dumps(result, indent=2, ensure_ascii=False)


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
def reject_articles(titles: list[str], reason: str = "",
                    also_remove: bool = True, note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Add titles to this topic's sticky rejection list. Rejected titles
    will be auto-skipped by future gather calls (`get_category_articles`,
    `harvest_list_page`, `search_articles`, `get_wikiproject_articles`,
    `add_articles`) so the same noise doesn't re-enter the topic on a
    later pull. Rejections are topic-scoped — rejecting "Oakes Ames" in
    topic `orchids` doesn't affect other topics.

    By default also removes the titles from the working list in the same
    call (they usually shouldn't stay in the list if you're rejecting
    them). Set `also_remove=False` to reject without removing — useful
    when the articles aren't in the list yet but you want to preempt
    future pulls.

    Args:
        titles: Titles to reject.
        reason: Optional free-text rationale, e.g. "wrong Oakes Ames —
                politician, not the orchidologist". Stored alongside the
                rejection for audit via `list_rejections`.
        also_remove: If True (default), also call remove_articles on the
                     same titles in the same tx.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err
    titles = [normalize_title(t) for t in titles]
    added = db.add_rejections(topic_id, titles, reason)
    removed = 0
    if also_remove and titles:
        removed = db.remove_articles(topic_id, titles)
    log_usage(ctx, "reject_articles",
              {"titles_count": len(titles), "also_remove": also_remove,
               "reason_given": bool(reason)},
              f"rejected {added}, removed {removed}",
              start_time=_start, note=note)
    return json.dumps({
        'rejected': added,
        'removed_from_working_list': removed,
        'reason': reason,
        'note': (
            'Future gather calls on this topic will auto-skip these titles. '
            'Call list_rejections to review, unreject_articles to undo.'
        ),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def list_rejections(note: str = "", topic: str | None = None,
                    ctx: Context = None) -> str:
    """List this topic's sticky rejections (title, reason, rejected_at),
    most recent first.

    Args:
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err
    entries = db.list_rejections(topic_id)
    log_usage(ctx, "list_rejections", {}, f"{len(entries)} rejections",
              start_time=_start, note=note)
    return json.dumps({
        'total_rejections': len(entries),
        'rejections': entries,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def unreject_articles(titles: list[str], note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Remove titles from this topic's rejection list. Does NOT add them
    back to the working list — call `add_articles` separately if you want
    them back.

    Args:
        titles: Titles to un-reject.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, _wiki, err = _require_topic(ctx, topic)
    if err:
        return err
    titles = [normalize_title(t) for t in titles]
    removed = db.remove_rejections(topic_id, titles)
    log_usage(ctx, "unreject_articles", {"titles_count": len(titles)},
              f"unrejected {removed}", start_time=_start, note=note)
    return json.dumps({
        'unrejected': removed,
        'note': 'These titles are no longer blocked from future gathers. '
                'Call add_articles to re-add them to the working list.',
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def remove_articles(titles: list[str], note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Remove articles from the working list.

    Server side has no cap — the DB batches deletes in 500-title SQL
    statements, so even 10K-title removals complete in one call. BUT:
    some MCP clients (observed: ChatGPT, Claude Code UI) practically
    truncate the `titles` list around ~200 entries before it reaches
    this tool. If you need to drop more than ~200 titles, prefer:

      * `remove_by_source(source, keep_if_other_sources=True)` —
        when the articles all came from one gather (category, list
        page, search). One call clears any number of articles.
      * `remove_by_pattern(pattern, match_description=True)` —
        when they share a title or description pattern. Also
        single-call.

    Use this tool for small, enumerated removals where you've
    hand-picked specific titles.

    Args:
        titles: Article titles to remove.
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
                 source: str | None = None,
                 sources_all: list[str] | None = None,
                 title_regex: str | None = None,
                 description_regex: str | None = None,
                 unscored_only: bool = False,
                 titles_only: bool = False,
                 limit: int = 100, offset: int = 0,
                 topic: str | None = None, ctx: Context = None) -> str:
    """Get articles from the working list with optional filters. Each
    returned article includes its `sources` list (the source labels it was
    added under), so you can see at a glance which pulls contributed it —
    useful for judging confidence during review.

    Args:
        min_score: Minimum score filter
        max_score: Maximum score filter
        source: Filter to articles that have this source (union / OR
                semantics when combined with sources_all). E.g.
                "category:Plants", "list_page:List of orchids",
                "search:incategory:Orchid genera".
        sources_all: Filter to articles that have ALL of these sources
                (intersection / AND semantics). Use for confidence
                cuts like `sources_all=["category:Orchidaceae", "wikiproject:Orchids"]`
                — the articles found by BOTH a category and a WikiProject
                are the highest-confidence core of the topic. Combines
                with `source`: the final filter is (has source OR no
                source filter) AND (has every sources_all element).
        title_regex: Filter to titles matching this case-insensitive regex
                (Python re.search semantics). Example: `"^[A-Z][a-z]+ [a-z]+$"`
                matches typical Latin binomials like "Bulbophyllum nutans"
                while excluding multi-word English titles.
        description_regex: Filter to Wikidata short descriptions matching
                this case-insensitive regex. Articles with empty/NULL
                descriptions never match. Run fetch_descriptions first.
        unscored_only: Only return articles without a score
        titles_only: If True, return just titles (saves tokens). Default False.
        limit: Max articles to return (default 100)
        offset: Skip this many articles (for pagination)
        topic: Optional topic name. Pass if your client doesn't maintain an MCP session.
    """
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    try:
        articles, total = db.get_articles(
            topic_id, min_score=min_score, max_score=max_score,
            source=source, sources_all=sources_all,
            title_regex=title_regex, description_regex=description_regex,
            unscored_only=unscored_only, limit=limit, offset=offset
        )
    except re.error as e:
        return json.dumps({
            'error': f'Invalid regex: {e}',
            'hint': 'title_regex / description_regex use Python re syntax. '
                    'Escape special characters with \\ and test against '
                    'sample titles before running on the full topic.',
        }, indent=2)

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
def resolve_redirects(dry_run: bool = False, note: str = "",
                      topic: str | None = None, ctx: Context = None) -> str:
    """Normalize every article title in the current topic to its canonical
    Wikipedia form. Follows redirects + title normalization (case, spacing).
    SAFE — no articles are dropped; titles whose MediaWiki page is missing
    stay in the corpus (flagged in the return), and articles whose canonical
    already exists in the corpus are merged (sources unioned, max score kept).

    Reach for this tool early in every build — a few minutes after gather,
    before review or export. Corpus titles can accumulate redirect-source
    variants from list-page harvests, search results, and manual adds;
    normalizing them once prevents double-counting the same article under
    multiple titles and makes comparisons (sources_all, reject lookups,
    benchmark scoring) honest.

    This is the ADDITIVE-SHAPED companion to `filter_articles`. Where
    `filter_articles` is a heavier subtractive cleanup (drops disambig /
    list / missing titles), this one only rewrites titles — never drops.
    Safe to run repeatedly.

    Args:
        dry_run: If True, report what WOULD change without writing. Useful
                 when you want a preview before committing.
        note: Optional free-text observation for the call's log entry.
        topic: Optional topic name; pass if your client doesn't maintain
               an MCP session.

    Returns JSON: {
      'total_titles', 'redirects_applied', 'missing_on_wikipedia',
      'merged_duplicates',
      'samples': {'redirects': [(from, to), ...], 'missing': [...]},
      'dry_run': bool,
    }
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    all_articles = db.get_all_articles_dict(topic_id)
    titles = list(all_articles.keys())
    redirect_map, missing, complete = _resolve_redirects(titles, wiki=wiki)
    if not complete:
        # Shouldn't happen without a deadline, but surface defensively.
        return json.dumps({'error': 'resolution incomplete'}, indent=2)

    canonical_map = _apply_redirect_map(titles, redirect_map)

    # Rebuild the corpus, merging duplicates that resolve to the same
    # canonical title.
    new_articles: dict[str, dict] = {}
    redirects_applied = 0
    merged_duplicates = 0
    redirect_samples: list[tuple[str, str]] = []
    missing_samples: list[str] = []
    for title in titles:
        canonical = canonical_map[title]
        canonical = normalize_title(canonical)
        article = all_articles[title]
        if canonical != title and len(redirect_samples) < 20:
            redirect_samples.append((title, canonical))
        if canonical != title:
            redirects_applied += 1
            article = {**article, 'description': None}
        if canonical not in new_articles:
            new_articles[canonical] = article
        else:
            merged_duplicates += 1
            for s in article.get('sources', []) or []:
                if s not in new_articles[canonical].get('sources', []):
                    new_articles[canonical].setdefault('sources', []).append(s)
            if article.get('score') and (
                    not new_articles[canonical].get('score') or
                    article['score'] > new_articles[canonical]['score']):
                new_articles[canonical]['score'] = article['score']

    for t in sorted(missing):
        if len(missing_samples) >= 20:
            break
        missing_samples.append(t)

    result = {
        'total_titles': len(titles),
        'redirects_applied': redirects_applied,
        'missing_on_wikipedia': len(missing),
        'merged_duplicates': merged_duplicates,
        'final_corpus_size': len(new_articles),
        'samples': {
            'redirects': redirect_samples,
            'missing': missing_samples,
        },
        'dry_run': dry_run,
    }

    if not dry_run and redirects_applied > 0:
        db.replace_all_articles(topic_id, new_articles)
        result['committed'] = True
    elif not dry_run:
        result['committed'] = False
        result['note'] = 'No redirects found — nothing to commit.'
    else:
        result['committed'] = False

    result['cost'] = _cost_report(_start)
    log_usage(ctx, "resolve_redirects",
              {"dry_run": dry_run},
              f"{redirects_applied} redirects, {len(missing)} missing, "
              f"{merged_duplicates} merged",
              start_time=_start, note=note)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def filter_articles(resolve_redirects: bool = True, remove_disambig: bool = True,
                    remove_lists: bool = True,
                    time_budget_s: int = 240,
                    max_drop_fraction: float = 0.1,
                    force: bool = False,
                    note: str = "",
                    topic: str | None = None, ctx: Context = None) -> str:
    """Clean up the working list: resolve redirects, remove disambiguation pages,
    remove list/index pages.

    Runs under a cooperative time budget (default 240s, under the MCP
    transport's 300s hard cap). On 18K-article topics the redirect +
    disambig phases together make ~720 API calls and can exceed the
    hard cap — if the budget is exhausted mid-phase, that phase's
    partial work is DISCARDED (not applied) and the tool returns
    `timed_out: true` + `phases_completed`. The AI can resume by
    re-calling with the completed phase flags set to False.

    SAFETY: this is a SUBTRACTIVE tool (drops articles from the working
    list). When the redirect phase finds that more than `max_drop_fraction`
    of the corpus resolves as MISSING on Wikipedia, the phase REFUSES to
    drop and returns a preview instead — this is the guardrail against
    the 2026-04-24 orchids-run failure mode where 11k/18k titles were
    silently dropped. Pass `force=True` to override the guardrail when
    you've reviewed the preview and want to proceed. The per-title missing
    set is reported in the preview so you can investigate before forcing.

    If you only need normalization (no drops), use `resolve_redirects`
    instead — it rewrites titles to canonical form without ever
    dropping anything.

    Args:
        resolve_redirects: Resolve redirect titles to canonical titles.
                           Drops titles MediaWiki reports as missing
                           (subject to the safety threshold below).
        remove_disambig: Remove disambiguation pages.
        remove_lists: Remove "List of...", "Index of...", etc.
        time_budget_s: Wall-clock budget in seconds (default 240).
        max_drop_fraction: Refuse to drop >this fraction of the corpus
                           as "missing on Wikipedia" without an explicit
                           `force=True` override. Default 0.1 (10%).
        force: Bypass the `max_drop_fraction` guardrail. Only pass this
               after reviewing a preview run and confirming the drops
               are genuine dead links.
        note: Optional free-text observation for this call's log entry.
        topic: Optional topic name. Pass if your client doesn't maintain
               an MCP session.
    """
    _start = _start_call()
    topic_id, wiki, err = _require_topic(ctx, topic)
    if err:
        return err

    deadline = time.monotonic() + max(1, time_budget_s)
    all_articles = db.get_all_articles_dict(topic_id)
    stats = {'before': len(all_articles)}
    phases_completed: list[str] = []
    phases_skipped: list[str] = []
    timed_out = False
    timed_out_phase: str | None = None

    # Resolve redirects. If the budget exhausts mid-collection, the partial
    # map is discarded (applying a partial map would give inconsistent state).
    if resolve_redirects:
        titles = list(all_articles.keys())
        redirect_map = {}
        missing_titles: set[str] = set()
        collection_complete = True
        for i in range(0, len(titles), 50):
            if time.monotonic() >= deadline:
                collection_complete = False
                timed_out = True
                timed_out_phase = 'redirects'
                break
            batch = titles[i:i + 50]
            params = {'titles': '|'.join(batch), 'redirects': '1'}
            data = api_query(params, wiki=wiki)
            if 'query' in data:
                for r in data['query'].get('redirects', []):
                    redirect_map[r['from']] = r['to']
                for n in data['query'].get('normalized', []):
                    redirect_map[n['from']] = n['to']
                # Track titles MediaWiki can't resolve at all. The
                # caption-as-title leak from harvest_list_page parks
                # phantom titles here — drop them rather than carry
                # them into the export.
                for p in data['query'].get('pages', []):
                    if p.get('missing', False):
                        missing_titles.add(p.get('title', ''))

        if collection_complete:
            # Safety: how many titles would be dropped as "missing"?
            would_drop = [
                t for t in all_articles
                if t in missing_titles and t not in redirect_map
            ]
            drop_fraction = (len(would_drop) / len(all_articles)
                             if all_articles else 0)
            if drop_fraction > max_drop_fraction and not force:
                log_usage(ctx, "filter_articles",
                          {"resolve_redirects": resolve_redirects,
                           "remove_disambig": remove_disambig,
                           "remove_lists": remove_lists,
                           "time_budget_s": time_budget_s},
                          f"REFUSED — would drop {len(would_drop)}/"
                          f"{len(all_articles)} as missing "
                          f"({drop_fraction:.1%}) — exceeds "
                          f"max_drop_fraction={max_drop_fraction}",
                          start_time=_start, note=note)
                return json.dumps({
                    'refused': True,
                    'reason': (
                        f'The redirect phase would drop {len(would_drop)} '
                        f'of {len(all_articles)} titles ({drop_fraction:.1%}) '
                        f'as "missing on Wikipedia" — this exceeds '
                        f'max_drop_fraction={max_drop_fraction}. No changes '
                        f'were made. Review the sample below; if the drops '
                        f'are genuine dead links you want to remove, re-call '
                        f'with force=True. If you only want to normalize '
                        f'redirects without dropping anything, use the '
                        f'resolve_redirects tool instead.'
                    ),
                    'would_drop_count': len(would_drop),
                    'corpus_size': len(all_articles),
                    'drop_fraction': round(drop_fraction, 4),
                    'max_drop_fraction': max_drop_fraction,
                    'sample_would_drop': sorted(would_drop)[:30],
                    'cost': _cost_report(_start),
                }, indent=2, ensure_ascii=False)

            new_articles = {}
            redirected = 0
            removed_missing = 0
            for title, article in all_articles.items():
                resolved = title
                for _ in range(5):
                    if resolved in redirect_map:
                        resolved = redirect_map[resolved]
                    else:
                        break
                resolved = normalize_title(resolved)
                # Drop titles MediaWiki doesn't recognize — no redirect
                # target, no page. Titles that redirected are in
                # redirect_map and won't be in missing_titles.
                if resolved == normalize_title(title) and title in missing_titles:
                    removed_missing += 1
                    continue
                if resolved != title:
                    redirected += 1
                    # Title changed — the stored description was for the old
                    # title and may be stale. Invalidate so fetch_descriptions
                    # refreshes it.
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
            if removed_missing:
                stats['removed_missing_titles'] = removed_missing
            stats['after_redirects'] = len(all_articles)
            phases_completed.append('redirects')
        else:
            stats['redirects_partial'] = True
            stats['redirects_probed'] = len(redirect_map)
            phases_skipped.append('redirects (timed out — partial map discarded)')

    # Remove disambiguation pages
    if remove_disambig and not timed_out:
        titles = list(all_articles.keys())
        disambig = set()
        collection_complete = True
        for i in range(0, len(titles), 50):
            if time.monotonic() >= deadline:
                collection_complete = False
                timed_out = True
                timed_out_phase = 'disambig'
                break
            batch = titles[i:i + 50]
            params = {'titles': '|'.join(batch), 'prop': 'pageprops', 'ppprop': 'disambiguation'}
            data = api_query(params, wiki=wiki)
            if 'query' in data and 'pages' in data['query']:
                for page in data['query']['pages']:
                    if 'pageprops' in page and 'disambiguation' in page['pageprops']:
                        disambig.add(normalize_title(page['title']))

        if collection_complete:
            for t in disambig:
                all_articles.pop(t, None)
            stats['disambig_removed'] = len(disambig)
            phases_completed.append('disambig')
        else:
            stats['disambig_partial'] = True
            stats['disambig_probed_so_far'] = len(disambig)
            phases_skipped.append('disambig (timed out — partial set discarded)')
    elif remove_disambig and timed_out:
        phases_skipped.append('disambig (skipped — prior phase timed out)')

    # Remove list pages and year-prefixed meta pages. No API cost; always
    # runs if requested, regardless of budget.
    if remove_lists:
        list_pages = [t for t in all_articles if t.lower().startswith(
            ('list of ', 'lists of ', 'index of ', 'outline of '))]
        meta_pages = [t for t in all_articles if re.match(r'^\d{4}\s', t)]
        dropped = set(list_pages) | set(meta_pages)
        for t in dropped:
            del all_articles[t]
        stats['lists_removed'] = len(list_pages)
        stats['meta_pages_removed'] = len(meta_pages)
        phases_completed.append('lists')

    stats['final'] = len(all_articles)
    stats['phases_completed'] = phases_completed
    stats['phases_skipped'] = phases_skipped
    stats['timed_out'] = timed_out

    # Write back to DB (only the phases that completed applied changes).
    db.replace_all_articles(topic_id, all_articles)

    if timed_out:
        # Tell the AI how to continue: call again with the completed
        # phases' flags set to False so we don't redo them.
        remaining = {
            'resolve_redirects': 'redirects' not in phases_completed,
            'remove_disambig': 'disambig' not in phases_completed,
            'remove_lists': 'lists' not in phases_completed,
        }
        stats['resume_suggestion'] = {
            'note': (
                f'Budget exhausted during the {timed_out_phase} phase. '
                'The partial result from that phase was discarded (not '
                'applied), so the DB is in a consistent state. Call '
                'filter_articles again with the flags below to run only '
                'the remaining phases.'
            ),
            'call_with': remaining,
        }

    stats['cost'] = _cost_report(_start)
    log_usage(ctx, "filter_articles",
              {"resolve_redirects": resolve_redirects,
               "remove_disambig": remove_disambig,
               "remove_lists": remove_lists,
               "time_budget_s": time_budget_s},
              f"{stats['before']} → {stats['final']}"
              f"{' (timed out in ' + timed_out_phase + ')' if timed_out else ''}",
              start_time=_start, timed_out=timed_out, note=note)
    return json.dumps(stats, indent=2)


@mcp.tool()
def export_csv(min_score: int = 0, scored_only: bool = False,
               enriched: bool = False,
               note: str = "",
               topic: str | None = None, ctx: Context = None) -> str:
    """Export the final article list as a downloadable CSV file.

    Returns a download link — give this URL to the user so they can download the CSV directly.

    Args:
        min_score: Minimum score to include (default 0 = export all articles).
                   Set to 7 to export only scored-and-relevant articles.
        scored_only: If True, only export articles that have been scored. Default False.
        enriched: If False (default), emit the Impact-Visualizer-compatible
                   two-column CSV: `title, description` with no header row.
                   If True, emit a five-column CSV with a header row:
                   `title, description, score, source_labels, first_added_at`.
                   Use enriched=True for manual review / downstream analysis;
                   keep the default for IV import. `source_labels` is pipe-
                   separated to avoid colliding with commas in label names.
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
        fetched = fetch_descriptions_with_fallback(missing, wiki=wiki)
        db.set_descriptions(topic_id, fetched)
        descriptions.update(fetched)

    # Save to a downloadable file. utf-8-sig prepends a BOM so Excel detects
    # UTF-8 (otherwise accented characters get mojibaked to Windows-1252).
    # csv.writer with newline='' emits RFC-4180 CRLF line endings and handles
    # quote escaping for titles containing commas, quotes, or newlines.
    slug = topic_name.lower().replace(' ', '_').replace("'", '').replace('"', '')
    export_dir = os.path.join(os.environ.get("EXPORT_DIR", "/opt/topic-builder/exports"))
    os.makedirs(export_dir, exist_ok=True)
    suffix = '-enriched' if enriched else ''
    filename = f"topic-articles-{slug}{suffix}.csv"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        if enriched:
            writer.writerow(['title', 'wikidata_qid', 'description', 'score',
                             'source_labels', 'first_added_at'])
            for title in titles:
                article = all_articles.get(title, {})
                sources = article.get('sources') or []
                writer.writerow([
                    title,
                    article.get('wikidata_qid') or '',
                    descriptions.get(title, ''),
                    article.get('score') if article.get('score') is not None else '',
                    '|'.join(sources),
                    article.get('created_at') or '',
                ])
        else:
            for title in titles:
                writer.writerow([title, descriptions.get(title, '')])

    download_url = f"https://topic-builder.wikiedu.org/exports/{filename}"

    # Sidecar rubric file on enriched exports — the rubric is the
    # shape-agnostic scope statement the AI (and later a reader) can use
    # to interpret the scored corpus. Plain .txt sidecar keeps the CSV
    # itself Impact-Visualizer-compatible.
    rubric = db.get_topic_rubric(topic_id)
    rubric_filename = None
    rubric_download_url = None
    if enriched and rubric:
        rubric_filename = f"topic-articles-{slug}-rubric.txt"
        rubric_path = os.path.join(export_dir, rubric_filename)
        with open(rubric_path, 'w', encoding='utf-8') as rf:
            rf.write(f"# Centrality rubric for topic: {topic_name}\n")
            rf.write(f"# wiki: {wiki}\n")
            rf.write(f"# exported: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
            rf.write("\n")
            rf.write(rubric)
            if not rubric.endswith('\n'):
                rf.write('\n')
        rubric_download_url = f"https://topic-builder.wikiedu.org/exports/{rubric_filename}"

    # Triangulation stats — articles present in multiple sources are more
    # trustworthy than single-sourced ones. The 2026-04-23 dogfood arc
    # showed triangulation quality monotonically predicts self-rated
    # quality (Lakes 85% multi-sourced → rating 8; K-drama 0% → rating 6).
    # Surfacing this at export time lets the AI (or user) decide whether
    # to add a second gathering axis before shipping.
    triangulation: dict = {}
    triangulation_warning = None
    if titles:
        single = 0
        multi = 0
        solo_contrib: dict[str, int] = {}
        for t in titles:
            sources = all_articles.get(t, {}).get('sources') or []
            n = len(sources)
            if n == 1:
                single += 1
                label = sources[0]
                solo_contrib[label] = solo_contrib.get(label, 0) + 1
            elif n >= 2:
                multi += 1
        total = len(titles)
        triangulation = {
            'total_articles': total,
            'multi_sourced': multi,
            'multi_sourced_pct': round(100.0 * multi / total, 1),
            'single_sourced': single,
            'single_sourced_pct': round(100.0 * single / total, 1),
        }
        if solo_contrib:
            top_solo = sorted(solo_contrib.items(), key=lambda kv: -kv[1])[:5]
            triangulation['top_solo_source_contributors'] = [
                {'source': s, 'solo_articles': n} for s, n in top_solo
            ]
        # Warn only on meaningfully-sized corpora — a 5-article topic with
        # 80% single-sourced is noise, not a quality signal.
        if total >= 20 and triangulation['single_sourced_pct'] > 70:
            triangulation_warning = (
                f"{single} of {total} articles ({triangulation['single_sourced_pct']}%) "
                f"are single-sourced. Topics with tight triangulation "
                f"(≥30% multi-sourced) have rated noticeably higher in "
                f"prior sessions. Consider adding a second gathering axis "
                f"(WikiProject, Wikidata P-property, list page harvest, or "
                f"category pull) and re-exporting, especially if the top "
                f"solo contributor is a list page or navbox-heavy source."
            )

    log_usage(ctx, "export_csv",
              {"min_score": min_score, "scored_only": scored_only,
               "enriched": enriched, "wiki": wiki},
              f"{len(titles)} articles exported", start_time=_start, note=note)
    note_suffix = (
        f'The CSV has six columns (title, wikidata_qid, description, score, '
        f'source_labels, first_added_at) with a header row. wikidata_qid is '
        f'blank for unresolved articles — call resolve_qids to populate it. '
        f'source_labels is pipe-separated. '
        f'For Impact Visualizer import use enriched=False (the two-column '
        f'default).' if enriched else
        f'The CSV has two columns per row: article title and a Wikidata short '
        f'description (empty if none). No header row. This is the '
        f'Impact-Visualizer-compatible format — pass the same wiki on import. '
        f'For richer output (score, source labels, timestamp), call export_csv '
        f'with enriched=True.'
    )
    response: dict = {
        'wiki': wiki,
        'article_count': len(titles),
        'min_score': min_score,
        'enriched': enriched,
        'download_url': download_url,
        'filename': filename,
        'triangulation': triangulation,
        'note': (
            f'Give the user the download link above. {note_suffix} '
            f'Titles refer to articles on {wiki}.wikipedia.org.'
        ),
    }
    if triangulation_warning:
        response['triangulation_warning'] = triangulation_warning
    if rubric_download_url:
        response['rubric_download_url'] = rubric_download_url
        response['rubric_filename'] = rubric_filename
    elif enriched and not rubric:
        response['rubric_missing'] = (
            'No centrality rubric was set for this topic — enriched '
            'exports normally ship a sidecar .txt rubric file so a '
            'reader can interpret the scores. Call set_topic_rubric '
            'before re-exporting if you want one.'
        )
    return json.dumps(response, indent=2, ensure_ascii=False)


# ── Dogfood / benchmark task entry points ────────────────────────────────

def _render_task_template(template: str, ts: str) -> str:
    """Substitute supported placeholders in a task template string.
    Currently supports {ts} (minute-UTC). More placeholders can be added
    later; unknown placeholders pass through unchanged."""
    return template.replace("{ts}", ts)


@mcp.tool()
def fetch_task_brief(task_id: str, ctx: Context = None) -> str:
    """Fetch a dogfood or benchmark task brief by ID. This is the entry
    point for a research / benchmark run: the operator's kickoff prompt
    is typically just 'Call fetch_task_brief(task_id="X"), then follow
    its instructions.' — the returned `brief` field contains everything
    the AI needs to run the task.

    Returns JSON: {task_id, variant, benchmark_slug, run_topic_name,
                   brief, metadata, created_at, updated_at}.

    **Template rendering.** The server stores both `run_topic_name` and
    `brief` as templates that may contain `{ts}`. At fetch time, `{ts}`
    is substituted with the current minute-UTC (`YYYYMMDDTHHMM`), so the
    returned `run_topic_name` and `brief` contain a fresh, unique run
    name. The same substituted name appears in the brief's instructions
    (e.g. the `start_topic(name=...)` call) — use exactly that name.
    Two fetches in the same minute get the same name; fetches ≥1 minute
    apart get distinct names. Don't improvise or modify.

    `variant` distinguishes prompt shapes (e.g. "thin" = minimal
    guidance, "informed" = includes baseline metrics). Different variants
    of the same benchmark are scored independently.

    Do NOT call this tool in normal topic-building sessions. It's a
    research entry point — reach for it only when explicitly instructed
    to run a benchmark / dogfood task.
    """
    _start = _start_call()
    task = db.get_dogfood_task(task_id)
    if task is None:
        available = [t['task_id'] for t in db.list_dogfood_tasks()]
        err = {
            'error': f'No task found with task_id={task_id!r}.',
            'available_task_ids': available,
            'hint': 'Call list_tasks() to see available task briefs.',
        }
        return json.dumps(err, indent=2, ensure_ascii=False)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M")
    name = _render_task_template(task['run_topic_name_template'], ts)
    brief = _render_task_template(task['brief_markdown'], ts)

    log_usage(ctx, "fetch_task_brief",
              {"task_id": task_id, "variant": task['variant'],
               "rendered_name": name},
              f"served brief ({len(brief)} chars)",
              start_time=_start)

    return json.dumps({
        'task_id': task['task_id'],
        'variant': task['variant'],
        'benchmark_slug': task['benchmark_slug'],
        'run_topic_name': name,
        'run_topic_name_template': task['run_topic_name_template'],
        'brief': brief,
        'metadata': task['metadata'],
        'created_at': task['created_at'],
        'updated_at': task['updated_at'],
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def list_tasks(variant: str | None = None,
               benchmark_slug: str | None = None,
               ctx: Context = None) -> str:
    """List available dogfood / benchmark task briefs (metadata only;
    the full brief text is in fetch_task_brief). Optionally filter by
    variant or benchmark_slug.

    Returns JSON: {count, tasks: [{task_id, variant, benchmark_slug,
                   run_topic_name, updated_at}, ...]}.

    Do NOT call this tool in normal topic-building sessions — it's for
    research / benchmark run setup only.
    """
    tasks = db.list_dogfood_tasks(variant=variant, benchmark_slug=benchmark_slug)
    trimmed = [
        {
            'task_id': t['task_id'],
            'variant': t['variant'],
            'benchmark_slug': t['benchmark_slug'],
            'run_topic_name_template': t['run_topic_name_template'],
            'updated_at': t['updated_at'],
        }
        for t in tasks
    ]
    return json.dumps({
        'count': len(trimmed),
        'tasks': trimmed,
    }, indent=2, ensure_ascii=False)


# ── Feedback ──────────────────────────────────────────────────────────────

@mcp.tool()
def submit_feedback(summary: str, what_worked: str = "", what_didnt: str = "",
                    missed_strategies: str = "",
                    rating: int | None = None, note: str = "",
                    coverage_estimate: dict | None = None,
                    strategies_used: list[str] | None = None,
                    spot_check: dict | None = None,
                    sharp_edges_hit: list[str] | None = None,
                    tool_friction: list[str] | None = None,
                    topic: str | None = None, ctx: Context = None) -> str:
    """Submit a brief retrospective on this topic-building session so the
    Wiki Education team can improve the tool. Offer to call this at the end
    of a session (before or after export_csv), or whenever the user signals
    they're done. Don't call it without the user's okay.

    The prose fields capture *how the session felt*. The structured fields
    capture *what happened* in a form we can trend across runs. Populate
    the structured fields even if the values are approximate — a rough
    number is more useful than an empty field when we compare sessions.

    Args:
        summary: 2-5 sentence plain-language account of how the session went —
                 topic, final article count, overall flow.
        what_worked: What helped — tools that were effective, strategies that
                     fit this topic, places the AI/user collaboration felt smooth.
        what_didnt: Pain points — missing tools, confusing output, noisy sources,
                    places the AI got stuck or had to work around the API.
                    Be specific; this is the most useful prose field.
        missed_strategies: Other ways you thought of for identifying articles
                           that the current tools didn't support well. Wikidata /
                           SPARQL shapes, PetScan compound queries, reading
                           lists, awards, author bibliographies, non-English
                           wikis, academic databases — tool shapes we wished
                           existed. Contrast with `strategies_used` (what you
                           DID reach for) and `coverage_estimate.remaining_strategies`
                           (tools that exist but you didn't apply this session).
        rating: Optional 1-10 rating of the overall experience.
        note: Optional free-text observation for this call's log entry.
              Use for mid-flow reflection; empty by default.
        coverage_estimate: Optional dict capturing your self-estimated
                           completeness at wrap-up. Shape:
                             {"confidence": 0.0–1.0,
                              "rationale": "one-sentence why",
                              "remaining_strategies": ["strategy1", ...]}
                           `confidence` is how complete you think the corpus
                           is relative to the scope. `remaining_strategies`
                           lists tool shapes that DO exist but weren't applied
                           this session.
        strategies_used: Optional list of tool-family tags capturing the
                         gather / review strategies you actually applied, in
                         rough order of usefulness. Suggested vocabulary:
                         "category_crawl", "wikiproject", "list_harvest",
                         "navbox", "wikidata_property", "search", "similarity",
                         "edge_browse", "fetch_leads", "rubric_cleanup".
                         Free-form tags welcome; stick to existing tags when
                         they fit so we can trend across sessions.
        spot_check: Optional dict summarizing your SPOT CHECK results.
                    Shape:
                      {"probes_count": int,
                       "hits": int,
                       "misses_redirect": int,
                       "misses_hallucination": int,
                       "misses_real_gap": int}
                    Counts don't have to be exact — "about 20 probes, 15
                    hits, 2 redirects, 3 real gaps" is fine.
        sharp_edges_hit: Optional list of KNOWN SHARP EDGE tags you
                         encountered. Suggested vocabulary:
                         "intitle_or_silent_empty", "shortdesc_misleading",
                         "container_category_empty", "auto_score_proper_noun",
                         "sparql_truncation", "filter_articles_refusal".
                         Free-form tags welcome.
        tool_friction: Optional list of tagged one-line friction observations
                       (e.g. "fetch_descriptions_timeout",
                       "harvest_navbox_empty_on_template"). Aggregates mid-run
                       surprises beyond what individual `note=` entries
                       captured.
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
    if coverage_estimate is not None:
        entry["coverage_estimate"] = coverage_estimate
    if strategies_used is not None:
        entry["strategies_used"] = strategies_used
    if spot_check is not None:
        entry["spot_check"] = spot_check
    if sharp_edges_hit is not None:
        entry["sharp_edges_hit"] = sharp_edges_hit
    if tool_friction is not None:
        entry["tool_friction"] = tool_friction
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
    log_params = {"topic": resolved_topic, "rating": rating}
    if isinstance(coverage_estimate, dict) and "confidence" in coverage_estimate:
        log_params["coverage_confidence"] = coverage_estimate.get("confidence")
    log_usage(ctx, "submit_feedback", log_params,
              f"feedback recorded ({len(summary)} chars)",
              start_time=_start, note=note)
    return ("Thanks — feedback recorded. The Wiki Education team will review it. "
            "Tell the user their feedback was submitted.")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
