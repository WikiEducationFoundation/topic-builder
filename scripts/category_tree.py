#!/usr/bin/env python3
"""Crawl a Wikipedia category tree and collect article titles.

Usage:
    # Survey subcategories only (reconnaissance)
    python scripts/category_tree.py --category "Climate change" --depth 1 --subcats-only

    # Collect all articles to depth 3
    python scripts/category_tree.py --category "Climate change" --depth 3

    # Exclude specific branches
    python scripts/category_tree.py --category "Climate change" --depth 3 \
        --exclude "Climate change in fiction" "Climate change denial"

    # Set a max article limit
    python scripts/category_tree.py --category "Climate change" --depth 4 --max-articles 10000
"""

import argparse
import collections
import json
import sys

from config import api_query_all, normalize_title


def get_subcategories(category):
    """Get immediate subcategories of a category."""
    params = {
        'list': 'categorymembers',
        'cmtitle': f'Category:{category}',
        'cmtype': 'subcat',
        'cmlimit': '500',
    }
    for item in api_query_all(params, 'categorymembers'):
        # Strip "Category:" prefix
        title = item['title']
        if title.startswith('Category:'):
            title = title[len('Category:'):]
        yield title


def get_category_articles(category):
    """Get articles (pages) directly in a category."""
    params = {
        'list': 'categorymembers',
        'cmtitle': f'Category:{category}',
        'cmtype': 'page',
        'cmnamespace': '0',  # mainspace only
        'cmlimit': '500',
    }
    for item in api_query_all(params, 'categorymembers'):
        yield normalize_title(item['title'])


def crawl_category_tree(root_category, max_depth, exclude=None, subcats_only=False, max_articles=50000):
    """BFS crawl of category tree.

    Returns:
        dict with 'articles', 'categories_visited', 'categories_by_depth', 'stats'
    """
    exclude = set(exclude or [])
    articles = set()
    categories_visited = set()
    categories_by_depth = collections.defaultdict(list)

    # BFS queue: (category_name, depth)
    queue = collections.deque([(root_category, 0)])
    categories_visited.add(root_category)
    categories_by_depth[0].append(root_category)

    article_limit_hit = False

    while queue:
        category, depth = queue.popleft()

        # Collect articles from this category (unless subcats-only mode)
        if not subcats_only:
            if len(articles) >= max_articles:
                article_limit_hit = True
                break

            count_before = len(articles)
            for title in get_category_articles(category):
                articles.add(title)
                if len(articles) >= max_articles:
                    article_limit_hit = True
                    break

            added = len(articles) - count_before
            if added > 0:
                print(f"  {category}: +{added} articles (total: {len(articles)})", file=sys.stderr)

        # Traverse subcategories if within depth limit
        if depth < max_depth:
            for subcat in get_subcategories(category):
                if subcat in categories_visited:
                    continue
                if subcat in exclude:
                    print(f"  Excluding: {subcat}", file=sys.stderr)
                    continue
                categories_visited.add(subcat)
                categories_by_depth[depth + 1].append(subcat)
                queue.append((subcat, depth + 1))

    result = {
        'articles': sorted(articles),
        'article_count': len(articles),
        'categories_visited': sorted(categories_visited),
        'category_count': len(categories_visited),
        'categories_by_depth': {str(d): sorted(cats) for d, cats in sorted(categories_by_depth.items())},
        'stats': {
            'root_category': root_category,
            'max_depth': max_depth,
            'excluded': sorted(exclude),
            'article_limit_hit': article_limit_hit,
            'max_articles': max_articles,
        }
    }

    if subcats_only:
        del result['articles']
        del result['article_count']

    return result


def main():
    parser = argparse.ArgumentParser(description='Crawl Wikipedia category tree')
    parser.add_argument('--category', '-c', required=True,
                        help='Root category name (without "Category:" prefix)')
    parser.add_argument('--depth', '-d', type=int, default=1,
                        help='Maximum depth to crawl (default: 1)')
    parser.add_argument('--exclude', '-e', nargs='*', default=[],
                        help='Category names to exclude (prune entire branch)')
    parser.add_argument('--subcats-only', '-s', action='store_true',
                        help='Only list subcategories, do not collect articles')
    parser.add_argument('--max-articles', '-m', type=int, default=50000,
                        help='Maximum number of articles to collect (default: 50000)')

    args = parser.parse_args()

    print(f"Crawling Category:{args.category} to depth {args.depth}...", file=sys.stderr)
    result = crawl_category_tree(
        root_category=args.category,
        max_depth=args.depth,
        exclude=args.exclude,
        subcats_only=args.subcats_only,
        max_articles=args.max_articles,
    )

    if args.subcats_only:
        print(f"\nFound {result['category_count']} categories", file=sys.stderr)
    else:
        print(f"\nFound {result['article_count']} articles across {result['category_count']} categories", file=sys.stderr)

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
