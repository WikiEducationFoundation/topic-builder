"""Wikipedia API utilities for the MCP server."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"  # default / enwiki shortcut
PETSCAN_URL = "https://petscan.wmcloud.org/"
USER_AGENT = "WikipediaTopicBuilder/1.0 (https://topic-builder.wikiedu.org/; sage@wikiedu.org)"
REQUEST_DELAY = 0.05


def wiki_api_url(wiki='en'):
    """Build the api.php URL for a given Wikipedia language edition.
    Wikipedia has 300+ language codes; we don't validate here — an unknown
    code will surface as an HTTP/DNS error at request time."""
    return f"https://{wiki}.wikipedia.org/w/api.php"

_last_request_time = 0

# Rate limit tracking
_rate_limit_hits = 0
_last_rate_limit_time = None

logger = logging.getLogger("wikipedia_api")


def get_rate_limit_stats():
    """Return rate limit stats for monitoring."""
    return {
        'total_rate_limit_hits': _rate_limit_hits,
        'last_rate_limit_time': _last_rate_limit_time,
    }


def api_get(url, params=None, timeout=30):
    global _last_request_time, _rate_limit_hits, _last_rate_limit_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    if params:
        query_string = urllib.parse.urlencode(params, doseq=True)
        full_url = f"{url}?{query_string}"
    else:
        full_url = url

    req = urllib.request.Request(full_url)
    req.add_header('User-Agent', USER_AGENT)

    for attempt in range(3):
        try:
            _last_request_time = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Check for rate limit warning headers
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    _rate_limit_hits += 1
                    _last_rate_limit_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    wait = int(retry_after)
                    logger.warning(f"Rate limited (Retry-After: {wait}s). Total hits: {_rate_limit_hits}")
                    time.sleep(wait)

                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _rate_limit_hits += 1
                _last_rate_limit_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                retry_after = e.headers.get('Retry-After', (attempt + 1) * 5)
                wait = int(retry_after)
                logger.warning(f"HTTP 429 rate limited, waiting {wait}s. Total hits: {_rate_limit_hits}")
                time.sleep(wait)
                continue
            elif e.code >= 500:
                wait = (attempt + 1) * 2
                logger.warning(f"HTTP {e.code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < 2:
                wait = (attempt + 1) * 2
                logger.warning(f"URL error: {e.reason}, retrying in {wait}s")
                time.sleep(wait)
                continue
            raise


def api_query(params, wiki='en'):
    params = dict(params)
    params['action'] = 'query'
    params['format'] = 'json'
    params['formatversion'] = '2'
    params['maxlag'] = '5'  # back off if MediaWiki servers are lagged >5s
    return api_get(wiki_api_url(wiki), params)


def api_query_all(params, result_key, max_items=50000, wiki='en'):
    params = dict(params)
    params['action'] = 'query'
    params['format'] = 'json'
    params['formatversion'] = '2'
    url = wiki_api_url(wiki)
    count = 0
    while True:
        data = api_get(url, params)
        if 'query' in data and result_key in data['query']:
            for item in data['query'][result_key]:
                yield item
                count += 1
                if count >= max_items:
                    return
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break


def normalize_title(title):
    title = urllib.parse.unquote(title)
    title = title.replace('_', ' ')
    if title:
        title = title[0].upper() + title[1:]
    return title.strip()


def fetch_short_descriptions(titles, wiki='en'):
    """Fetch Wikidata short descriptions for a list of article titles.

    Returns a dict mapping each input title to its short description (empty
    string if missing). Uses the pageprops API in batches of 50 and follows
    title normalizations + redirects so titles stored in slightly different
    form still get matched to the canonical page. `wiki` selects the
    language edition (e.g. 'en', 'de', 'es').
    """
    out = {t: '' for t in titles}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        data = api_query({
            'titles': '|'.join(batch),
            'prop': 'pageprops',
            'ppprop': 'wikibase-shortdesc',
            'redirects': '1',
        }, wiki=wiki)
        query = data.get('query', {}) if isinstance(data, dict) else {}
        # Chain normalizations and redirects: original -> canonical page title.
        chain = {t: t for t in batch}
        for item in query.get('normalized', []):
            for k, v in list(chain.items()):
                if v == item.get('from'):
                    chain[k] = item.get('to')
        for item in query.get('redirects', []):
            for k, v in list(chain.items()):
                if v == item.get('from'):
                    chain[k] = item.get('to')
        descs = {}
        for page in query.get('pages', []):
            title = page.get('title')
            desc = (page.get('pageprops') or {}).get('wikibase-shortdesc', '')
            if title:
                descs[title] = desc
        for orig, target in chain.items():
            if descs.get(target):
                out[orig] = descs[target]
    return out
