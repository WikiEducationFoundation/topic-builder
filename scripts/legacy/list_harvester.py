#!/usr/bin/env python3
"""Extract article links from "List of..." and "Outline of..." pages.

Usage:
    # Harvest links from a specific list page
    python scripts/list_harvester.py --title "Index of climate change articles"

    # Auto-discover and harvest list/outline pages for a topic
    python scripts/list_harvester.py --search "climate change"
"""

import argparse
import json
import sys

from config import api_query, api_query_all, normalize_title


def get_page_links(title):
    """Get all mainspace article links from a page."""
    params = {
        'titles': title,
        'prop': 'links',
        'plnamespace': '0',
        'pllimit': '500',
    }

    links = []
    # Use continuation manually since prop queries paginate differently
    query_params = dict(params)
    query_params['action'] = 'query'
    query_params['format'] = 'json'
    query_params['formatversion'] = '2'

    from config import api_get, WIKIPEDIA_API
    while True:
        data = api_get(WIKIPEDIA_API, query_params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                for link in page.get('links', []):
                    links.append(normalize_title(link['title']))

        if 'continue' in data:
            query_params.update(data['continue'])
        else:
            break

    return links


def find_list_pages(topic):
    """Find List/Outline/Index pages related to a topic."""
    queries = [
        f'intitle:"List of" intitle:"{topic}"',
        f'intitle:"Outline of" intitle:"{topic}"',
        f'intitle:"Index of" intitle:"{topic}"',
    ]

    pages = []
    for query in queries:
        params = {
            'list': 'search',
            'srsearch': query,
            'srnamespace': '0',
            'srlimit': '20',
            'srinfo': '',
            'srprop': '',
        }
        for item in api_query_all(params, 'search'):
            pages.append(item['title'])

    return pages


def main():
    parser = argparse.ArgumentParser(description='Harvest article links from list pages')
    parser.add_argument('--title', '-t',
                        help='Specific list page title to harvest')
    parser.add_argument('--search', '-s',
                        help='Topic to search for list/outline/index pages')

    args = parser.parse_args()

    if not args.title and not args.search:
        print("Error: provide --title or --search", file=sys.stderr)
        sys.exit(1)

    results = {}

    if args.title:
        pages = [args.title]
    else:
        print(f"Searching for list pages about: {args.search}", file=sys.stderr)
        pages = find_list_pages(args.search)
        print(f"Found {len(pages)} list pages: {pages}", file=sys.stderr)

    for page in pages:
        print(f"Harvesting links from: {page}", file=sys.stderr)
        links = get_page_links(page)
        results[page] = links
        print(f"  Found {len(links)} links", file=sys.stderr)

    # Flatten all articles with source tracking
    all_articles = set()
    for links in results.values():
        all_articles.update(links)

    output = {
        'sources': {page: sorted(links) for page, links in results.items()},
        'articles': sorted(all_articles),
        'article_count': len(all_articles),
    }

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
