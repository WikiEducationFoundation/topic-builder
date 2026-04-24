"""Score a fresh Topic Builder run against a frozen benchmark.

Runs LOCALLY. SSHes to the deployed server to pull the run topic's
current corpus (via scripts/bootstrap_benchmark.py on the host) and
usage-log entries. Reads gold.csv + baseline.json from the local
benchmarks/<slug>/ directory.

Emits a scoreboard markdown report:

  - precision (run-corpus ∩ gold / run-corpus)
  - recall    (run-corpus ∩ gold / gold)
  - reach     (articles in run-corpus but not in gold — audit target)
  - Δ tool_call_count, Δ total_api_calls (gate cost metrics), and
    Δ wall_time_s (informational only — see caveat below)
  - pass/fail gate per the ratchet rules:
      precision AND recall don't regress, AND
      at least one of {tool_call_count, total_api_calls} improves

Wall-time caveat: wall_time_s is NOT in the gate. Operator-approval
flows (Codex prompts for permission on first use of each tool; Claude
Code does similar) inflate wall-time without reflecting tool efficiency.
We still report wall_time for visibility but don't let it satisfy the
cost improvement requirement.

API-calls caveat: if a baseline records 0 total_api_calls, that axis
is treated as UNRECORDED and skipped from the gate. Baselines computed
before the Stage 1.1 logging backfill have api_calls=0 as missing
data; if we included them in the gate, every run would artificially
"regress" on a metric the baseline never measured. The scoreboard's
Cost table labels that axis "no (baseline unrecorded)" so you can
see why it dropped out.

Usage:
  python3 scripts/benchmark_score.py <benchmark-slug> <run-topic-name>

Example:
  python3 scripts/benchmark_score.py apollo-11 "apollo-11-ratchet-2026-04-25"

The benchmark-slug refers to a subdirectory under benchmarks/. The
run-topic-name is an existing topic on the deployed server (a fresh
build under a distinct topic name keeps the historical baseline run
intact for comparison).
"""
import csv
import datetime as dt
import json
import os
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from redirect_utils import resolve_redirects  # noqa: E402
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")
DEPLOY_KEY = os.path.join(REPO_ROOT, "deploy_key")


