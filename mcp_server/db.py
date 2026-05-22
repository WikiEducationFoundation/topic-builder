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
        -- Auth (Wikimedia OAuth 2.0). Tokens are stored as SHA-256 hashes
        -- so a DB compromise doesn't yield active tokens. Issued by the
        -- /oauth/callback handler after a successful OAuth dance.
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            wikipedia_username TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            last_used_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(wikipedia_username);
        -- Short-lived CSRF state for the OAuth redirect flow. Cleaned up on a
        -- 10-min sweep; rows older than that are stale.
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        -- Cached index of WikiProjects tracked by the Wikipedia 1.0 bot
        -- (User:WP_1.0_bot/Tables/Project/<canonical>). Used by
        -- preview_wikiproject to resolve user-supplied project names to
        -- the bot's canonical form (handles plural/singular drift like
        -- "Plants" → "Plant", and surfaces "not WP1.0-tracked" cleanly).
        -- Refreshed lazily when older than the staleness threshold; full
        -- index is ~2.7K rows so refresh is cheap.
        CREATE TABLE IF NOT EXISTS wp_bot_projects (
            canonical_name TEXT PRIMARY KEY,
            normalized_name TEXT NOT NULL,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_wp_bot_normalized
            ON wp_bot_projects(normalized_name);
        -- Cross-wiki WikiProject equivalents, derived from Wikidata
        -- sitelinks on each enwiki WikiProject's Wikidata item. One row
        -- per (en_project, target_wiki) pair. Lets check_wikiproject /
        -- get_wikiproject_articles answer "what does this WP look like
        -- on fr/de/es/..." without per-call HTTP — refreshed lazily,
        -- same pattern as wp_bot_projects.
        CREATE TABLE IF NOT EXISTS wp_crosswiki (
            en_project TEXT NOT NULL,
            normalized_en TEXT NOT NULL,
            qid TEXT NOT NULL,
            wiki TEXT NOT NULL,
            page_title TEXT NOT NULL,
            fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (en_project, wiki)
        );
        CREATE INDEX IF NOT EXISTS idx_wp_crosswiki_norm
            ON wp_crosswiki(normalized_en);
        CREATE INDEX IF NOT EXISTS idx_wp_crosswiki_qid
            ON wp_crosswiki(qid);
        -- Frozen Impact Visualizer handoff packages. publish_topic mints a
        -- handle and snapshots the article list + IV config; IV fetches
        -- /packages/<handle> server-side after the user clicks Import.
        -- Auth is handle unguessability — the URL is a capability.
        CREATE TABLE IF NOT EXISTS iv_packages (
            handle TEXT PRIMARY KEY,
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            config_json TEXT NOT NULL,
            articles_json TEXT NOT NULL,
            source_topic TEXT NOT NULL,
            source_topic_id INTEGER NOT NULL,
            publisher_user TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            consumed_at TEXT,
            expires_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_iv_packages_topic
            ON iv_packages(topic_id);
        CREATE INDEX IF NOT EXISTS idx_iv_packages_publisher
            ON iv_packages(publisher_user);
        CREATE INDEX IF NOT EXISTS idx_iv_packages_expires
            ON iv_packages(expires_at);
        -- Tag taxonomy + per-article membership. Tags are per-topic
        -- (no global registry), many-to-many, optionally value-bearing
        -- (a tag may declare 'properties' carrying per-article values).
        -- Designed to subsume IV's Classifications feature: same wire
        -- shape, sourced from TB at publish time instead of computed
        -- via per-article Wikidata fan-out.
        CREATE TABLE IF NOT EXISTS topic_tags (
            topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            ordering INTEGER NOT NULL DEFAULT 0,
            derived_from TEXT,
            properties_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (topic_id, name)
        );
        -- Per-article tag membership. article_id FKs articles(id); topic_id
        -- is denormalized for query speed and joined-FK to topic_tags so a
        -- topic_tags delete cascades to membership. properties_json carries
        -- per-article values for the tag's declared properties (empty array
        -- for binary tags).
        CREATE TABLE IF NOT EXISTS article_tags (
            topic_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            properties_json TEXT NOT NULL DEFAULT '[]',
            assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (topic_id, article_id, tag_name),
            FOREIGN KEY (topic_id, tag_name)
                REFERENCES topic_tags(topic_id, name) ON DELETE CASCADE,
            FOREIGN KEY (article_id)
                REFERENCES articles(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_article_tags_topic_tag
            ON article_tags(topic_id, tag_name);
        CREATE INDEX IF NOT EXISTS idx_article_tags_article
            ON article_tags(article_id);
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
    # Migrate existing DBs that predate auto-dispatch. NULL means
    # "never dispatched" — sorts first under ASC ordering, so the
    # auto-dispatch picker selects never-dispatched tasks before
    # already-dispatched ones (round-robin coverage).
    if task_cols and 'last_dispatched_at' not in task_cols:
        conn.execute(
            "ALTER TABLE dogfood_tasks ADD COLUMN last_dispatched_at TEXT")
    # Migrate existing DBs that predate the centrality rubric. Empty string
    # means "no rubric set yet" — AI should write one at scoping time.
    if 'centrality_rubric' not in topic_cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN centrality_rubric TEXT NOT NULL DEFAULT ''")
    # Migrate existing DBs that predate Ship 2 topic metadata. Stores a small
    # JSON KV: topic_profile (axis values from shape_axes.md), and
    # last_redirect_collapse stats (collapse pct + timestamp from the most
    # recent resolve_redirects call). NULL/empty-dict means "no metadata
    # captured yet" — backward-compatible with pre-Ship-2 topics.
    if 'metadata_json' not in topic_cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
    # Auth: per-topic ownership and visibility. owner_username is NULL for
    # legacy topics that predate auth; backfilled by MIGRATION_DEFAULT_OWNER
    # below (env-gated, opt-in). visibility values: 'private' (default),
    # 'public_read' (anyone reads, owner writes), 'public_edit' (anyone
    # authenticated reads + writes).
    if 'owner_username' not in topic_cols:
        conn.execute("ALTER TABLE topics ADD COLUMN owner_username TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topics_owner ON topics(owner_username)")
    if 'visibility' not in topic_cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topics_visibility ON topics(visibility)")
    # Optional one-shot migration: assign a default owner to any topic that
    # still has owner_username = NULL. Operator opts in by setting
    # MIGRATION_DEFAULT_OWNER in the environment; without it, legacy topics
    # remain unowned (their tools still work because permission enforcement
    # is feature-flagged off until AUTH_ENFORCEMENT is set).
    default_owner = os.environ.get("MIGRATION_DEFAULT_OWNER")
    if default_owner:
        conn.execute(
            "UPDATE topics SET owner_username = ? "
            "WHERE owner_username IS NULL",
            (default_owner,))
    # Migrate existing DBs that predate iv_packages.source_topic_id (the
    # denormalized stable TB topics.id IV uses to recognize republishes of
    # an already-imported topic). The column is NOT NULL on fresh schemas;
    # SQLite can't ALTER-add NOT NULL, so we add it nullable and backfill
    # from topic_id. Inserts always provide it going forward.
    iv_pkg_cols = []
    try:
        iv_pkg_cols = [r[1] for r in conn.execute("PRAGMA table_info(iv_packages)")]
    except sqlite3.OperationalError:
        pass
    if iv_pkg_cols and 'source_topic_id' not in iv_pkg_cols:
        conn.execute("ALTER TABLE iv_packages ADD COLUMN source_topic_id INTEGER")
        conn.execute(
            "UPDATE iv_packages SET source_topic_id = topic_id "
            "WHERE source_topic_id IS NULL")
    conn.commit()
    conn.close()


def get_topic_metadata(topic_id):
    """Return the topic's metadata KV dict, or {} if none."""
    conn = _connect()
    row = conn.execute("SELECT metadata_json FROM topics WHERE id = ?",
                       (topic_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    try:
        import json
        return json.loads(row['metadata_json'] or '{}')
    except (ValueError, TypeError):
        return {}


def update_topic_metadata(topic_id, updates):
    """Merge `updates` (a dict) into the topic's metadata KV. Existing keys
    are overwritten by `updates`; keys not in `updates` are preserved."""
    import json
    current = get_topic_metadata(topic_id)
    current.update(updates)
    conn = _connect()
    conn.execute("UPDATE topics SET metadata_json = ?, updated_at = datetime('now') "
                 "WHERE id = ?", (json.dumps(current, ensure_ascii=False), topic_id))
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


# --- Tag taxonomy ---------------------------------------------------------
#
# Tags layer alongside the centrality score: centrality is an axis (how
# core), tags are sets (what subset). Validation here mirrors IV's wire
# shape for Classification + ArticleClassification — a topic_tag row is
# structurally an IV Classification minus the `prerequisites` half, and a
# property def maps slug-for-slug to IV's Classification.properties shape.
# Membership writes (article_tags) live in Slice 2 helpers.

_TAG_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_PROPERTY_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_SEGMENT_KEY_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_WIKIDATA_PID_RE = re.compile(r'^P\d+$')
_WIKIDATA_QID_RE = re.compile(r'^Q\d+$')


def validate_tag_definitions(tags):
    """Validate + normalize a list of tag definitions. Returns
    (cleaned_list, error_or_None). cleaned_list preserves caller order;
    `ordering` is filled in from list position when omitted."""
    if not isinstance(tags, list):
        return None, "tags must be a list."
    cleaned = []
    seen_names = set()
    for i, tag in enumerate(tags):
        if not isinstance(tag, dict):
            return None, f"tags[{i}] must be a dict."
        name = tag.get('name')
        if not isinstance(name, str) or not _TAG_NAME_RE.match(name):
            return None, (
                f"tags[{i}].name must be a kebab-case slug "
                f"(a-z, 0-9, _, -; first char alphanumeric; <=64 chars). "
                f"Got: {name!r}")
        if name in seen_names:
            return None, f"Duplicate tag name {name!r}."
        seen_names.add(name)
        description = tag.get('description', '')
        if not isinstance(description, str):
            return None, f"tags[{i}].description must be a string."
        if len(description) > 500:
            return None, (
                f"tags[{i}].description exceeds 500 chars "
                f"({len(description)}).")
        ordering = tag.get('ordering', i)
        if not isinstance(ordering, int):
            return None, f"tags[{i}].ordering must be int."
        derived_from = tag.get('derived_from')
        if derived_from is not None and not isinstance(derived_from, str):
            return None, f"tags[{i}].derived_from must be string or null."
        properties = tag.get('properties', [])
        cleaned_props, err = _validate_tag_properties(properties, f"tags[{i}]")
        if err:
            return None, err
        cleaned.append({
            'name': name,
            'description': description,
            'ordering': ordering,
            'derived_from': derived_from,
            'properties': cleaned_props,
        })
    return cleaned, None


def _validate_tag_properties(properties, where):
    if not isinstance(properties, list):
        return None, f"{where}.properties must be a list."
    cleaned = []
    seen_slugs = set()
    for j, prop in enumerate(properties):
        if not isinstance(prop, dict):
            return None, f"{where}.properties[{j}] must be a dict."
        slug = prop.get('slug')
        if not isinstance(slug, str) or not _PROPERTY_SLUG_RE.match(slug):
            return None, (
                f"{where}.properties[{j}].slug must be kebab-case. "
                f"Got: {slug!r}")
        if slug in seen_slugs:
            return None, f"{where}.properties: duplicate slug {slug!r}."
        seen_slugs.add(slug)
        name = prop.get('name')
        if not isinstance(name, str) or not name:
            return None, (
                f"{where}.properties[{j}].name must be non-empty string.")
        wpid = prop.get('wikidata_property_id')
        if wpid is not None and (not isinstance(wpid, str)
                                 or not _WIKIDATA_PID_RE.match(wpid)):
            return None, (
                f"{where}.properties[{j}].wikidata_property_id must match "
                f"P<digits> or be omitted. Got: {wpid!r}")
        segments = prop.get('segments')
        cleaned_segs, err = _validate_tag_segments(
            segments, f"{where}.properties[{j}]")
        if err:
            return None, err
        cleaned_prop = {'slug': slug, 'name': name, 'segments': cleaned_segs}
        if wpid:
            cleaned_prop['wikidata_property_id'] = wpid
        cleaned.append(cleaned_prop)
    return cleaned, None


def _validate_tag_segments(segments, where):
    if segments is True:
        return True, None
    if not isinstance(segments, list):
        return None, (
            f"{where}.segments must be `true` (auto-group by top values) "
            f"or a list of segment dicts.")
    cleaned = []
    seen_keys = set()
    default_count = 0
    for k, seg in enumerate(segments):
        if not isinstance(seg, dict):
            return None, f"{where}.segments[{k}] must be a dict."
        key = seg.get('key')
        if not isinstance(key, str) or not _SEGMENT_KEY_RE.match(key):
            return None, (
                f"{where}.segments[{k}].key must be kebab-case. Got: {key!r}")
        if key in seen_keys:
            return None, f"{where}.segments: duplicate key {key!r}."
        seen_keys.add(key)
        label = seg.get('label')
        if not isinstance(label, str) or not label:
            return None, f"{where}.segments[{k}].label must be non-empty."
        value_ids = seg.get('value_ids', [])
        if not isinstance(value_ids, list):
            return None, f"{where}.segments[{k}].value_ids must be a list."
        for v, vid in enumerate(value_ids):
            if not isinstance(vid, str) or not _WIKIDATA_QID_RE.match(vid):
                return None, (
                    f"{where}.segments[{k}].value_ids[{v}] must match "
                    f"Q<digits>. Got: {vid!r}")
        default = seg.get('default', False)
        if not isinstance(default, bool):
            return None, f"{where}.segments[{k}].default must be bool."
        if default:
            default_count += 1
        cleaned_seg = {'key': key, 'label': label}
        if value_ids:
            cleaned_seg['value_ids'] = value_ids
        if default:
            cleaned_seg['default'] = True
        cleaned.append(cleaned_seg)
    if default_count > 1:
        return None, (
            f"{where}.segments: at most one segment may set default=true.")
    return cleaned, None


def list_topic_tags(topic_id):
    """Return the topic's tag taxonomy ordered by `ordering` then `name`.
    Empty list if no tags defined."""
    conn = _connect()
    rows = conn.execute(
        "SELECT name, description, ordering, derived_from, "
        "       properties_json, created_at, updated_at "
        "FROM topic_tags WHERE topic_id = ? "
        "ORDER BY ordering, name",
        (topic_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'name': r['name'],
            'description': r['description'],
            'ordering': r['ordering'],
            'derived_from': r['derived_from'],
            'properties': json.loads(r['properties_json'] or '[]'),
            'created_at': r['created_at'],
            'updated_at': r['updated_at'],
        })
    return result


def replace_topic_tags(topic_id, cleaned_tags):
    """Replace the topic's tag taxonomy. Tags absent from `cleaned_tags`
    are dropped (cascading to article_tags). Tags present with an existing
    name are updated in place; membership is preserved.

    Caller is responsible for validation via `validate_tag_definitions`.

    Returns {'added': [...], 'updated': [...], 'removed': [...]}.
    """
    conn = _connect()
    existing_rows = conn.execute(
        "SELECT name FROM topic_tags WHERE topic_id = ?",
        (topic_id,)).fetchall()
    existing_names = {r['name'] for r in existing_rows}
    new_names = {t['name'] for t in cleaned_tags}

    added = []
    updated = []
    removed = sorted(existing_names - new_names)

    for name in removed:
        conn.execute(
            "DELETE FROM topic_tags WHERE topic_id = ? AND name = ?",
            (topic_id, name))

    for tag in cleaned_tags:
        props_json = json.dumps(tag['properties'], ensure_ascii=False)
        if tag['name'] in existing_names:
            conn.execute(
                "UPDATE topic_tags SET description = ?, ordering = ?, "
                "       derived_from = ?, properties_json = ?, "
                "       updated_at = datetime('now') "
                "WHERE topic_id = ? AND name = ?",
                (tag['description'], tag['ordering'], tag['derived_from'],
                 props_json, topic_id, tag['name']))
            updated.append(tag['name'])
        else:
            conn.execute(
                "INSERT INTO topic_tags (topic_id, name, description, "
                "       ordering, derived_from, properties_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (topic_id, tag['name'], tag['description'], tag['ordering'],
                 tag['derived_from'], props_json))
            added.append(tag['name'])

    conn.execute(
        "UPDATE topics SET updated_at = datetime('now') WHERE id = ?",
        (topic_id,))
    conn.commit()
    conn.close()
    return {'added': added, 'updated': updated, 'removed': removed}


def tag_definition_exists(topic_id, tag_name):
    """True if the topic has a tag with this name defined."""
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM topic_tags WHERE topic_id = ? AND name = ?",
        (topic_id, tag_name)).fetchone()
    conn.close()
    return row is not None


def resolve_titles_to_ids(topic_id, titles):
    """Public wrapper: open a connection and resolve titles → ids."""
    conn = _connect()
    try:
        return _resolve_titles_to_ids(conn, topic_id, titles)
    finally:
        conn.close()


def _resolve_titles_to_ids(conn, topic_id, titles):
    """Resolve a list of article titles to ids within a topic. Returns
    (title→id dict, sorted list of titles not in topic). Batched to avoid
    SQLite's variable-count limit."""
    found = {}
    seen = set(titles)
    for i in range(0, len(titles), 500):
        batch = titles[i:i + 500]
        placeholders = ','.join('?' * len(batch))
        rows = conn.execute(
            f"SELECT id, title FROM articles "
            f"WHERE topic_id = ? AND title IN ({placeholders})",
            [topic_id] + list(batch)).fetchall()
        for r in rows:
            found[r['title']] = r['id']
    not_in_topic = sorted(seen - set(found.keys()))
    return found, not_in_topic


def tag_articles_by_titles(topic_id, tag_name, titles):
    """Apply `tag_name` to articles with these titles. Caller must have
    confirmed the tag definition exists. Returns {'tagged_new', 'already_tagged',
    'not_in_topic'}. Property values are not set here — Slice 3 covers that."""
    if not titles:
        return {'tagged_new': 0, 'already_tagged': 0, 'not_in_topic': []}
    conn = _connect()
    found_ids, not_in_topic = _resolve_titles_to_ids(conn, topic_id, titles)
    article_ids = list(found_ids.values())
    tagged_new = 0
    if article_ids:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO article_tags "
            "(topic_id, article_id, tag_name) VALUES (?, ?, ?)",
            [(topic_id, aid, tag_name) for aid in article_ids])
        tagged_new = conn.total_changes - before
    conn.commit()
    conn.close()
    return {
        'tagged_new': tagged_new,
        'already_tagged': len(article_ids) - tagged_new,
        'not_in_topic': not_in_topic,
    }


def untag_articles_by_titles(topic_id, tag_name, titles):
    """Remove the tag from these titles. Returns {'untagged',
    'in_topic_but_not_tagged', 'not_in_topic'}."""
    if not titles:
        return {'untagged': 0, 'in_topic_but_not_tagged': 0, 'not_in_topic': []}
    conn = _connect()
    found_ids, not_in_topic = _resolve_titles_to_ids(conn, topic_id, titles)
    article_ids = list(found_ids.values())
    untagged = 0
    if article_ids:
        for i in range(0, len(article_ids), 500):
            batch = article_ids[i:i + 500]
            placeholders = ','.join('?' * len(batch))
            cur = conn.execute(
                f"DELETE FROM article_tags WHERE topic_id = ? "
                f"AND tag_name = ? AND article_id IN ({placeholders})",
                [topic_id, tag_name] + list(batch))
            untagged += cur.rowcount
    conn.commit()
    conn.close()
    return {
        'untagged': untagged,
        'in_topic_but_not_tagged': len(article_ids) - untagged,
        'not_in_topic': not_in_topic,
    }


def tag_articles_by_source(topic_id, tag_name, source_label,
                           prefix_match=False):
    """Apply `tag_name` to every article whose sources include
    `source_label` (or, if prefix_match, any source label starting with it).
    Returns {'matched', 'tagged_new', 'already_tagged'}."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, sources FROM articles WHERE topic_id = ?",
        (topic_id,)).fetchall()
    article_ids = []
    for r in rows:
        sources = json.loads(r['sources'])
        if prefix_match:
            if any(s.startswith(source_label) for s in sources):
                article_ids.append(r['id'])
        elif source_label in sources:
            article_ids.append(r['id'])
    tagged_new = 0
    if article_ids:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO article_tags "
            "(topic_id, article_id, tag_name) VALUES (?, ?, ?)",
            [(topic_id, aid, tag_name) for aid in article_ids])
        tagged_new = conn.total_changes - before
    conn.commit()
    conn.close()
    return {
        'matched': len(article_ids),
        'tagged_new': tagged_new,
        'already_tagged': len(article_ids) - tagged_new,
    }


def untag_articles_by_source(topic_id, tag_name, source_label,
                             prefix_match=False):
    """Remove `tag_name` membership from every article whose sources match.
    Returns {'matched', 'untagged'}."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, sources FROM articles WHERE topic_id = ?",
        (topic_id,)).fetchall()
    article_ids = []
    for r in rows:
        sources = json.loads(r['sources'])
        if prefix_match:
            if any(s.startswith(source_label) for s in sources):
                article_ids.append(r['id'])
        elif source_label in sources:
            article_ids.append(r['id'])
    untagged = 0
    if article_ids:
        for i in range(0, len(article_ids), 500):
            batch = article_ids[i:i + 500]
            placeholders = ','.join('?' * len(batch))
            cur = conn.execute(
                f"DELETE FROM article_tags WHERE topic_id = ? "
                f"AND tag_name = ? AND article_id IN ({placeholders})",
                [topic_id, tag_name] + list(batch))
            untagged += cur.rowcount
    conn.commit()
    conn.close()
    return {'matched': len(article_ids), 'untagged': untagged}


def tag_articles_by_pattern(topic_id, tag_name, title_regex=None,
                            description_regex=None):
    """Apply `tag_name` to articles whose title or description matches the
    regex (case-insensitive). If both regexes are set, they AND together.
    Returns {'matched', 'tagged_new', 'already_tagged'}."""
    if not title_regex and not description_regex:
        return {'matched': 0, 'tagged_new': 0, 'already_tagged': 0}
    title_re = re.compile(title_regex, re.IGNORECASE) if title_regex else None
    desc_re = (re.compile(description_regex, re.IGNORECASE)
               if description_regex else None)
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, description FROM articles WHERE topic_id = ?",
        (topic_id,)).fetchall()
    article_ids = []
    for r in rows:
        title = r['title']
        desc = r['description'] or ''
        if title_re and not title_re.search(title):
            continue
        if desc_re and not desc_re.search(desc):
            continue
        article_ids.append(r['id'])
    tagged_new = 0
    if article_ids:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO article_tags "
            "(topic_id, article_id, tag_name) VALUES (?, ?, ?)",
            [(topic_id, aid, tag_name) for aid in article_ids])
        tagged_new = conn.total_changes - before
    conn.commit()
    conn.close()
    return {
        'matched': len(article_ids),
        'tagged_new': tagged_new,
        'already_tagged': len(article_ids) - tagged_new,
    }


