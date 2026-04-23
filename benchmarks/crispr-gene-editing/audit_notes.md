# CRISPR gene editing gold audit notes

Human-written commentary for the CRISPR benchmark. See
`audit_summary.md` for the classifier's fresh output. This file is
curated and shouldn't be overwritten.

## Summary

| | Count |
|---|---|
| Total articles in arc-run corpus | 99 |
| **CENTRAL (`in`)** | 50 |
| **PERIPHERAL (`peripheral`)** | 32 |
| **OUT (`out`; remove from corpus)** | 17 |
| **Uncertain** | 0 |

**Audited gold = 82 articles** (in + peripheral).

## Comparison to Apollo 11 baseline

| Metric | Apollo 11 | CRISPR |
|---|---|---|
| Arc corpus size | 699 | 99 |
| Audited gold | 137 | 82 |
| **Precision (arc run)** | **19.6%** | **82.8%** |
| Triangulation at export | 30.3% multi | 0% multi (single-source) |
| Arc tool-call count | 50 | 14 |
| Arc API-call count | 478 | 46 |
| AI self-rating | 7 | 8 |

CRISPR's precision is 4× Apollo 11's. The topic shape rewarded Codex's
distinctive-vocabulary approach: one lexical search + one similarity
pass + manual trim. Apollo 11's broad category pulls hit orders of
magnitude more noise. This makes CRISPR a different kind of ratchet
target: hard to improve precision further (already high), easy to
improve reach (the single-source corpus probably misses several
on-topic articles).

## Judgment calls worth Sage's eyeball

### 1. Sean Parker → PERIPHERAL

Funded the Parker Institute for Cancer Immunotherapy (CRISPR trials).
Core notability is Napster/Facebook, not CRISPR. Defensible OUT.

### 2. University of California, Berkeley → PERIPHERAL

Doudna's institution, central to CRISPR patent history. Article itself
is broad. Defensible OUT.

### 3. Chen Hu / Deng Hongkui → PERIPHERAL

Chinese stem-cell researchers in He Jiankui orbit. Articles aren't
CRISPR-focused. Defensible OUT.

### 4. Thalassemia → OUT; Beta thalassemia → PERIPHERAL

Generic disease umbrella OUT; specific CRISPR-therapy target PERIPHERAL.

### 5. Small nucleolar RNA / Insert (molecular biology) → PERIPHERAL

Adjacent molecular biology. Defensible OUT if stricter scope.

### 6. Genetically modified animal / crops → PERIPHERAL

Broader than CRISPR but overlap is substantive.

### 7. Human germline engineering → CENTRAL

Kept CENTRAL because CRISPR dominates the technology and the
He Jiankui affair is central to the article.

## Distribution of the 17 OUT

All lexical-search noise from Codex's broad `search:crispr-gene-editing`
call. Codex already removed 13 before export; these 17 slipped through.
Pattern:

- Generic-noun concepts: Technology, Transport, Vehicle, Plastic,
  Cement, Submarine, Incandescent light bulb, Integrated circuit,
  High tech
- Tangential one-chapter touches: Sputnik crisis, Terraforming of
  Mars, Fully Automated Luxury Communism
- Random contextual pulls: Umeå (researcher city?), Ark Invest
  (asset manager), Non-fungible token
- Overly-generic lists: List of inventions and discoveries by women
- Disease umbrella: Thalassemia

**Ratchet target:** a future run with better relevance filtering
(`auto_score_by_description` with appropriate markers, or centrality
scoring once that lands) should drive this toward 0.

## Reach targets — on-topic articles likely NOT in current gold

From domain knowledge of CRISPR:

- **Emmanuelle Charpentier** — Doudna's 2020 Nobel co-laureate. Should
  be CENTRAL; isn't in current corpus. Notable miss.
- **David Liu** — prime-editing inventor (Broad Institute).
- **Base editing** as a standalone article.
- **Cpf1** / **Cas13** / **Cas14** / **SaCas9** — alternative Cas
  variants with distinct applications.
- **Philippe Horvath** — Barrangou's co-researcher on CRISPR bacterial
  immunity.
- **Streptococcus thermophilus** — original CRISPR-discovery organism.

Each is a direct reach candidate for future Wikidata-P101 probing.

## Updating the gold

When a future run adds an article not in current `gold.csv`, run
`audit.py` against the new addition. If it passes as in or peripheral,
it joins the gold.
