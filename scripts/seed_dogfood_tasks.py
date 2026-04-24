"""Seed dogfood_tasks table from dogfood/tasks/*.md source files.

Idempotent: runs INSERT OR REPLACE keyed on task_id, so editing a
brief file and re-running updates in place. Prints a summary at the end.

Designed to run on the deployed server via:

    bash scripts/smoke.sh scripts/seed_dogfood_tasks.py

which scp's this file to /tmp on the host and runs it through
/opt/topic-builder/venv/bin/python so `import db` resolves against the
server's code + DB.

File format (YAML-lite frontmatter + markdown body):

    ---
    task_id: apollo-11-thin
    variant: thin
    benchmark_slug: apollo-11
    run_topic_name: apollo-11 ratchet-2026-04-23-thin
    ---

    <markdown body — served verbatim via fetch_task_brief>
"""
import glob
import os
import sys

# On the deployed host, smoke.sh runs this script with /tmp as cwd,
# so we need to add the app dir to sys.path to `import db`. Locally
# (if ever run for development), fall back to the repo's mcp_server.
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


# The script looks for task .md files in these paths in order:
#   1. /tmp/dogfood_tasks/          (host: operator pre-scp's the tasks
#                                    dir here before running smoke.sh)
#   2. <repo>/dogfood/tasks/        (local run: straight from the repo)
TASK_DIR_CANDIDATES = [
    "/tmp/dogfood_tasks",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dogfood", "tasks",
    ),
]


def parse_frontmatter(text: str):
    """Minimal YAML-lite frontmatter parser. Supports only flat key: value
    lines, no nested structures or arrays — enough for this use case."""
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter opener '---'")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("missing frontmatter closer '---'")
    yaml_text = text[4:end]
    body = text[end + 5:].lstrip("\n")
    meta = {}
    for lineno, raw in enumerate(yaml_text.splitlines(), start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"frontmatter line {lineno} missing ':': {raw!r}")
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        # Strip optional quotes on the value.
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        meta[key] = val
    return meta, body


def load_tasks_from_dir(path: str):
    """Return a list of (frontmatter_dict, body_str, source_file) tuples."""
    out = []
    files = sorted(glob.glob(os.path.join(path, "*.md")))
    # Skip README; task files only.
    files = [f for f in files if os.path.basename(f).lower() != "readme.md"]
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            text = fh.read()
        meta, body = parse_frontmatter(text)
        out.append((meta, body, f))
    return out


def main():
    chosen_dir = None
    for d in TASK_DIR_CANDIDATES:
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.md")):
            chosen_dir = d
            break
    if chosen_dir is None:
        print("ERROR: no tasks directory found. Looked in:")
        for d in TASK_DIR_CANDIDATES:
            print(f"  - {d}")
        print("\nIf running on the deployed host via smoke.sh, scp the "
              "tasks directory first:\n"
              "  source .env && scp -i deploy_key -r dogfood/tasks "
              "\"$DEPLOY_USER@$DEPLOY_HOST:/tmp/dogfood_tasks\"\n"
              "then re-run: bash scripts/smoke.sh scripts/seed_dogfood_tasks.py")
        sys.exit(2)

    tasks = load_tasks_from_dir(chosen_dir)
    print(f"Loaded {len(tasks)} task(s) from {chosen_dir}")

    count = 0
    for meta, body, src in tasks:
        required = ("task_id", "variant", "run_topic_name")
        for k in required:
            if not meta.get(k):
                raise ValueError(f"{src}: missing frontmatter key {k!r}")
        task_id = meta["task_id"]
        variant = meta["variant"]
        run_topic_name = meta["run_topic_name"]
        benchmark_slug = meta.get("benchmark_slug") or None
        stored = db.upsert_dogfood_task(
            task_id=task_id,
            variant=variant,
            run_topic_name=run_topic_name,
            brief_markdown=body,
            benchmark_slug=benchmark_slug,
        )
        brief_len = len(stored["brief_markdown"]) if stored else 0
        print(f"  upsert {task_id!r:36s} variant={variant!s:8s} "
              f"slug={benchmark_slug!s:28s} brief={brief_len} chars")
        count += 1

    print(f"\nOK — {count} task(s) upserted.")
    print("\nCurrent dogfood_tasks in DB:")
    for t in db.list_dogfood_tasks():
        print(f"  {t['task_id']!r:36s} -> {t['run_topic_name']!r}")


if __name__ == "__main__":
    main()
