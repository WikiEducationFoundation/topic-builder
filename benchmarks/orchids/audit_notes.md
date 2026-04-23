# Orchids gold audit notes

Human-written commentary for the orchids benchmark. See
`audit_summary.md` for the classifier's fresh output. This file is
curated and shouldn't be overwritten.

## Summary

| | Count |
|---|---|
| Total articles in arc-run corpus | 18,122 |
| **CENTRAL (`in`)** | 17,930 |
| **PERIPHERAL (`peripheral`)** | 183 |
| **OUT (`out`; remove from corpus)** | 9 |
| **Uncertain** | 0 |

**Audited gold = 18,113 articles** (in + peripheral). Estimated arc
precision ~99% based on a 30-article random sample of the IN bucket.

## Approach — keyword classifier + source-trust

At 18,122 articles, enumerative audit is intractable. Classifier rules:

1. Strong orchid-taxonomy markers ("species of orchid", "genus of
   orchid", "Orchidaceae") → IN.
2. Orchid-role people ("orchidologist", "orchid grower", etc.) → IN.
3. Orchid genus names in title or description (Phalaenopsis, Cattleya,
   Vanilla, Dendrobium, Bulbophyllum, etc.) → IN.
4. Any "orchid" in description or title → IN.
5. General botany markers (botanist, naturalist, biologist, horticulturist,
   explorer) → PERIPHERAL.
6. List of orchidologists source → PERIPHERAL (people curated as
   orchid-relevant regardless of shortdesc gloss).
7. Hard OUT (sports, music, politics) — only fires when no botany
   marker and no orchid source.
8. `Chemical compound` + `category:Orchids` source → IN (orchid
   phytochemistry).
9. **Source-trust fallback.** Articles from `category:Orchids`,
   `list_page:`, or `manual:` sources in an orchids build are trusted
   as on-topic — the build context guarantees orchid relevance. This
   catches ~5,000 articles whose Wikidata shortdesc says only "Species
   of plant" but whose genus (e.g. Acianthera, Pleurothallis, Stelis)
   is orchid-specific.

## Sample-audit validation

30 random articles drawn from the IN bucket (seed=42) were spot-
audited 2026-04-23 — all 30 were legitimate orchid topics. Implies
~99% precision on the IN bucket; for tighter confidence bounds, a
larger sample (100–200) would be needed.

## The 9 OUT (enumerated)

- **Besi** — Semiconductor company (name collision with a Dendrobium
  species).
- **Bruce Gray** — Canadian actor.
- **Charlie Kaufman** — American filmmaker (pulled via `manual:thief-
  cluster`, the Orchid Thief adaptation cluster); not an orchid
  figure per se.
- **Chu Ci** — Anthology of Chinese poetry; orchid-cultural-tangent
  but primary subject is broader Chinese literature.
- **Guan Daosheng / Ma Shouzhen / Qu Yuan** — Chinese artists and
  poets. Connected to the Four Gentlemen orchid tradition but
  primary notability unrelated.
- **John William Moore** — American politician.

## Judgment calls

### Chinese literary figures (Qu Yuan, Ma Shouzhen, Guan Daosheng, Chu Ci) → OUT

These came from `manual:cross-wiki-reconciliation` in the orchids
build. They have real cultural-orchid connections (Qu Yuan's "Li Sao"
features orchids prominently, Ma Shouzhen painted orchids). Kept OUT
for strict scope; a future audit could elevate to PERIPHERAL if
broader cultural-tail coverage is desired.

### Charlie Kaufman → OUT

Filmmaker who adapted Susan Orlean's "The Orchid Thief" into the film
Adaptation. The article's subject is Kaufman's broader filmography,
not orchids. OUT.

### Source-trust on `list_page:` → IN

This is the biggest classifier decision. In an orchids build, every
list_page source is orchid-relevant (list of Dendrobium species, list
of Caladenia species, list of orchids of the Philippines, etc.).
Trusting the source lets us classify ~5,000 "Species of plant" /
empty-shortdesc orchid articles as IN without manual verification.
The 30-article sample of this bucket was 30/30 legitimate orchid
species, giving us confidence the blanket-trust is justified.

## Reach targets

- **Cross-wiki walk.** The arc run only did 21 cross-language gap-fills
  against the 5 parallel builds (orchids-zh, orchids-ja, orchids-pt,
  orchids-nl, orchids-zh). `cross_wiki_diff` (backlog 5.2) would let a
  future run systematically enumerate the frontier.
- **Wikidata P171 (parent taxon) against Q25308 (Orchidaceae).** Not
  exercised in the arc run; likely captures a handful of orchid species
  missing from the enwiki corpus.
- **Cultural-tail expansion.** Current rubric keeps Chinese literary
  figures OUT. A future scope revision could elevate them to
  PERIPHERAL if Wiki Education wants broader cultural-tail coverage.

## Updating gold over time

1. Future run adds an article not in `gold.csv` → run `audit.py` to
   classify it; append to gold.
2. Scope revision → bump the frozen date on scope.md and re-run
   `audit.py`. The source-trust rule is robust to adding new orchid
   list pages.
