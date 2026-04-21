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
            wiki TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            score INTEGER,
            sources TEXT NOT NULL DEFAULT '[]',
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(topic_id, title)
        );
        CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic_id);
        CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(topic_id, score);
    """)
    # Migrate existing DBs that predate the description column. NULL means
    # "not fetched yet"; empty string means "fetched, no short-desc on Wikipedia".
    art_cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)")]
    if 'description' not in art_cols:
        conn.execute("ALTER TABLE articles ADD COLUMN description TEXT")
    # Migrate existing DBs that predate per-topic wiki selection. Pre-existing
    # topics were all built against English Wikipedia.
    topic_cols = [r[1] for r in conn.execute("PRAGMA table_info(topics)")]
    if 'wiki' not in topic_cols:
        conn.execute("ALTER TABLE topics ADD COLUMN wiki TEXT NOT NULL DEFAULT 'en'")
    conn.commit()
    conn.close()


def _slugify(name):
    return name.lower().replace(' ', '_').replace("'", '').replace('"', '')


def create_or_get_topic(name, wiki='en'):
    """Create a new topic or return existing one.
    Returns (topic_id, is_new, article_count, canonical_wiki).

    For an existing topic, `canonical_wiki` is the wiki stored at creation —
    the passed `wiki` argument is ignored on resume (topics are bound to a
    wiki at creation time)."""
    slug = _slugify(name)
    conn = _connect()
    row = conn.execute("SELECT id, wiki FROM topics WHERE slug = ?", (slug,)).fetchone()
    if row:
        topic_id = row['id']
        count = conn.execute("SELECT COUNT(*) as c FROM articles WHERE topic_id = ?",
                             (topic_id,)).fetchone()['c']
        conn.close()
        return topic_id, False, count, row['wiki']
    else:
        cur = conn.execute("INSERT INTO topics (name, slug, wiki) VALUES (?, ?, ?)",
                           (name, slug, wiki))
        topic_id = cur.lastrowid
        conn.commit()
        conn.close()
        return topic_id, True, 0, wiki


def get_topic_by_name(name):
    """Look up a topic by name. Returns (topic_id, canonical_name, wiki) or
    (None, None, None) if missing."""
    slug = _slugify(name)
    conn = _connect()
    row = conn.execute("SELECT id, name, wiki FROM topics WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    if row:
        return row['id'], row['name'], row['wiki']
    return None, None, None


def append_feedback(entry):
    """Append a feedback record (dict) as JSON Lines to the feedback log."""
    log_dir = os.environ.get("LOG_DIR", "/opt/topic-builder/logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "feedback.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_topics():
    """List all topics with article counts."""
    conn = _connect()
    rows = conn.execute("""
        SELECT t.id, t.name, t.slug, t.wiki, t.created_at, t.updated_at,
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
        f"SELECT title, score, sources, description FROM articles WHERE {where} ORDER BY title LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()

    articles = []
    for r in rows:
        a = {'title': r['title'], 'score': r['score'],
             'sources': json.loads(r['sources']),
             'description': r['description'] or ''}
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
    """Get all articles as a dict of title -> {sources, score, description}.
    description is '' when fetched-but-empty and None when not-yet-fetched."""
    conn = _connect()
    rows = conn.execute("SELECT title, score, sources, description FROM articles WHERE topic_id = ?",
                        (topic_id,)).fetchall()
    conn.close()
    return {r['title']: {'score': r['score'], 'sources': json.loads(r['sources']),
                          'description': r['description']} for r in rows}


def get_status(topic_id):
    """Get topic stats."""
    conn = _connect()
    wiki_row = conn.execute("SELECT wiki FROM topics WHERE id = ?", (topic_id,)).fetchone()
    wiki = wiki_row['wiki'] if wiki_row else 'en'
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

    # Description coverage
    described = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE topic_id = ? AND description IS NOT NULL AND description != ''",
        (topic_id,)).fetchone()['c']
    desc_empty = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE topic_id = ? AND description = ''",
        (topic_id,)).fetchone()['c']
    desc_unfetched = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE topic_id = ? AND description IS NULL",
        (topic_id,)).fetchone()['c']

    conn.close()
    return {
        'wiki': wiki,
        'total_articles': total,
        'scored': scored,
        'unscored': total - scored,
        'score_distribution': dist,
        'source_breakdown': dict(source_counts.most_common()),
        'description_coverage': {
            'with_desc': described,
            'empty_desc': desc_empty,
            'not_fetched': desc_unfetched,
        },
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
    articles_dict: {title: {sources: [...], score: int|None, description: str|None}}"""
    conn = _connect()
    conn.execute("DELETE FROM articles WHERE topic_id = ?", (topic_id,))
    for title, data in articles_dict.items():
        conn.execute(
            "INSERT INTO articles (topic_id, title, score, sources, description) VALUES (?, ?, ?, ?, ?)",
            (topic_id, title, data.get('score'), json.dumps(data.get('sources', [])),
             data.get('description'))
        )
    conn.execute("UPDATE topics SET updated_at = datetime('now') WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()


def set_descriptions(topic_id, desc_map):
    """Store short descriptions for articles. desc_map: {title: description}.
    Empty strings are stored as-is (distinct from NULL = not-yet-fetched).
    Returns count updated."""
    conn = _connect()
    updated = 0
    for title, desc in desc_map.items():
        cur = conn.execute(
            "UPDATE articles SET description = ? WHERE topic_id = ? AND title = ?",
            (desc, topic_id, title))
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def get_undescribed_titles(topic_id, limit=500):
    """Return titles that don't have a description yet (description IS NULL).
    Empty-string descriptions count as 'already fetched' and are excluded."""
    conn = _connect()
    rows = conn.execute(
        "SELECT title FROM articles WHERE topic_id = ? AND description IS NULL ORDER BY title LIMIT ?",
        (topic_id, limit)
    ).fetchall()
    conn.close()
    return [r['title'] for r in rows]


def count_undescribed(topic_id):
    """Count articles without a description (NULL, not empty)."""
    conn = _connect()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE topic_id = ? AND description IS NULL",
        (topic_id,)
    ).fetchone()['c']
    conn.close()
    return count


# Initialize on import
init_db()
