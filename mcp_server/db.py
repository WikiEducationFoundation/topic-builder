"""SQLite persistence layer for topic builder state."""

import json
import os
import re
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
            centrality_rubric TEXT NOT NULL DEFAULT '',
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
            wikidata_qid TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(topic_id, title)
        );
        CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic_id);
        CREATE INDEX IF NOT EXISTS idx_articles_score ON articles(topic_id, score);
        CREATE TABLE IF NOT EXISTS rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            rejected_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(topic_id, title)
        );
        CREATE INDEX IF NOT EXISTS idx_rejections_topic ON rejections(topic_id);
        CREATE TABLE IF NOT EXISTS dogfood_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            variant TEXT NOT NULL,
            benchmark_slug TEXT,
            run_topic_name TEXT NOT NULL,
            brief_markdown TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_dogfood_tasks_variant ON dogfood_tasks(variant);
        CREATE INDEX IF NOT EXISTS idx_dogfood_tasks_benchmark ON dogfood_tasks(benchmark_slug);
        CREATE TABLE IF NOT EXISTS dogfood_exemplars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            shape TEXT NOT NULL DEFAULT '',
            body_markdown TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            last_validated_against TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_dogfood_exemplars_slug ON dogfood_exemplars(slug);
    """)
    # Migrate existing DBs that predate the description column. NULL means
    # "not fetched yet"; empty string means "fetched, no short-desc on Wikipedia".
    art_cols = [r[1] for r in conn.execute("PRAGMA table_info(articles)")]
    if 'description' not in art_cols:
        conn.execute("ALTER TABLE articles ADD COLUMN description TEXT")
    # Migrate existing DBs that predate the wikidata_qid column. NULL means
    # "not resolved yet"; empty string means "resolved, no QID on Wikipedia"
    # (unusual — redirects, disambig pages, brand-new articles).
    if 'wikidata_qid' not in art_cols:
        conn.execute("ALTER TABLE articles ADD COLUMN wikidata_qid TEXT")
    # Migrate existing DBs that predate per-topic wiki selection. Pre-existing
    # topics were all built against English Wikipedia.
    topic_cols = [r[1] for r in conn.execute("PRAGMA table_info(topics)")]
    if 'wiki' not in topic_cols:
        conn.execute("ALTER TABLE topics ADD COLUMN wiki TEXT NOT NULL DEFAULT 'en'")
    # Migrate existing DBs that predate the dogfood_tasks template column.
    # The template is rendered per-fetch by fetch_task_brief (substitutes
    # {ts} with the current minute-UTC); populate from the existing static
    # run_topic_name on migration so pre-existing tasks still work.
    task_cols = []
    try:
        task_cols = [r[1] for r in conn.execute("PRAGMA table_info(dogfood_tasks)")]
    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet; nothing to migrate.
    if task_cols and 'run_topic_name_template' not in task_cols:
        conn.execute(
            "ALTER TABLE dogfood_tasks ADD COLUMN run_topic_name_template TEXT")
        conn.execute(
            "UPDATE dogfood_tasks SET run_topic_name_template = run_topic_name "
            "WHERE run_topic_name_template IS NULL")
    # Migrate existing DBs that predate the centrality rubric. Empty string
    # means "no rubric set yet" — AI should write one at scoping time.
    if 'centrality_rubric' not in topic_cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN centrality_rubric TEXT NOT NULL DEFAULT ''")
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


def get_topic_rubric(topic_id):
    """Read the centrality rubric for a topic. Returns '' if unset."""
    conn = _connect()
    row = conn.execute(
        "SELECT centrality_rubric FROM topics WHERE id = ?",
        (topic_id,)).fetchone()
    conn.close()
    return row['centrality_rubric'] if row else ''


def set_topic_rubric(topic_id, rubric):
    """Persist the centrality rubric. Idempotent; overwrites prior value.
    Also bumps `updated_at` so `list_topics` reflects the edit."""
    conn = _connect()
    conn.execute(
        "UPDATE topics SET centrality_rubric = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (rubric, topic_id))
    conn.commit()
    conn.close()


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
    """Remove articles by title. Returns count removed. Batches into
    500-title DELETE ... IN (...) queries so a 10K-title removal runs as
    ~20 statements instead of 10K."""
    if not titles:
        return 0
    conn = _connect()
    removed = 0
    # SQLite's default SQLITE_MAX_VARIABLE_NUMBER is 999; 500 + 1 (topic_id)
    # keeps us well under that with headroom.
    for i in range(0, len(titles), 500):
        batch = titles[i:i + 500]
        placeholders = ','.join('?' * len(batch))
        cur = conn.execute(
            f"DELETE FROM articles WHERE topic_id = ? AND title IN ({placeholders})",
            [topic_id] + list(batch),
        )
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
                 sources_all=None, title_regex=None, description_regex=None,
                 unscored_only=False, limit=200, offset=0):
    """Get articles with filters. Returns (articles_list, total_matching).

    Score / unscored filters are pushed to SQL; source / sources_all /
    regex filters are applied in Python after loading because the sources
    array is JSON and regex matching wants Python semantics anyway. Total
    is accurate across all filters (we filter then paginate)."""
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
    rows = conn.execute(
        f"SELECT title, score, sources, description FROM articles WHERE {where} ORDER BY title",
        params
    ).fetchall()
    conn.close()

    title_re = re.compile(title_regex, re.IGNORECASE) if title_regex else None
    desc_re = re.compile(description_regex, re.IGNORECASE) if description_regex else None
    sources_all_set = set(sources_all) if sources_all else None

    articles = []
    for r in rows:
        sources = json.loads(r['sources'])
        description = r['description'] or ''
        title = r['title']
        if source and source not in sources:
            continue
        if sources_all_set and not sources_all_set.issubset(sources):
            continue
        if title_re and not title_re.search(title):
            continue
        if desc_re and not desc_re.search(description):
            continue
        articles.append({
            'title': title, 'score': r['score'],
            'sources': sources, 'description': description,
        })

    total = len(articles)
    paged = articles[offset:offset + limit]
    return paged, total


def get_all_titles(topic_id):
    """Get all article titles for a topic. Returns set."""
    conn = _connect()
    rows = conn.execute("SELECT title FROM articles WHERE topic_id = ?", (topic_id,)).fetchall()
    conn.close()
    return {r['title'] for r in rows}


def get_all_articles_dict(topic_id):
    """Get all articles as a dict of title -> {sources, score, description,
    wikidata_qid, created_at}. description is '' when fetched-but-empty and
    None when not-yet-fetched; same convention for wikidata_qid."""
    conn = _connect()
    rows = conn.execute(
        "SELECT title, score, sources, description, wikidata_qid, created_at "
        "FROM articles WHERE topic_id = ?",
        (topic_id,),
    ).fetchall()
    conn.close()
    return {
        r['title']: {
            'score': r['score'],
            'sources': json.loads(r['sources']),
            'description': r['description'],
            'wikidata_qid': r['wikidata_qid'],
            'created_at': r['created_at'],
        }
        for r in rows
    }


def get_unresolved_qid_titles(topic_id, limit=500):
    """Return titles in the working list that haven't been QID-resolved
    yet (wikidata_qid IS NULL — distinct from empty-string which means
    'resolved, no QID exists'). Cheap enough to call in a loop."""
    conn = _connect()
    rows = conn.execute(
        "SELECT title FROM articles WHERE topic_id = ? "
        "AND wikidata_qid IS NULL ORDER BY title LIMIT ?",
        (topic_id, limit),
    ).fetchall()
    conn.close()
    return [r['title'] for r in rows]


def count_unresolved_qids(topic_id):
    """Count articles still needing QID resolution."""
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM articles "
        "WHERE topic_id = ? AND wikidata_qid IS NULL",
        (topic_id,),
    ).fetchone()
    conn.close()
    return row['c']


def set_wikidata_qids(topic_id, qid_map):
    """Store QIDs for a batch of titles. qid_map is {title: qid_or_empty}.
    Empty-string means "resolved but this title has no QID" (redirect,
    disambig, brand-new article). Returns count of rows updated."""
    if not qid_map:
        return 0
    conn = _connect()
    updated = 0
    for title, qid in qid_map.items():
        cur = conn.execute(
            "UPDATE articles SET wikidata_qid = ? "
            "WHERE topic_id = ? AND title = ?",
            (qid, topic_id, title),
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def add_rejections(topic_id, titles, reason=''):
    """Persist titles into the rejections table. INSERT OR IGNORE on
    (topic_id, title) — re-rejecting an already-rejected title doesn't
    update the reason. Returns count of newly rejected titles."""
    if not titles:
        return 0
    conn = _connect()
    added = 0
    for title in titles:
        cur = conn.execute(
            "INSERT OR IGNORE INTO rejections (topic_id, title, reason) "
            "VALUES (?, ?, ?)",
            (topic_id, title, reason),
        )
        added += cur.rowcount
    conn.commit()
    conn.close()
    return added


def remove_rejections(topic_id, titles):
    """Un-reject titles. Returns count removed."""
    if not titles:
        return 0
    conn = _connect()
    removed = 0
    for i in range(0, len(titles), 500):
        batch = titles[i:i + 500]
        placeholders = ','.join('?' * len(batch))
        cur = conn.execute(
            f"DELETE FROM rejections WHERE topic_id = ? AND title IN ({placeholders})",
            [topic_id] + list(batch),
        )
        removed += cur.rowcount
    conn.commit()
    conn.close()
    return removed


def list_rejections(topic_id):
    """Return all rejections for a topic as a list of dicts."""
    conn = _connect()
    rows = conn.execute(
        "SELECT title, reason, rejected_at FROM rejections WHERE topic_id = ? "
        "ORDER BY rejected_at DESC",
        (topic_id,),
    ).fetchall()
    conn.close()
    return [{'title': r['title'], 'reason': r['reason'] or '',
             'rejected_at': r['rejected_at']} for r in rows]


def get_rejections_map(topic_id):
    """Return a dict mapping rejected title -> reason for this topic.
    Callers check `title in rejections_map` for the block, and can read
    `rejections_map[title]` to surface the reason to the AI/user.
    Cheap enough to call once per gather-tool invocation."""
    conn = _connect()
    rows = conn.execute(
        "SELECT title, reason FROM rejections WHERE topic_id = ?",
        (topic_id,),
    ).fetchall()
    conn.close()
    return {r['title']: (r['reason'] or '') for r in rows}


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


def upsert_dogfood_task(task_id, variant, run_topic_name_template,
                        brief_markdown,
                        benchmark_slug=None, metadata=None):
    """Insert or replace a dogfood task. Keyed on task_id (UNIQUE).
    Bumps updated_at on replace. Returns the stored row as a dict.

    `run_topic_name_template` is a string that may contain {ts} (minute-UTC
    rendered at fetch time) and similar placeholders. The server-side
    `fetch_task_brief` handles the rendering; this function just stores
    the raw template. Legacy callers that pass a literal name (no
    placeholders) still work — the template renders as itself."""
    conn = _connect()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    # Both columns are populated to keep the (NOT NULL) run_topic_name
    # constraint satisfied; consumers should read from _template.
    conn.execute("""
        INSERT INTO dogfood_tasks (task_id, variant, benchmark_slug,
                                    run_topic_name, run_topic_name_template,
                                    brief_markdown,
                                    metadata_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(task_id) DO UPDATE SET
            variant = excluded.variant,
            benchmark_slug = excluded.benchmark_slug,
            run_topic_name = excluded.run_topic_name,
            run_topic_name_template = excluded.run_topic_name_template,
            brief_markdown = excluded.brief_markdown,
            metadata_json = excluded.metadata_json,
            updated_at = datetime('now')
    """, (task_id, variant, benchmark_slug,
          run_topic_name_template, run_topic_name_template,
          brief_markdown, meta_json))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dogfood_tasks WHERE task_id = ?",
        (task_id,)
    ).fetchone()
    conn.close()
    return _row_to_task_dict(row) if row else None


def get_dogfood_task(task_id):
    """Return a task dict or None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM dogfood_tasks WHERE task_id = ?",
        (task_id,)
    ).fetchone()
    conn.close()
    return _row_to_task_dict(row) if row else None


