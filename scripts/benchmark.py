#!/usr/bin/env python3
"""Run a Topic Builder benchmark: replay a scripted call sequence against a
disposable SQLite DB, diff the resulting working list against a gold set,
emit a markdown report.

Usage:
    python3 scripts/benchmark.py <topic-slug>
    python3 scripts/benchmark.py <topic-slug> --no-replay

Reads benchmarks/<topic-slug>/:
    scope.md       (not parsed; for humans)
    gold.csv       (authoritative: title, on_topic, ...)
    calls.jsonl    (one {"tool": ..., "args": ...} per line)

Design notes:
- The runner imports `mcp_server/server.py` directly and calls the tool
  functions in-process. It sets DB_PATH, EXPORT_DIR, and LOG_DIR to a
  temporary directory so the real production DB is untouched. Wikipedia's
  API is hit for real — that's the behaviour we're measuring.
- Tool calls in `calls.jsonl` must include an explicit `topic` argument
  (the functions are session-aware but we don't have an MCP session here).
- If `gold.csv` is empty or missing, the runner prints the calls-only
  summary and exits without scoring.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_ROOT = REPO_ROOT / "benchmarks"
SERVER_DIR = REPO_ROOT / "mcp_server"


def read_gold(path: Path):
    """Return (positives: set[str], negatives: set[str], all_rows: list[dict]).
    positives = titles with on_topic=true; negatives = on_topic=false."""
    if not path.exists():
        return set(), set(), []
    positives, negatives, rows = set(), set(), []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            on_topic = (row.get("on_topic") or "").strip().lower() in ("true", "t", "yes", "1")
            rows.append(row)
            (positives if on_topic else negatives).add(title)
    return positives, negatives, rows


def read_calls(path: Path):
    """Return a list of {tool, args} dicts from a JSONL file."""
    if not path.exists():
        return []
    calls = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                calls.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"warning: skipping bad JSONL line: {e}", file=sys.stderr)
    return calls


def setup_disposable_env(tmpdir: Path):
    """Point the server at a throwaway DB / exports / logs directory."""
    (tmpdir / "data").mkdir(exist_ok=True)
    (tmpdir / "exports").mkdir(exist_ok=True)
    (tmpdir / "logs").mkdir(exist_ok=True)
    os.environ["DB_PATH"] = str(tmpdir / "data" / "bench.db")
    os.environ["EXPORT_DIR"] = str(tmpdir / "exports")
    os.environ["LOG_DIR"] = str(tmpdir / "logs")


def load_server_module():
    """Import mcp_server/server.py in a way that resolves its intra-package imports."""
    sys.path.insert(0, str(SERVER_DIR))
    import server  # noqa: E402  (path set just above)
    return server


class _MockCtx:
    """Minimal ctx stand-in for in-process tool calls. Server tools access
    `ctx.session` as a handle to the per-session state dict; giving them a
    stable object (hashable by id) lets the session-topic tracking work."""
    class _Session:
        pass
    def __init__(self):
        self.session = self._Session()


def replay_calls(server_mod, calls):
    """Execute calls in order. Returns a list of {tool, args, error?} for logging.

    The runner keeps a single MockCtx for the whole replay — every call sees
    the same "session", so the server's _set_topic / _get_topic machinery
    works the way it would under a stateful client.

    Arguments in calls.jsonl are filtered against each tool's real signature,
    so callers can over-specify (e.g. include `topic` for a tool that doesn't
    accept it) without crashing the run."""
    import inspect
    ctx = _MockCtx()
    trace = []
    for i, call in enumerate(calls):
        tool_name = call.get("tool")
        args = call.get("args", {})
        fn = getattr(server_mod, tool_name, None)
        entry = {"i": i, "tool": tool_name, "args": args}
        if fn is None:
            entry["error"] = f"unknown tool: {tool_name}"
            trace.append(entry)
            continue
        # Filter args to ones the function actually accepts (so calls.jsonl
        # can over-specify without breaking replays against tool-signature
        # changes).
        try:
            sig = inspect.signature(fn)
            accepted = set(sig.parameters.keys())
            filtered = {k: v for k, v in args.items() if k in accepted}
        except (TypeError, ValueError):
            filtered = dict(args)
        try:
            fn(ctx=ctx, **filtered)
            entry["ok"] = True
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
        trace.append(entry)
    return trace


def load_working_list(server_mod, topic_slug: str):
    """Return the set of titles currently in the disposable DB's working list."""
    import db as db_mod  # db.py, available on sys.path via SERVER_DIR
    tid, _ = db_mod.get_topic_by_name(topic_slug)
    if tid is None:
        return set(), {}
    articles = db_mod.get_all_articles_dict(tid)
    return set(articles.keys()), articles


