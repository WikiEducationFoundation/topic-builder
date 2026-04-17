#!/usr/bin/env python3
"""Summarize Wikipedia Topic Builder session state on the host.

Reads /opt/topic-builder/{data/topics.db, logs/usage.jsonl, logs/feedback.jsonl,
exports/}. With no argument, prints an overview of all topics and a tail of the
usage log. Pass a topic id or a substring of its name to drill into one topic.

Ad-hoc invocation (no host deploy needed):

    scp -i deploy_key scripts/session_status.py root@$HOST:/tmp/status.py
    ssh -i deploy_key root@$HOST "/opt/topic-builder/venv/bin/python /tmp/status.py [ARGS]"

Examples:
    python3 status.py                    # overview
    python3 status.py 6                  # topic id 6
    python3 status.py "hispanic"         # substring match
    python3 status.py 6 --recent 50
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/opt/topic-builder")
DB_PATH = BASE / "data" / "topics.db"
USAGE_LOG = BASE / "logs" / "usage.jsonl"
FEEDBACK_LOG = BASE / "logs" / "feedback.jsonl"
EXPORTS_DIR = BASE / "exports"

STAGE_BY_TOOL = {
    "start_topic": "1. scope",
    "reset_topic": "1. scope",
    "resume_topic": "1. scope",
    "survey_categories": "2. recon",
    "check_wikiproject": "2. recon",
    "find_list_pages": "2. recon",
    "get_wikiproject_articles": "3. gather",
    "get_category_articles": "3. gather",
    "harvest_list_page": "3. gather",
    "search_articles": "3. gather",
    "add_articles": "3. gather",
    "score_by_extract": "4. score",
    "score_all_unscored": "4. score",
    "set_scores": "4. score",
    "auto_score_by_title": "4. score",
    "browse_edges": "5. edge-browse",
    "search_similar": "5. edge-browse",
    "filter_articles": "6. cleanup",
    "remove_articles": "6. cleanup",
    "remove_by_pattern": "6. cleanup",
    "remove_by_source": "6. cleanup",
    "export_csv": "6. export",
    "submit_feedback": "7. feedback",
}


def export_slug(topic_name: str) -> str:
    """Matches the slugging in server.py::export_csv."""
    return topic_name.lower().replace(" ", "_").replace("'", "").replace('"', "")


def fmt_ts(ts) -> str:
    if not ts:
        return "?"
    return str(ts).split(".")[0].replace("T", " ")


def short_params(params) -> str:
    if not isinstance(params, dict):
        return str(params)
    parts = []
    for k, v in params.items():
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_topics(conn):
    return conn.execute("""
        SELECT t.id, t.name, COUNT(a.id), MAX(a.created_at)
        FROM topics t
        LEFT JOIN articles a ON a.topic_id = t.id
        GROUP BY t.id
        ORDER BY t.id
    """).fetchall()


def source_breakdown(conn, topic_id: int) -> Counter:
    counts: Counter = Counter()
    for (sources_json,) in conn.execute(
        "SELECT sources FROM articles WHERE topic_id = ?", (topic_id,)
    ):
        try:
            for s in json.loads(sources_json or "[]"):
                counts[s] += 1
        except (json.JSONDecodeError, TypeError):
            counts[str(sources_json)] += 1
    return counts


def score_distribution(conn, topic_id: int):
    return conn.execute(
        "SELECT score, COUNT(*) FROM articles WHERE topic_id = ? GROUP BY score ORDER BY score IS NULL, score",
        (topic_id,),
    ).fetchall()


def description_coverage(conn, topic_id: int):
    """Return (described, empty, not_fetched). 'empty' = fetched-but-no-desc."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)")]
    if 'description' not in cols:
        return None
    described = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? AND description IS NOT NULL AND description != ''",
        (topic_id,),
    ).fetchone()[0]
    empty = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? AND description = ''",
        (topic_id,),
    ).fetchone()[0]
    not_fetched = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? AND description IS NULL",
        (topic_id,),
    ).fetchone()[0]
    return described, empty, not_fetched


def usage_entries_for_topic(topic_name: str, limit: int):
    matches = [e for e in iter_jsonl(USAGE_LOG) if e.get("topic") == topic_name]
    return matches[-limit:]


def tail_usage(limit: int):
    entries = list(iter_jsonl(USAGE_LOG))
    return entries[-limit:]


def feedback_for_topic(topic_name: str):
    return [e for e in iter_jsonl(FEEDBACK_LOG) if e.get("topic") == topic_name]


