"""Shared configuration and API utilities for Wikipedia topic builder scripts."""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Load contact email from .env
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '.env')
CONTACT_EMAIL = None
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith('CONTACT_EMAIL='):
                CONTACT_EMAIL = line.split('=', 1)[1]

# API endpoints
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
PETSCAN_URL = "https://petscan.wmcloud.org/"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

# User-Agent per Wikimedia policy
USER_AGENT = f"WikipediaTopicBuilder/1.0 (https://topic-builder.wikiedu.org/; {CONTACT_EMAIL or 'unknown'})"

# Rate limiting
REQUEST_DELAY = 0.05  # 50ms between requests


_last_request_time = 0


def api_get(url, params=None):
    """Make a GET request with rate limiting and retry logic.

    Returns parsed JSON response.
    """
    global _last_request_time

    # Rate limiting
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            _last_request_time = time.time()
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = (attempt + 1) * 2
                print(f"HTTP {e.code}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 2
                print(f"URL error: {e.reason}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise

    raise RuntimeError(f"Failed after {max_retries} retries: {full_url}")


def api_query(params):
    """Make a MediaWiki API query request. Adds format=json and formatversion=2."""
    params = dict(params)
    params['action'] = 'query'
    params['format'] = 'json'
    params['formatversion'] = '2'
    return api_get(WIKIPEDIA_API, params)


def api_query_all(params, result_key):
    """Auto-paginate a MediaWiki API query, yielding all results.

    result_key: the key within response['query'] that contains results
                (e.g., 'categorymembers', 'search', 'embeddedin')

    Yields individual result items across all pages.
    """
    params = dict(params)
    params['action'] = 'query'
    params['format'] = 'json'
    params['formatversion'] = '2'

    while True:
        data = api_get(WIKIPEDIA_API, params)

        if 'query' in data and result_key in data['query']:
            for item in data['query'][result_key]:
                yield item

        if 'continue' in data:
            params.update(data['continue'])
        else:
            break


def batch_query(titles, props, batch_size=50):
    """Query properties for titles in batches of 50 (MediaWiki max).

    Yields (title, page_data) tuples.
    """
    title_list = list(titles)
    for i in range(0, len(title_list), batch_size):
        batch = title_list[i:i + batch_size]
        params = {
            'titles': '|'.join(batch),
            'prop': props,
        }
        data = api_query(params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                yield page


def normalize_title(title):
    """Normalize a Wikipedia article title.

    - Replace underscores with spaces
    - URL-decode
    - Capitalize first character
    """
    title = urllib.parse.unquote(title)
    title = title.replace('_', ' ')
    if title:
        title = title[0].upper() + title[1:]
    return title.strip()
