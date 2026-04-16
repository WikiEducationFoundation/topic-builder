"""SQLite persistence layer for topic builder state."""

import json
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/opt/topic-builder/data/topics.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            score INTEGER,
            sources TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(topic_id, title)
        );
        CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic_id);
        CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(topic_id, score);
    """)
    conn.commit()
    conn.close()


def _slugify(name):
    return name.lower().replace(' ', '_').replace("'", '').replace('"', '')


def create_or_get_topic(name):
    """Create a new topic or return existing one. Returns (topic_id, is_new, article_count)."""
    slug = _slugify(name)
    conn = _connect()
    row = conn.execute("SELECT id FROM topics WHERE slug = ?", (slug,)).fetchone()
    if row:
        topic_id = row['id']
        count = conn.execute("SELECT COUNT(*) as c FROM articles WHERE topic_id = ?",
                             (topic_id,)).fetchone()['c']
        conn.close()
        return topic_id, False, count
    else:
        cur = conn.execute("INSERT INTO topics (name, slug) VALUES (?, ?)", (name, slug))
        topic_id = cur.lastrowid
        conn.commit()
        conn.close()
        return topic_id, True, 0


def list_topics():
    """List all topics with article counts."""
    conn = _connect()
    rows = conn.execute("""
        SELECT t.id, t.name, t.slug, t.created_at, t.updated_at,
               COUNT(a.id) as article_count
        FROM topics t LEFT JOIN articles a ON t.id = a.topic_id
        GROUP BY t.id ORDER BY t.updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_articles(topic_id, articles_data):
    """Add or update articles. articles_data: list of (title, source, score_or_None).
    Returns (added, updated) counts."""
    conn = _connect()
    added = 0
    updated = 0
    for title, source, score in articles_data:
        row = conn.execute("SELECT id, sources, score FROM articles WHERE topic_id = ? AND title = ?",
                           (topic_id, title)).fetchone()
        if row:
            sources = json.loads(row['sources'])
            changed = False
            if source and source not in sources:
                sources.append(source)
                changed = True
            if score is not None and (row['score'] is None or score > row['score']):
                conn.execute("UPDATE articles SET sources = ?, score = ? WHERE id = ?",
                             (json.dumps(sources), score, row['id']))
                changed = True
            elif changed:
                conn.execute("UPDATE articles SET sources = ? WHERE id = ?",
                             (json.dumps(sources), row['id']))
            if changed:
                updated += 1
        else:
            sources = [source] if source else []
            conn.execute("INSERT INTO articles (topic_id, title, score, sources) VALUES (?, ?, ?, ?)",
                         (topic_id, title, score, json.dumps(sources)))
            added += 1
    conn.execute("UPDATE topics SET updated_at = datetime('now') WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
    return added, updated


def remove_articles(topic_id, titles):
    """Remove articles by title. Returns count removed."""
    conn = _connect()
    removed = 0
    for title in titles:
        cur = conn.execute("DELETE FROM articles WHERE topic_id = ? AND title = ?",
                           (topic_id, title))
        removed += cur.rowcount
    conn.commit()
    conn.close()
    return removed


def set_scores(topic_id, scores):
    """Set scores for articles. scores: dict of title -> score. Returns count updated."""
    conn = _connect()
    updated = 0
    for title, score in scores.items():
        cur = conn.execute("UPDATE articles SET score = ? WHERE topic_id = ? AND title = ?",
                           (score, topic_id, title))
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def get_articles(topic_id, min_score=None, max_score=None, source=None,
                 unscored_only=False, limit=200, offset=0):
    """Get articles with filters. Returns (articles_list, total_matching)."""
    conn = _connect()
    conditions = ["topic_id = ?"]
    params = [topic_id]

    if unscored_only:
        conditions.append("score IS NULL")
    if min_score is not None:
        conditions.append("score >= ?")
        params.append(min_score)
    if max_score is not None:
        conditions.append("score <= ?")
        params.append(max_score)

    where = " AND ".join(conditions)

    total = conn.execute(f"SELECT COUNT(*) as c FROM articles WHERE {where}", params).fetchone()['c']

    rows = conn.execute(
        f"SELECT title, score, sources FROM articles WHERE {where} ORDER BY title LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    articles = []
    for r in rows:
        a = {'title': r['title'], 'score': r['score'], 'sources': json.loads(r['sources'])}
        if source and source not in a['sources']:
            continue
        articles.append(a)

    conn.close()

    # If filtering by source, total is approximate (source is in JSON, hard to filter in SQL)
    if source:
        all_rows = conn if False else articles  # already filtered above
        total = len(articles)  # approximate for source filter

    return articles, total


def get_all_titles(topic_id):
    """Get all article titles for a topic. Returns set."""
    conn = _connect()
    rows = conn.execute("SELECT title FROM articles WHERE topic_id = ?", (topic_id,)).fetchall()
    conn.close()
    return {r['title'] for r in rows}


def get_all_articles_dict(topic_id):
    """Get all articles as a dict of title -> {sources, score}."""
    conn = _connect()
    rows = conn.execute("SELECT title, score, sources FROM articles WHERE topic_id = ?",
                        (topic_id,)).fetchall()
    conn.close()
    return {r['title']: {'score': r['score'], 'sources': json.loads(r['sources'])} for r in rows}


def get_status(topic_id):
    """Get topic stats."""
    conn = _connect()
    total = conn.execute("SELECT COUNT(*) as c FROM articles WHERE topic_id = ?",
                         (topic_id,)).fetchone()['c']
    scored = conn.execute("SELECT COUNT(*) as c FROM articles WHERE topic_id = ? AND score IS NOT NULL",
                          (topic_id,)).fetchone()['c']

    # Score distribution
    dist_rows = conn.execute(
        "SELECT score, COUNT(*) as c FROM articles WHERE topic_id = ? AND score IS NOT NULL GROUP BY score",
        (topic_id,)
    ).fetchall()
    dist = {str(r['score']): r['c'] for r in dist_rows}

    # Source breakdown (approximate — sources is JSON array)
    all_sources = conn.execute("SELECT sources FROM articles WHERE topic_id = ?",
                               (topic_id,)).fetchall()
    from collections import Counter
    source_counts = Counter()
    for r in all_sources:
        for s in json.loads(r['sources']):
            source_counts[s] += 1

    conn.close()
    return {
        'total_articles': total,
        'scored': scored,
        'unscored': total - scored,
        'score_distribution': dist,
        'source_breakdown': dict(source_counts.most_common()),
    }


def update_article_sources(topic_id, title, new_sources):
    """Update the sources list for a single article."""
    conn = _connect()
    conn.execute("UPDATE articles SET sources = ? WHERE topic_id = ? AND title = ?",
                 (json.dumps(new_sources), topic_id, title))
    conn.commit()
    conn.close()


def replace_all_articles(topic_id, articles_dict):
    """Replace all articles for a topic (used by filter_articles).
    articles_dict: {title: {sources: [...], score: int|None}}"""
    conn = _connect()
    conn.execute("DELETE FROM articles WHERE topic_id = ?", (topic_id,))
    for title, data in articles_dict.items():
        conn.execute("INSERT INTO articles (topic_id, title, score, sources) VALUES (?, ?, ?, ?)",
                     (topic_id, title, data.get('score'), json.dumps(data.get('sources', []))))
    conn.execute("UPDATE topics SET updated_at = datetime('now') WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


# Initialize on import
init_db()
