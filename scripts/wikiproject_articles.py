#!/usr/bin/env python3
"""Find articles tagged by a WikiProject's assessment banner.

Usage:
    # Get all articles tagged by WikiProject Climate change
    python scripts/wikiproject_articles.py --project "Climate change"

    # Check if a WikiProject exists first
    python scripts/wikiproject_articles.py --project "Climate change" --check-only
"""

import argparse
import json
import sys

from config import api_query, api_query_all, normalize_title


def check_wikiproject_exists(project_name):
    """Check if a WikiProject banner template exists."""
    template_title = f"Template:WikiProject {project_name}"
    params = {
        'titles': template_title,
        'prop': 'info',
    }
    data = api_query(params)
    if 'query' in data and 'pages' in data['query']:
        for page in data['query']['pages']:
            if not page.get('missing', False):
                return True
    return False


def get_wikiproject_articles(project_name, max_articles=50000):
    """Get all articles tagged by a WikiProject banner.

    Uses list=embeddedin to find talk pages that transclude the WikiProject template,
    then strips the Talk: prefix to get article titles.
    """
    template_title = f"Template:WikiProject {project_name}"
    params = {
        'list': 'embeddedin',
        'eititle': template_title,
        'einamespace': '1',  # Talk namespace
        'eilimit': '500',
    }

    articles = []
    for item in api_query_all(params, 'embeddedin'):
        title = item['title']
        # Strip "Talk:" prefix
        if title.startswith('Talk:'):
            title = title[len('Talk:'):]
        articles.append(normalize_title(title))

        if len(articles) >= max_articles:
            break

        if len(articles) % 1000 == 0:
            print(f"  Found {len(articles)} articles so far...", file=sys.stderr)

    return articles


def main():
    parser = argparse.ArgumentParser(description='Find articles tagged by a WikiProject')
    parser.add_argument('--project', '-p', required=True,
                        help='WikiProject name (e.g., "Climate change")')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check if the WikiProject template exists')
    parser.add_argument('--max-articles', '-m', type=int, default=50000,
                        help='Maximum articles to return (default: 50000)')

    args = parser.parse_args()

    if args.check_only:
        exists = check_wikiproject_exists(args.project)
        result = {
            'project': args.project,
            'template': f"Template:WikiProject {args.project}",
            'exists': exists,
        }
        json.dump(result, sys.stdout, indent=2)
        print()
        return

    print(f"Finding articles for WikiProject {args.project}...", file=sys.stderr)

    if not check_wikiproject_exists(args.project):
        print(f"WikiProject template not found: Template:WikiProject {args.project}", file=sys.stderr)
        result = {
            'project': args.project,
            'exists': False,
            'articles': [],
            'article_count': 0,
        }
        json.dump(result, sys.stdout, indent=2)
        print()
        return

    articles = get_wikiproject_articles(args.project, max_articles=args.max_articles)

    result = {
        'project': args.project,
        'exists': True,
        'articles': sorted(set(articles)),
        'article_count': len(set(articles)),
    }

    print(f"Found {result['article_count']} articles", file=sys.stderr)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
