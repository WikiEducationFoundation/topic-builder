#!/usr/bin/env python3
"""Review a Topic Builder run end-to-end on the host.

Sibling of session_status.py — that one is the broad-overview tool,
this one is the focused-on-one-topic review tool. Use after a session
wraps to surface the AI's self-assessment, confabulation flags,
sharp-edge reports, and workflow gaps in a single screen of output.

Reads /opt/topic-builder/{data/topics.db, logs/usage.jsonl,
logs/feedback.jsonl, exports/}. Resolves topic by id or substring.

Ad-hoc invocation (no host deploy needed):

    bash scripts/smoke.sh scripts/review_run.py -- houseplants

After deploy.sh syncs to /opt/topic-builder/bin/review.py:

    ssh -i deploy_key root@$HOST \\
        "/opt/topic-builder/venv/bin/python /opt/topic-builder/bin/review.py houseplants"

Examples:
    review_run.py                       # list recent topics
    review_run.py 67                    # topic id 67
    review_run.py "houseplants"         # substring match
    review_run.py 67 --recent 80        # show 80 tool-call tail
    review_run.py 67 --full-feedback    # dump raw feedback JSON
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


# ── small utilities ─────────────────────────────────────────────────

def hr(title: str = "") -> str:
    line = "─" * 64
    return f"\n{line}\n {title}\n{line}" if title else line


def fmt_age(iso: str | None) -> str:
    if not iso:
        return "?"
    try:
        # SQLite "datetime('now')" produces "YYYY-MM-DD HH:MM:SS" UTC.
        dt = datetime.fromisoformat(iso.replace(" ", "T")).replace(
            tzinfo=timezone.utc) if "T" not in iso else \
            datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return iso
    delta = datetime.now(timezone.utc) - dt
    s = int(delta.total_seconds())
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60}m ago"
    return f"{s // 86400}d{(s % 86400) // 3600}h ago"


def truncate(s: str, n: int = 240) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[: n - 1] + "…"


# ── DB / log helpers ────────────────────────────────────────────────

def resolve_topic(conn: sqlite3.Connection, query: str | None):
    """Return (id, row) or (None, None). query may be int-like or substring."""
    if query is None:
        return None, None
    if query.isdigit():
        row = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (int(query),)).fetchone()
        return (row["id"], row) if row else (None, None)
    # Substring: prefer exact match, else most-recent matching.
    row = conn.execute(
        "SELECT * FROM topics WHERE LOWER(name) = LOWER(?)",
        (query,)).fetchone()
    if row:
        return row["id"], row
    rows = conn.execute(
        "SELECT * FROM topics WHERE LOWER(name) LIKE LOWER(?) "
        "ORDER BY id DESC LIMIT 5",
        (f"%{query}%",)).fetchall()
    if not rows:
        return None, None
    if len(rows) > 1:
        print(f"Multiple matches for {query!r}:")
        for r in rows:
            print(f"  {r['id']:4d}  {r['name']}")
        print("Re-run with the id you want.")
        sys.exit(2)
    return rows[0]["id"], rows[0]


def list_recent_topics(conn: sqlite3.Connection, limit: int = 15) -> None:
    print(hr("Recent topics"))
    rows = conn.execute(
        "SELECT t.id, t.name, t.wiki, t.owner_username, t.visibility, "
        "t.created_at, COUNT(a.title) AS n "
        "FROM topics t LEFT JOIN articles a ON a.topic_id = t.id "
        "GROUP BY t.id ORDER BY t.id DESC LIMIT ?", (limit,)).fetchall()
    for r in rows:
        owner = (r["owner_username"] or "—")[:18]
        print(f"  {r['id']:4d}  {r['name'][:40]:40s}  "
              f"{r['wiki']:>3s}  owner={owner:<18s}  "
              f"vis={r['visibility']:<12s}  n={r['n']:<5}  "
              f"created={fmt_age(r['created_at'])}")
    print()


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            try:
                yield json.loads(line)
            except Exception:
                continue


# ── render sections ─────────────────────────────────────────────────

def render_header(row) -> None:
    print(hr(f"TOPIC {row['id']}: {row['name']}"))
    age = fmt_age(row["created_at"])
    owner = row["owner_username"] or "(unowned)"
    print(f"  wiki={row['wiki']}  owner={owner!r}  "
          f"visibility={row['visibility']}  created={age}")


def render_rubric(row) -> None:
    rubric = row["centrality_rubric"] or ""
    if not rubric.strip():
        print("\n  RUBRIC: NOT SET  ⚠ (server_instructions says mandatory "
              "before any gather call)")
        return
    print(f"\n  RUBRIC: set ({len(rubric)} chars)")
    for line in rubric.strip().splitlines()[:8]:
        print(f"    │ {line}")
    n_extra = len(rubric.strip().splitlines()) - 8
    if n_extra > 0:
        print(f"    │ … ({n_extra} more line{'s' if n_extra > 1 else ''})")


def render_metadata(row) -> None:
    raw = row["metadata_json"] or "{}"
    try:
        meta = json.loads(raw)
    except Exception:
        meta = {}
    if not meta:
        return
    print("\n  METADATA:")
    for k, v in meta.items():
        if isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        print(f"    {k}: {v}")


def render_corpus_shape(conn: sqlite3.Connection, topic_id: int) -> None:
    n_total = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ?",
        (topic_id,)).fetchone()[0]
    n_scored = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? "
        "AND score IS NOT NULL", (topic_id,)).fetchone()[0]
    n_with_desc = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? "
        "AND description IS NOT NULL AND description != ''",
        (topic_id,)).fetchone()[0]
    n_no_desc = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? "
        "AND description = ''", (topic_id,)).fetchone()[0]
    n_unfetched = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE topic_id = ? "
        "AND description IS NULL", (topic_id,)).fetchone()[0]
    print(f"\n  CORPUS: {n_total} articles")
    print(f"    scored:           {n_scored}/{n_total}")
    print(f"    with description: {n_with_desc}")
    print(f"    fetched-but-empty:{n_no_desc}")
    print(f"    not yet fetched:  {n_unfetched}")


def render_sources(conn: sqlite3.Connection, topic_id: int,
                   top_n: int = 12) -> None:
    """Sources live as a JSON array per articles row; aggregate ourselves."""
    counts: Counter = Counter()
    for (sources_json,) in conn.execute(
            "SELECT sources FROM articles WHERE topic_id = ?", (topic_id,)):
        try:
            for s in json.loads(sources_json or "[]"):
                counts[s] += 1
        except (json.JSONDecodeError, TypeError):
            counts[str(sources_json)] += 1
    if not counts:
        return
    print(f"\n  SOURCES ({len(counts)} distinct):")
    for label, n in counts.most_common(top_n):
        print(f"    {n:5d}  {label}")
    if len(counts) > top_n:
        print(f"    … {len(counts) - top_n} more")


def collect_tool_calls(topic_name: str) -> list[dict]:
    return [e for e in iter_jsonl(USAGE_LOG)
            if e.get("topic") == topic_name]


def render_tool_counts(calls: list[dict]) -> None:
    if not calls:
        return
    counts = Counter(e.get("tool", "?") for e in calls)
    print(f"\n  TOOL CALLS BY FREQUENCY ({len(calls)} total):")
    for tool, n in counts.most_common():
        print(f"    {n:3d}  {tool}")


def infer_stage(calls: list[dict]) -> str:
    # Priority: if export_csv has fired, "exported";
    # if submit_feedback has fired, "feedback";
    # else last tool's stage from a coarse map.
    tools = [e.get("tool") for e in calls]
    if "export_csv" in tools:
        return "exported"
    if "submit_feedback" in tools:
        return "feedback (no export)"
    if not tools:
        return "no calls"
    last = tools[-1]
    return f"last tool: {last}"


def render_recent_calls(calls: list[dict], limit: int) -> None:
    tail = calls[-limit:]
    if not tail:
        return
    print(f"\n  RECENT TOOL CALLS (last {len(tail)} of {len(calls)}):")
    for e in tail:
        ts = (e.get("ts") or "")[:19].replace("T", " ")
        tool = e.get("tool", "?")
        params = e.get("params") or {}
        result = truncate(str(e.get("result") or ""), 100)
        # Compress params to a single line
        pkv = ", ".join(f"{k}={v}" for k, v in list(params.items())[:6])
        if len(params) > 6:
            pkv += ", …"
        print(f"    {ts}  {tool}({truncate(pkv, 110)}) -> {result}")


# ── feedback rendering ──────────────────────────────────────────────

def collect_feedback(topic_name: str) -> list[dict]:
    return [e for e in iter_jsonl(FEEDBACK_LOG)
            if e.get("topic") == topic_name]


def render_feedback(entries: list[dict], full: bool) -> None:
    if not entries:
        print("\n  FEEDBACK: none submitted")
        return
    if full:
        print(hr(f"FEEDBACK (raw, {len(entries)} entr"
                 f"{'y' if len(entries) == 1 else 'ies'})"))
        for e in entries:
            print(json.dumps(e, indent=2, ensure_ascii=False))
        return
    for e in entries:
        ts = (e.get("ts") or "")[:19].replace("T", " ")
        rating = e.get("rating", "?")
        runtime = e.get("runtime") or {}
        rt = (f"{runtime.get('agent','?')}"
              f"/{runtime.get('model','?')}"
              f"/{runtime.get('effort','?')}")
        print(hr(f"FEEDBACK  ts={ts}  rating={rating}/10  runtime={rt}"))

        cov = e.get("coverage_estimate") or {}
        if cov:
            band = cov.get("band") or "?"
            ovr = cov.get("ai_override")
            sigs = cov.get("signals") or {}
            print(f"\n  COVERAGE: band={band}"
                  f"{f' ai_override={ovr}' if ovr is not None else ''}")
            if cov.get("ai_override_rationale"):
                for line in str(cov["ai_override_rationale"]).split(". "):
                    if line.strip():
                        print(f"    rationale: {line.strip()}.")
            if cov.get("band_rationale"):
                print(f"    band-rationale: {cov['band_rationale']}")
            if sigs:
                tri = sigs.get("triangulation_pct")
                if tri is not None:
                    print(f"    signals: triangulation={tri:.1%}  "
                          f"strategies_attempted={sigs.get('shape_strategies_attempted')}  "
                          f"redirect_collapse={sigs.get('redirect_collapse_rate', 0):.1%}  "
                          f"yield_trajectory={sigs.get('yield_trajectory')}")

        for field in ("summary", "what_worked", "what_didnt",
                      "missed_strategies"):
            v = e.get(field)
            if v:
                print(f"\n  {field.upper()}:")
                for line in str(v).split(". "):
                    if line.strip():
                        print(f"    {line.strip()}{'.' if not line.endswith('.') else ''}")

        spot = e.get("spot_check") or {}
        if spot:
            print(f"\n  SPOT-CHECK: probes={spot.get('probes_count')}  "
                  f"hits={spot.get('hits')}  "
                  f"redirect-misses={spot.get('misses_redirect')}  "
                  f"hallucination-misses={spot.get('misses_hallucination')}  "
                  f"real-gap-misses={spot.get('misses_real_gap')}")

        for field, label in (("strategies_used", "STRATEGIES CLAIMED"),
                             ("sharp_edges_hit", "SHARP EDGES HIT"),
                             ("tool_friction", "TOOL FRICTION")):
            v = e.get(field) or []
            if v:
                print(f"\n  {label}: {', '.join(v) if isinstance(v, list) else v}")

        moves = ((e.get("strategy_execution") or {})
                 .get("moves_observed_from_log") or [])
        if moves:
            print(f"\n  MOVES OBSERVED FROM LOG ({len(moves)}):")
            for m in moves:
                print(f"    • {m}")

        flags = e.get("confabulation_flags") or []
        if flags:
            print(f"\n  ⚠ CONFABULATION FLAGS ({len(flags)}):")
            for fl in flags:
                print(f"    field={fl.get('field')}  "
                      f"claim={fl.get('claim')!r}")
                if fl.get("expected_evidence"):
                    print(f"      expected: {fl['expected_evidence']}")
                if fl.get("observed"):
                    print(f"      observed: {fl['observed']}")


# ── exports ─────────────────────────────────────────────────────────

def render_exports(topic_name: str) -> None:
    if not EXPORTS_DIR.exists():
        return
    matches = sorted(EXPORTS_DIR.glob("*.csv"))
    relevant = [p for p in matches
                if topic_name.lower().replace(" ", "_") in p.name.lower()
                or topic_name.lower().replace(" ", "-") in p.name.lower()]
    if not relevant:
        print("\n  EXPORTS: none on disk for this topic")
        return
    print(f"\n  EXPORTS ({len(relevant)}):")
    for p in relevant:
        size = p.stat().st_size
        print(f"    {p.name}  {size:>8,} bytes")


# ── main ────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("topic", nargs="?", default=None,
                    help="topic id or substring match. Omit to list recent.")
    ap.add_argument("--recent", type=int, default=30,
                    help="number of trailing tool calls to show (default 30)")
    ap.add_argument("--full-feedback", action="store_true",
                    help="dump raw feedback JSON instead of pretty-printing")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.topic is None:
        list_recent_topics(conn)
        return

    topic_id, row = resolve_topic(conn, args.topic)
    if topic_id is None:
        print(f"No topic matches {args.topic!r}", file=sys.stderr)
        sys.exit(1)

    render_header(row)
    render_rubric(row)
    render_metadata(row)
    render_corpus_shape(conn, topic_id)
    render_sources(conn, topic_id)

    calls = collect_tool_calls(row["name"])
    render_tool_counts(calls)
    print(f"\n  STAGE: {infer_stage(calls)}")
    render_recent_calls(calls, args.recent)

    feedback = collect_feedback(row["name"])
    render_feedback(feedback, args.full_feedback)

    render_exports(row["name"])
    print()


if __name__ == "__main__":
    main()