def exports_for_topic(topic_name: str):
    if not EXPORTS_DIR.exists():
        return []
    target = f"topic-articles-{export_slug(topic_name)}.csv"
    hits = []
    for p in EXPORTS_DIR.iterdir():
        if p.name == target:
            st = p.stat()
            hits.append((p.name, st.st_size, st.st_mtime))
    return sorted(hits, key=lambda r: r[2])


def infer_stage(entries) -> str:
    for entry in reversed(entries):
        tool = entry.get("tool", "")
        if tool in STAGE_BY_TOOL:
            return STAGE_BY_TOOL[tool]
    return "(no recognized activity)"


def resolve_topic(conn, query: str):
    if query.isdigit():
        return conn.execute(
            "SELECT id, name FROM topics WHERE id = ?", (int(query),)
        ).fetchone()
    rows = conn.execute(
        "SELECT id, name FROM topics WHERE lower(name) LIKE ? ORDER BY id",
        (f"%{query.lower()}%",),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        print(f"Multiple topics match '{query}':", file=sys.stderr)
        for r in rows:
            print(f"  {r[0]}  {r[1]}", file=sys.stderr)
        print("Pass the topic id to disambiguate.", file=sys.stderr)
        sys.exit(2)
    return rows[0]


def print_overview(conn, recent: int):
    topics = load_topics(conn)
    print(f"=== TOPICS ({len(topics)}) ===")
    print(f"{'id':>3}  {'articles':>8}  {'last touched':<20}  name")
    for tid, name, count, last in topics:
        print(f"{tid:>3}  {count:>8}  {fmt_ts(last):<20}  {name}")
    print()
    entries = tail_usage(recent)
    print(f"=== RECENT USAGE LOG (last {len(entries)}) ===")
    for e in entries:
        ts = fmt_ts(e.get("ts"))
        topic = e.get("topic", "?")
        tool = e.get("tool", "?")
        result = e.get("result", "")
        params = e.get("params", {})
        print(f"  {ts}  [{topic}] {tool}({short_params(params)}) -> {result}")


def print_topic_detail(conn, tid: int, name: str, recent: int):
    count = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ?", (tid,)
    ).fetchone()[0]

    print(f"=== TOPIC {tid}: {name} ===")
    print(f"articles: {count}")
    print()

    scores = score_distribution(conn, tid)
    scored = sum(n for s, n in scores if s is not None)
    print(f"--- score distribution ({scored}/{count} scored) ---")
    for s, n in scores:
        label = "unscored" if s is None else f"score {s}"
        print(f"  {label:>10}  {n:>5}")
    print()

    cov = description_coverage(conn, tid)
    if cov is not None:
        described, empty, not_fetched = cov
        print(f"--- description coverage ---")
        print(f"  with description    {described:>5}")
        print(f"  fetched, no desc    {empty:>5}")
        print(f"  not yet fetched     {not_fetched:>5}")
        print()

    sources = source_breakdown(conn, tid)
    print(f"--- top sources ({len(sources)} distinct) ---")
    for src, n in sources.most_common(15):
        print(f"  {n:>5}  {src}")
    if len(sources) > 15:
        print(f"  ... {len(sources) - 15} more")
    print()

    exports = exports_for_topic(name)
    print(f"--- exports on disk ({len(exports)}) ---")
    for fn, size, mt in exports:
        ts = datetime.fromtimestamp(mt, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"  {ts}  {size:>8} bytes  {fn}")
    if not exports:
        print("  (none)")
    print()

    feedback = feedback_for_topic(name)
    if feedback:
        print(f"--- feedback ({len(feedback)}) ---")
        for e in feedback:
            ts = fmt_ts(e.get("ts"))
            rating = e.get("rating", "?")
            summary = (e.get("summary") or "")[:80]
            print(f"  {ts}  rating={rating}  {summary}")
        print()

    entries = usage_entries_for_topic(name, limit=recent)
    print(f"--- last {len(entries)} tool calls for this topic ---")
    for e in entries:
        ts = fmt_ts(e.get("ts"))
        tool = e.get("tool", "?")
        result = e.get("result", "")
        params = e.get("params", {})
        ac = e.get("articles_count")
        ac_s = f" (total={ac})" if ac is not None else ""
        print(f"  {ts}  {tool}({short_params(params)}){ac_s} -> {result}")
    print()

    print(f"inferred flow stage: {infer_stage(entries)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("topic", nargs="?", help="topic id or name substring")
    p.add_argument("--recent", type=int, default=20, help="recent entries to show (default 20)")
    args = p.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    if args.topic:
        match = resolve_topic(conn, args.topic)
        if not match:
            print(f"No topic matched '{args.topic}'", file=sys.stderr)
            sys.exit(2)
        tid, name = match
        print_topic_detail(conn, tid, name, args.recent)
    else:
        print_overview(conn, args.recent)


if __name__ == "__main__":
    main()