def untag_all_for_tag(topic_id, tag_name):
    """Wipe all membership for a tag without deleting its definition.
    Returns count untagged."""
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM article_tags WHERE topic_id = ? AND tag_name = ?",
        (topic_id, tag_name))
    untagged = cur.rowcount
    conn.commit()
    conn.close()
    return untagged


def get_topic_tag(topic_id, tag_name):
    """Return a single tag definition (with parsed properties), or None
    if the tag isn't defined. Used by Wikidata-driven tagging to look up
    declared property defs by slug."""
    conn = _connect()
    row = conn.execute(
        "SELECT name, description, ordering, derived_from, properties_json "
        "FROM topic_tags WHERE topic_id = ? AND name = ?",
        (topic_id, tag_name)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        'name': row['name'],
        'description': row['description'],
        'ordering': row['ordering'],
        'derived_from': row['derived_from'],
        'properties': json.loads(row['properties_json'] or '[]'),
    }


def get_topic_qids(topic_id):
    """Return [(article_id, title, qid), ...] for every article in the
    topic that has a non-empty wikidata_qid. Used as the candidate set
    for tag_by_wikidata."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, wikidata_qid FROM articles "
        "WHERE topic_id = ? AND wikidata_qid IS NOT NULL "
        "AND wikidata_qid != ''",
        (topic_id,)).fetchall()
    conn.close()
    return [(r['id'], r['title'], r['wikidata_qid']) for r in rows]


def upsert_article_tags_with_values(topic_id, tag_name, assignments):
    """Insert or update article_tags rows. `assignments` is a list of
    (article_id, properties_json_str). For each row: insert if missing,
    update properties_json if present. Returns {'tagged_new', 'updated',
    'unchanged'}."""
    if not assignments:
        return {'tagged_new': 0, 'updated': 0, 'unchanged': 0}
    conn = _connect()
    tagged_new = 0
    updated = 0
    unchanged = 0
    for article_id, props_json in assignments:
        existing = conn.execute(
            "SELECT properties_json FROM article_tags "
            "WHERE topic_id = ? AND article_id = ? AND tag_name = ?",
            (topic_id, article_id, tag_name)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO article_tags "
                "(topic_id, article_id, tag_name, properties_json) "
                "VALUES (?, ?, ?, ?)",
                (topic_id, article_id, tag_name, props_json))
            tagged_new += 1
        elif existing['properties_json'] != props_json:
            conn.execute(
                "UPDATE article_tags SET properties_json = ?, "
                "       assigned_at = datetime('now') "
                "WHERE topic_id = ? AND article_id = ? AND tag_name = ?",
                (props_json, topic_id, article_id, tag_name))
            updated += 1
        else:
            unchanged += 1
    conn.commit()
    conn.close()
    return {
        'tagged_new': tagged_new,
        'updated': updated,
        'unchanged': unchanged,
    }


def set_tag_property_value(topic_id, tag_name, article_id, slug, value_ids):
    """Set values for a single property on a single article's tag row.
    Membership must already exist (caller should check). Other properties
    on the row are preserved. Returns True if the row was updated, False
    if there's no membership row to update."""
    conn = _connect()
    row = conn.execute(
        "SELECT properties_json FROM article_tags "
        "WHERE topic_id = ? AND article_id = ? AND tag_name = ?",
        (topic_id, article_id, tag_name)).fetchone()
    if row is None:
        conn.close()
        return False
    props = json.loads(row['properties_json'] or '[]')
    # Replace existing entry for this slug, or append.
    replaced = False
    for entry in props:
        if entry.get('slug') == slug:
            entry['value_ids'] = list(value_ids)
            replaced = True
            break
    if not replaced:
        props.append({'slug': slug, 'value_ids': list(value_ids)})
    conn.execute(
        "UPDATE article_tags SET properties_json = ?, "
        "       assigned_at = datetime('now') "
        "WHERE topic_id = ? AND article_id = ? AND tag_name = ?",
        (json.dumps(props, ensure_ascii=False),
         topic_id, article_id, tag_name))
    conn.commit()
    conn.close()
    return True


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


