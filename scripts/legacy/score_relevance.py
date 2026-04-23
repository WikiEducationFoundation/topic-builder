#!/usr/bin/env python3
"""Score article titles for relevance to a topic using keyword/pattern heuristics.

This provides a fast first-pass scoring. The LLM reviews borderline cases afterward.

Usage:
    python scripts/score_relevance.py --input articles.json --topic "climate change"
    python scripts/score_relevance.py --input articles.json --topic "climate change" --threshold 7
"""

import argparse
import json
import re
import sys


# Climate change relevance signals — (pattern, score_boost, description)
# These are additive: an article matching multiple patterns gets the highest applicable score
CLIMATE_CHANGE_SIGNALS = {
    # Direct climate change (score 9-10)
    'direct': [
        (r'climate change', 10),
        (r'global warming', 10),
        (r'greenhouse effect', 9),
        (r'climate crisis', 10),
        (r'climate emergency', 10),
        (r'anthropogenic.*warming', 10),
        (r'attribution of.*climate', 10),
        (r'effects? of climate', 10),
        (r'impact of climate', 10),
        (r'climate adaptation', 9),
        (r'climate mitigation', 9),
        (r'climate action', 9),
        (r'climate justice', 9),
        (r'climate denial', 9),
        (r'climate skep', 9),
        (r'climate sensitivity', 9),
        (r'climate model', 9),
        (r'climate feedback', 9),
        (r'climate variability', 8),
        (r'climate system', 8),
        (r'climate science', 9),
        (r'climate policy', 9),
        (r'climate law', 9),
        (r'climate litigation', 9),
        (r'climate financ', 9),
        (r'climate communi', 9),
        (r'climate governance', 9),
        (r'climate movement', 9),
        (r'climate activist', 9),
        (r'climate protest', 9),
        (r'climate strike', 9),
        (r'climate refugee', 9),
        (r'climate migration', 9),
        (r'climate target', 9),
        (r'climate pledge', 9),
        (r'climate summit', 9),
    ],
    # Strong climate connection (score 7-8)
    'strong': [
        (r'greenhouse gas', 8),
        (r'carbon emission', 8),
        (r'carbon dioxide.*atmosph', 8),
        (r'carbon tax', 8),
        (r'carbon trading', 8),
        (r'carbon capture', 8),
        (r'carbon sequestration', 8),
        (r'carbon offset', 8),
        (r'carbon neutral', 8),
        (r'carbon budget', 8),
        (r'carbon footprint', 8),
        (r'carbon sink', 8),
        (r'net zero', 8),
        (r'emission.?reduction', 8),
        (r'emission.?trading', 8),
        (r'sea.?level rise', 8),
        (r'ocean acidification', 8),
        (r'ocean warming', 8),
        (r'arctic.*warming', 8),
        (r'arctic.*melt', 8),
        (r'ice.*sheet.*loss', 8),
        (r'glacier.*retreat', 8),
        (r'permafrost.*thaw', 8),
        (r'deforestation', 7),
        (r'reforestation', 7),
        (r'afforestation', 7),
        (r'ipcc', 8),
        (r'intergovernmental panel', 8),
        (r'unfccc', 8),
        (r'paris agreement', 8),
        (r'kyoto protocol', 8),
        (r'cop\s?\d', 8),
        (r'united nations.*climate', 8),
        (r'methane emission', 8),
        (r'carbon dioxide', 7),
        (r'fossil fuel', 7),
        (r'coal phase.?out', 8),
        (r'fossil.*phase.?out', 8),
        (r'geoengineering', 8),
        (r'solar radiation management', 8),
        (r'carbon dioxide removal', 8),
        (r'direct air capture', 8),
        (r'tipping point.*climat', 9),
        (r'climate tipping', 9),
        (r'planetary boundar', 8),
    ],
    # Moderate connection (score 5-6)
    'moderate': [
        (r'renewable energy', 6),
        (r'solar power', 5),
        (r'solar energy', 5),
        (r'wind power', 5),
        (r'wind energy', 5),
        (r'wind farm', 5),
        (r'hydroelectric', 5),
        (r'geothermal', 5),
        (r'clean energy', 6),
        (r'energy transition', 7),
        (r'energy efficiency', 5),
        (r'electric vehicle', 5),
        (r'sustainable develop', 5),
        (r'sustainability', 4),
        (r'biodiversity loss', 6),
        (r'mass extinction', 6),
        (r'species.*extinct', 5),
        (r'coral.*bleach', 7),
        (r'coral reef', 5),
        (r'drought', 5),
        (r'heatwave|heat wave', 6),
        (r'wildfire', 5),
        (r'flood', 4),
        (r'hurricane', 4),
        (r'cyclone', 4),
        (r'extreme weather', 7),
        (r'weather.*extreme', 7),
        (r'air pollution', 5),
        (r'air quality', 4),
        (r'ozone.*depletion', 6),
        (r'ozone layer', 6),
        (r'aerosol', 5),
        (r'albedo', 6),
        (r'radiative forc', 8),
        (r'thermal expansion', 6),
        (r'ice core', 7),
        (r'paleoclimate', 8),
        (r'holocene', 6),
        (r'pleistocene', 5),
        (r'little ice age', 7),
        (r'medieval warm', 7),
        (r'milankovitch', 7),
        (r'el ni[ñn]o', 6),
        (r'la ni[ñn]a', 6),
        (r'thermohaline', 7),
        (r'atlantic.*overturning', 8),
        (r'amoc', 8),
        (r'nuclear power', 4),
        (r'natural gas', 4),
        (r'coal.?fired', 5),
        (r'power plant', 3),
        (r'power station', 3),
        (r'emission', 6),
    ],
}


