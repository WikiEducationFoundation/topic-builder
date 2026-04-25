"""Seed dogfood_exemplars table from dogfood/exemplars/*.md source files.

Idempotent: runs INSERT OR REPLACE keyed on slug, so editing an
exemplar file and re-running updates in place. Prints a summary at
the end.

Designed to run on the deployed server via:

    bash scripts/scp_exemplars.sh
    bash scripts/smoke.sh scripts/seed_dogfood_exemplars.py

scp_exemplars.sh copies the dogfood/exemplars/ directory to
/tmp/dogfood_exemplars on the host; smoke.sh then runs this script
through the deployed venv.

File format (YAML-lite frontmatter + markdown body):

    ---
    slug: orchids
    title: Orchids
    shape: very large taxonomic topic ...
    last_validated_against: 2026-04-25
    ---

    <markdown body — menu card + full case study, served verbatim
     by list_exemplars / get_exemplar>
"""
import glob
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


EXEMPLAR_DIR_CANDIDATES = [
    "/tmp/dogfood_exemplars",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dogfood", "exemplars",
    ),
]


def parse_frontmatter(text: str):
    """Flat YAML-lite: key: value lines only. Same as the seed_dogfood_tasks
    parser — exemplar frontmatter is intentionally kept flat so we don't
    have to maintain a real YAML parser."""
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
        if (val.startswith('"') and val.endswith('"')) or \
           (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        meta[key] = val
    return meta, body


def load_exemplars_from_dir(path: str):
    out = []
    files = sorted(glob.glob(os.path.join(path, "*.md")))
    files = [f for f in files if os.path.basename(f).lower() != "readme.md"]
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            text = fh.read()
        meta, body = parse_frontmatter(text)
        out.append((meta, body, f))
    return out


def main():
    chosen_dir = None
    for d in EXEMPLAR_DIR_CANDIDATES:
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.md")):
            chosen_dir = d
            break
    if chosen_dir is None:
        print("ERROR: no exemplars directory found. Looked in:")
        for d in EXEMPLAR_DIR_CANDIDATES:
            print(f"  - {d}")
        sys.exit(2)

    exemplars = load_exemplars_from_dir(chosen_dir)
    print(f"Loaded {len(exemplars)} exemplar(s) from {chosen_dir}")

    count = 0
    for meta, body, src in exemplars:
        required = ("slug", "title")
        for k in required:
            if not meta.get(k):
                raise ValueError(f"{src}: missing frontmatter key {k!r}")
        slug = meta["slug"]
        title = meta["title"]
        shape = meta.get("shape", "")
        last_validated = meta.get("last_validated_against", "")
        # Stash any extra frontmatter keys as metadata (forward-compat).
        extra_meta = {
            k: v for k, v in meta.items()
            if k not in ("slug", "title", "shape", "last_validated_against")
        }
        stored = db.upsert_dogfood_exemplar(
            slug=slug,
            title=title,
            shape=shape,
            body_markdown=body,
            last_validated_against=last_validated,
            metadata=extra_meta,
        )
        body_len = len(stored["body_markdown"]) if stored else 0
        print(f"  upsert {slug!r:32s} title={title!r:40s} body={body_len} chars")
        count += 1

    print(f"\nOK — {count} exemplar(s) upserted.")
    print("\nCurrent dogfood_exemplars in DB:")
    for e in db.list_dogfood_exemplars():
        print(f"  {e['slug']!r:32s} -> {e['title']!r}")


if __name__ == "__main__":
    main()
