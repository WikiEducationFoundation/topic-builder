"""Shared helpers for benchmark audit.py classifiers.

The big one: `validate_gold_titles(gold_path)` — checks every in/peripheral/
redlink/redirect-classified row in gold.csv against Wikipedia and updates
the classification when the article-existence facts change. Mark missing
titles `redlink`, mark redirect-sources `redirect` (with canonical target
in notes), recover real articles that were stale-redlinked.

This is "ground truth from Wikipedia" — a layer above the keyword-classifier
in audit.py. Reproducible across machines, easy to call from any audit.py:

    from audit_lib import validate_gold_titles
    validate_gold_titles(GOLD_PATH)

Idempotent: re-running detects fresh redlinks (article since deleted) and
recovers from stale ones (article since created). Designed to run after
the keyword classifier has done its pass; existence ground truth then
overrides where it differs.
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


WIKIPEDIA_API = "https://{wiki}.wikipedia.org/w/api.php"
USER_AGENT = "wiki-edu-topic-builder audit_lib (sage@wikiedu.org)"

# Conservative defaults: 50 titles per call is the API limit; 0.5s between
# calls keeps us well under the 200-req/s anonymous quota with headroom for
# transient backoffs.
DEFAULT_BATCH_SIZE = 50
DEFAULT_DELAY_S = 0.5
DEFAULT_MAX_RETRIES = 6


def _api_call(wiki: str, titles: list[str]) -> dict:
    """One MW query against `titles`, returning the parsed JSON dict.
    Includes redirects=1 so the response surfaces both `redirects` (redirect
    source -> target mappings) and `pages` with missing flags on canonical
    targets. Caller maps requested titles back via redirects + normalized."""
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "info",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    }
    qs = urllib.parse.urlencode(params)
    url = f"{WIKIPEDIA_API.format(wiki=wiki)}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _resolve_titles(data: dict, requested: list[str]) -> dict:
    """Map each requested title to {'state': ..., 'target': ...} where
    state is 'real' / 'redirect' / 'redlink' / 'unknown' and target is
    the canonical title (for redirect rows)."""
    pages_by_title = {p.get("title", ""): p
                      for p in data.get("query", {}).get("pages", []) or []}
    norms = {n["from"]: n["to"]
             for n in data.get("query", {}).get("normalized", []) or []}
    redirs = {r["from"]: r["to"]
              for r in data.get("query", {}).get("redirects", []) or []}

    result = {}
    for t in requested:
        # Normalize first (whitespace, capitalization).
        normalized = norms.get(t, t)
        # Then check if it's a redirect.
        if normalized in redirs:
            target = redirs[normalized]
            # Redirect-target may itself be missing if the target was deleted
            # but the redirect remains. Verify.
            tgt_page = pages_by_title.get(target, {})
            if tgt_page.get("missing"):
                result[t] = {"state": "redlink", "target": None,
                             "note": f"redirect→{target} but target is missing"}
            else:
                result[t] = {"state": "redirect", "target": target}
        else:
            # Not a redirect: look up canonical (= normalized).
            page = pages_by_title.get(normalized, {})
            if page.get("missing"):
                result[t] = {"state": "redlink", "target": None}
            elif page:
                result[t] = {"state": "real", "target": None}
            else:
                # Title not in response — API may have rejected it (invalid
                # characters, namespace issue). Don't change classification.
                result[t] = {"state": "unknown", "target": None}
    return result


def _api_call_with_retry(wiki: str, titles: list[str],
                         max_retries: int) -> dict:
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return _api_call(wiki, titles)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited: backoff exponentially with cap at 60s.
                wait = min(delay * (2 ** attempt), 60.0)
                print(f"    HTTP 429; backing off {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            wait = min(2.0 * (attempt + 1), 30.0)
            time.sleep(wait)
            continue
    raise RuntimeError(f"max retries exceeded for batch starting {titles[0]!r}")


def validate_gold_titles(gold_path: str, *,
                         wiki: str = "en",
                         batch_size: int = DEFAULT_BATCH_SIZE,
                         delay_s: float = DEFAULT_DELAY_S,
                         max_retries: int = DEFAULT_MAX_RETRIES,
                         verbose: bool = True) -> dict:
    """Reconcile gold.csv classifications with Wikipedia article-existence
    ground truth.

    For every row whose on_topic is in {in, peripheral, redlink, redirect},
    query Wikipedia and apply the appropriate update:
      - title is missing on Wikipedia → on_topic = 'redlink'
      - title is a redirect to canonical target → on_topic = 'redirect',
        notes = '→ <target>'
      - title is a real (non-redirect) article → keep classification (the
        keyword classifier owns the in/peripheral/out call)
      - title was previously redlink but now exists → keep redlink for now;
        the next audit.py classifier run will reclassify it. (We don't
        guess in/peripheral/out from this layer.)

    Skips: rows with on_topic=out (we don't waste API on confirmed-OUT) and
    on_topic=uncertain or pending_audit (let the classifier handle them).

    Returns counts dict.
    """
    with open(gold_path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    body = rows[1:]

    # Schema lookup
    H = {name: i for i, name in enumerate(header)}
    title_col = H.get("title", 0)
    on_topic_col = H.get("on_topic", 1)
    notes_col = H.get("notes", 5)

    # Worklist: every title currently classified as in/peripheral/redlink/
    # redirect (we re-check redlink + redirect to handle Wikipedia changes).
    CHECK_STATES = {"in", "peripheral", "redlink", "redirect"}
    work_indexes = []
    for i, row in enumerate(body):
        cls = row[on_topic_col] if len(row) > on_topic_col else ""
        if cls in CHECK_STATES:
            work_indexes.append(i)

    if verbose:
        print(f"validate_gold_titles: {len(work_indexes)} of {len(body)} rows "
              f"to check against {wiki}.wikipedia.org")

    counts = {
        "checked": 0,
        "to_redlink": 0,
        "to_redirect": 0,
        "redlink_to_existing": 0,
        "no_change": 0,
        "unknown": 0,
        "errors": 0,
    }
    delta_samples = {"to_redlink": [], "to_redirect": [],
                     "redlink_to_existing": []}

    for batch_start in range(0, len(work_indexes), batch_size):
        batch_idx = work_indexes[batch_start:batch_start + batch_size]
        batch_titles = [body[i][title_col] for i in batch_idx]
        try:
            data = _api_call_with_retry(wiki, batch_titles, max_retries)
        except Exception as e:
            counts["errors"] += len(batch_titles)
            if verbose:
                print(f"  batch error: {e}", file=sys.stderr)
            continue
        resolved = _resolve_titles(data, batch_titles)
        for idx, title in zip(batch_idx, batch_titles):
            counts["checked"] += 1
            res = resolved.get(title, {"state": "unknown"})
            state = res["state"]
            current = body[idx][on_topic_col]
            row = body[idx]
            # Ensure notes column exists
            while len(row) <= notes_col:
                row.append("")
            if state == "redlink" and current != "redlink":
                row[on_topic_col] = "redlink"
                _annotate(row, notes_col, f"redlink (was {current})")
                counts["to_redlink"] += 1
                if len(delta_samples["to_redlink"]) < 12:
                    delta_samples["to_redlink"].append((title, current))
            elif state == "redirect" and current != "redirect":
                row[on_topic_col] = "redirect"
                _annotate(row, notes_col,
                          f"redirect→{res.get('target')} (was {current})")
                counts["to_redirect"] += 1
                if len(delta_samples["to_redirect"]) < 12:
                    delta_samples["to_redirect"].append(
                        (title, current, res.get("target")))
            elif state == "real" and current == "redlink":
                # The article now exists. Reset classification to 'pending_audit'
                # so the keyword classifier picks it up on next pass.
                row[on_topic_col] = "pending_audit"
                _annotate(row, notes_col, "redlink→pending_audit (article now exists)")
                counts["redlink_to_existing"] += 1
                if len(delta_samples["redlink_to_existing"]) < 12:
                    delta_samples["redlink_to_existing"].append(title)
            elif state == "unknown":
                counts["unknown"] += 1
            else:
                counts["no_change"] += 1
        time.sleep(delay_s)
        if verbose and (batch_start // batch_size) % 20 == 0:
            print(f"  {counts['checked']}/{len(work_indexes)} checked: "
                  f"+{counts['to_redlink']} redlink, "
                  f"+{counts['to_redirect']} redirect, "
                  f"+{counts['redlink_to_existing']} recovered")

    # Write back if anything changed
    changed = (counts["to_redlink"] + counts["to_redirect"]
               + counts["redlink_to_existing"])
    if changed:
        with open(gold_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in body:
                w.writerow(r)

    if verbose:
        print(f"validate_gold_titles: done. "
              f"+{counts['to_redlink']} redlinks, "
              f"+{counts['to_redirect']} redirects, "
              f"+{counts['redlink_to_existing']} redlinks→pending. "
              f"({counts['no_change']} unchanged, {counts['unknown']} unknown, "
              f"{counts['errors']} errors)")
        if delta_samples["to_redlink"]:
            print(f"  sample to_redlink (first 12): "
                  f"{[t for t, _ in delta_samples['to_redlink']]}")
        if delta_samples["to_redirect"]:
            print(f"  sample to_redirect (first 12): "
                  f"{[(t, tgt) for t, _, tgt in delta_samples['to_redirect']]}")
        if delta_samples["redlink_to_existing"]:
            print(f"  sample redlink→pending (first 12): "
                  f"{delta_samples['redlink_to_existing']}")

    return counts


def _annotate(row, notes_col, msg):
    """Append a note to the notes cell, preserving prior annotations."""
    existing = row[notes_col] or ""
    if existing:
        row[notes_col] = f"{existing}; {msg}"
    else:
        row[notes_col] = msg


if __name__ == "__main__":
    # Standalone CLI: python audit_lib.py <gold.csv> [wiki]
    if len(sys.argv) < 2:
        print("usage: python audit_lib.py <gold.csv> [wiki=en]")
        sys.exit(2)
    path = sys.argv[1]
    w = sys.argv[2] if len(sys.argv) > 2 else "en"
    validate_gold_titles(path, wiki=w)