def pick_and_dispatch_dogfood_task(variant=None):
    """Atomically pick the staleest dogfood task (smallest
    last_dispatched_at; NULL sorts first so never-dispatched tasks
    win), optionally filtered by variant. Marks it dispatched
    (`last_dispatched_at = now`) and returns the row.

    Round-robin behavior: simultaneous callers within a tiny window
    get DIFFERENT tasks because each call updates `last_dispatched_at`
    before returning, so the next caller sees a different staleest.
    BEGIN IMMEDIATE serializes the SELECT-then-UPDATE pair across
    concurrent connections.

    Returns None if no tasks match the filter (variant). Caller
    should distinguish that from an empty DB. Ties on
    `last_dispatched_at` (e.g. multiple never-dispatched) break by
    `task_id` ASC for determinism."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        sql = "SELECT * FROM dogfood_tasks"
        params = []
        if variant:
            sql += " WHERE variant = ?"
            params.append(variant)
        sql += " ORDER BY last_dispatched_at ASC, task_id ASC LIMIT 1"
        row = conn.execute(sql, params).fetchone()
        if row is None:
            conn.rollback()
            return None
        chosen_id = row['id']
        conn.execute(
            "UPDATE dogfood_tasks "
            "SET last_dispatched_at = datetime('now') "
            "WHERE id = ?",
            (chosen_id,)
        )
        conn.commit()
        # Refetch to get the updated last_dispatched_at value.
        row = conn.execute(
            "SELECT * FROM dogfood_tasks WHERE id = ?", (chosen_id,)
        ).fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _row_to_task_dict(row)


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
    last_dispatched = None
    try:
        last_dispatched = row['last_dispatched_at']
    except (IndexError, KeyError):
        last_dispatched = None
    return {
        'task_id': row['task_id'],
        'variant': row['variant'],
        'benchmark_slug': row['benchmark_slug'],
        'run_topic_name_template': template,
        'brief_markdown': row['brief_markdown'],
        'metadata': meta,
        'last_dispatched_at': last_dispatched,
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


# ── Auth: token + ACL helpers ──────────────────────────────────────────

import hashlib
import secrets


def normalize_username(username):
    """Normalize a Wikipedia username for stable comparison. Wikipedia
    capitalizes the first character and uses underscores for spaces in
    URLs, but the displayed form may use spaces. Use this whenever we
    compare a stored owner against a caller."""
    if not username:
        return ""
    s = username.strip().replace("_", " ")
    if s:
        s = s[0].upper() + s[1:]
    return s


def hash_token(raw_token):
    """SHA-256 hash of a raw bearer token. The DB stores only the hash."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_token():
    """Mint a new opaque bearer token. Format: tb_<32 hex chars>."""
    return "tb_" + secrets.token_hex(16)