def score_against_gold(working: set, positives: set, negatives: set):
    """Precision / recall against gold. negatives is used only to compute
    how many working-list articles were validated-off-topic vs. unknown."""
    in_gold = working & (positives | negatives)
    on_topic_hits = working & positives
    off_topic_hits = working & negatives
    unknown = working - (positives | negatives)
    missed = positives - working

    precision_against_known = (
        len(on_topic_hits) / len(in_gold) if in_gold else None
    )
    recall = (
        len(on_topic_hits) / len(positives) if positives else None
    )
    return {
        "working_size": len(working),
        "gold_positives": len(positives),
        "gold_negatives": len(negatives),
        "on_topic_hits": len(on_topic_hits),
        "off_topic_hits_caught": len(off_topic_hits),
        "unknown_in_working": len(unknown),
        "missed_from_gold": len(missed),
        "precision_against_known": precision_against_known,
        "recall": recall,
    }


def fmt_pct(v):
    return "—" if v is None else f"{v:.1%}"


def emit_report(topic_slug: str, scope_path: Path, calls: list, trace: list,
                gold_positives: set, gold_negatives: set, metrics: dict,
                sample_missed: list, sample_unknown: list):
    lines = [
        f"# Benchmark report — `{topic_slug}`",
        "",
        f"- Scope: `{scope_path.relative_to(REPO_ROOT)}`",
        f"- Calls: {len(calls)} ({sum(1 for t in trace if 'error' in t)} errors)",
        f"- Gold positives: {len(gold_positives)}, gold negatives: {len(gold_negatives)}",
        "",
        "## Metrics",
        "",
        f"| | |",
        f"|---|---:|",
        f"| Working-list size | {metrics['working_size']} |",
        f"| Gold positives hit (recall) | {metrics['on_topic_hits']} / {metrics['gold_positives']} ({fmt_pct(metrics['recall'])}) |",
        f"| Gold negatives caught (noise in working list) | {metrics['off_topic_hits_caught']} |",
        f"| Unknown (not in gold at all) | {metrics['unknown_in_working']} |",
        f"| Gold positives missed | {metrics['missed_from_gold']} |",
        f"| Precision against known-gold | {fmt_pct(metrics['precision_against_known'])} |",
        "",
    ]
    if any("error" in t for t in trace):
        lines.append("## Call errors")
        lines.append("")
        for t in trace:
            if "error" in t:
                lines.append(f"- `{t['tool']}({t['args']!r})` — {t['error']}")
        lines.append("")
    if sample_missed:
        lines.append("## Sample missed gold positives (first 20)")
        lines.append("")
        for t in sample_missed[:20]:
            lines.append(f"- {t}")
        lines.append("")
    if sample_unknown:
        lines.append("## Sample unknown-in-working (not audited yet, first 20)")
        lines.append("")
        for t in sample_unknown[:20]:
            lines.append(f"- {t}")
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("topic_slug", help="subdirectory name under benchmarks/")
    p.add_argument("--no-replay", action="store_true",
                   help="skip calls.jsonl replay; just print gold stats")
    args = p.parse_args()

    bench_dir = BENCH_ROOT / args.topic_slug
    if not bench_dir.exists():
        print(f"no benchmark directory at {bench_dir}", file=sys.stderr)
        sys.exit(2)

    scope_path = bench_dir / "scope.md"
    gold_path = bench_dir / "gold.csv"
    calls_path = bench_dir / "calls.jsonl"

    positives, negatives, gold_rows = read_gold(gold_path)
    calls = [] if args.no_replay else read_calls(calls_path)

    if not calls and not positives:
        print(f"{args.topic_slug}: nothing to run (no gold, no calls).")
        print(f"  gold.csv: {'missing' if not gold_path.exists() else 'empty'}")
        print(f"  calls.jsonl: {'missing' if not calls_path.exists() else 'empty'}")
        return

    print(f"# {args.topic_slug}")
    print(f"scope.md: {'present' if scope_path.exists() else 'MISSING'}")
    print(f"gold.csv: {len(gold_rows)} rows  ({len(positives)} positives, {len(negatives)} negatives)")
    print(f"calls.jsonl: {len(calls)} calls")
    print()

    if not calls:
        print("No calls.jsonl to replay; showing gold summary only.")
        return

    with tempfile.TemporaryDirectory(prefix=f"bench-{args.topic_slug}-") as tmp:
        tmp = Path(tmp)
        setup_disposable_env(tmp)
        try:
            server_mod = load_server_module()
        except Exception as e:
            print(f"failed to import server module: {e}", file=sys.stderr)
            sys.exit(3)

        trace = replay_calls(server_mod, calls)
        working, _articles = load_working_list(server_mod, args.topic_slug)

    metrics = score_against_gold(working, positives, negatives)

    missed = sorted(positives - working)
    unknown = sorted(working - (positives | negatives))
    report = emit_report(
        args.topic_slug, scope_path, calls, trace,
        positives, negatives, metrics,
        sample_missed=missed, sample_unknown=unknown,
    )
    print(report)


if __name__ == "__main__":
    main()
