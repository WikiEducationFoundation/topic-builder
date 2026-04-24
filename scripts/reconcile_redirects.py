"""Reconcile redirects in a benchmark's gold.csv.

For each title, resolve to canonical form via Wikipedia's redirect +
normalize API, then ensure every row carries an honest status:

  1. Self-canonical row (title == resolved): no action.
  2. Redirect source whose canonical is also in gold:
       - Canonical row keeps its classification (promoted from pending_audit
         if any non-canonical row in the group has a decisive classification).
       - Non-canonical rows are MARKED on_topic=redirect (preserved for
         provenance; scoreboard excludes them). Notes get '→ canonical'.
       - If decisive classifications DISAGREE between canonical and a
         redirect source, a warning is printed — canonical wins regardless.
  3. Redirect source whose canonical is NOT in gold:
       - Rewrite the row's title to the canonical form. Keep classification.
  4. Title missing on Wikipedia (no article under any redirect chain):
       - MARK on_topic=redlink. Preserve original classification in notes
         as "[was: <original>]".

Why mark instead of drop: redirect/redlink rows document "we've seen this
title, here's what it is" so future runs don't resurface them as reach
candidates. Scoring excludes both statuses from gold_in/gold_out so they
don't warp recall or precision.

Usage:
    python3 scripts/reconcile_redirects.py <slug> [--dry-run]
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

    # Planned actions. Each row gets AT MOST one action.
    #   rewrite: (row, new_title, new_cls, new_notes_prefix)
    #   mark_redirect: (row, canonical_target)   — on_topic → 'redirect'
    #   mark_redlink: (row, original_on_topic)   — on_topic → 'redlink'
    rewrites = []
    mark_redirect = []
    mark_redlink = []
    conflict_warnings = []

    # Already-missing titles: mark as redlink.
    for row in rows:
        orig = row["title"]
        if resolved.get(orig) is None:
            mark_redlink.append((row, row["on_topic"]))

    for canonical, group_rows in groups.items():
        # Skip "missing" groups — handled above.
        if resolved.get(canonical) is None:
            continue

        if len(group_rows) == 1:
            row = group_rows[0]
            if row["title"] != canonical:
                rewrites.append((row, canonical, row["on_topic"], None))
            continue

        # Multiple rows → pick winner, mark others as redirect.
        # Winner preference: canonical-title-match first, then decisive class.
        def _sort_key(r):
            return (0 if r["title"] == canonical else 1,
                    _class_rank(r["on_topic"]))
        sorted_rows = sorted(group_rows, key=_sort_key)
        winner = sorted_rows[0]

        # If winner's own classification is pending_audit but another row
        # in the group has a decisive one, promote it.
        winner_cls = winner["on_topic"]
        decisive_rows = [r for r in group_rows if r["on_topic"] in DECISIVE]
        if winner_cls == "pending_audit" and decisive_rows:
            winner_cls = decisive_rows[0]["on_topic"]

        # Detect disagreement among decisive classifications for the warning.
        decisive_equiv = {_CONFLICT_EQUIV[r["on_topic"]] for r in decisive_rows}
        if len(decisive_equiv) > 1:
            conflict_warnings.append((canonical, group_rows, winner, winner_cls))

        # Winner: may need title rewrite if it isn't the canonical row.
        if winner["title"] != canonical:
            rewrites.append((winner, canonical, winner_cls, None))
        elif winner_cls != winner["on_topic"]:
            rewrites.append((winner, winner["title"], winner_cls, None))

        # All non-winner rows become redirect markers.
        for r in group_rows:
            if r is winner:
                continue
            mark_redirect.append((r, canonical))

    n_rewrite = len(rewrites)
    n_mark_redirect = len(mark_redirect)
    n_mark_redlink = len(mark_redlink)
    n_conflict = len(conflict_warnings)

    print()
    print(f"=== {args.slug} reconciliation plan ===")
    print(f"  Self-canonical (no change):         {unchanged}")
    print(f"  Redirect/normalization detected:    {redirects_found}")
    print(f"  Rows to rewrite (→ canonical):      {n_rewrite}")
    print(f"  Rows to mark on_topic=redirect:     {n_mark_redirect}")
    print(f"  Rows to mark on_topic=redlink:      {n_mark_redlink}")
    print(f"  Canonical-vs-redirect disagreements: {n_conflict}")

    if n_rewrite > 0:
        print("\nWill rewrite (first 20):")
        for row, new_title, new_cls, _ in rewrites[:20]:
            old = row["title"]
            cls_note = ""
            if new_cls != row["on_topic"]:
                cls_note = f"  [class: {row['on_topic']} → {new_cls}]"
            print(f"  - {old!r} → {new_title!r}{cls_note}")
        if n_rewrite > 20:
            print(f"  ... and {n_rewrite - 20} more")

    if n_mark_redirect > 0:
        print("\nWill mark on_topic=redirect (first 20):")
        for row, canonical in mark_redirect[:20]:
            print(f"  - {row['title']!r} (was {row['on_topic']!r}) "
                  f"→ redirect → {canonical!r}")
        if n_mark_redirect > 20:
            print(f"  ... and {n_mark_redirect - 20} more")

    if n_mark_redlink > 0:
        print("\nWill mark on_topic=redlink (first 20):")
        for row, orig_cls in mark_redlink[:20]:
            print(f"  - {row['title']!r} (was {orig_cls!r}) → redlink")
        if n_mark_redlink > 20:
            print(f"  ... and {n_mark_redlink - 20} more")

    if n_conflict > 0:
        print("\n⚠ Canonical-vs-redirect-source classification disagreements")
        print("  (canonical wins; redirect sources will be marked `redirect`):")
        for canonical, group_rows, winner, winner_cls in conflict_warnings[:10]:
            print(f"  Canonical {canonical!r} (keeping {winner_cls!r}):")
            for r in group_rows:
                marker = " ←WINNER" if r is winner else ""
                print(f"    - {r['title']!r}: {r['on_topic']!r}{marker}")
        if n_conflict > 10:
            print(f"  ... and {n_conflict - 10} more disagreements")

    if args.dry_run:
        print("\n(dry-run: no changes written)")
        return

    # Build lookup maps. Note: a row can only be in one action (rewrites
    # and mark_redirect are mutually exclusive by construction).
    rewrite_map = {id(r): (t, c, n)
                   for r, t, c, n in rewrites}
    redirect_map_local = {id(r): canon for r, canon in mark_redirect}
    redlink_map_local = {id(r): orig for r, orig in mark_redlink}

    for row in rows:
        rid = id(row)
        if rid in redlink_map_local:
            orig = redlink_map_local[rid]
            row["on_topic"] = "redlink"
            note = f"[was: {orig}]"
            row["notes"] = (row.get("notes") + " " + note).strip() \
                if row.get("notes") else note
        elif rid in redirect_map_local:
            canon = redirect_map_local[rid]
            orig = row["on_topic"]
            row["on_topic"] = "redirect"
            note = f"→ {canon}"
            # If the original classification differed from the canonical's,
            # preserve it in notes for audit history.
            prev_note = row.get("notes") or ""
            pieces = [note]
            if orig not in ("pending_audit", "redirect", "redlink"):
                pieces.append(f"[was: {orig}]")
            if prev_note:
                pieces.insert(0, prev_note)
            row["notes"] = " ".join(pieces)
        elif rid in rewrite_map:
            new_title, new_cls, _ = rewrite_map[rid]
            row["title"] = new_title
            row["on_topic"] = new_cls

    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in GOLD_COLUMNS})

    print(f"\nOK — wrote {gold_path} ({len(rows)} rows, "
          f"{n_rewrite} rewritten, {n_mark_redirect} → redirect, "
          f"{n_mark_redlink} → redlink).")


if __name__ == "__main__":
    main()
