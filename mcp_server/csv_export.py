"""Reusable CSV-export helpers.

Used by:
  - server.export_csv (the MCP tool)
  - topics_ui (the on-demand HTTP download route at /topics/<slug>/download.csv)

Lives in its own module so the HTTP route and the MCP tool can share IO
logic without server.py importing topics_ui (which would cycle, since
server.py registers topics_ui at startup).
"""

from __future__ import annotations

import csv
import datetime
import os

import db
from wikipedia_api import fetch_descriptions_with_fallback


def export_dir() -> str:
    return os.environ.get("EXPORT_DIR", "/opt/topic-builder/exports")


def topic_slug(topic_name: str) -> str:
    return topic_name.lower().replace(" ", "_").replace("'", "").replace('"', "")


def csv_filename(slug: str, *, enriched: bool) -> str:
    suffix = "-enriched" if enriched else ""
    return f"topic-articles-{slug}{suffix}.csv"


def rubric_filename(slug: str) -> str:
    return f"topic-articles-{slug}-rubric.txt"


def write_topic_csv(topic_id: int, topic_name: str, wiki: str, *,
                    enriched: bool = False,
                    min_score: int = 0,
                    scored_only: bool = False) -> dict:
    """Write the topic's CSV (and rubric sidecar for enriched exports) under
    the configured export directory. Returns metadata used by both the MCP
    tool's response shape and the HTTP route.

    Keys in the returned dict:
      filename, filepath, article_count, titles, all_articles, descriptions,
      rubric_filename (or None), rubric_filepath (or None).
    """
    all_articles = db.get_all_articles_dict(topic_id)

    titles: list[str] = []
    for title, article in sorted(all_articles.items()):
        score = article.get("score")
        if scored_only and score is None:
            continue
        if score is not None and score < min_score:
            continue
        if min_score > 0 and score is None:
            continue
        titles.append(title)

    descriptions: dict[str, str] = {}
    if enriched:
        missing: list[str] = []
        for title in titles:
            stored = all_articles.get(title, {}).get("description")
            if stored is None:
                missing.append(title)
            else:
                descriptions[title] = stored
        if missing:
            fetched = fetch_descriptions_with_fallback(missing, wiki=wiki)
            db.set_descriptions(topic_id, fetched)
            descriptions.update(fetched)

    out_dir = export_dir()
    os.makedirs(out_dir, exist_ok=True)
    slug = topic_slug(topic_name)
    filename = csv_filename(slug, enriched=enriched)
    filepath = os.path.join(out_dir, filename)

    # Enriched is for human/Excel consumption: utf-8-sig BOM helps Excel
    # detect UTF-8, header row labels columns. Default is for Impact
    # Visualizer import: single-column titles, no BOM (IV's CSV
    # normalizer doesn't strip BOM and would mangle the first row), no
    # header. csv.writer with newline='' emits RFC-4180 CRLF and quotes
    # only when needed.
    if enriched:
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "title", "wikidata_qid", "description", "score",
                "source_labels", "first_added_at",
            ])
            for title in titles:
                article = all_articles.get(title, {})
                sources = article.get("sources") or []
                writer.writerow([
                    title,
                    article.get("wikidata_qid") or "",
                    descriptions.get(title, ""),
                    article.get("score") if article.get("score") is not None else "",
                    "|".join(sources),
                    article.get("created_at") or "",
                ])
    else:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for title in titles:
                writer.writerow([title])

    rubric_fname = None
    rubric_path = None
    if enriched:
        rubric = db.get_topic_rubric(topic_id)
        if rubric:
            rubric_fname = rubric_filename(slug)
            rubric_path = os.path.join(out_dir, rubric_fname)
            with open(rubric_path, "w", encoding="utf-8") as rf:
                rf.write(f"# Centrality rubric for topic: {topic_name}\n")
                rf.write(f"# wiki: {wiki}\n")
                rf.write(f"# exported: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
                rf.write("\n")
                rf.write(rubric)
                if not rubric.endswith("\n"):
                    rf.write("\n")

    return {
        "filename": filename,
        "filepath": filepath,
        "article_count": len(titles),
        "titles": titles,
        "all_articles": all_articles,
        "descriptions": descriptions,
        "rubric_filename": rubric_fname,
        "rubric_filepath": rubric_path,
    }
