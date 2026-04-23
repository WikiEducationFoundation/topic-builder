# Apollo 11 gold audit notes

Human-written commentary for the Apollo 11 benchmark. See
`audit_summary.md` for the classifier's fresh output (regenerated
whenever `audit.py` runs). This file is curated and shouldn't be
overwritten.

## Summary

| | Count |
|---|---|
| Total articles in arc-run corpus | 699 |
| **CENTRAL (`in`)** | 69 |
| **PERIPHERAL (`peripheral`)** | 68 |
| **OUT (`out`; remove from corpus)** | 562 |
| **Uncertain** | 0 |

**Audited gold ≈ 137 articles** (in + peripheral). Arc-run precision
against gold = 137 / 699 = 19.6%. The 562 OUT entries are
overwhelmingly from the broad `category:Apollo program` and
`category:Moon landing` pulls — these categories capture all 17 Apollo
missions plus conspiracy discourse, sample displays by state, books
and films about non-11 missions, and Apollo-adjacent people without 11
roles. A tight Apollo 11 scope legitimately excludes most of this.

## Judgment calls worth Sage's eyeball

Classifications where I applied scope-consistent rules but the
alternative reading was defensible.

### 1. Apollo 8 / 10 / 12 crew biographies → OUT

Scope ambiguity ruling says "Crew biographies are CENTRAL — the person
IS the mission." That applies to A11 crew. For A8 / A10 / A12 crew
(Borman, Anders, Lovell, Young, Stafford, Cernan, Conrad, Bean, Gordon),
I classified them as **OUT** reasoning that the scope's other ruling —
"Apollo-adjacent figures without a meaningful 11 connection: OUT" —
dominates when the person didn't fly 11. Alternative read: A8/A10/A12
missions are PERIPHERAL, so their crew biographies are PERIPHERAL too.
~9 articles swing.

### 2. Mission-specific crater articles named after other-mission crew → OUT

Anders (crater), Borman (crater), Lovell (crater), Grissom (crater), etc.
are named after astronauts who weren't on 11. Per the scope's
"named-after Apollo 11 crew" rule (Armstrong / Aldrin / Collins only),
these are OUT.

### 3. Earthrise (Apollo 8 photograph) → PERIPHERAL

Initially classified IN (iconic image) but corrected to PERIPHERAL —
it's from Apollo 8 and the scope's OUT rule says "general spaceflight
history not specific to Apollo 11 or its immediate program neighbors"
could arguably push to OUT. Kept PERIPHERAL because A8 is a PERIPHERAL
mission per scope.

### 4. Lunar Roving Vehicle → PERIPHERAL

Used only on Apollo 15–17, so strictly speaking doesn't contextualize
11. Kept PERIPHERAL via general-program-hardware rule for consistency
with Saturn V / LM / CSM, but OUT would also be defensible.

### 5. US state / international goodwill lunar sample displays → PERIPHERAL

The sample-display program was a mix of A11 and A17 goodwill. All "X
lunar sample displays" articles land in PERIPHERAL via a regex, ~30
articles. Could alternatively classify by which mission's sample each
display got (expensive) or move all to OUT.

### 6. "In the Shadow of the Moon (2007 film)" → CENTRAL

Documentary features Apollo 11 crew prominently but covers the full
Apollo program. Kept CENTRAL because it's a "primary cultural work"
with heavy A11 emphasis; PERIPHERAL is also defensible.

### 7. JFK's "We choose to go to the Moon" speech → PERIPHERAL

1962 speech predates A11 by 7 years, but commissioned the program that
produced 11. Kept PERIPHERAL as contextualizing material.

### 8. USS Hornet (CV-12) → CENTRAL; USS Princeton / USS Guadalcanal → OUT

Hornet was A11's recovery carrier → CENTRAL per mission-specific-artifact
rule. Princeton (A10) and Guadalcanal (A9) recovered other missions →
OUT.

### 9. Moonshot (2009 film) → CENTRAL

The Wikidata description said only "2009 British television film" —
I initially marked OUT as a generic pop-culture tangent. On second
look, this film IS specifically about Apollo 11 (Channel 4 docu-drama).
Moved to CENTRAL.

### 10. "A Man on the Moon" (1994 Chaikin book) → OUT

Covers the whole Apollo program; A11 is one chapter. Per scope's
"cultural works mentioning 11 among other subjects are OUT unless
primarily about 11," ruled OUT.

## Distribution, by pattern

| Pattern | Count |
|---|---|
| Pre-11 Saturn test flights (A-00x, AS-10x, AS-20x) | ~12 |
| Saturn rocket family variants (C-2, INT-20, V-D, etc.) | ~20 |
| Other Apollo missions 13–17 + their samples/photography | ~30 |
| Conspiracy-theory articles + theorists | ~20 |
| Other-mission astronauts (not crew, not ground support) | ~35 |
| Generic spaceflight / Moon / infrastructure | ~25 |
| Lunar craters from other missions' landing sites | ~40 |
| Tangential pop-culture (Simpsons, Doctor Who, video games) | ~20 |
| US state / international goodwill lunar sample displays | ~30 (PERIPHERAL) |
| Mission-specific 11 artifacts + crew + cultural works | ~100 (IN + a few PERIPHERAL) |

## What this means for the benchmark

- Gold v1 = **137 articles** (in + peripheral) out of the 699 in the
  arc corpus.
- Arc precision = 137 / 699 = **19.6%** — realistic for an
  inclusion-heavy, category-driven build.
- Future runs can improve precision (same gold, fewer non-gold
  articles) AND reach (find audited new members beyond gold).

## Known gaps the baseline missed (reach targets)

- **Things named after Apollo 11 via Wikidata P138** — probably a
  double-digit number of schools, streets, craters not in the 699.
- **Apollo 11 cultural works** — novels, memoirs, documentaries that
  didn't surface from category pulls. `harvest_navbox(Apollo program)`
  or targeted `intitle:"Apollo 11"` searches would find more.
- **Cross-wiki equivalents** — Russian / German Wikipedia coverage of
  A11 includes articles not sitelinked to enwiki. Low-priority reach.

## Updating gold over time

1. A future run that finds a CENTRAL or PERIPHERAL article not in
   `gold.csv` → re-audit it and append.
2. If `scope.md` is revised, gold becomes stale and needs re-audit;
   bump the frozen date on scope.md and re-run `audit.py`.
3. Judgment calls above can be re-litigated by editing scope.md's
   ambiguity rulings and re-running the classifier.
