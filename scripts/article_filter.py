#!/usr/bin/env python3
"""Filter and clean article lists: deduplicate, resolve redirects, remove non-articles.

Usage:
    # Full filter pipeline on a JSON article list
    python scripts/article_filter.py --input results.json --resolve-redirects --filter-disambig --filter-lists

    # Just deduplicate and normalize
    python scripts/article_filter.py --input results.json

    # Filter a plain text file (one title per line)
    python scripts/article_filter.py --input-text titles.txt --resolve-redirects

    # Read from stdin (pipe from another script)
    python scripts/category_tree.py -c "Climate change" -d 2 | python scripts/article_filter.py --resolve-redirects
"""

import argparse
import json
import sys

from config import api_query, normalize_title


def deduplicate(titles):
    """Deduplicate titles after normalization. Returns sorted unique list."""
    seen = set()
    unique = []
    for title in titles:
        normalized = normalize_title(title)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return sorted(unique)


def resolve_redirects(titles, batch_size=50):
    """Resolve redirects in batches. Returns dict mapping original -> resolved title."""
    resolved = {}
    title_list = list(titles)

    for i in range(0, len(title_list), batch_size):
        batch = title_list[i:i + batch_size]
        params = {
            'titles': '|'.join(batch),
            'redirects': '1',
        }
        data = api_query(params)

        # Build redirect map from this batch
        redirect_map = {}
        if 'query' in data:
            # Handle normalized titles
            for norm in data['query'].get('normalized', []):
                redirect_map[norm['from']] = norm['to']

            # Handle redirects
            for redir in data['query'].get('redirects', []):
                redirect_map[redir['from']] = redir['to']

        # Resolve each title in the batch
        for title in batch:
            current = title
            # Follow the chain (normalization then redirect)
            for _ in range(5):  # max chain depth
                if current in redirect_map:
                    current = redirect_map[current]
                else:
                    break
            resolved[title] = normalize_title(current)

        done = min(i + batch_size, len(title_list))
        print(f"  Resolved redirects: {done}/{len(title_list)}", file=sys.stderr)

    return resolved


def find_disambiguation_pages(titles, batch_size=50):
    """Identify disambiguation pages. Returns set of titles that are disambig pages."""
    disambig = set()
    title_list = list(titles)

    for i in range(0, len(title_list), batch_size):
        batch = title_list[i:i + batch_size]
        params = {
            'titles': '|'.join(batch),
            'prop': 'pageprops',
            'ppprop': 'disambiguation',
        }
        data = api_query(params)

        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                if 'pageprops' in page and 'disambiguation' in page['pageprops']:
                    disambig.add(normalize_title(page['title']))

    return disambig


def find_missing_pages(titles, batch_size=50):
    """Identify titles that don't exist as pages. Returns set of missing titles."""
    missing = set()
    title_list = list(titles)

    for i in range(0, len(title_list), batch_size):
        batch = title_list[i:i + batch_size]
        params = {
            'titles': '|'.join(batch),
            'prop': 'info',
        }
        data = api_query(params)

        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                if page.get('missing', False):
                    missing.add(normalize_title(page['title']))

    return missing


def is_list_page(title):
    """Check if a title looks like a list/index/outline page."""
    lower = title.lower()
    return (lower.startswith('list of ') or
            lower.startswith('lists of ') or
            lower.startswith('index of ') or
            lower.startswith('outline of '))


def filter_articles(titles, resolve_redir=False, filter_disambig=False,
                    filter_lists=False, filter_missing=False):
    """Run the full filter pipeline. Returns filtered list and stats."""
    stats = {'input_count': len(titles)}

    # Step 1: normalize and deduplicate
    titles = deduplicate(titles)
    stats['after_dedup'] = len(titles)

    # Step 2: resolve redirects
    if resolve_redir:
        print("Resolving redirects...", file=sys.stderr)
        redirect_map = resolve_redirects(titles)
        redirected_count = sum(1 for t in titles if redirect_map.get(t, t) != t)
        titles = deduplicate(redirect_map[t] for t in titles)
        stats['redirects_resolved'] = redirected_count
        stats['after_redirects'] = len(titles)

    # Step 3: filter disambiguation pages
    if filter_disambig:
        print("Checking for disambiguation pages...", file=sys.stderr)
        disambig = find_disambiguation_pages(titles)
        titles = [t for t in titles if t not in disambig]
        stats['disambig_removed'] = len(disambig)
        stats['after_disambig'] = len(titles)

    # Step 4: filter list/index/outline pages
    if filter_lists:
        list_pages = [t for t in titles if is_list_page(t)]
        titles = [t for t in titles if not is_list_page(t)]
        stats['lists_removed'] = len(list_pages)
        stats['lists_removed_titles'] = list_pages
        stats['after_lists'] = len(titles)

    # Step 5: filter missing pages
    if filter_missing:
        print("Checking for missing pages...", file=sys.stderr)
        missing = find_missing_pages(titles)
        titles = [t for t in titles if t not in missing]
        stats['missing_removed'] = len(missing)
        stats['after_missing'] = len(titles)

    stats['final_count'] = len(titles)
    return titles, stats


def main():
    parser = argparse.ArgumentParser(description='Filter and clean Wikipedia article lists')
    parser.add_argument('--input', '-i',
                        help='JSON file with articles (expects {"articles": [...]} or [...])')
    parser.add_argument('--input-text',
                        help='Plain text file with one title per line')
    parser.add_argument('--resolve-redirects', '-r', action='store_true',
                        help='Resolve redirects to canonical titles')
    parser.add_argument('--filter-disambig', action='store_true',
                        help='Remove disambiguation pages')
    parser.add_argument('--filter-lists', action='store_true',
                        help='Remove "List of...", "Index of...", "Outline of..." pages')
    parser.add_argument('--filter-missing', action='store_true',
                        help='Remove titles that do not exist as pages')

    args = parser.parse_args()

    # Load titles
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
        if isinstance(data, list):
            titles = data
        elif isinstance(data, dict) and 'articles' in data:
            titles = data['articles']
        else:
            print("Error: JSON must be a list or have an 'articles' key", file=sys.stderr)
            sys.exit(1)
    elif args.input_text:
        with open(args.input_text) as f:
            titles = [line.strip() for line in f if line.strip()]
    else:
        # Read from stdin (expect JSON)
        data = json.load(sys.stdin)
        if isinstance(data, list):
            titles = data
        elif isinstance(data, dict) and 'articles' in data:
            titles = data['articles']
        else:
            print("Error: JSON must be a list or have an 'articles' key", file=sys.stderr)
            sys.exit(1)

    titles, stats = filter_articles(
        titles,
        resolve_redir=args.resolve_redirects,
        filter_disambig=args.filter_disambig,
        filter_lists=args.filter_lists,
        filter_missing=args.filter_missing,
    )

    result = {
        'articles': titles,
        'article_count': len(titles),
        'stats': stats,
    }

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
