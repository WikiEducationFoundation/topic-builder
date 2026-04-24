"""Reconcile redirects in a benchmark's gold.csv.

For each title in gold.csv, resolve to canonical form via Wikipedia's
redirect+normalize API, then:

  1. Self-canonical (title == resolved): no action.
  2. Redirect source whose canonical is ALSO in gold: merge.
     The "winner" row is picked by:
       (a) most-decisive classification (in/peripheral/out > pending_audit)
       (b) within ties, the canonical title's own row wins
     Other rows are dropped. If two rows have decisive classifications
     that DISAGREE (e.g., one 'in' and one 'out' for the same canonical),
     the group is retained and flagged for manual review.
  3. Redirect source whose canonical is NOT in gold: rewrite the row's
     title to the canonical form; keep everything else.
  4. Missing on Wikipedia (page deleted / never existed): flagged but
     not dropped — human should review.

Usage:
    python3 scripts/reconcile_redirects.py <slug> [--dry-run]

Example:
    python3 scripts/reconcile_redirects.py orchids --dry-run
    python3 scripts/reconcile_redirects.py orchids
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from redirect_utils import resolve_redirects  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")

GOLD_COLUMNS = [
    "title", "on_topic", "sources", "score", "description", "notes",
    "source_run",
]

DECISIVE = {"in", "peripheral", "out", "true", "false"}
# Deterministic rank-within-decisive. Binary 'true'/'false' are the
# pre-2026-04-23 schema still in use on hispanic-latino-stem-us —
# treat as equivalent to 'in' / 'out' for the purposes of reconciliation.
_DECISIVE_RANK = {
    "in": 0,
    "true": 0,
    "peripheral": 1,
    "out": 2,
    "false": 2,
}
# Classifications considered semantically equivalent for conflict detection
# (a row labeled 'true' and another labeled 'in' should NOT be flagged as
# conflicting; a 'true' and 'out' SHOULD).
_CONFLICT_EQUIV = {"in": "in", "true": "in",
                   "peripheral": "peripheral",
                   "out": "out", "false": "out"}


def _class_rank(on_topic):
    if on_topic in _DECISIVE_RANK:
        return _DECISIVE_RANK[on_topic]
    if on_topic == "pending_audit":
        return 10
    return 20


def main():
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    gold_path = os.path.join(BENCHMARKS_DIR, args.slug, "gold.csv")
    if not os.path.exists(gold_path):
        print(f"ERROR: no gold.csv at {gold_path}", file=sys.stderr)
        sys.exit(1)

    with open(gold_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    titles = [row["title"] for row in rows]

    print(f"Resolving {len(titles)} titles in {gold_path}...")

    def progress(i, total, error=None):
        if error:
            print(f"  batch {i}/{total}: ERROR {error}", file=sys.stderr)
        elif i % 20 == 0 or i == total:
            print(f"  batch {i}/{total}", file=sys.stderr)

    resolved = resolve_redirects(titles, wiki="en", progress=progress)
    print("Resolution complete.")

    # Group rows by canonical target. Missing titles become their own
    # group (they stay as-is, flagged).
    groups = defaultdict(list)  # canonical → [row]
    missing = []
    unchanged = 0
    redirects_found = 0
    for row in rows:
        orig = row["title"]
        canonical = resolved.get(orig)
        if canonical is None:
            missing.append(orig)
            groups[orig].append(row)
            continue
        if canonical == orig:
            unchanged += 1
        else:
            redirects_found += 1
        groups[canonical].append(row)

    rows_to_drop = []                         # row refs
    drop_targets = {}                         # id(row) → canonical target
    rows_to_rewrite = []                      # (row_ref, new_title, new_cls)
    conflicts = []                            # list of (canonical, [rows])

    for canonical, group_rows in groups.items():
        if len(group_rows) == 1:
            row = group_rows[0]
            if row["title"] != canonical and resolved.get(row["title"]) is not None:
                rows_to_rewrite.append((row, canonical, row["on_topic"]))
            continue

        # Multiple rows → reconciliation required.
        decisive_rows = [r for r in group_rows if r["on_topic"] in DECISIVE]
        # Conflict detection uses semantic equivalence (true ≡ in, false ≡ out).
        decisive_equiv = {_CONFLICT_EQUIV[r["on_topic"]] for r in decisive_rows}
        if len(decisive_equiv) > 1:
            conflicts.append((canonical, group_rows))
            continue

        # No disagreement — merge into a winner.
        # Winner: lowest class_rank, tie-broken by canonical-title match.
        def _sort_key(r):
            return (_class_rank(r["on_topic"]),
                    0 if r["title"] == canonical else 1)
        sorted_rows = sorted(group_rows, key=_sort_key)
        winner = sorted_rows[0]
        winner_cls = winner["on_topic"]
        # If the winner is pending_audit but there's a decisive row in
        # the group, promote that classification onto the winner.
        if winner_cls == "pending_audit" and decisive_rows:
            winner_cls = decisive_rows[0]["on_topic"]
        for r in group_rows:
            if r is winner:
                if r["title"] != canonical:
                    rows_to_rewrite.append((r, canonical, winner_cls))
                elif winner_cls != r["on_topic"]:
                    rows_to_rewrite.append((r, r["title"], winner_cls))
            else:
                rows_to_drop.append(r)
                drop_targets[id(r)] = canonical

    n_drop = len(rows_to_drop)
    n_rewrite = len(rows_to_rewrite)
    n_conflict = len(conflicts)
    n_missing = len(missing)

    print()
    print(f"=== {args.slug} reconciliation plan ===")
    print(f"  Self-canonical (no change):       {unchanged}")
    print(f"  Redirect/normalization detected:  {redirects_found}")
    print(f"  Rows to drop (merged duplicates): {n_drop}")
    print(f"  Rows to rewrite (→ canonical):    {n_rewrite}")
    print(f"  Classification conflicts:         {n_conflict}")
    print(f"  Missing on Wikipedia:             {n_missing}")

    if n_drop > 0:
        print("\nWill drop (first 20):")
        for row in rows_to_drop[:20]:
            tgt = drop_targets.get(id(row), "?")
            print(f"  - {row['title']!r} ({row['on_topic']}) → merged into {tgt!r}")
        if n_drop > 20:
            print(f"  ... and {n_drop - 20} more")

    if n_rewrite > 0:
        print("\nWill rewrite (first 20):")
        for row, new_title, new_cls in rows_to_rewrite[:20]:
            old = row["title"]
            cls_note = ""
            if new_cls != row["on_topic"]:
                cls_note = f"  [class: {row['on_topic']} → {new_cls}]"
            print(f"  - {old!r} → {new_title!r}{cls_note}")
        if n_rewrite > 20:
            print(f"  ... and {n_rewrite - 20} more")

    if n_conflict > 0:
        print("\n⚠ Classification conflicts (kept for manual review):")
        for canonical, group_rows in conflicts[:10]:
            print(f"  Canonical {canonical!r}:")
            for r in group_rows:
                print(f"    - {r['title']!r}: {r['on_topic']!r}")
        if n_conflict > 10:
            print(f"  ... and {n_conflict - 10} more conflicts")

    if n_missing > 0:
        print("\n⚠ Titles not on Wikipedia (flagged, not dropped):")
        for t in missing[:20]:
            print(f"  - {t!r}")
        if n_missing > 20:
            print(f"  ... and {n_missing - 20} more")

    if args.dry_run:
        print("\n(dry-run: no changes written)")
        return

    dropped_ids = {id(r) for r in rows_to_drop}
    rewrite_map = {id(r): (new_title, new_cls)
                   for r, new_title, new_cls in rows_to_rewrite}

    new_rows = []
    for row in rows:
        if id(row) in dropped_ids:
            continue
        if id(row) in rewrite_map:
            new_title, new_cls = rewrite_map[id(row)]
            row["title"] = new_title
            row["on_topic"] = new_cls
        new_rows.append(row)

    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in new_rows:
            w.writerow({k: row.get(k, "") for k in GOLD_COLUMNS})

    print(f"\nOK — wrote {gold_path} ({len(new_rows)} rows, "
          f"{len(rows) - len(new_rows)} merged out).")


if __name__ == "__main__":
    main()
