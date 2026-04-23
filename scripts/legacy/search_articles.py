#!/usr/bin/env python3
"""Search Wikipedia using CirrusSearch for flexible article discovery.

Usage:
    # Basic keyword search
    python scripts/search_articles.py --query "climate change mitigation"

    # CirrusSearch operators
    python scripts/search_articles.py --query 'incategory:"Climate change" hastemplate:"Infobox country"'

    # Find articles linking to a specific page
    python scripts/search_articles.py --query 'linksto:"Climate change"' --limit 500

    # Find articles similar to a given article
    python scripts/search_articles.py --query 'morelike:"Effects of climate change"'

    # Title search only
    python scripts/search_articles.py --query 'intitle:"climate change"' --limit 1000
"""

import argparse
import json
import sys

from config import api_query_all


def search_articles(query, limit=500, include_snippets=False):
    """Search Wikipedia using CirrusSearch.

    Returns list of result dicts with 'title' and optionally 'snippet'.
    """
    params = {
        'list': 'search',
        'srsearch': query,
        'srnamespace': '0',
        'srlimit': str(min(limit, 500)),
        'srinfo': '',
        'srprop': 'snippet' if include_snippets else '',
    }

    results = []
    for item in api_query_all(params, 'search'):
        entry = {'title': item['title']}
        if include_snippets and 'snippet' in item:
            # Strip HTML tags from snippet
            import re
            entry['snippet'] = re.sub(r'<[^>]+>', '', item['snippet'])
        results.append(entry)
        if len(results) >= limit:
            break

    return results


def main():
    parser = argparse.ArgumentParser(description='Search Wikipedia with CirrusSearch')
    parser.add_argument('--query', '-q', required=True,
                        help='Search query (supports CirrusSearch operators)')
    parser.add_argument('--limit', '-l', type=int, default=500,
                        help='Maximum results to return (default: 500)')
    parser.add_argument('--snippets', '-s', action='store_true',
                        help='Include text snippets in results')

    args = parser.parse_args()

    print(f"Searching: {args.query}", file=sys.stderr)
    results = search_articles(args.query, limit=args.limit, include_snippets=args.snippets)

    output = {
        'query': args.query,
        'articles': [r['title'] for r in results],
        'article_count': len(results),
    }
    if args.snippets:
        output['results_with_snippets'] = results

    print(f"Found {len(results)} results", file=sys.stderr)
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
