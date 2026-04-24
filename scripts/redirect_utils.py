"""Resolve Wikipedia titles to their canonical form via MediaWiki's
action=query redirects + normalize API.

Used by offline scripts (reconcile_redirects, promote_reach,
benchmark_score) to normalize titles before comparison / append. The
server-side equivalent lives in mcp_server/wikipedia_api.py so the
resolve_redirects MCP tool can use the same underlying logic against
a topic's live corpus.
"""
import json
import time
import urllib.parse
import urllib.request

USER_AGENT = (
    "WikipediaTopicBuilder/1.0 "
    "(https://topic-builder.wikiedu.org/; sage@wikiedu.org)"
)
BATCH_SIZE = 50  # MediaWiki accepts up to 50 titles per query.
RATE_LIMIT_DELAY = 0.1  # 100ms between calls — friendly to WMF infra.


def _api_url(wiki):
    return f"https://{wiki}.wikipedia.org/w/api.php"


def resolve_redirects(titles, wiki="en", progress=None):
    """Resolve a list of Wikipedia titles to their canonical forms.

    Returns a dict mapping each input title to:
      - The canonical title (string) if resolved successfully. Unchanged
        if the title is self-canonical; rewritten if it's a redirect
        source or needs normalization (case / spacing).
      - None if the title doesn't exist on Wikipedia (page missing).

    Handles redirect chains (follows to final target up to depth 5) and
    title normalizations. Batches at 50 titles per call with a 100ms
    rate-limit delay.

    Args:
      titles: iterable of title strings. Duplicates are deduped internally.
      wiki: language edition (default 'en').
      progress: optional callback fn(batch_index, total_batches, error=None).
    """
    unique_titles = list(dict.fromkeys(titles))  # preserve order, dedupe
    out = {t: t for t in unique_titles}
    total_batches = (len(unique_titles) + BATCH_SIZE - 1) // BATCH_SIZE
    last_call = 0.0

    for i in range(0, len(unique_titles), BATCH_SIZE):
        batch = unique_titles[i:i + BATCH_SIZE]
        elapsed = time.time() - last_call
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)

        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "titles": "|".join(batch),
            "redirects": "1",
            "maxlag": "5",
        }
        url = f"{_api_url(wiki)}?{urllib.parse.urlencode(params, doseq=True)}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", USER_AGENT)

        try:
            last_call = time.time()
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except Exception as e:
            if progress:
                progress(i // BATCH_SIZE + 1, total_batches, error=str(e))
            continue

        query = data.get("query", {}) if isinstance(data, dict) else {}

        # Chain maps FROM → TO for both normalizations and redirects.
        chain = {}
        for item in query.get("normalized", []):
            chain[item["from"]] = item["to"]
        for item in query.get("redirects", []):
            chain.setdefault(item["from"], item["to"])

        missing_set = set()
        for page in query.get("pages", []):
            if page.get("missing"):
                missing_set.add(page.get("title"))

        for orig in batch:
            target = orig
            for _ in range(5):  # cap depth; prevent cycles
                if target in chain:
                    target = chain[target]
                else:
                    break
            if target in missing_set:
                out[orig] = None
            else:
                out[orig] = target

        if progress:
            progress(i // BATCH_SIZE + 1, total_batches)

    return out
