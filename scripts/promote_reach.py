"""Promote a ratchet run's reach titles into gold.csv as pending_audit.

Usage:
    python3 scripts/promote_reach.py <benchmark-slug> <run-topic-name> [--dry-run]

Example:
    python3 scripts/promote_reach.py orchids "orchids ratchet-2026-04-23"

What it does:
    1. Loads benchmarks/<slug>/gold.csv locally.
    2. Fetches the run topic's current corpus titles from the deployed
       server (same SSH path benchmark_score.py uses).
    3. Computes reach = corpus - gold-titles.
    4. Appends each reach title to gold.csv with:
         on_topic=pending_audit
         source_run=<run-topic-name>       (provenance)
       leaving sources / score / description / notes blank.
    5. Writes the file back.

Why:
    Every ratchet run surfaces a reach list ("articles my corpus has
    that gold doesn't know about yet"). Without promotion, the same
    candidates show up on every subsequent run's reach list. With
    promotion, each run enqueues them as pending_audit so the audit
    queue grows and future scoreboards only re-surface NEWLY-found
    reach. The scoring script treats pending_audit as "not yet
    classified" — it does NOT count toward recall or precision. So
    promotion is zero-risk for the scoreboard.

Safety:
    - NEVER mutates an existing on_topic value. If a title is already
      in gold.csv under any status, we skip it. Human decisions win.
    - Idempotent: re-running with the same inputs is a no-op (all
      reach titles were already promoted on the first run).
    - --dry-run shows what WOULD be promoted without writing.

Caveat (read before re-running an `audit.py` classifier):
    Per-benchmark audit.py scripts (e.g. benchmarks/orchids/audit.py)
    OVERWRITE gold.csv with their classification output. If you
    re-run a benchmark's audit.py AFTER promote_reach.py has appended
    rows, you will LOSE the promoted reach + any manual classification
    edits. This is the existing convention inherited from 2026-04-23
    bootstrap; nothing new introduced here. If re-classifying becomes
    a regular need, plan for a merge pass instead of a wholesale
    rewrite.
"""
import csv
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from benchmark_score import BENCHMARKS_DIR, fetch_run_state, load_env  # noqa: E402
from redirect_utils import resolve_redirects  # noqa: E402


GOLD_COLUMNS = [
    "title", "on_topic", "sources", "score", "description", "notes",
    "source_run",
]


def load_existing_gold(path):
    """Return (list of row dicts, set of titles). Rows are preserved
    verbatim — any columns we don't know about get passed through."""
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
    titles = {row["title"] for row in rows}
    return rows, titles


