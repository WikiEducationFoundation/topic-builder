"""One-shot: delete informed-variant dogfood tasks from the DB.

Two-phase dogfood (Ship 1, 2026-04-25) replaces the thin/informed
split — every run is now a thin phase-1 build followed by a phase-2
reach-extension. The informed-variant briefs are retired (their .md
files removed in the same commit). This script deletes the
corresponding rows from the dogfood_tasks table on the deployed host.

Run on the host via:

    bash scripts/smoke.sh scripts/retire_informed_tasks.py

Idempotent: safe to re-run; informs you if no rows match.
"""
import os
import sys

_HOST_APP = "/opt/topic-builder/app"
_LOCAL_APP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp_server",
)
for p in (_HOST_APP, _LOCAL_APP):
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import db  # noqa: E402


def main():
    conn = db._connect()
    rows = conn.execute(
        "SELECT task_id FROM dogfood_tasks "
        "WHERE task_id LIKE '%-informed' OR variant = 'informed'"
    ).fetchall()
    if not rows:
        print("OK — no informed-variant tasks in DB.")
        return
    print(f"Found {len(rows)} informed-variant task(s) to delete:")
    for r in rows:
        print(f"  {r['task_id']!r}")
    conn.execute(
        "DELETE FROM dogfood_tasks "
        "WHERE task_id LIKE '%-informed' OR variant = 'informed'"
    )
    conn.commit()
    print(f"\nOK — deleted {len(rows)} row(s).")
    print("\nRemaining dogfood_tasks:")
    for t in db.list_dogfood_tasks():
        print(f"  {t['task_id']!r:36s} variant={t['variant']!r}")


if __name__ == "__main__":
    main()
