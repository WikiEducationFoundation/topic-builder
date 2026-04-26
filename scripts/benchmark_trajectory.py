"""Per-topic benchmark trajectory: every run on the deployed server,
phase-1 / phase-2 / full corpus partition, scored against current gold,
with per-phase cost (api_calls + tool_calls + wall time).

Phase-1 partition uses `articles.created_at` < first submit_feedback ts.
Caveat: phase-2 remove+re-add cycles update created_at, so phase-1
corpus is sometimes lost (shown as the AI-self-reported corpus_size
fallback when this happens).

SSH's into the deployed host once to fetch all run state + usage logs;
scores locally against benchmarks/<slug>/gold.csv. Reuses
benchmark_score's load_env / ssh_cmd helpers.

Usage:
  python3 scripts/benchmark_trajectory.py
  python3 scripts/benchmark_trajectory.py --slug apollo-11
  python3 scripts/benchmark_trajectory.py --slug climate-change orchids
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import benchmark_score  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")
SMOKE_SH = os.path.join(REPO_ROOT, "scripts", "smoke.sh")


def _norm_ts(ts):
    """Normalize a timestamp to 'YYYY-MM-DDTHH:MM:SS' for safe string
    comparison. SQLite created_at uses space-separator + no microseconds
    + no tz; feedback ts uses ISO with microseconds + tz suffix."""
    if not ts:
        return ""
    ts = ts.replace(" ", "T")
    if "." in ts:
        ts = ts.split(".", 1)[0]
    if "+" in ts:
        ts = ts.split("+", 1)[0]
    return ts[:19]


def list_benchmark_slugs():
    """Auto-discover benchmark slugs by scanning benchmarks/<slug>/gold.csv."""
    slugs = []
    for entry in sorted(os.listdir(BENCHMARKS_DIR)):
        path = os.path.join(BENCHMARKS_DIR, entry, "gold.csv")
        if os.path.isfile(path):
            slugs.append(entry)
    return slugs


def load_gold(slug):
    """Returns {'in': set, 'out': set, 'redirect': set, 'redlink': set}."""
    path = os.path.join(BENCHMARKS_DIR, slug, "gold.csv")
    if not os.path.exists(path):
        return None
    sets = {"in": set(), "out": set(), "redirect": set(), "redlink": set()}
    with open(path) as f:
        for row in csv.DictReader(f):
            cls = (row.get("on_topic") or "").strip().lower()
            t = (row.get("title") or "").strip()
            if not t:
                continue
            if cls in ("in", "peripheral"):
                sets["in"].add(t)
            elif cls in sets:
                sets[cls].add(t)
    return sets


def fetch_host_state(env, slugs):
    """One SSH call that returns a JSON manifest of every benchmark
    topic on the deployed server: (id, name, slug-match, created_at)
    + per-topic corpus titles + created_at, feedback entries (with
    phases + signals), and usage entries (ts, tool, api_calls)."""
    # Build pattern list — each slug becomes a name-prefix to match
    slug_prefixes = []
    for s in slugs:
        slug_prefixes.append(s)
        slug_prefixes.append(s.replace("-", "_"))
        slug_prefixes.append(s.replace("-", " "))

    # Host-side python: dump everything to stdout as JSON.
    remote_py = rf'''
import json, os, sys
sys.path.insert(0, "/opt/topic-builder/app")
import db
LOG_DIR = "/opt/topic-builder/logs"
prefixes = {json.dumps(slug_prefixes)}

# Find benchmark topics
conn = db._connect()
all_topics = conn.execute(
    "SELECT id, name, created_at FROM topics ORDER BY id"
).fetchall()
runs = []
for t in all_topics:
    nm = t["name"].lower()
    matched_slug = None
    for p in prefixes:
        if nm.startswith(p.lower()):
            # Map back to canonical slug form
            matched_slug = p.replace(" ", "-").replace("_", "-").lower()
            break
    if matched_slug:
        runs.append({{"topic_id": t["id"], "topic_name": t["name"],
                     "topic_slug_match": matched_slug,
                     "created_at": t["created_at"]}})

# For each run: corpus + feedback + matching usage entries
for r in runs:
    tid = r["topic_id"]
    arts = conn.execute(
        "SELECT title, created_at FROM articles WHERE topic_id=?",
        (tid,)
    ).fetchall()
    r["articles"] = [{{"title": a["title"], "created_at": a["created_at"]}}
                     for a in arts]

# Feedback entries (only ones matching benchmark topic names)
benchmark_names = {{r["topic_name"] for r in runs}}
feedback_path = os.path.join(LOG_DIR, "feedback.jsonl")
feedback_by_topic = {{}}
if os.path.exists(feedback_path):
    with open(feedback_path) as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            tn = e.get("topic")
            if tn in benchmark_names:
                feedback_by_topic.setdefault(tn, []).append({{
                    "ts": e.get("ts"),
                    "phase": e.get("phase", 1),
                    "rating": e.get("rating"),
                    "coverage_estimate": e.get("coverage_estimate"),
                }})

# Usage entries: log_usage records `topic` (name), not `topic_id`.
usage_path = os.path.join(LOG_DIR, "usage.jsonl")
usage_by_topic = {{}}
if os.path.exists(usage_path):
    with open(usage_path) as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            tn = e.get("topic")
            if tn in benchmark_names:
                usage_by_topic.setdefault(tn, []).append({{
                    "ts": e.get("ts"),
                    "tool": e.get("tool"),
                    "api_calls": e.get("wikipedia_api_calls") or 0,
                    "elapsed_ms": e.get("elapsed_ms") or 0,
                }})

print(json.dumps({{
    "runs": runs,
    "feedback_by_topic": feedback_by_topic,
    "usage_by_topic": usage_by_topic,
}}))
'''
    # Use smoke.sh wrapper to scp + run on host. Avoids ssh shell-quoting.
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     prefix="bench_traj_") as f:
        f.write(remote_py)
        script_path = f.name
    try:
        p = subprocess.run([SMOKE_SH, script_path],
                           capture_output=True, text=True, check=False)
        if p.returncode != 0:
            raise RuntimeError(f"smoke.sh failed: {p.stderr}")
        # smoke.sh forwards stderr too — strip any leading log noise.
        # Find the JSON line (starts with '{' and parses cleanly).
        for line in p.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(
            f"no JSON output from host. stdout: {p.stdout[:500]}")
    finally:
        os.unlink(script_path)


def partition_corpus(articles, phase1_end_ts):
    """Returns (phase1_titles, full_titles).
    phase1 = articles whose created_at < phase1_end_ts (normalized);
    full = all articles."""
    full = {a["title"] for a in articles if a["title"]}
    if not phase1_end_ts:
        return set(), full
    cut = _norm_ts(phase1_end_ts)
    phase1 = {a["title"] for a in articles
              if a["title"] and _norm_ts(a["created_at"]) < cut}
    return phase1, full


def partition_usage(usage_entries, phase1_end_ts, phase2_end_ts=None):
    """Returns dict with phase1 / phase2 / full keys, each
    {api_calls, tool_calls, wall_s}."""
    def bucket(entries):
        if not entries:
            return {"api_calls": 0, "tool_calls": 0, "wall_s": 0}
        api = sum(e.get("api_calls") or 0 for e in entries)
        tools = len(entries)
        # Wall = ts of last - ts of first
        ts_list = sorted(_norm_ts(e["ts"]) for e in entries if e.get("ts"))
        wall = 0
        if len(ts_list) >= 2:
            from datetime import datetime
            try:
                a = datetime.fromisoformat(ts_list[0])
                b = datetime.fromisoformat(ts_list[-1])
                wall = round((b - a).total_seconds())
            except ValueError:
                wall = 0
        return {"api_calls": api, "tool_calls": tools, "wall_s": wall}

    p1_cut = _norm_ts(phase1_end_ts) if phase1_end_ts else None
    p2_cut = _norm_ts(phase2_end_ts) if phase2_end_ts else None

    p1 = []
    p2 = []
    for e in usage_entries:
        ts = _norm_ts(e.get("ts"))
        if p1_cut is None:
            p1.append(e)
        elif ts < p1_cut:
            p1.append(e)
        elif p2_cut is None or ts < p2_cut:
            p2.append(e)
        # else: post-phase-2 (rescores etc.); skip

    return {
        "phase1": bucket(p1),
        "phase2": bucket(p2),
        "full": bucket(usage_entries),
    }


def score(corpus, gold):
    if not corpus or gold is None:
        return None, None, 0, 0
    hit_in = corpus & gold["in"]
    hit_out = corpus & gold["out"]
    audited = len(hit_in) + len(hit_out)
    prec = (len(hit_in) / audited) if audited else None
    rec = (len(hit_in) / len(gold["in"])) if gold["in"] else None
    return prec, rec, len(hit_in), len(hit_out)


def fmt_pct(v):
    return f"{v*100:.1f}%" if v is not None else "—"


def fmt_int(v):
    return f"{v:,}" if v else ("0" if v == 0 else "—")


def render_per_slug(slug, gold, runs, host_state):
    if not runs:
        print(f"\n## {slug}\n\n*No runs on server matching this slug.*")
        return
    if gold is None:
        print(f"\n## {slug}\n\n*No gold.csv for this slug.*")
        return

    print(f"\n## {slug} (gold: {len(gold['in'])} in, {len(gold['out'])} out)\n")
    print("| date | run | phase | corpus | precision | recall | api | tools | wall (s) |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|")

    for r in runs:
        tid = r["topic_id"]
        name = r["topic_name"]
        articles = r.get("articles", [])
        ts_short = (r.get("created_at", "") or "")[:16]
        fb = sorted(host_state["feedback_by_topic"].get(name, []),
                    key=lambda x: x.get("ts", ""))
        fb_p1 = next((f for f in fb if f["phase"] == 1), None)
        fb_p2 = next((f for f in fb if f["phase"] == 2), None)
        fb_legacy = next((f for f in fb if f["phase"] not in (1, 2)), None)

        phase1_end = (fb_p1 or fb_legacy or {}).get("ts")
        phase2_end = (fb_p2 or {}).get("ts")

        p1, full = partition_corpus(articles, phase1_end)
        usage = host_state["usage_by_topic"].get(name, [])
        cost = partition_usage(usage, phase1_end, phase2_end)

        is_two_phase = bool(fb_p1 and fb_p2)
        # Print phase-1 row only for two-phase runs (or two-phase reconstruction
        # via db lost). For single-phase runs, post-feedback corpus drift is
        # not interesting enough to surface.
        if is_two_phase:
            if p1 and len(p1) < len(full):
                p1p, p1r, _, _ = score(p1, gold)
                c = cost["phase1"]
                print(f"| {ts_short} | {name} | phase 1 | {len(p1)} | "
                      f"{fmt_pct(p1p)} | {fmt_pct(p1r)} | "
                      f"{c['api_calls']} | {c['tool_calls']} | {c['wall_s']} |")
            else:
                # Phase-1 corpus lost (remove+re-add cycle); AI-est size fallback
                ai_size = ((fb_p1.get("coverage_estimate") or {}).get("signals") or {}).get("corpus_size")
                c = cost["phase1"]
                size_str = f"~{ai_size}" if ai_size else "—"
                print(f"| {ts_short} | {name} | phase 1 (db lost) | {size_str} | "
                      f"— | — | {c['api_calls']} | {c['tool_calls']} | {c['wall_s']} |")

        # Phase-2 / full row
        if is_two_phase:
            phase_label = "phase 2"
            c = cost["phase2"]
        elif fb_legacy or fb_p1:
            phase_label = "single-phase"
            c = cost["full"]
        else:
            phase_label = "no feedback"
            c = cost["full"]

        if full:
            fp, fr, _, _ = score(full, gold)
            print(f"| {ts_short} | {name} | {phase_label} | {len(full)} | "
                  f"{fmt_pct(fp)} | {fmt_pct(fr)} | "
                  f"{c['api_calls']} | {c['tool_calls']} | {c['wall_s']} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", nargs="*",
                        help="Subset of benchmark slugs to report on. "
                             "Defaults to all benchmarks.")
    args = parser.parse_args()

    env = benchmark_score.load_env()
    all_slugs = list_benchmark_slugs()
    target_slugs = args.slug if args.slug else all_slugs
    target_slugs = [s for s in target_slugs if s in all_slugs]
    if not target_slugs:
        print("No matching benchmark slugs.", file=sys.stderr)
        sys.exit(2)

    print(f"Fetching host state for {len(target_slugs)} benchmarks...",
          file=sys.stderr)
    host_state = fetch_host_state(env, target_slugs)
    runs_by_slug = {}
    for r in host_state["runs"]:
        runs_by_slug.setdefault(r["topic_slug_match"], []).append(r)

    print(f"# Benchmark trajectory")
    for slug in target_slugs:
        gold = load_gold(slug)
        runs = sorted(runs_by_slug.get(slug, []),
                      key=lambda r: r.get("created_at", ""))
        render_per_slug(slug, gold, runs, host_state)


if __name__ == "__main__":
    main()