def upsert_dogfood_exemplar(slug, title, shape, body_markdown,
                            last_validated_against='', metadata=None):
    """Insert or replace an exemplar. Keyed on slug (UNIQUE).
    Bumps updated_at on replace. Returns the stored row as a dict."""
    conn = _connect()
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)
    conn.execute("""
        INSERT INTO dogfood_exemplars (slug, title, shape, body_markdown,
                                       metadata_json, last_validated_against,
                                       updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            shape = excluded.shape,
            body_markdown = excluded.body_markdown,
            metadata_json = excluded.metadata_json,
            last_validated_against = excluded.last_validated_against,
            updated_at = datetime('now')
    """, (slug, title, shape, body_markdown, meta_json, last_validated_against))
    conn.commit()
    row = conn.execute(
        "SELECT * FROM dogfood_exemplars WHERE slug = ?", (slug,)
    ).fetchone()
    conn.close()
    return _row_to_exemplar_dict(row) if row else None


def get_dogfood_exemplar(slug):
    """Return an exemplar dict or None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM dogfood_exemplars WHERE slug = ?", (slug,)
    ).fetchone()
    conn.close()
    return _row_to_exemplar_dict(row) if row else None


def list_dogfood_exemplars(exclude_slug=None):
    """Return all exemplars as dicts, optionally excluding one slug.
    Ordered by slug."""
    conn = _connect()
    if exclude_slug:
        rows = conn.execute(
            "SELECT * FROM dogfood_exemplars WHERE slug != ? ORDER BY slug",
            (exclude_slug,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM dogfood_exemplars ORDER BY slug"
        ).fetchall()
    conn.close()
    return [_row_to_exemplar_dict(r) for r in rows]


def _row_to_exemplar_dict(row):
    if row is None:
        return None
    meta = {}
    try:
        meta = json.loads(row['metadata_json'] or '{}')
    except Exception:
        meta = {}
    return {
        "id": row['id'],
        "slug": row['slug'],
        "title": row['title'],
        "shape": row['shape'],
        "body_markdown": row['body_markdown'],
        "metadata": meta,
        "last_validated_against": row['last_validated_against'],
        "created_at": row['created_at'],
        "updated_at": row['updated_at'],
    }


def list_dogfood_tasks(variant=None, benchmark_slug=None):
    """Return all tasks as dicts, optionally filtered by variant or
    benchmark_slug. Ordered by task_id."""
    conn = _connect()
    sql = "SELECT * FROM dogfood_tasks"
    where = []
    params = []
    if variant:
        where.append("variant = ?")
        params.append(variant)
    if benchmark_slug:
        where.append("benchmark_slug = ?")
        params.append(benchmark_slug)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY task_id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_task_dict(r) for r in rows]


def _row_to_task_dict(row):
    if row is None:
        return None
    meta = {}
    try:
        meta = json.loads(row['metadata_json'] or '{}')
    except Exception:
        meta = {}
    # Prefer the template column; fall back to legacy run_topic_name for
    # rows that predate the template migration (shouldn't happen after
    # init_db runs, but be defensive).
    template = None
    try:
        template = row['run_topic_name_template']
    except (IndexError, KeyError):
        template = None
    if not template:
        template = row['run_topic_name']
    return {
        'task_id': row['task_id'],
        'variant': row['variant'],
        'benchmark_slug': row['benchmark_slug'],
        'run_topic_name_template': template,
        'brief_markdown': row['brief_markdown'],
        'metadata': meta,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


# Initialize on import
init_db()
