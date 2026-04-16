#!/usr/bin/env python3
"""Fetch article extracts from Wikipedia and score relevance based on content.

Much more accurate than title-only scoring because the article intro reveals
what the article is actually about.

Usage:
    python scripts/extract_scorer.py --input articles.json --topic "climate change" --threshold 7
"""

import argparse
import json
import re
import sys
import time

from config import api_query, normalize_title


# Keywords to look for in article extracts, with weights
CLIMATE_EXTRACT_SIGNALS = [
    # Direct climate terms (high signal)
    (r'climate change', 5),
    (r'global warming', 5),
    (r'greenhouse gas', 4),
    (r'greenhouse effect', 4),
    (r'carbon dioxide|CO2|CO₂', 3),
    (r'carbon emission', 4),
    (r'fossil fuel', 3),
    (r'climate crisis', 5),
    (r'climate action', 4),
    (r'climate policy', 4),
    (r'climate science', 4),
    (r'climate model', 4),
    (r'climate system', 3),
    (r'climate activist', 4),
    (r'climate movement', 4),
    (r'climate justice', 4),
    (r'climatolog', 4),
    (r'ipcc|intergovernmental panel on climate', 4),
    (r'unfccc|united nations framework convention', 4),
    (r'paris agreement', 4),
    (r'kyoto protocol', 4),

    # Environmental/atmospheric (medium signal)
    (r'emission', 2),
    (r'carbon', 2),
    (r'methane', 2),
    (r'atmosphere|atmospheric', 2),
    (r'temperature', 1),
    (r'warming', 2),
    (r'sea level', 3),
    (r'ocean acidif', 4),
    (r'deforestation', 3),
    (r'renewable energy', 2),
    (r'clean energy', 2),
    (r'energy transition', 3),
    (r'decarboni', 4),
    (r'net.?zero', 4),
    (r'sustainability|sustainable', 1),
    (r'environment', 1),
    (r'ecological', 1),
    (r'biodiversity', 1),
    (r'conservation', 1),
    (r'pollution', 1),
    (r'ozone', 2),
    (r'aerosol', 2),
    (r'radiative', 3),
    (r'albedo', 3),
    (r'ice sheet|ice cap|glacier|glacial', 2),
    (r'permafrost', 3),
    (r'paleoclimate', 3),
    (r'geoengineering', 4),
    (r'carbon capture', 4),
    (r'carbon sequestration', 4),
    (r'extreme weather', 3),
    (r'drought', 1),
    (r'flood', 1),
    (r'wildfire', 1),
    (r'heat wave|heatwave', 2),
    (r'coral bleach', 3),
    (r'species.*extinct|extinction', 1),
    (r'ecosystem', 1),
]

# Score thresholds for weighted sum
# Sum >= 8: score 9 (very relevant)
# Sum >= 5: score 7
# Sum >= 3: score 5
# Sum >= 1: score 3
# Sum == 0: score 1


def score_extract(extract_text):
    """Score an article extract for climate change relevance.

    Returns (score 1-10, total_weight, matched_terms).
    """
    if not extract_text:
        return 1, 0, []

    lower = extract_text.lower()
    total_weight = 0
    matched = []

    for pattern, weight in CLIMATE_EXTRACT_SIGNALS:
        matches = re.findall(pattern, lower)
        if matches:
            total_weight += weight * min(len(matches), 3)  # cap at 3 occurrences
            matched.append(pattern)

    # Convert weight to score
    if total_weight >= 10:
        score = 10
    elif total_weight >= 7:
        score = 9
    elif total_weight >= 5:
        score = 8
    elif total_weight >= 4:
        score = 7
    elif total_weight >= 3:
        score = 6
    elif total_weight >= 2:
        score = 5
    elif total_weight >= 1:
        score = 4
    else:
        score = 1

    return score, total_weight, matched


def fetch_extracts_batch(titles, batch_size=50):
    """Fetch article extracts in batches. Returns dict of title -> extract."""
    extracts = {}
    title_list = list(titles)

    for i in range(0, len(title_list), batch_size):
        batch = title_list[i:i + batch_size]
        params = {
            'titles': '|'.join(batch),
            'prop': 'extracts',
            'exintro': 'true',
            'explaintext': 'true',
            'exsentences': '5',  # first 5 sentences
        }
        data = api_query(params)

        if 'query' in data and 'pages' in data['query']:
            for page in data['query']['pages']:
                if not page.get('missing', False):
                    title = normalize_title(page['title'])
                    extract = page.get('extract', '')
                    extracts[title] = extract

        done = min(i + batch_size, len(title_list))
        print(f"  Fetched extracts: {done}/{len(title_list)}", file=sys.stderr)

    return extracts


def main():
    parser = argparse.ArgumentParser(description='Score articles using Wikipedia extracts')
    parser.add_argument('--input', '-i', required=True,
                        help='JSON file with article titles')
    parser.add_argument('--topic', '-t', default='climate change')
    parser.add_argument('--threshold', type=int, default=0,
                        help='Only output articles at or above this score')
    parser.add_argument('--output-all', action='store_true',
                        help='Output all articles with scores (not just above threshold)')

    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)
    if isinstance(data, list):
        titles = data
    elif isinstance(data, dict) and 'articles' in data:
        titles = data['articles']
    else:
        titles = list(data)

    print(f"Fetching extracts for {len(titles)} articles...", file=sys.stderr)
    extracts = fetch_extracts_batch(titles)
    print(f"Got extracts for {len(extracts)} articles", file=sys.stderr)

    scored = []
    for title in titles:
        extract = extracts.get(title, '')
        score, weight, matched = score_extract(extract)
        entry = {
            'title': title,
            'score': score,
            'weight': weight,
        }
        scored.append(entry)

    scored.sort(key=lambda x: (-x['score'], x['title']))

    if args.threshold > 0 and not args.output_all:
        output_scored = [s for s in scored if s['score'] >= args.threshold]
    else:
        output_scored = scored

    # Stats
    from collections import Counter
    dist = Counter(s['score'] for s in scored)
    print(f"\nScore distribution:", file=sys.stderr)
    for score_val in sorted(dist.keys(), reverse=True):
        print(f"  {score_val}: {dist[score_val]} articles", file=sys.stderr)
    above_threshold = sum(1 for s in scored if s['score'] >= (args.threshold or 7))
    print(f"Articles scoring {args.threshold or 7}+: {above_threshold}", file=sys.stderr)

    output = {
        'scored_articles': output_scored,
        'total_scored': len(scored),
        'total_output': len(output_scored),
        'distribution': {str(k): v for k, v in sorted(dist.items(), reverse=True)},
    }
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
