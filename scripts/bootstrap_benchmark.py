"""Bootstrap baseline.json + gold.csv for a benchmark topic.

Runs on the server (via `scripts/smoke.sh`). Given a topic name, reads
the usage log + feedback log + DB and emits:

  /tmp/benchmark-<slug>/baseline.json
  /tmp/benchmark-<slug>/gold.csv

`gold.csv` has `on_topic=pending_audit` on every row — the per-benchmark
audit script classifies afterwards.

Usage (on the server):
  /opt/topic-builder/venv/bin/python /tmp/bootstrap_benchmark.py "<Topic Name>"
"""
import csv
import json
import os
import sys
sys.path.insert(0, '/opt/topic-builder/app')

import db

USAGE_LOG = "/opt/topic-builder/logs/usage.jsonl"
FEEDBACK_LOG = "/opt/topic-builder/logs/feedback.jsonl"


def slugify(name: str) -> str:
    return name.lower().replace(' ', '_').replace("'", '').replace('"', '').replace('(', '').replace(')', '')


def load_entries(topic_name):
    entries = []
    with open(USAGE_LOG) as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("topic") == topic_name:
                entries.append(e)
    return entries


def load_feedbacks(topic_name):
    fbs = []
    with open(FEEDBACK_LOG) as f:
        for line in f:
            try:
                fb = json.loads(line)
            except json.JSONDecodeError:
                continue
            if fb.get("topic") == topic_name:
                fbs.append(fb)
    return fbs


def compute_baseline(topic_name):
    import datetime as dt
    entries = load_entries(topic_name)
    if not entries:
        return None
    first_ts = entries[0]["ts"]
    last_ts = entries[-1]["ts"]
    t0 = dt.datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
    t1 = dt.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
    wall_time_s = round((t1 - t0).total_seconds())

    total_api_calls = sum(e.get("wikipedia_api_calls") or 0 for e in entries)
    total_rate_limit_hits = sum(e.get("rate_limit_hits_this_call") or 0 for e in entries)

    fbs = load_feedbacks(topic_name)
    rating = fbs[-1].get("rating") if fbs else None

    tid, _n, _w = db.get_topic_by_name(topic_name)
    articles = db.get_all_articles_dict(tid) if tid else {}
    single = multi = 0
    for _t, a in articles.items():
        n = len(a.get("sources") or [])
        if n == 1:
            single += 1
        elif n >= 2:
            multi += 1
    total = len(articles)
    return {
        "topic": topic_name,
        "topic_id": tid,
        "first_tool_ts": first_ts,
        "last_tool_ts": last_ts,
        "wall_time_s": wall_time_s,
        "tool_call_count": len(entries),
        "total_api_calls": total_api_calls,
        "total_rate_limit_hits": total_rate_limit_hits,
        "final_article_count": total,
        "single_sourced": single,
        "single_sourced_pct": round(100.0 * single / total, 1) if total else 0.0,
        "multi_sourced": multi,
        "multi_sourced_pct": round(100.0 * multi / total, 1) if total else 0.0,
        "ai_self_rating": rating,
        "precision_vs_gold_v1": 1.0,
        "recall_vs_gold_v1": 1.0,
        "reach_beyond_prior_gold": 0,
        "baseline_note": (
            "First baseline. Gold starts == current corpus; the benchmark's "
            "per-topic audit script classifies each row as in/peripheral/out. "
            "Precision becomes meaningful after audit; reach becomes non-zero "
            "when a later run finds on-topic additions beyond gold."
        ),
    }


def dump_gold_csv(topic_name, out_path):
    tid, _n, _w = db.get_topic_by_name(topic_name)
    articles = db.get_all_articles_dict(tid) if tid else {}
    rows = sorted(articles.items())
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "on_topic", "sources", "score", "description", "notes"])
        for title, a in rows:
            w.writerow([
                title,
                "pending_audit",
                "|".join(a.get("sources") or []),
                a.get("score") or "",
                (a.get("description") or "").replace("\n", " ")[:300],
                "",
            ])
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: bootstrap_benchmark.py <topic name>", file=sys.stderr)
        sys.exit(2)
    topic = sys.argv[1]
    slug = slugify(topic)
    out_dir = f"/tmp/benchmark-{slug}"
    os.makedirs(out_dir, exist_ok=True)

    baseline = compute_baseline(topic)
    if baseline is None:
        print(f"No usage entries found for topic {topic!r}", file=sys.stderr)
        sys.exit(1)

    with open(os.path.join(out_dir, "baseline.json"), "w") as f:
        json.dump(baseline, f, indent=2, default=str)
    n = dump_gold_csv(topic, os.path.join(out_dir, "gold.csv"))
    print(f"Topic {topic!r}")
    print(f"  slug: {slug}")
    print(f"  tool_call_count: {baseline['tool_call_count']}")
    print(f"  total_api_calls: {baseline['total_api_calls']}")
    print(f"  wall_time_s: {baseline['wall_time_s']}")
    print(f"  ai_self_rating: {baseline['ai_self_rating']}")
    print(f"  final_article_count: {baseline['final_article_count']}")
    print(f"  multi_sourced_pct: {baseline['multi_sourced_pct']}")
    print(f"Wrote {out_dir}/baseline.json, {out_dir}/gold.csv ({n} rows)")
