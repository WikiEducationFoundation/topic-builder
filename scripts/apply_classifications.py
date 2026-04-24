"""Apply in/peripheral/out classifications to pending_audit rows in a
benchmark's gold.csv.

Usage:
    python3 scripts/apply_classifications.py <slug> <classifications.json>

The JSON file is a flat dict mapping title → classification, where
classification ∈ {"in", "peripheral", "out"}. Titles not in the dict
are left unchanged. Titles whose current on_topic is NOT pending_audit
are skipped with a warning (human decisions always win; this script
never overwrites an already-classified row).

Prints a summary of what changed, grouped by new classification.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
BENCHMARKS_DIR = os.path.join(REPO_ROOT, "benchmarks")

GOLD_COLUMNS = [
    "title", "on_topic", "sources", "score", "description", "notes",
    "source_run",
]

VALID_CLASSES = {"in", "peripheral", "out"}


def main():
    if len(sys.argv) != 3:
        print("usage: apply_classifications.py <slug> <classifications.json>",
              file=sys.stderr)
        sys.exit(2)
    slug, cls_path = sys.argv[1], sys.argv[2]
    gold_path = os.path.join(BENCHMARKS_DIR, slug, "gold.csv")

    if not os.path.exists(gold_path):
        print(f"ERROR: no gold.csv at {gold_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(cls_path):
        print(f"ERROR: no classifications file at {cls_path}", file=sys.stderr)
        sys.exit(1)

    with open(cls_path) as f:
        classifications = json.load(f)

    bad = [k for k, v in classifications.items() if v not in VALID_CLASSES]
    if bad:
        print(f"ERROR: invalid classifications for titles: {bad}",
              file=sys.stderr)
        print(f"Valid values: {VALID_CLASSES}", file=sys.stderr)
        sys.exit(1)

    with open(gold_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    applied = {"in": [], "peripheral": [], "out": []}
    skipped_not_pending = []
    not_found = set(classifications.keys())

    for row in rows:
        title = row["title"]
        if title not in classifications:
            continue
        not_found.discard(title)
        new_cls = classifications[title]
        if row["on_topic"] != "pending_audit":
            skipped_not_pending.append((title, row["on_topic"], new_cls))
            continue
        row["on_topic"] = new_cls
        applied[new_cls].append(title)

    # Write back.
    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in GOLD_COLUMNS})

    total_changed = sum(len(v) for v in applied.values())
    print(f"Applied {total_changed} classifications to {gold_path}")
    for cls in ("in", "peripheral", "out"):
        titles = applied[cls]
        print(f"  → {cls}: {len(titles)}")
        for t in titles[:10]:
            print(f"     - {t}")
        if len(titles) > 10:
            print(f"     ... and {len(titles) - 10} more")

    if skipped_not_pending:
        print(f"\nSkipped {len(skipped_not_pending)} already-classified rows (human decisions win):")
        for title, cur, would in skipped_not_pending[:5]:
            print(f"  - {title!r}: kept {cur!r} (skipped would-be {would!r})")
        if len(skipped_not_pending) > 5:
            print(f"  ... and {len(skipped_not_pending) - 5} more")

    if not_found:
        print(f"\n⚠ {len(not_found)} classifications had no matching row in gold.csv:")
        for t in sorted(not_found)[:10]:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