def create_auth_token(wikipedia_username, ttl_days=30):
    """Create + persist a new token for the given Wikipedia user. Returns
    (raw_token, expires_at). The raw token is shown to the user once;
    the DB only stores its hash."""
    raw = generate_token()
    h = hash_token(raw)
    user = normalize_username(wikipedia_username)
    conn = _connect()
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, wikipedia_username, expires_at) "
        "VALUES (?, ?, datetime('now', ?))",
        (h, user, f"+{int(ttl_days)} days"))
    expires_at = conn.execute(
        "SELECT expires_at FROM auth_tokens WHERE token_hash = ?",
        (h,)).fetchone()['expires_at']
    conn.commit()
    conn.close()
    return raw, expires_at


def lookup_auth_token(raw_token):
    """Resolve a raw bearer token to its user. Returns dict with
    {username, expires_at, revoked_at, last_used_at} or None if not
    found / expired / revoked. On a successful lookup, slides the
    expiry forward (30-day sliding TTL): active users never re-auth,
    abandoned tokens die naturally."""
    if not raw_token or not raw_token.startswith("tb_"):
        return None
    h = hash_token(raw_token)
    conn = _connect()
    row = conn.execute(
        "SELECT id, wikipedia_username, expires_at, revoked_at, last_used_at "
        "FROM auth_tokens WHERE token_hash = ?", (h,)).fetchone()
    if row is None:
        conn.close()
        return None
    if row['revoked_at']:
        conn.close()
        return None
    # Compare expires_at against now in SQLite to avoid TZ math in Python.
    fresh = conn.execute(
        "SELECT (expires_at > datetime('now')) AS ok FROM auth_tokens "
        "WHERE id = ?", (row['id'],)).fetchone()
    if not fresh or not fresh['ok']:
        conn.close()
        return None
    updated = conn.execute(
        "UPDATE auth_tokens "
        "SET last_used_at = datetime('now'), "
        "    expires_at   = datetime('now', '+30 days') "
        "WHERE id = ? "
        "RETURNING expires_at, last_used_at", (row['id'],)).fetchone()
    conn.commit()
    conn.close()
    return {
        'username': row['wikipedia_username'],
        'expires_at': updated['expires_at'] if updated else row['expires_at'],
        'revoked_at': row['revoked_at'],
        'last_used_at': updated['last_used_at'] if updated else row['last_used_at'],
    }


