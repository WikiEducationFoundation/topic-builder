# Topic Builder benchmark run — orchids (2026-04-23 ratchet)

You are running the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`) against a single benchmark topic. Your goal this session is to build a fresh corpus for this topic under a new, non-colliding name, ending with an honest `submit_feedback`. Your work will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs on the "taxonomy at scale" shape — the marquee completeness test at 18k+ articles.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today):
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it at session start.
  - New `fetch_article_leads(titles, sentences=3)` tool — for misleading Wikidata shortdescs.
- **Don't call `export_csv`.** The scoring script pulls the corpus directly from the server. On a topic with this much triangulation, export isn't needed anyway.
- **Use the EXACT run-topic name below.** The scoring script looks up the topic by name. Using the baseline name would overwrite frozen ground truth.
- **Cross-wiki guidance for this ratchet: stay enwiki.** Cross-wiki was the baseline's biggest unexploited reach strategy, but the `cross_wiki_diff` tool isn't shipped yet (it's on the Tier 2 backlog), and the frozen gold is enwiki-only. Manual cross-wiki walking would be expensive and wouldn't affect the scoreboard. Lean hard on enwiki completeness instead — Wikidata P171 (parent taxon) against Q25308 (Orchidaceae) is the highest-leverage reach move that fits on this ratchet.

## Run-topic name

- **Run-topic name (exact):** `orchids ratchet-2026-04-23`
- **Baseline name (DO NOT use):** `orchids`
- **Wiki:** `en`

## Step 0 — Setup check

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions (came in on session init via MCP `instructions=`). Note SCOPE RUBRIC, PIPELINE, COST AWARENESS, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, WRAP-UP.
3. If tools aren't loaded, stop and surface the blocker.

## Step 1 — Persist the rubric

Call `set_topic_rubric(rubric=<verbatim text below>)`. Don't paraphrase.

```
# Centrality rubric — orchids benchmark
# Frozen 2026-04-23. A rubric change invalidates gold.csv.

CENTRAL — Wikipedia articles about orchids (Orchidaceae family) and
  their immediate biology: species, genera, natural hybrids, cultivars,
  and notable individual plants; orchid-focused taxonomy; named
  orchid-related institutions (botanical gardens specializing in
  orchids, orchid societies); orchid-focused cultural works (books,
  documentaries, paintings centered on orchids); orchid phytochemistry
  (compounds identified in or isolated from orchids); orchid pests,
  pathogens, and symbionts where the article's subject is the
  interaction with orchids; and people whose primary notability is
  orchid-specific work (orchidologists, orchid breeders, orchid
  hunters, orchid growers, orchid hybridizers).

PERIPHERAL — General botanists, naturalists, biologists, explorers,
  or botanical illustrators whose work includes orchid taxonomy but
  whose primary notability isn't orchid-specific. Also: related
  botanical gardens without orchid specialization; cultural works
  that include orchids among many subjects (East Asian Four
  Gentlemen art tradition if the broader work is the article's
  subject); plant-collector biographies where some species are
  orchids.

OUT — Non-orchid plants, generic flowering plants not in Orchidaceae,
  non-botanical topics pulled in by name collision or lexical noise
  (semiconductor companies sharing a species epithet, actors sharing
  a botanist's name, anthologies that mention orchids only in
  passing), and bios of non-botanical figures swept up by cross-wiki
  reconciliation without orchid-specific work.

