"""Rebuild a benchmark's baseline.json from a completed run topic.

Lifts a thin-variant (or otherwise) run's metrics into `benchmarks/<slug>/
baseline.json`, archiving the old baseline. Uses the same fields the
original bootstrap_benchmark.py produces + the redirect-aware precision
/ recall computation from benchmark_score.py.

Usage:
    python3 scripts/update_baseline_from_run.py <slug> <run-topic-name> [--dry-run]
    python3 scripts/update_baseline_from_run.py --task <task-id> [--nth N] [--dry-run]

The old baseline.json is renamed to `baseline-archive-YYYYMMDD.json` so
history is preserved (local only — gold.csv + baseline files aren't
tracked in git for benchmark topics).
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from benchmark_score import (  # noqa: E402
    BENCHMARKS_DIR, fetch_run_state, load_env, load_gold, score,
    ssh_cmd, _resolve_task_mode,
)


def compute_server_side_stats(env, topic_name):
    """Get the bootstrap-style baseline fields (topic_id, timestamps,
    rate-limit hits, source-count stats, ai_self_rating) from the server."""
    remote_py = rf'''
import datetime as dt, json, sys
sys.path.insert(0, "/opt/topic-builder/app")
import db
USAGE_LOG = "/opt/topic-builder/logs/usage.jsonl"
FEEDBACK_LOG = "/opt/topic-builder/logs/feedback.jsonl"
topic_name = """{topic_name}"""
entries = []
with open(USAGE_LOG) as f:
    for line in f:
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("topic") == topic_name:
            entries.append(e)
fbs = []
try:
    with open(FEEDBACK_LOG) as f:
        for line in f:
            try:
                fb = json.loads(line)
            except Exception:
                continue
            if fb.get("topic") == topic_name:
                fbs.append(fb)
except FileNotFoundError:
    pass
if not entries:
    print(json.dumps({{"error": "no usage entries for topic"}}))
    sys.exit(0)
first_ts = entries[0]["ts"]
last_ts = entries[-1]["ts"]
t0 = dt.datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
t1 = dt.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
wall = round((t1 - t0).total_seconds())
total_rl = sum(e.get("rate_limit_hits_this_call") or 0 for e in entries)
rating = fbs[-1].get("rating") if fbs else None
feedback = fbs[-1] if fbs else {{}}
tid, _n, _w = db.get_topic_by_name(topic_name)
articles = db.get_all_articles_dict(tid) if tid else {{}}
single = multi = 0
for _t, a in articles.items():
    n = len(a.get("sources") or [])
    if n == 1:
        single += 1
    elif n >= 2:
        multi += 1
total = len(articles)
print(json.dumps({{
    "topic_id": tid,
    "first_tool_ts": first_ts,
    "last_tool_ts": last_ts,
    "wall_time_s": wall,
    "tool_call_count": len(entries),
    "total_rate_limit_hits": total_rl,
    "single_sourced": single,
    "single_sourced_pct": round(100.0 * single / total, 1) if total else 0.0,
    "multi_sourced": multi,
    "multi_sourced_pct": round(100.0 * multi / total, 1) if total else 0.0,
    "ai_self_rating": rating,
    "feedback_confidence": (feedback.get("coverage_estimate") or {{}}).get("confidence"),
    "feedback_variant_tag": feedback.get("note", ""),
}}))
'''
    rc, out, err = ssh_cmd(env, f"/opt/topic-builder/venv/bin/python -c '{remote_py}'")
    if rc != 0:
        raise RuntimeError(f"ssh failed computing server-side stats: {err}")
    info = json.loads(out.strip())
    if "error" in info:
        raise ValueError(f"server-side stats error: {info['error']}")
    return info


def build_baseline(slug, run_topic, source_variant):
    """Combine the scoreboard metrics (precision/recall/reach from
    benchmark_score.score) with the bootstrap-style server stats into a
    single baseline.json dict."""
    env = load_env()
    scoreboard = score(slug, run_topic)
    if "error" in scoreboard:
        raise ValueError(scoreboard["error"])

    server_stats = compute_server_side_stats(env, run_topic)
    gold = load_gold(slug)
    gold_in = sum(1 for c in gold.values() if c in ("in", "true"))
    gold_peripheral = sum(1 for c in gold.values() if c == "peripheral")
    gold_out = sum(1 for c in gold.values() if c in ("out", "false"))
    gold_redirect = sum(1 for c in gold.values() if c == "redirect")
    gold_redlink = sum(1 for c in gold.values() if c == "redlink")
    gold_pending = sum(1 for c in gold.values() if c == "pending_audit")
    gold_uncertain = sum(1 for c in gold.values() if c == "uncertain")

    return {
        "topic": run_topic,
        "topic_id": server_stats["topic_id"],
        "first_tool_ts": server_stats["first_tool_ts"],
        "last_tool_ts": server_stats["last_tool_ts"],
        "wall_time_s": server_stats["wall_time_s"],
        "tool_call_count": server_stats["tool_call_count"],
        "total_api_calls": scoreboard["total_api_calls"],
        "total_rate_limit_hits": server_stats["total_rate_limit_hits"],
        "final_article_count": scoreboard["run_corpus_size"],
        "single_sourced": server_stats["single_sourced"],
        "single_sourced_pct": server_stats["single_sourced_pct"],
        "multi_sourced": server_stats["multi_sourced"],
        "multi_sourced_pct": server_stats["multi_sourced_pct"],
        "ai_self_rating": server_stats["ai_self_rating"],
        "ai_coverage_confidence": server_stats["feedback_confidence"],
        "precision_vs_gold_v1": scoreboard["precision"],
        "recall_vs_gold_v1": scoreboard["recall"],
        "reach_beyond_prior_gold": scoreboard["reach_count"],
        "gold_in_count": gold_in,
        "gold_peripheral_count": gold_peripheral,
        "gold_out_count": gold_out,
        "gold_redirect_count": gold_redirect,
        "gold_redlink_count": gold_redlink,
        "gold_pending_audit_count": gold_pending,
        "gold_uncertain_count": gold_uncertain,
        "gold_size": gold_in + gold_peripheral,  # used in recall denominator
        "source_variant": source_variant,
        "baseline_note": (
            f"Baseline lifted from run {run_topic!r} (variant: "
            f"{source_variant}). Precision / recall computed against "
            f"the redirect-aware gold at the time of this rebuild. "
            f"See benchmarks/README.md for how ratchet runs compete."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("slug_or_positional1", nargs="?")
    p.add_argument("run_topic", nargs="?")
    p.add_argument("--task", metavar="TASK_ID")
    p.add_argument("--nth", type=int, default=0)
    p.add_argument("--variant", default="thin",
                   help="Tag stored in baseline's `source_variant` field. "
                        "Used for provenance. Default: thin.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.task:
        slug, run_topic = _resolve_task_mode(args.task, nth=args.nth)
    elif args.slug_or_positional1 and args.run_topic:
        slug = args.slug_or_positional1
        run_topic = args.run_topic
    else:
        p.error("must supply <slug> <run-topic-name> OR --task <task-id>")

    print(f"Building new baseline from run {run_topic!r} (slug={slug})...")
    baseline = build_baseline(slug, run_topic, args.variant)
    print(f"  corpus: {baseline['final_article_count']}")
    print(f"  precision: {baseline['precision_vs_gold_v1']:.4f}")
    print(f"  recall:    {baseline['recall_vs_gold_v1']:.4f}")
    print(f"  reach:     {baseline['reach_beyond_prior_gold']}")
    print(f"  cost:      wall={baseline['wall_time_s']}s, "
          f"api={baseline['total_api_calls']}, "
          f"tool={baseline['tool_call_count']}")

    baseline_path = os.path.join(BENCHMARKS_DIR, slug, "baseline.json")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    archive_path = os.path.join(
        BENCHMARKS_DIR, slug, f"baseline-archive-{stamp}.json")

    if args.dry_run:
        print("\n(dry-run: not writing)\n")
        print(json.dumps(baseline, indent=2))
        return

    if os.path.exists(baseline_path):
        # Don't clobber an existing archive from the same day.
        if os.path.exists(archive_path):
            archive_path = archive_path.replace(
                f"{stamp}.json",
                f"{stamp}-{dt.datetime.now().strftime('%H%M%S')}.json")
        os.rename(baseline_path, archive_path)
        print(f"  archived previous baseline → {archive_path}")

    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, default=str)
    print(f"  wrote new baseline → {baseline_path}")


if __name__ == "__main__":
    main()