def revoke_auth_token(raw_token):
    """Mark a token revoked. Returns True if it existed and was active."""
    if not raw_token:
        return False
    h = hash_token(raw_token)
    conn = _connect()
    cur = conn.execute(
        "UPDATE auth_tokens SET revoked_at = datetime('now') "
        "WHERE token_hash = ? AND revoked_at IS NULL", (h,))
    conn.commit()
    rowcount = cur.rowcount
    conn.close()
    return rowcount > 0


def list_active_tokens(wikipedia_username):
    """List a user's non-revoked, unexpired tokens (without raw values).
    Used by the token-management UI on /oauth."""
    user = normalize_username(wikipedia_username)
    conn = _connect()
    rows = conn.execute(
        "SELECT id, created_at, expires_at, last_used_at FROM auth_tokens "
        "WHERE wikipedia_username = ? AND revoked_at IS NULL "
        "AND expires_at > datetime('now') ORDER BY created_at DESC",
        (user,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_oauth_state():
    """Create + persist a CSRF state nonce for the OAuth redirect dance.
    Returns the raw state value to put in the cookie + the URL."""
    state = secrets.token_urlsafe(24)
    conn = _connect()
    conn.execute("INSERT INTO oauth_states (state) VALUES (?)", (state,))
    conn.commit()
    conn.close()
    return state


def consume_oauth_state(state, max_age_seconds=600):
    """Look up + delete a state nonce in one transaction. Returns True
    if it existed and is fresh (created within max_age_seconds)."""
    if not state:
        return False
    conn = _connect()
    row = conn.execute(
        "SELECT created_at, "
        "(strftime('%s','now') - strftime('%s', created_at)) AS age "
        "FROM oauth_states WHERE state = ?", (state,)).fetchone()
    if row is None:
        conn.close()
        return False
    age = int(row['age'] or 0)
    conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    # Best-effort sweep of stale rows on every consume.
    conn.execute(
        "DELETE FROM oauth_states WHERE "
        "strftime('%s','now') - strftime('%s', created_at) > ?",
        (int(max_age_seconds),))
    conn.commit()
    conn.close()
    return age <= int(max_age_seconds)


def normalize_wp_project_name(name):
    """Lowercase + collapse non-alphanumerics for fuzzy WikiProject lookup.
    Handles "Climate change" / "climate_change" / "Climate-Change" all
    mapping to "climatechange". Plural/singular drift is handled at the
    callsite (try with and without trailing 's'), not here."""
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def lookup_wp_bot_project(query):
    """Resolve a user-supplied project name to its bot-canonical form.
    Returns canonical_name or None. Tries exact, then normalized, then
    plural-stripped normalized."""
    if not query:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT canonical_name FROM wp_bot_projects WHERE canonical_name = ?",
            (query,)).fetchone()
        if row:
            return row['canonical_name']
        norm = normalize_wp_project_name(query)
        if not norm:
            return None
        row = conn.execute(
            "SELECT canonical_name FROM wp_bot_projects WHERE normalized_name = ?",
            (norm,)).fetchone()
        if row:
            return row['canonical_name']
        # Plural fallback: "Plants" → "Plant", "Birds" → "Bird".
        if norm.endswith("s") and len(norm) > 2:
            row = conn.execute(
                "SELECT canonical_name FROM wp_bot_projects WHERE normalized_name = ?",
                (norm[:-1],)).fetchone()
            if row:
                return row['canonical_name']
        return None
    finally:
        conn.close()


def wp_bot_index_age_seconds():
    """Age of the most recent wp_bot_projects row in seconds, or None
    if the table is empty. Used to decide when to refresh."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT (strftime('%s','now') - strftime('%s', MAX(fetched_at))) "
            "AS age FROM wp_bot_projects").fetchone()
        if row is None or row['age'] is None:
            return None
        return int(row['age'])
    finally:
        conn.close()


def replace_wp_bot_index(canonical_names):
    """Atomically replace the wp_bot_projects index. Used by the
    refresh path; fetches all subpages of User:WP_1.0_bot/Tables/Project/
    in one go and rewrites the table."""
    now_iso = None  # let SQLite default fill it
    conn = _connect()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM wp_bot_projects")
        rows = [
            (name, normalize_wp_project_name(name))
            for name in canonical_names if name]
        conn.executemany(
            "INSERT INTO wp_bot_projects (canonical_name, normalized_name) "
            "VALUES (?, ?)", rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def wp_crosswiki_index_age_seconds():
    """Age of the most recent wp_crosswiki row in seconds, or None if
    the table is empty. Used to decide when to refresh."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT (strftime('%s','now') - strftime('%s', MAX(fetched_at))) "
            "AS age FROM wp_crosswiki").fetchone()
        if row is None or row['age'] is None:
            return None
        return int(row['age'])
    finally:
        conn.close()