# Notes for auditors:
# - At 18,122 articles, this benchmark uses a keyword-rule classifier
#   with source-trust (articles pulled from category:Orchids or
#   orchid-list-pages are trusted as on-topic taxa, since orchid
#   builds only harvest orchid-relevant lists by construction).
# - Sample-audit via WebFetch is the recommended validation path:
#   pull 30–100 random articles from each bucket, verify against
#   their Wikipedia articles, and refine classifier rules if
#   precision on the sample drops below a threshold.
# - Orchid phytochemistry is CENTRAL (orchid-specific compounds); the
#   classifier marks "Chemical compound" + category:Orchids as IN.
# - Cultural-tail coverage: East Asian Four Gentlemen tradition
#   (Chinese poetry / painting featuring orchids) is IN via the
#   orchid-cultural-tail criterion when the article's primary subject
#   is the orchid cultural role. The specific authors/artists (Qu Yuan,
#   Guan Daosheng) are tangential and currently OUT; a future audit
#   could lift them to PERIPHERAL if we want broader cultural-tail
#   coverage.
```

## Step 2 — Internalize the scope

**Short statement:** Wikipedia articles about members of the Orchidaceae family (orchids) and their immediate biology, taxonomy, cultivation, pollination, phytochemistry, and cultural role. Includes orchid-focused people and institutions; includes orchid cultural works; excludes non-Orchidaceae plants and general botany unless orchid-specific.

**In scope:**
- **Orchid taxonomy.** Species, genera, subtribes, hybrids (natural and cultivated), cultivars, named individual plants of the Orchidaceae family. Notable example genera: Phalaenopsis, Cattleya, Dendrobium, Vanda, Cymbidium, Oncidium, Vanilla, Bulbophyllum, Paphiopedilum, Epidendrum, Masdevallia, Laelia, Caladenia, Acianthera, Pleurothallis, Stelis, Lepanthes, Ornithocephalus.
- **Orchid-specific people.** Orchidologists, orchid hunters, orchid growers, orchid hybridizers, orchid breeders, orchid collectors, orchid nursery operators. Scientists whose primary published work is orchid taxonomy or orchid biology.
- **Orchid-specific institutions.** Botanical gardens specializing in orchids, orchid societies, orchid research centers.
- **Orchid cultural works.** Books, documentaries, films whose primary subject is orchids (e.g. *The Orchid Thief* — but not necessarily its film adaptation unless that article is primarily about the orchid subject matter).
- **Orchid phytochemistry.** Chemical compounds identified in or isolated from orchids, including fragrance components and medicinal compounds.
- **Orchid pollination biology.** Articles about pollination mechanisms specific to orchids, orchid-symbiont mycorrhizae, orchid-pollinator coevolution.
- **Orchid pests, diseases, and conservation.** Pests and pathogens where the article's subject is the interaction with orchids; conservation status articles for orchid species.

**Explicitly out of scope:**
- **Non-Orchidaceae plants.** Roses, lilies, irises, any flowering plant family other than Orchidaceae. Even if the plant shares an orchid-species epithet, OUT.
- **General botany.** Pollination biology in general, plant taxonomy in general, flowering-plant evolution in general — OUT unless orchid-focused.
- **Name collisions.** Articles unrelated to orchids pulled in by fuzzy search or list-page inclusion (semiconductor companies, actors, politicians whose names match orchid-species epithets or list entries).
- **Non-orchid figures from cross-wiki reconciliation.** Chinese artists/poets (Qu Yuan, Ma Shouzhen, Guan Daosheng) tangentially connected to orchid cultural tradition (e.g. via Four Gentlemen motif) but whose primary notability is unrelated — default OUT.

**Ambiguity rulings:**
- **General botanists.** PERIPHERAL default. A botanist who described orchid taxa but is also known for other families is peripheral (Carl Ludwig Blume, Alfred Cogniaux, Achille Richard).
- **Orchid phytochemicals.** IN. Chemical compounds from orchids whose articles are in category:Orchids count.
- **Four Gentlemen art tradition** ("Four plants in East Asian art"). The overarching cultural article is IN. Specific artists who painted the Four Gentlemen are OUT by default unless the article emphasizes orchid-specific work.
- **Empty Wikidata shortdesc + orchid source.** IN — trust the source (build context guarantees orchid relevance).
- **Cross-wiki-reconciliation manual sources.** Mostly IN (articles walked back to enwiki from other-language orchid builds). Non-botanical biographies from cross-wiki are OUT.

### Topic-specific guardrails

- **SCALE.** 18k articles. Cost awareness matters: prefer `preview_category_pull`, `preview_harvest_list_page` before committing. Watch for `cost_warning` responses.
- **Source trust.** Articles pulled from `category:Orchids` or list pages of orchid species should be trusted as on-topic — the build context guarantees orchid relevance. Don't require a confirming shortdesc for taxonomic articles.
- **Enwiki focus for this ratchet.** Cross-wiki was the baseline's reach frontier, but `cross_wiki_diff` isn't shipped yet and the gold is enwiki-only. Skip manual cross-wiki walks for this run.
- **Cultural tail.** Keep Chinese literary figures (Qu Yuan, Ma Shouzhen, Guan Daosheng) OUT per rubric. "Four plants in East Asian art" (the overarching article) is IN.
- **Wikidata P171 (parent taxon) against Q25308 (Orchidaceae).** Not exercised in the baseline. `wikidata_entities_by_property(property="P171", value="Q25308")` or equivalent SPARQL is the highest-leverage reach move for this ratchet.
- **Keyword-rule validation.** The audit classifier uses genus names + description keywords ("orchid", "Orchidaceae", "species of orchid"). If your corpus has a large bucket of taxa whose shortdescs say only "Species of plant" and no orchid term, trust source-provenance from `category:Orchids` or orchid list-pages.

## Step 3 — Build to completeness

Standard pipeline, cost-aware:
- Reconnaissance — WikiProject probe (`check_wikiproject("Orchids")`), category survey on `Category:Orchidaceae` and `Category:Orchids` (both exist as separate nodes; the baseline walked through both), list-page discovery (many genus-specific "List of X species" pages), Wikidata search.
- Gather — `get_category_articles` on `Category:Orchidaceae` at a carefully-chosen depth (`preview_category_pull` first to check size); `harvest_list_page` on genus list pages (`main_content_only=True`); `harvest_navbox` if there's a suitable orchid navbox; `search_articles` and `search_similar` as complements. `wikidata_entities_by_property(P171=Q25308)` for the taxa probe.
- Descriptions — `fetch_descriptions` (with REST fallback on empties).
- Review — most orchid taxa don't need lead-checks; their source-provenance is the trust signal. `fetch_article_leads` is useful on borderline biographies (is this person an orchidologist or a general botanist?) and on cultural-works articles.
- Cleanup — `filter_articles` will drop disambiguation pages (which orchid-adjacent names sometimes trigger), `remove_by_pattern` for cross-category seepage, `remove_by_source` for any single source that turned out to be noisy.

### Reach targets from the baseline run

- **Wikidata P171 against Q25308** — the highest-leverage unexploited move. Not exercised in the baseline; likely captures orchid species missing from the enwiki corpus.
- **Reduce the 9 known OUT false-positives** — Besi (semiconductor company), Bruce Gray (actor), and non-botanical cross-wiki reconciliation entries. A ratcheting run with relevance filtering or title-type verification should drop these pre-commit.
- **Cultural-tail scope is narrow** — Chinese literary figures OUT per current rubric. Don't expand scope.

## Step 4 — SPOT CHECK + GAP CHECK

1. Fabricate ~15–25 niche orchid titles you'd expect in the corpus (specific genera you haven't named yet, specific notable hybrids, specific orchidologists, specific orchid-focused cultural works, specific orchid pests/diseases). Authorized to fabricate autonomously.
2. Check presence via `get_articles(title_regex="^(T1|T2|…)$")` or `preview_search`.
3. Classify misses: variant-name (redirect) / LLM hallucination / real gap.
4. Diagnose patterns: if several missed species cluster under one genus, that's a signal the genus list page wasn't harvested — rerun the list page rather than add by hand.
5. Repair real gaps; seed `browse_edges` from clusters.

## Step 5 — Rubric review

Call `get_topic_rubric()`. Note scope wrinkles in feedback. DO NOT change the rubric.

## Step 6 — Submit feedback

```
submit_feedback(
    summary="<2-5 sentences>",
    what_worked="<concrete tools / strategies that worked>",
    what_didnt="<concrete pain points, sharp-edges hit>",
    missed_strategies="<tool shapes you wished existed — empty if none>",
    rating=<1–10>,
    coverage_estimate={
        "confidence": <0.0–1.0>,
        "rationale": "<one sentence>",
        "remaining_strategies": ["<existing tool shapes you didn't apply>", ...]
    }
)
```

`confidence` = self-estimate of corpus completeness relative to the frozen scope (enwiki-only for this ratchet). Honest low beats inflated high. A high-confidence on this topic is realistic given the source-trust model + strong category triangulation — but "I didn't do cross-wiki" and "I didn't do the P171 Wikidata probe" are both reasonable dings if you skipped either.

## Step 7 — Do NOT call `export_csv`

The scoring script pulls the corpus directly from the server.

## Done

Reply with a brief summary: final article count, coverage_estimate.confidence, and any notable friction. Also useful: did the Wikidata P171 probe surface new taxa not already in category:Orchids? (ratchet signal for whether a Wikidata-first strategy is a win on taxonomy-at-scale shapes.)
