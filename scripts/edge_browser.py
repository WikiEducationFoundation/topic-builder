#!/usr/bin/env python3
"""Browse outgoing links from articles to find related articles not yet in the topic.

Takes a set of "seed" articles (already included in the topic) and finds articles
they link to that aren't yet included. Articles linked by multiple seeds are
more likely to be relevant.

Usage:
    # Find articles linked from the top-confidence articles that aren't in the topic yet
    python scripts/edge_browser.py --seeds seeds.json --existing included.json --min-links 3
"""

import argparse
import json
import sys
from collections import Counter

from config import api_query, normalize_title, WIKIPEDIA_API, api_get


def get_outgoing_links(title):
    """Get all mainspace article links from a page."""
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'links',
        'plnamespace': '0',
        'pllimit': '500',
        'format': 'json',
        'formatversion': '2',
    }

    links = []
    while True:
        data = api_get(WIKIPEDIA_API, params)
        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                for link in page.get('links', []):
                    links.append(normalize_title(link['title']))

        if 'continue' in data:
            params.update(data['continue'])
        else:
            break

    return links


def main():
    parser = argparse.ArgumentParser(description='Browse edges of topic for missed articles')
    parser.add_argument('--seeds', '-s', required=True,
                        help='JSON file with seed article titles to browse from')
    parser.add_argument('--existing', '-e', required=True,
                        help='JSON file with already-included article titles')
    parser.add_argument('--min-links', '-m', type=int, default=3,
                        help='Minimum number of seed articles that must link to a candidate (default: 3)')
    parser.add_argument('--max-seeds', type=int, default=200,
                        help='Maximum number of seed articles to browse (default: 200)')

    args = parser.parse_args()

    with open(args.seeds) as f:
        seeds = json.load(f)
    if isinstance(seeds, dict):
        seeds = seeds.get('articles', list(seeds.keys()))

    with open(args.existing) as f:
        existing = set(json.load(f))

    # Limit seeds
    seeds = seeds[:args.max_seeds]

    print(f"Browsing links from {len(seeds)} seed articles...", file=sys.stderr)
    print(f"Existing topic has {len(existing)} articles", file=sys.stderr)

    # Count how many seeds link to each external article
    link_counts = Counter()
    linking_seeds = {}  # article -> list of seeds that link to it

    for i, seed in enumerate(seeds):
        links = get_outgoing_links(seed)
        for link in links:
            if link not in existing:
                link_counts[link] += 1
                if link not in linking_seeds:
                    linking_seeds[link] = []
                linking_seeds[link].append(seed)

        if (i + 1) % 20 == 0:
            print(f"  Browsed {i+1}/{len(seeds)} seeds...", file=sys.stderr)

    # Filter by minimum link count
    candidates = [(article, count) for article, count in link_counts.most_common()
                   if count >= args.min_links]

    print(f"\nFound {len(candidates)} candidates linked by {args.min_links}+ seeds", file=sys.stderr)

    output = {
        'candidates': [
            {
                'title': article,
                'linked_by_count': count,
                'linked_by_seeds': linking_seeds[article][:10],  # cap at 10 examples
            }
            for article, count in candidates
        ],
        'candidate_count': len(candidates),
        'seeds_browsed': len(seeds),
        'min_links': args.min_links,
    }

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