def replace_wp_crosswiki(edges):
    """Atomically replace the wp_crosswiki index. `edges` is an iterable
    of (en_project, qid, wiki, page_title) tuples — one per cross-wiki
    sitelink. Returns the number of rows written."""
    conn = _connect()
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM wp_crosswiki")
        rows = [
            (en, normalize_wp_project_name(en), qid, wiki, title)
            for (en, qid, wiki, title) in edges
            if en and qid and wiki and title]
        conn.executemany(
            "INSERT OR REPLACE INTO wp_crosswiki "
            "(en_project, normalized_en, qid, wiki, page_title) "
            "VALUES (?, ?, ?, ?, ?)", rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def lookup_wp_crosswiki(en_project, wiki):
    """Return the local project-page title on `wiki` for the given
    enwiki WikiProject name (canonical, without the
    "Wikipedia:WikiProject " prefix), or None.

    Resolution: exact en_project match first, then normalized match
    (handles case/whitespace drift)."""
    if not en_project or not wiki:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT page_title FROM wp_crosswiki "
            "WHERE en_project = ? AND wiki = ?",
            (en_project, wiki)).fetchone()
        if row:
            return row['page_title']
        norm = normalize_wp_project_name(en_project)
        if not norm:
            return None
        row = conn.execute(
            "SELECT page_title FROM wp_crosswiki "
            "WHERE normalized_en = ? AND wiki = ? LIMIT 1",
            (norm, wiki)).fetchone()
        return row['page_title'] if row else None
    finally:
        conn.close()


