# African American STEM gold audit notes

Human-written commentary for the AA STEM benchmark. See
`audit_summary.md` for the classifier's fresh output. This file is
curated and shouldn't be overwritten by re-running `audit.py`.

## Summary (after WebFetch resolutions)

| | Count |
|---|---|
| Total articles in arc-run corpus | 832 |
| **CENTRAL (`in`)** | 736 |
| **PERIPHERAL (`peripheral`)** | 21 |
| **OUT (`out`; remove from corpus)** | 75 |
| **Uncertain** | 0 |

**Audited gold = 757 articles** (in + peripheral). Arc-run precision
against gold = 757 / 832 = 91.0%.

The pipeline: `audit.py` classifies 812 articles cleanly and flags 20
uncertain. `apply_webfetch_resolutions.py` then overlays hand-verified
classifications for those 20 (obtained by fetching each article via
WebFetch and judging against scope).

## Comparison to other benchmarks

| Metric | Apollo 11 | CRISPR | AA STEM |
|---|---|---|---|
| Arc corpus | 699 | 99 | 832 |
| Gold | 137 | 82 | 757 |
| Arc precision | 19.6% | 82.8% | 91.0% |
| Triangulation | 30.3% | 0% | 61.8% |
| Tool calls | 50 | 14 | 39 |

AA STEM's high precision reflects the category-based build: the
`category:African-American scientists` + `category:African-American engineers`
sources are tight. The 75 OUT items are mostly non-research physicians
(from the medicine blocklist) plus a handful of politicians /
entrepreneurs / administrators / athletes who got swept up.

## The 20 WebFetch-resolved cases

Resolved 2026-04-23 via Wikipedia article fetch + scope classification.
See `apply_webfetch_resolutions.py` for the frozen map.

| Title | Final | Wikipedia-based rationale |
|---|---|---|
| Alfred Oscar Coffin | peripheral | Math + Romance languages professor; teaching-primary, not research |
| Colette Pierce Burnette | peripheral | Industrial engineer → university administration |
| Edward S. Hope | peripheral | Civil engineering professor → naval administration; STEM-background admin |
| G. Gabrielle Starr | peripheral | Cognitive-neuroscience research but admin-primary as college president |
| Gloria Chisum | **in** | Experimental psychology research on high-performance aircraft vision; applied STEM |
| Gregory Washington | peripheral | Mechanical-engineering researcher now university president |
| Jalonne White-Newsome | peripheral | Environmental-health PhD but policy/advocacy primary |
| James B. Dudley | peripheral | Led agricultural + technical college; STEM-adjacent institutional leadership |
| Kimani Toussaint | **in** | Engineering professor (optical nanotech) at Brown — clear STEM research |
| LaVerne E. Ragster | peripheral | Marine biologist → university president; admin-primary |
| Michael Harris-Love | **in** | Rehabilitation scientist / clinician-investigator with NIH + VA research |
| Odest Chadwicke Jenkins | **in** | Computer scientist (robotics) at Michigan; STEM research |
| Paris Adkins-Jackson | **in** | Columbia epidemiologist; STEM health research |
| Peggy G. Carr | **out** | Developmental psychology + educational assessment — social science / policy |
| Renee M. Johnson | **out** | Adolescent mental health + substance abuse — social science |
| Sherita Ceasar | peripheral | Telecom SVP with engineering background; executive-primary |
| Tiara Moore | **in** | Environmental DNA research at Nature Conservancy |
| William Hallett Greene | **in** | First Black meteorologist / Signal Corps station chief — STEM research |
| Willie Rockward | **in** | Physics professor (nano-optics, metamaterials) at US institution |
| Yvonne Maddox | peripheral | Health-equity research, admin-primary career |

Totals: 8 in, 10 peripheral, 2 out.

## Interesting edge-case observations

- **Gloria Chisum** is IN despite "American academic" Wikidata shortdesc
  — her actual notability is experimental psychology research on
  pilot-vision eyewear. "Wikidata shortdesc understates the STEM career"
  — same pattern motivated the `fetch_article_leads` backlog item.
- **Peggy G. Carr** and **Renee M. Johnson** are the only two OUT
  additions. Both are in `category:African-American scientists` but
  their actual work is social science (educational assessment,
  mental-health sociology) — Wikipedia-side miscategorizations.
- **Ten of 20 ended up PERIPHERAL** — STEM-trained people who moved
  into university / institutional / policy leadership. Rubric-PERIPHERAL
  captures them appropriately.

## Reach targets

- The AA STEM medicine blocklist (`medicine_blocklist.txt`) has 807
  titles; ~500 are in the current corpus and flagged OUT by the
  classifier. A ratcheting run using `remove_by_source` tied to the
  blocklist would drop the OUT count substantially.
- Wikidata P106 (occupation) + P172 (ethnic group) joins could surface
  bios the category sweep missed.
- Cross-wiki candidates: Francophone African researchers with US
  postdocs (frwiki), Afro-Caribbean scientists with US careers
  (eswiki for Afro-Cuban, etc.).
- Historical bios (pre-1960 STEM pioneers) are under-represented.