def load_env():
    """Read DEPLOY_HOST / DEPLOY_USER from .env (matches monitor_dogfood.sh)."""
    env = {}
    env_path = os.path.join(REPO_ROOT, ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def ssh_cmd(env, remote_cmd):
    """Run a command on the deployed server. Returns (rc, stdout, stderr)."""
    host = f"{env.get('DEPLOY_USER', 'root')}@{env['DEPLOY_HOST']}"
    cmd = [
        "ssh", "-i", DEPLOY_KEY,
        "-o", "StrictHostKeyChecking=no",
        "-o", "LogLevel=ERROR",
        host, remote_cmd,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout, p.stderr


def fetch_run_state(env, topic_name):
    """Pull the run topic's corpus + usage-log metrics from the server."""
    # Corpus titles via SQLite query over the DB
    remote_py = rf'''
import json, sys
sys.path.insert(0, "/opt/topic-builder/app")
import db
tid, name, wiki = db.get_topic_by_name("""{topic_name}""")
if not tid:
    print(json.dumps({{"error": "topic not found"}}))
    sys.exit(0)
articles = db.get_all_articles_dict(tid)
print(json.dumps({{
    "topic_id": tid, "canonical_name": name, "wiki": wiki,
    "titles": sorted(articles.keys()),
}}))
'''
    rc, out, err = ssh_cmd(env, f"/opt/topic-builder/venv/bin/python -c '{remote_py}'")
    if rc != 0:
        raise RuntimeError(f"ssh failed fetching corpus: {err}")
    corpus_info = json.loads(out.strip())
    if "error" in corpus_info:
        return None

    # Usage-log entries for the topic
    rc, log_out, err = ssh_cmd(
        env,
        f'grep -a \'"topic": "{topic_name}"\' /opt/topic-builder/logs/usage.jsonl || true',
    )
    entries = []
    for line in log_out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Compute cost metrics
    if entries:
        t0 = dt.datetime.fromisoformat(entries[0]["ts"].replace("Z", "+00:00"))
        t1 = dt.datetime.fromisoformat(entries[-1]["ts"].replace("Z", "+00:00"))
        wall_time_s = round((t1 - t0).total_seconds())
        total_api_calls = sum(e.get("wikipedia_api_calls") or 0 for e in entries)
        tool_call_count = len(entries)
    else:
        wall_time_s = 0
        total_api_calls = 0
        tool_call_count = 0

    return {
        "topic": corpus_info["canonical_name"],
        "wiki": corpus_info["wiki"],
        "corpus": set(corpus_info["titles"]),
        "corpus_size": len(corpus_info["titles"]),
        "wall_time_s": wall_time_s,
        "total_api_calls": total_api_calls,
        "tool_call_count": tool_call_count,
    }


def load_gold(slug):
    path = os.path.join(BENCHMARKS_DIR, slug, "gold.csv")
    gold = {}
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            gold[row["title"]] = row["on_topic"]
    return gold


def load_baseline(slug):
    path = os.path.join(BENCHMARKS_DIR, slug, "baseline.json")
    with open(path) as f:
        return json.load(f)


def score(slug, run_topic_name):
    env = load_env()
    run = fetch_run_state(env, run_topic_name)
    if run is None:
        return {"error": f"Topic {run_topic_name!r} not found on the server"}

    gold = load_gold(slug)
    baseline = load_baseline(slug)

    gold_in = {t for t, c in gold.items() if c in ("in", "peripheral", "true")}
    gold_out = {t for t, c in gold.items() if c in ("out", "false")}
    gold_uncertain = {t for t, c in gold.items() if c == "uncertain"}
    unaudited = {t for t, c in gold.items() if c == "pending_audit"}
    # 'redirect' rows are provenance markers (title is a Wikipedia redirect
    # source pointing at a canonical row in the same gold). 'redlink' rows
    # flag titles that have no Wikipedia article. Both are excluded from
    # scoring denominators — they represent "known, not countable."
    gold_redirect = {t for t, c in gold.items() if c == "redirect"}
    gold_redlink = {t for t, c in gold.items() if c == "redlink"}

    # Normalize live corpus titles to their canonical Wikipedia form
    # before comparing to gold. The AI-assembled corpus can contain
    # redirect-source titles (e.g., "CRISPR-Cas" that redirects to
    # "CRISPR"); without normalization, scoring treats them as distinct
    # from their gold counterparts even when gold has been reconciled.
    # Cost: one batched API call per 50 corpus titles, rate-limited.
    raw_corpus = run["corpus"]
    wiki = run.get("wiki", "en") or "en"
    print(f"Normalizing {len(raw_corpus)} corpus titles via redirect "
          f"resolution...", file=sys.stderr)
    title_map = resolve_redirects(sorted(raw_corpus), wiki=wiki)
    corpus = set()
    corpus_normalized_count = 0
    corpus_missing_count = 0
    for t in raw_corpus:
        canonical = title_map.get(t, t)
        if canonical is None:
            # Title doesn't exist on Wikipedia anymore. Count it as the
            # original title for visibility (it's in the corpus but a
            # dead link); it won't hit gold.
            corpus.add(t)
            corpus_missing_count += 1
            continue
        corpus.add(canonical)
        if canonical != t:
            corpus_normalized_count += 1
    print(f"  {corpus_normalized_count} corpus titles normalized to canonical, "
          f"{corpus_missing_count} missing on Wikipedia.", file=sys.stderr)

    hit_gold = corpus & gold_in
    hit_out = corpus & gold_out
    reach = corpus - set(gold.keys())
    missed_gold = gold_in - corpus

    # Precision computed against the AUDITED subset of corpus (those
    # classified as gold_in or gold_out). For benchmarks where gold
    # covers every corpus article (apollo-11, crispr, aa-stem, orchids)
    # this equals full-corpus precision. For partial-audit cases like
    # hispanic-latino-stem-us, it matches baseline methodology:
    #   precision = hit_gold / (hit_gold + hit_out)
    audited_in_corpus = len(hit_gold) + len(hit_out)
    precision = (len(hit_gold) / audited_in_corpus) if audited_in_corpus else 0.0
    recall = len(hit_gold) / len(gold_in) if gold_in else 1.0

    def delta(field):
        b = baseline.get(field)
        if b is None:
            return run[field], None
        return run[field], run[field] - b

    wall_r, wall_d = delta("wall_time_s")
    api_r, api_d = delta("total_api_calls")
    tool_r, tool_d = delta("tool_call_count")
    corpus_b = baseline.get("final_article_count")
    corpus_d = run["corpus_size"] - corpus_b if corpus_b is not None else None

    baseline_prec = baseline.get("precision_vs_gold_v1", 1.0)
    baseline_rec = baseline.get("recall_vs_gold_v1", 1.0)
    # 0.001 tolerance (0.1 percentage point) absorbs baseline-JSON
    # rounding + small integer-counting noise (e.g. 1 article difference
    # shifting precision by ~0.0014 on a 700-article corpus).
    tol = 1e-3
    prec_ok = precision >= baseline_prec - tol
    recall_ok = recall >= baseline_rec - tol
    # Gate: wall_time_s is EXCLUDED — operator-approval flows (Codex
    # first-tool-use prompts, etc.) inflate wall-time without reflecting
    # tool efficiency. api_calls + tool_calls are the honest signals.
    #
    # If a baseline records 0 total_api_calls, treat that axis as
    # UNRECORDED (missing data from pre-logging-backfill runs) and skip
    # it — otherwise every ratchet run appears to "regress" on a metric
    # the baseline never actually measured.
    baseline_api_calls = baseline.get("total_api_calls", 0) or 0
    api_axis_usable = baseline_api_calls > 0
    cost_candidates = []
    if api_axis_usable:
        cost_candidates.append(api_d)
    cost_candidates.append(tool_d)
    cost_ok = any(d is not None and d < 0 for d in cost_candidates)
    gate_pass = prec_ok and recall_ok and cost_ok

    return {
        "benchmark": slug,
        "run_topic": run["topic"],
        "run_wiki": run["wiki"],
        "run_corpus_size": run["corpus_size"],
        "baseline_corpus_size": corpus_b,
        "corpus_delta": corpus_d,
        "gold_size": len(gold_in),
        "gold_out_count": len(gold_out),
        "gold_uncertain_count": len(gold_uncertain),
        "gold_unaudited_count": len(unaudited),
        "gold_redirect_count": len(gold_redirect),
        "gold_redlink_count": len(gold_redlink),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "baseline_precision": baseline_prec,
        "baseline_recall": baseline_rec,
        "hit_gold_count": len(hit_gold),
        "hit_out_count": len(hit_out),
        "reach_count": len(reach),
        "missed_gold_count": len(missed_gold),
        "wall_time_s": wall_r,
        "wall_time_delta": wall_d,
        "total_api_calls": api_r,
        "total_api_calls_delta": api_d,
        "api_axis_in_gate": api_axis_usable,
        "tool_call_count": tool_r,
        "tool_call_count_delta": tool_d,
        "precision_ok": prec_ok,
        "recall_ok": recall_ok,
        "any_cost_improved": cost_ok,
        "gate_pass": gate_pass,
        "reach_sample": sorted(reach)[:20],
        "missed_gold_sample": sorted(missed_gold)[:20],
        "hit_out_sample": sorted(hit_out)[:20],
    }


def fmt_delta(d, cost_direction="lower"):
    if d is None:
        return "—"
    if d == 0:
        return "±0"
    arrow = "↓" if d < 0 else "↑"
    label = ("improved" if (cost_direction == "lower" and d < 0)
             else "worse" if cost_direction == "lower" else "")
    return f"{arrow}{abs(d)}" + (f" ({label})" if label else "")


def format_scoreboard(s):
    if "error" in s:
        return f"ERROR: {s['error']}\n"
    L = []
    L.append(f"# Benchmark scoreboard: {s['benchmark']}")
    L.append("")
    L.append(f"Run topic: **{s['run_topic']!r}** on {s['run_wiki']}.wikipedia.org")
    L.append("")
    L.append("## Gate verdict")
    L.append("")
    L.append(
        f"**{'✅ PASS' if s['gate_pass'] else '❌ FAIL'}** — "
        f"precision {'OK' if s['precision_ok'] else 'REGRESSED'}, "
        f"recall {'OK' if s['recall_ok'] else 'REGRESSED'}, "
        f"cost metrics {'improved' if s['any_cost_improved'] else 'did not improve'}."
    )
    L.append("")
    L.append("## Quality")
    L.append("")
    L.append("| Metric | Run | Baseline | Note |")
    L.append("|---|---:|---:|---|")
    L.append(f"| Corpus size | {s['run_corpus_size']} | {s['baseline_corpus_size']} | "
             f"Δ {fmt_delta(s['corpus_delta'], 'neutral')} |")
    audited_denom = s['hit_gold_count'] + s['hit_out_count']
    L.append(f"| Precision vs. gold | {s['precision']:.1%} | {s['baseline_precision']:.1%} | "
             f"{s['hit_gold_count']} gold hits of {audited_denom} audited in corpus"
             f"{' (gold covers every corpus article)' if audited_denom == s['run_corpus_size'] else ''} |")
    L.append(f"| Recall vs. gold | {s['recall']:.1%} | {s['baseline_recall']:.1%} | "
             f"{s['hit_gold_count']} of {s['gold_size']} gold covered |")
    L.append(f"| Reach (beyond gold) | {s['reach_count']} | — | audit for gold growth |")
    L.append(f"| Hit OUT (false-positive) | {s['hit_out_count']} | — | gold says off-topic |")
    L.append(f"| Missed gold | {s['missed_gold_count']} | — | recall-loss candidates |")
    L.append("")
    L.append("## Cost")
    L.append("")
    L.append("Gate cost metrics are API calls + tool calls. Wall time is "
             "reported informationally but does NOT count toward the gate — "
             "operator-approval flows (Codex permission prompts on first "
             "use of each tool) inflate it without reflecting tool efficiency.")
    L.append("")
    L.append("| Metric | Run | Baseline | Δ | In gate? |")
    L.append("|---|---:|---:|---|---|")
    L.append(f"| Wall time (s) | {s['wall_time_s']} | "
             f"{s['wall_time_s'] - (s['wall_time_delta'] or 0)} | "
             f"{fmt_delta(s['wall_time_delta'])} | no (informational) |")
    api_gate_label = ("yes" if s.get('api_axis_in_gate', True)
                      else "no (baseline unrecorded)")
    L.append(f"| API calls | {s['total_api_calls']} | "
             f"{s['total_api_calls'] - (s['total_api_calls_delta'] or 0)} | "
             f"{fmt_delta(s['total_api_calls_delta'])} | {api_gate_label} |")
    L.append(f"| Tool calls | {s['tool_call_count']} | "
             f"{s['tool_call_count'] - (s['tool_call_count_delta'] or 0)} | "
             f"{fmt_delta(s['tool_call_count_delta'])} | yes |")
    L.append("")

    excluded = (s['gold_unaudited_count'] + s['gold_uncertain_count']
                + s['gold_redirect_count'] + s['gold_redlink_count'])
    if excluded:
        L.append("## Gold status")
        L.append("")
        if s['gold_unaudited_count']:
            L.append(f"- {s['gold_unaudited_count']} rows `pending_audit` — "
                     f"precision/recall approximate until gold is fully classified.")
        if s['gold_uncertain_count']:
            L.append(f"- {s['gold_uncertain_count']} rows `uncertain` — "
                     f"excluded from both numerator and denominator.")
        if s['gold_redirect_count']:
            L.append(f"- {s['gold_redirect_count']} rows `redirect` — "
                     f"provenance markers (Wikipedia redirect sources pointing "
                     f"at canonical rows). Excluded from scoring.")
        if s['gold_redlink_count']:
            L.append(f"- {s['gold_redlink_count']} rows `redlink` — "
                     f"titles with no Wikipedia article. Excluded from scoring.")
        L.append("")

    for label, field, direction in [
        ("Reach sample (audit to grow gold)", "reach_sample", "reach"),
        ("Missed gold sample (recall loss)", "missed_gold_sample", "missed"),
        ("False-positive sample (hits OUT gold)", "hit_out_sample", "out"),
    ]:
        sample = s[field]
        if sample:
            count_field = {
                "reach_sample": "reach_count",
                "missed_gold_sample": "missed_gold_count",
                "hit_out_sample": "hit_out_count",
            }[field]
            L.append(f"## {label} (first {len(sample)} of {s[count_field]})")
            L.append("")
            for t in sample:
                L.append(f"- {t}")
            L.append("")

    return "\n".join(L)


def _resolve_task_mode(task_id, nth=0):
    """For --task mode: look up the task in the DB, find matching run
    topics on the server, pick the Nth-most-recent. Returns
    (benchmark_slug, run_topic_name)."""
    env = load_env()
    # Import db directly on the host to pull the task record + the list
    # of matching topics. Simple and cheap: one ssh roundtrip.
    remote_py = rf'''
import json, sys, re
sys.path.insert(0, "/opt/topic-builder/app")
import db
task = db.get_dogfood_task("""{task_id}""")
if task is None:
    print(json.dumps({{"error": "task not found"}}))
    sys.exit(0)
template = task["run_topic_name_template"] or ""
# Build a regex that matches the rendered name: replace {{ts}} with a
# timestamp pattern, escape the rest.
if "{{ts}}" in template:
    stem_pattern = re.escape(template).replace(r"\\{{ts\\}}", r"(\d{{12}})")
else:
    stem_pattern = re.escape(template)
regex = re.compile("^" + stem_pattern + "$")
matching = []
for t in db.list_topics():
    m = regex.match(t["name"])
    if m:
        ts = m.group(1) if m.groups() else ""
        matching.append({{"name": t["name"], "ts": ts,
                           "article_count": t.get("article_count") or 0}})
matching.sort(key=lambda r: r["ts"], reverse=True)
print(json.dumps({{
    "benchmark_slug": task["benchmark_slug"],
    "template": template,
    "matches": matching,
}}))
'''
    rc, out, err = ssh_cmd(env, f"/opt/topic-builder/venv/bin/python -c '{remote_py}'")
    if rc != 0:
        raise RuntimeError(f"ssh failed resolving task: {err}")
    info = json.loads(out.strip())
    if "error" in info:
        raise ValueError(
            f"Task {task_id!r} not found on the server. "
            "Re-seed dogfood_tasks or use the direct <slug> <run-topic-name> form.")
    slug = info["benchmark_slug"]
    if not slug:
        raise ValueError(
            f"Task {task_id!r} has no benchmark_slug; cannot use --task mode. "
            "Use the direct <slug> <run-topic-name> form instead.")
    matches = info["matches"]
    if not matches:
        raise ValueError(
            f"Task {task_id!r}: no run topics on the server match template "
            f"{info['template']!r}. Start a run first.")
    if nth >= len(matches):
        raise ValueError(
            f"Task {task_id!r}: only {len(matches)} matching run(s), "
            f"can't access index {nth}.")
    chosen = matches[nth]
    print(f"Task {task_id!r} → slug={slug!r}, run_topic={chosen['name']!r} "
          f"(nth={nth} of {len(matches)} matching; {chosen['article_count']} articles)",
          file=sys.stderr)
    return slug, chosen["name"]


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(
        description="Score a benchmark run against frozen gold + baseline.")
    p.add_argument("slug_or_positional1", nargs="?",
                   help="Benchmark slug (positional, direct mode)")
    p.add_argument("run_topic", nargs="?",
                   help="Run topic name (positional, direct mode)")
    p.add_argument("--task", metavar="TASK_ID",
                   help="Task-ID lookup mode: find the matching run topic on "
                        "the server by template, pick --nth-most-recent.")
    p.add_argument("--nth", type=int, default=0,
                   help="With --task: index into the matching run topics "
                        "(0=most recent, 1=second-most, ...). Default 0.")
    args = p.parse_args()

    if args.task:
        try:
            slug, run_topic = _resolve_task_mode(args.task, nth=args.nth)
        except (RuntimeError, ValueError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.slug_or_positional1 and args.run_topic:
        slug = args.slug_or_positional1
        run_topic = args.run_topic
    else:
        print("usage: benchmark_score.py <benchmark-slug> <run-topic-name>",
              file=sys.stderr)
        print("       benchmark_score.py --task <task-id> [--nth N]",
              file=sys.stderr)
        sys.exit(2)

    s = score(slug, run_topic)
    md = format_scoreboard(s)
    print(md)

    # Sidecar JSON for machine consumption + archiving
    if "error" not in s:
        runs_dir = os.path.join(BENCHMARKS_DIR, slug, "runs")
        os.makedirs(runs_dir, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe = run_topic.lower().replace(" ", "_").replace("/", "_")
        md_path = os.path.join(runs_dir, f"{stamp}_{safe}.md")
        json_path = os.path.join(runs_dir, f"{stamp}_{safe}.json")
        with open(md_path, "w") as f:
            f.write(md)
        with open(json_path, "w") as f:
            json.dump({k: (sorted(v) if isinstance(v, set) else v)
                       for k, v in s.items()}, f, indent=2, default=str)
        print(f"\nScoreboard archived:\n  {md_path}\n  {json_path}",
              file=sys.stderr)