def list_wp_crosswiki(en_project):
    """Return [(wiki, page_title, qid), ...] for every wiki that has a
    cross-wiki equivalent for the given enwiki WikiProject."""
    if not en_project:
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT wiki, page_title, qid FROM wp_crosswiki "
            "WHERE en_project = ? ORDER BY wiki", (en_project,)).fetchall()
        if rows:
            return [(r['wiki'], r['page_title'], r['qid']) for r in rows]
        norm = normalize_wp_project_name(en_project)
        if not norm:
            return []
        rows = conn.execute(
            "SELECT wiki, page_title, qid FROM wp_crosswiki "
            "WHERE normalized_en = ? ORDER BY wiki", (norm,)).fetchall()
        return [(r['wiki'], r['page_title'], r['qid']) for r in rows]
    finally:
        conn.close()


def search_wp_crosswiki(keyword, limit=50):
    """Search the cross-wiki index by normalized substring match on
    en_project. Returns [(en_project, [(wiki, page_title), ...]), ...]
    distinct en_projects, capped at `limit`."""
    if not keyword:
        return []
    norm_kw = normalize_wp_project_name(keyword)
    if not norm_kw:
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT en_project, wiki, page_title FROM wp_crosswiki "
            "WHERE normalized_en LIKE ? ORDER BY en_project, wiki",
            (f"%{norm_kw}%",)).fetchall()
        by_project = {}
        for r in rows:
            by_project.setdefault(r['en_project'], []).append(
                (r['wiki'], r['page_title']))
            if len(by_project) > limit and r['en_project'] not in by_project:
                break
        return [(p, sl) for p, sl in by_project.items()][:limit]
    finally:
        conn.close()


def get_topic_acl(topic_id):
    """Return (owner_username, visibility) for a topic. owner is None for
    legacy unclaimed topics. visibility is one of 'private', 'public_read',
    'public_edit'."""
    conn = _connect()
    row = conn.execute(
        "SELECT owner_username, visibility FROM topics WHERE id = ?",
        (topic_id,)).fetchone()
    conn.close()
    if not row:
        return None, 'private'
    return row['owner_username'], (row['visibility'] or 'private')


def set_topic_owner(topic_id, owner_username):
    """Assign / reassign a topic's owner. Used by start_topic on creation
    and by the (deferred) admin transfer_topic tool."""
    user = normalize_username(owner_username) if owner_username else None
    conn = _connect()
    conn.execute(
        "UPDATE topics SET owner_username = ?, updated_at = datetime('now') "
        "WHERE id = ?", (user, topic_id))
    conn.commit()
    conn.close()


def set_topic_visibility(topic_id, visibility):
    """Set a topic's visibility. Caller is expected to have verified
    permission (owner-only) at the tool layer."""
    if visibility not in ('private', 'public_read', 'public_edit'):
        raise ValueError(
            f"visibility must be 'private', 'public_read', or 'public_edit' "
            f"(got {visibility!r})")
    conn = _connect()
    conn.execute(
        "UPDATE topics SET visibility = ?, updated_at = datetime('now') "
        "WHERE id = ?", (visibility, topic_id))
    conn.commit()
    conn.close()


def topic_diff(topic_a_id, topic_b_id, sample_size=20):
    """Partition the union of two topics' titles into only_a / only_b /
    both. Returns counts + per-bucket samples. Read-only; doesn't
    mutate either topic. Topics must be on the same wiki for the diff
    to be meaningful — caller is responsible for checking that."""
    conn = _connect()
    a_titles = {r['title'] for r in conn.execute(
        "SELECT title FROM articles WHERE topic_id = ?",
        (topic_a_id,))}
    b_titles = {r['title'] for r in conn.execute(
        "SELECT title FROM articles WHERE topic_id = ?",
        (topic_b_id,))}
    conn.close()

    only_a = sorted(a_titles - b_titles)
    only_b = sorted(b_titles - a_titles)
    both = sorted(a_titles & b_titles)

    s = max(0, int(sample_size))
    return {
        "only_a": {"count": len(only_a), "samples": only_a[:s]},
        "only_b": {"count": len(only_b), "samples": only_b[:s]},
        "both":   {"count": len(both),   "samples": both[:s]},
    }


