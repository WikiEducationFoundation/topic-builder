"""Wikipedia API utilities for the MCP server."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from contextvars import ContextVar

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

# Rate limit tracking (process-cumulative)
_rate_limit_hits = 0
_last_rate_limit_time = None

# Per-call counters. A tool resets these at entry, and log_usage reads them
# at exit to attribute cost (api_calls + rate-limit events) to that specific
# tool invocation. ContextVars are propagated through async call chains by
# default, so concurrent MCP sessions don't clobber each other.
_call_api_calls: ContextVar[int] = ContextVar('_call_api_calls', default=0)
_call_rate_limit_hits: ContextVar[int] = ContextVar('_call_rate_limit_hits', default=0)

logger = logging.getLogger("wikipedia_api")


def reset_call_counters():
    """Zero out per-call counters. Call at the start of each tool invocation."""
    _call_api_calls.set(0)
    _call_rate_limit_hits.set(0)


def get_call_counters() -> dict:
    """Read per-call counters. Call at the end of a tool invocation."""
    return {
        'wikipedia_api_calls': _call_api_calls.get(),
        'rate_limit_hits_this_call': _call_rate_limit_hits.get(),
    }


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
            _call_api_calls.set(_call_api_calls.get() + 1)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Check for rate limit warning headers
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    _rate_limit_hits += 1
                    _call_rate_limit_hits.set(_call_rate_limit_hits.get() + 1)
                    _last_rate_limit_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    wait = int(retry_after)
                    logger.warning(f"Rate limited (Retry-After: {wait}s). Total hits: {_rate_limit_hits}")
                    time.sleep(wait)

                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _rate_limit_hits += 1
                _call_rate_limit_hits.set(_call_rate_limit_hits.get() + 1)
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


def _first_sentence(text, max_chars=200):
    """Extract a best-effort first sentence from a plain-text REST extract.
    Recognizes ASCII `.!?` followed by whitespace/eos AND full-width CJK
    sentence-enders `。！？` (no whitespace needed — CJK doesn't space
    between sentences). Skips any match within the first 30 chars (likely
    an abbreviation like 'Dr.' / 'Mt.') and caps at max_chars so long
    opening sentences don't bloat the description column."""
    if not text:
        return ''
    text = text.strip()
    import re
    match = re.search(r'(?:[.!?](?:\s|$)|[。！？])', text[30:])
    if match:
        end = 30 + match.end()
        result = text[:end]
        if len(result) > max_chars:
            return result[:max_chars].rstrip() + '…'
        return result
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + '…'
    return text


def fetch_rest_intros(titles, wiki):
    """Fetch first-sentence intros from MediaWiki's REST page-summary
    endpoint. Returns a dict title -> first sentence (may be empty string
    when the page is missing or the extract is blank).

    Intended as a fallback when Wikidata short-descs are empty — English
    Wikidata short-desc coverage is near-complete, but most other language
    editions are sparse, so `fetch_short_descriptions` alone returns
    mostly empty on non-en topics. The REST extract pulls the first
    paragraph of the article body, so non-en pages almost always have
    *something* even without a Wikidata short-desc."""
    import urllib.parse
    out = {t: '' for t in titles}
    base = f"https://{wiki}.wikipedia.org/api/rest_v1/page/summary/"
    for title in titles:
        encoded = urllib.parse.quote(title.replace(' ', '_'), safe='')
        try:
            data = api_get(base + encoded, timeout=10)
        except Exception:
            continue
        extract = (data or {}).get('extract', '') if isinstance(data, dict) else ''
        if extract:
            out[title] = _first_sentence(extract)
    return out


def fetch_descriptions_with_fallback(titles, wiki='en'):
    """Fetch Wikidata short-descs, then fall back to REST /page/summary
    intros for titles where Wikidata came back empty AND the wiki is
    non-en. On enwiki the Wikidata layer is sufficient (we skip the REST
    fallback to save requests). Returns dict title -> description."""
    out = fetch_short_descriptions(titles, wiki=wiki)
    if wiki != 'en':
        empty_titles = [t for t, d in out.items() if not d]
        if empty_titles:
            rest = fetch_rest_intros(empty_titles, wiki)
            for t, intro in rest.items():
                if intro:
                    out[t] = intro
    return out


# ── Wikidata SPARQL ────────────────────────────────────────────────────────
#
# query.wikidata.org has stricter rate limits than the per-wiki action API:
# a 60s per-query hard cap, 5 req/s soft throttle, and a strict User-Agent
# requirement. An in-memory TTL cache avoids re-hitting the endpoint for
# repeated helper calls inside a session. The cache is process-local — it
# resets on deploys, which is fine: miss cost is one query, not catastrophic.

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
_wikidata_cache: dict[str, tuple[float, list[dict]]] = {}
_WIKIDATA_CACHE_TTL_S = 3600  # 1 hour