def write_gold(path, rows):
    """Rewrite gold.csv with the current columns. Rows may have extra
    keys (legacy columns); we write exactly GOLD_COLUMNS and silently
    drop extras. Any missing column is filled with ''."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in GOLD_COLUMNS})


def main():
    argv = [a for a in sys.argv[1:]]
    dry_run = False
    if "--dry-run" in argv:
        dry_run = True
        argv.remove("--dry-run")
    if len(argv) != 2:
        print("usage: promote_reach.py <benchmark-slug> <run-topic-name> [--dry-run]",
              file=sys.stderr)
        sys.exit(2)
    slug, run_topic = argv

    gold_path = os.path.join(BENCHMARKS_DIR, slug, "gold.csv")
    if not os.path.exists(gold_path):
        print(f"ERROR: no gold.csv at {gold_path}", file=sys.stderr)
        sys.exit(1)

    existing_rows, existing_titles = load_existing_gold(gold_path)
    print(f"Loaded {len(existing_rows)} existing gold rows from {gold_path}")

    env = load_env()
    print(f"Fetching corpus for run topic {run_topic!r} from server...")
    run_state = fetch_run_state(env, run_topic)
    if run_state is None:
        print(f"ERROR: run topic {run_topic!r} not found on server.",
              file=sys.stderr)
        sys.exit(1)

    corpus = run_state["corpus"]
    raw_reach = sorted(corpus - existing_titles)

    # Resolve raw reach titles to their canonical forms. This prevents
    # promoting redirect sources when the canonical is already in gold
    # (avoids the duplicate-rows pattern reconcile_redirects.py cleans up).
    if raw_reach:
        print(f"Resolving {len(raw_reach)} raw reach titles to canonical "
              f"forms via Wikipedia...")
        wiki = run_state.get("wiki", "en") or "en"
        resolved = resolve_redirects(raw_reach, wiki=wiki)
    else:
        resolved = {}

    # Each raw reach title gets one of these actions:
    #   promote_canonical: add a new row title=canonical, on_topic=pending_audit
    #   mark_redirect:     add a new row title=raw, on_topic=redirect,
    #                      notes="→ canonical" — preserves provenance
    #                      for a title whose canonical is already in gold.
    #   mark_redlink:      add a new row title=raw, on_topic=redlink —
    #                      preserves the fact that we saw this title, but
    #                      flags it as a dead link.
    #   skip_dedup:        another raw title already promotes this canonical;
    #                      don't add a second canonical row.
    promote_canonical = []  # list of canonical titles
    redirect_rows = []      # list of (raw_title, canonical_target)
    redlink_rows = []       # list of raw_titles
    promoted_canonicals = set()
    for raw in raw_reach:
        canonical = resolved.get(raw, raw)
        if canonical is None:
            # Skip if already in gold under any status.
            if raw in existing_titles:
                continue
            redlink_rows.append(raw)
            continue
        if canonical in existing_titles:
            # Canonical already in gold — preserve the redirect-source
            # provenance (unless the raw title itself is already in gold).
            if raw != canonical and raw not in existing_titles:
                redirect_rows.append((raw, canonical))
            continue
        if canonical in promoted_canonicals:
            # Two raw reach titles resolved to the same canonical.
            # Still preserve the extra raw as a redirect marker.
            if raw != canonical and raw not in existing_titles:
                redirect_rows.append((raw, canonical))
            continue
        promoted_canonicals.add(canonical)
        promote_canonical.append(canonical)
        # If the raw title differs from the canonical, also add a redirect
        # marker row for the raw title so future runs recognize it.
        if raw != canonical and raw not in existing_titles:
            redirect_rows.append((raw, canonical))

    print(f"Corpus size: {len(corpus)}")
    print(f"Already in gold (direct match): {len(corpus & existing_titles)}")
    print(f"Raw reach candidates: {len(raw_reach)}")
    print(f"  → new canonicals to promote (pending_audit): "
          f"{len(promote_canonical)}")
    print(f"  → redirect-source rows to add (on_topic=redirect): "
          f"{len(redirect_rows)}")
    print(f"  → redlink rows to add (on_topic=redlink): "
          f"{len(redlink_rows)}")

    total_new = len(promote_canonical) + len(redirect_rows) + len(redlink_rows)
    if total_new == 0:
        print("\nNothing to add. Gold already contains every reach title's "
              "canonical form, and every raw reach title is either already "
              "marked or matches its canonical directly.")
        return

    if dry_run:
        print("\n(dry-run: not writing to gold.csv)\n")
        print(f"Would add {total_new} rows total.")
        if promote_canonical:
            print(f"\nFirst 20 canonical pending_audit rows:")
            for t in promote_canonical[:20]:
                print(f"  - {t}")
            if len(promote_canonical) > 20:
                print(f"  ... and {len(promote_canonical) - 20} more")
        if redirect_rows:
            print(f"\nFirst 20 redirect rows:")
            for raw, canon in redirect_rows[:20]:
                print(f"  - {raw!r} → {canon!r}")
            if len(redirect_rows) > 20:
                print(f"  ... and {len(redirect_rows) - 20} more")
        if redlink_rows:
            print(f"\nFirst 20 redlink rows:")
            for raw in redlink_rows[:20]:
                print(f"  - {raw!r}")
            if len(redlink_rows) > 20:
                print(f"  ... and {len(redlink_rows) - 20} more")
        return

    new_rows = []
    for title in promote_canonical:
        new_rows.append({
            "title": title,
            "on_topic": "pending_audit",
            "sources": "",
            "score": "",
            "description": "",
            "notes": "",
            "source_run": run_topic,
        })
    for raw, canonical in redirect_rows:
        new_rows.append({
            "title": raw,
            "on_topic": "redirect",
            "sources": "",
            "score": "",
            "description": "",
            "notes": f"→ {canonical}",
            "source_run": run_topic,
        })
    for raw in redlink_rows:
        new_rows.append({
            "title": raw,
            "on_topic": "redlink",
            "sources": "",
            "score": "",
            "description": "",
            "notes": "",
            "source_run": run_topic,
        })

    write_gold(gold_path, existing_rows + new_rows)
    total = len(existing_rows) + len(new_rows)

    print(f"\nOK — wrote {gold_path}.")
    print(f"  gold.csv now has {total} rows total "
          f"({total - len(new_rows)} prior + {len(new_rows)} new).")
    print(f"  Added: {len(promote_canonical)} pending_audit, "
          f"{len(redirect_rows)} redirect, {len(redlink_rows)} redlink.")
    print(f"  source_run={run_topic!r}")
    if promote_canonical:
        print("\nNext step: audit the pending_audit rows at your leisure. "
              "Edit on_topic from 'pending_audit' to 'in' / 'peripheral' / "
              "'out' directly in gold.csv; the scoring script will pick up "
              "the change on the next run.")


if __name__ == "__main__":
    main()