def topic_diff_by_source(topic_a_id, topic_b_id):
    """Per-source breakdown of which sources contribute to the only_a
    bucket (titles present in A but not in B). Useful for
    'why did this baseline-vs-current diff get 200 extra titles? which
    sources contributed them?' Returns
    {source_label: count_in_only_a}.
    """
    conn = _connect()
    a_rows = conn.execute(
        "SELECT title, sources FROM articles WHERE topic_id = ?",
        (topic_a_id,)).fetchall()
    b_titles = {r['title'] for r in conn.execute(
        "SELECT title FROM articles WHERE topic_id = ?",
        (topic_b_id,))}
    conn.close()

    counts: dict[str, int] = {}
    for row in a_rows:
        if row['title'] in b_titles:
            continue
        try:
            srcs = json.loads(row['sources'] or '[]')
        except Exception:
            srcs = []
        for s in srcs:
            counts[s] = counts.get(s, 0) + 1
    return counts


def list_topics_for(caller_username):
    """List topics visible to the given caller. Returns the same shape as
    list_topics() with extra owner / visibility / mine fields. If
    caller_username is None (anonymous), returns only public topics."""
    caller = normalize_username(caller_username) if caller_username else None
    conn = _connect()
    if caller:
        rows = conn.execute("""
            SELECT t.id, t.name, t.slug, t.wiki, t.created_at, t.updated_at,
                   t.owner_username, t.visibility,
                   COUNT(a.id) as article_count
            FROM topics t LEFT JOIN articles a ON t.id = a.topic_id
            WHERE t.owner_username = ?
               OR t.visibility != 'private'
            GROUP BY t.id ORDER BY t.updated_at DESC
        """, (caller,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT t.id, t.name, t.slug, t.wiki, t.created_at, t.updated_at,
                   t.owner_username, t.visibility,
                   COUNT(a.id) as article_count
            FROM topics t LEFT JOIN articles a ON t.id = a.topic_id
            WHERE t.visibility != 'private'
            GROUP BY t.id ORDER BY t.updated_at DESC
        """).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d['mine'] = bool(caller and d.get('owner_username') == caller)
        out.append(d)
    return out


# ── Impact Visualizer handoff: package + log helpers ───────────────────


def mint_iv_handle():
    """Mint a new handoff handle. Format: tbp_<22 url-safe chars>
    (~16 bytes entropy). Caller checks the rare PRIMARY KEY collision
    by retrying."""
    return "tbp_" + secrets.token_urlsafe(16)


def create_iv_package(handle, topic_id, config, articles, source_topic,
                      source_topic_id, publisher_user, ttl_days=30):
    """Insert a frozen IV package row. config and articles are
    JSON-serialized here so callers don't have to remember to dump.
    Returns expires_at (ISO string, in UTC SQLite-default form).

    source_topic_id is denormalized alongside source_topic so the
    package can outlive a deleted TB topic — IV uses it to recognize
    republishes of an already-imported topic."""
    conn = _connect()
    conn.execute(
        "INSERT INTO iv_packages "
        "(handle, topic_id, config_json, articles_json, source_topic, "
        " source_topic_id, publisher_user, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', ?))",
        (handle, topic_id,
         json.dumps(config, ensure_ascii=False),
         json.dumps(articles, ensure_ascii=False),
         source_topic,
         source_topic_id,
         publisher_user,
         f"+{int(ttl_days)} days"))
    expires_at = conn.execute(
        "SELECT expires_at FROM iv_packages WHERE handle = ?",
        (handle,)).fetchone()['expires_at']
    conn.commit()
    conn.close()
    return expires_at


def get_iv_package(handle):
    """Return the package as a dict with config + articles decoded, or
    None if missing. Does NOT filter by expiry — caller (the HTTP
    route) decides expiry behavior."""
    conn = _connect()
    row = conn.execute(
        "SELECT handle, topic_id, config_json, articles_json, source_topic, "
        "       source_topic_id, publisher_user, created_at, consumed_at, "
        "       expires_at, schema_version "
        "FROM iv_packages WHERE handle = ?", (handle,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        'handle': row['handle'],
        'topic_id': row['topic_id'],
        'config': json.loads(row['config_json']),
        'articles': json.loads(row['articles_json']),
        'source_topic': row['source_topic'],
        'source_topic_id': row['source_topic_id'],
        'publisher_user': row['publisher_user'],
        'created_at': row['created_at'],
        'consumed_at': row['consumed_at'],
        'expires_at': row['expires_at'],
        'schema_version': row['schema_version'],
    }


def mark_iv_package_consumed(handle):
    """Set consumed_at on first successful fetch. Returns True only on
    the first call (so the HTTP route's JSONL log line can record
    'consumed_first_time'). No-op + False on subsequent calls."""
    conn = _connect()
    cur = conn.execute(
        "UPDATE iv_packages SET consumed_at = datetime('now') "
        "WHERE handle = ? AND consumed_at IS NULL", (handle,))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def list_iv_packages_for_topic(topic_id):
    """List a topic's packages newest-first. For future debug surfaces."""
    conn = _connect()
    rows = conn.execute(
        "SELECT handle, source_topic, source_topic_id, publisher_user, "
        "       created_at, consumed_at, expires_at, schema_version "
        "FROM iv_packages WHERE topic_id = ? "
        "ORDER BY created_at DESC", (topic_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cleanup_expired_iv_packages(grace_days=7):
    """Delete rows whose expires_at + grace_days has passed. Returns
    count deleted. Grace period keeps debug forensics for a week past
    expiry."""
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM iv_packages "
        "WHERE datetime(expires_at, ?) < datetime('now')",
        (f"+{int(grace_days)} days",))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


def append_package_event(entry):
    """Append a publish/fetch event as JSON Lines to packages.jsonl.
    Mirrors append_feedback's shape."""
    log_dir = os.environ.get("LOG_DIR", "/opt/topic-builder/logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "packages.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Initialize on import
init_db()