def score_title(title, topic='climate change'):
    """Score a single title for relevance. Returns (score, matching_signals)."""
    lower = title.lower()
    best_score = 1  # default: not relevant
    signals = []

    for category, patterns in CLIMATE_CHANGE_SIGNALS.items():
        for pattern, score in patterns:
            if re.search(pattern, lower):
                if score > best_score:
                    best_score = score
                signals.append((pattern, score))

    return best_score, signals


def main():
    parser = argparse.ArgumentParser(description='Score article titles for topic relevance')
    parser.add_argument('--input', '-i', required=True,
                        help='JSON file with article list (array or {"articles": [...]})')
    parser.add_argument('--topic', '-t', default='climate change',
                        help='Topic name (currently only climate change is supported)')
    parser.add_argument('--threshold', type=int, default=0,
                        help='Only output articles at or above this score')
    parser.add_argument('--show-signals', action='store_true',
                        help='Show which patterns matched for each article')

    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)
    if isinstance(data, list):
        articles = data
    elif isinstance(data, dict) and 'articles' in data:
        articles = data['articles']
    else:
        articles = data

    scored = []
    for title in articles:
        score, signals = score_title(title)
        entry = {'title': title, 'score': score}
        if args.show_signals and signals:
            entry['signals'] = [s[0] for s in signals]
        scored.append(entry)

    # Sort by score descending
    scored.sort(key=lambda x: (-x['score'], x['title']))

    if args.threshold > 0:
        scored = [s for s in scored if s['score'] >= args.threshold]

    # Summary stats
    from collections import Counter
    dist = Counter(s['score'] for s in scored)
    print(f"Score distribution:", file=sys.stderr)
    for score in sorted(dist.keys(), reverse=True):
        print(f"  {score}: {dist[score]} articles", file=sys.stderr)
    print(f"Total: {len(scored)} articles", file=sys.stderr)

    output = {
        'scored_articles': scored,
        'total': len(scored),
        'distribution': {str(k): v for k, v in sorted(dist.items(), reverse=True)},
    }
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