def _simplify_sparql_binding(binding: dict) -> dict:
    """Flatten a SPARQL binding row to {var_name: value_str}.

    Wikidata returns bindings as {var: {type, value, ...}}. We drop the
    type metadata and simplify entity URIs to bare QIDs — the AI cares
    about `Q25308`, not `http://www.wikidata.org/entity/Q25308`. Same
    for property URIs (`P171` vs the full URI). Literal values pass
    through untouched."""
    row = {}
    for var, cell in binding.items():
        val = cell.get('value', '')
        if cell.get('type') == 'uri':
            if val.startswith('http://www.wikidata.org/entity/'):
                val = val[len('http://www.wikidata.org/entity/'):]
            elif val.startswith('http://www.wikidata.org/prop/'):
                # Property URIs come in several flavors; last segment is the PID.
                val = val.rsplit('/', 1)[-1]
        row[var] = val
    return row


def wikidata_sparql(query: str, timeout: int = 60,
                   use_cache: bool = True) -> list[dict]:
    """Run a SPARQL query against query.wikidata.org.

    Returns a list of simplified binding dicts — each dict maps SELECT
    variable name to string value, with entity URIs reduced to bare QIDs.
    Reuses `api_get`, so per-call counters + rate-limit backoff + User-Agent
    handling come for free.

    `use_cache=True` (default) hits an in-memory 1-hour TTL cache keyed
    by the query text. Pass False for diagnostics or when you know data
    has changed."""
    import hashlib
    cache_key = hashlib.sha256(query.encode('utf-8')).hexdigest()
    if use_cache:
        cached = _wikidata_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < _WIKIDATA_CACHE_TTL_S:
            return cached[1]

    params = {'query': query, 'format': 'json'}
    data = api_get(WIKIDATA_SPARQL_ENDPOINT, params, timeout=timeout)
    if not isinstance(data, dict):
        return []
    bindings = (data.get('results', {}) or {}).get('bindings', []) or []
    rows = [_simplify_sparql_binding(b) for b in bindings]

    if use_cache:
        _wikidata_cache[cache_key] = (time.monotonic(), rows)
    return rows


def wikidata_entities_by_property(property_id: str, value_qid: str,
                                  wiki: str = 'en',
                                  limit: int = 500) -> list[dict]:
    """Common-case helper: find Wikidata entities whose `property_id` links
    to `value_qid`, returning QID + label + per-wiki sitelink title +
    description.

    Both arguments are bare IDs — `"P171"` (parent taxon) + `"Q25308"`
    (Orchidaceae) returns every entity whose parent taxon is Orchidaceae.
    Result row shape:
        {"qid": "Q...",
         "label": "...",           # label in `wiki`'s language
         "title": "...",           # sitelink title on <wiki>.wikipedia.org,
                                   # empty if no sitelink exists
         "description": "..."}     # Wikidata description, empty if none

    Titles come with underscores replaced by spaces so they match the
    working-list format.

    Use this when you want "give me all the X whose Y is Z." For
    compound queries or anything with multiple properties, drop down
    to raw `wikidata_sparql`."""
    # Be conservative: accept Q-id values only. Literal-valued properties
    # like P50 (author) can still go through raw SPARQL — document in the
    # MCP tool layer.
    if not property_id.startswith('P') or not value_qid.startswith('Q'):
        raise ValueError(
            "property_id must start with 'P' (e.g. 'P171') and value_qid "
            "must start with 'Q' (e.g. 'Q25308'). For literal-valued "
            "queries, use wikidata_sparql directly."
        )
    limit = max(1, min(int(limit), 10000))
    sparql = f"""
    SELECT ?item ?itemLabel ?article ?description WHERE {{
      ?item wdt:{property_id} wd:{value_qid} .
      OPTIONAL {{
        ?article schema:about ?item ;
                 schema:isPartOf <https://{wiki}.wikipedia.org/> .
      }}
      OPTIONAL {{
        ?item schema:description ?description .
        FILTER(LANG(?description) = "{wiki}")
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{wiki}". }}
    }}
    LIMIT {limit}
    """
    rows = wikidata_sparql(sparql)
    title_prefix = f"https://{wiki}.wikipedia.org/wiki/"
    out = []
    for r in rows:
        article_url = r.get('article', '')
        title = ''
        if article_url.startswith(title_prefix):
            title = urllib.parse.unquote(
                article_url[len(title_prefix):]).replace('_', ' ')
        out.append({
            'qid': r.get('item', ''),
            'label': r.get('itemLabel', ''),
            'title': title,
            'description': r.get('description', ''),
        })
    return out


# ── Wikipedia description helpers ─────────────────────────────────────────


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
