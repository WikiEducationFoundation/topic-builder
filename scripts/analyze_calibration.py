"""Post-hoc calibration analysis: join `submit_feedback` records with
gold-derived recall (where benchmarks exist) to validate the
band-derivation thresholds in `_calibration_band` (server.py).

For each feedback record that has both a `coverage_estimate.band` and
a topic name that maps to a benchmark slug, this script pulls the
run's current corpus from the host, computes recall against the
benchmark's gold.csv, and tabulates band vs actual recall. Use the
output to tune the band thresholds in server.py.

Runs LOCALLY. Reads benchmarks/<slug>/gold.csv from the local repo;
SSHes to the deployed server (via .env keys, same pattern as
benchmark_score.py) for feedback.jsonl + per-topic corpora.

Usage:
  python3 scripts/analyze_calibration.py
  python3 scripts/analyze_calibration.py --since 2026-04-25
  python3 scripts/analyze_calibration.py --slug apollo-11

Output:
  Markdown table to stdout: topic | band | ai_confidence |
  ai_override | actual_recall | residual_error.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from redirect_utils import resolve_redirects  # noqa: E402
import benchmark_score  # noqa: E402  — reuse load_env, ssh_cmd, fetch_run_state

REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")


def list_benchmark_slugs():
    """Return slugs that have a gold.csv on disk."""
    slugs = []
    if not os.path.isdir(BENCHMARKS_DIR):
        return slugs
    for entry in sorted(os.listdir(BENCHMARKS_DIR)):
        gold_path = os.path.join(BENCHMARKS_DIR, entry, "gold.csv")
        if os.path.exists(gold_path):
            slugs.append(entry)
    return slugs


def topic_to_slug(topic_name, slugs):
    """Heuristic: match a topic name to a benchmark slug by checking
    whether the slug appears as a prefix of the slugified topic name.
    Returns the slug or None."""
    norm = topic_name.lower().replace("_", "-").replace(" ", "-")
    candidates = [s for s in slugs if norm.startswith(s)]
    if not candidates:
        return None
    # Pick the longest match (so "hispanic-latino-stem-us" wins over
    # "hispanic-latino" if both existed).
    return max(candidates, key=len)


def read_gold(slug):
    """Load the IN set from benchmarks/<slug>/gold.csv. Returns
    a frozenset of titles classified `in` or `peripheral` (gold_in
    in the scoreboard's recall-denominator sense)."""
    gold_path = os.path.join(BENCHMARKS_DIR, slug, "gold.csv")
    if not os.path.exists(gold_path):
        return None
    in_set: set[str] = set()
    with open(gold_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            classification = (row.get("on_topic")
                              or row.get("classification")
                              or row.get("class")
                              or "").strip().lower()
            title = (row.get("title") or "").strip()
            if title and classification in ("in", "peripheral"):
                in_set.add(title)
    return frozenset(in_set)


def fetch_feedback(env):
    """Pull feedback.jsonl from the host and return parsed records."""
    rc, out, err = benchmark_score.ssh_cmd(
        env, "cat /opt/topic-builder/logs/feedback.jsonl 2>/dev/null || true")
    if rc != 0:
        raise RuntimeError(f"ssh failed fetching feedback log: {err}")
    records = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def compute_recall(env, topic_name, gold):
    """Pull the topic's current corpus and compute recall against gold."""
    state = benchmark_score.fetch_run_state(env, topic_name)
    if not state:
        return None
    corpus = state["corpus"]
    if not gold:
        return None
    intersection = corpus & gold
    return len(intersection) / len(gold) if gold else None


def expected_recall_for_band(band):
    """Loose mapping of band → expected recall range (used to surface
    residual error)."""
    return {
        "low": (0.0, 0.50),
        "moderate": (0.50, 0.75),
        "high": (0.75, 1.0),
    }.get(band, (None, None))


def residual_for_band(band, recall):
    """Signed distance from the band's expected range. Negative = the
    actual recall is below the band's expected floor (band is too
    optimistic). Positive = above the band's expected ceiling (band
    is too pessimistic). Zero means within the expected range."""
    if recall is None:
        return None
    lo, hi = expected_recall_for_band(band)
    if lo is None:
        return None
    if recall < lo:
        return round(recall - lo, 4)
    if recall > hi:
        return round(recall - hi, 4)
    return 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since",
                        help="Only consider feedback from this date "
                             "(YYYY-MM-DD). Default: all records.")
    parser.add_argument("--slug",
                        help="Filter to feedback whose topic maps to "
                             "this benchmark slug. Default: all matched.")
    args = parser.parse_args()

    env = benchmark_score.load_env()
    slugs = list_benchmark_slugs()
    if not slugs:
        print("No benchmarks found under benchmarks/. Nothing to score against.")
        return

    records = fetch_feedback(env)

    rows: list[dict] = []
    for rec in records:
        ce = rec.get("coverage_estimate") or {}
        band = ce.get("band")
        if not band:
            continue
        ts = rec.get("ts", "")
        if args.since and ts < args.since:
            continue
        topic = rec.get("topic", "")
        slug = topic_to_slug(topic, slugs)
        if not slug:
            continue
        if args.slug and slug != args.slug:
            continue
        gold = read_gold(slug)
        if not gold:
            continue
        recall = compute_recall(env, topic, gold)
        if recall is None:
            continue
        signals = ce.get("signals") or {}
        rows.append({
            "ts": ts[:10],
            "topic": topic,
            "slug": slug,
            "band": band,
            "ai_confidence": ce.get("confidence"),
            "ai_override": ce.get("ai_override"),
            "triangulation_pct": signals.get("triangulation_pct"),
            "attempted": signals.get("shape_strategies_attempted"),
            "applicable": signals.get("shape_strategies_applicable"),
            "actual_recall": round(recall, 4),
            "residual_error": residual_for_band(band, recall),
        })

    if not rows:
        print("No feedback records matched (no band-derived calibration "
              "or no benchmark mapping).")
        return

    # Sort by date desc
    rows.sort(key=lambda r: r["ts"], reverse=True)

    # Render markdown table
    cols = ["ts", "topic", "slug", "band", "ai_confidence", "ai_override",
            "triangulation_pct", "attempted/applicable", "actual_recall",
            "residual_error"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "|".join(["---"] * len(cols)) + "|")
    def _fmt(v, fmt):
        """Format a numeric field, gracefully handling string values
        (older feedback used 'low'/'medium'/'high' for confidence)."""
        if v is None:
            return "—"
        if isinstance(v, str):
            return v
        try:
            return format(v, fmt)
        except (TypeError, ValueError):
            return str(v)

    for r in rows:
        att_app = (f"{r['attempted']}/{r['applicable']}"
                   if r['applicable'] else "—")
        print("| " + " | ".join([
            r["ts"],
            r["topic"][:40],
            r["slug"],
            r["band"],
            _fmt(r["ai_confidence"], ".2f"),
            _fmt(r["ai_override"], ".2f"),
            _fmt(r["triangulation_pct"], ".2%"),
            att_app,
            f"{r['actual_recall']:.2%}",
            _fmt(r['residual_error'], "+.2f"),
        ]) + " |")

    # Per-band summary
    print()
    print("## Per-band summary")
    print()
    by_band: dict[str, list[float]] = {}
    for r in rows:
        by_band.setdefault(r["band"], []).append(r["actual_recall"])
    print("| band | n | mean recall | min | max | expected range |")
    print("|---|---|---|---|---|---|")
    for band in ("low", "moderate", "high"):
        vals = by_band.get(band, [])
        if not vals:
            continue
        lo, hi = expected_recall_for_band(band)
        rng = f"{lo:.0%}–{hi:.0%}" if lo is not None else "—"
        print(f"| {band} | {len(vals)} | "
              f"{sum(vals) / len(vals):.2%} | "
              f"{min(vals):.2%} | {max(vals):.2%} | {rng} |")


if __name__ == "__main__":
    main()
