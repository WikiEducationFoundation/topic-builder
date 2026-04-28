# Strategy brainstorm — directions we haven't explored

Brainstorming doc, 2026-04-27. Cataloging "in-retrospect-obvious"
topic-discovery directions that are *not* extensions of moves we
already make. The recent `seed-anchored-mining-from-canonical-article`
ship (read the topic article, harvest its links / backlinks /
categories / templates) is the prototype for "structurally novel"
that this doc tries to surface more of.

Not a plan. Not a backlog. A menu, organized so future-you can step
through one axis at a time and decide what's worth promoting to
`backlog/README.md`.

## Status (updated 2026-04-28)

**Shipped to production 2026-04-28** (originally promoted from this brainstorm to backlog 2026-04-27, then built same week — see `docs/shipped.md`):
- See also section harvest (was Top Pick #3 / axis A1) — new tool `get_article_see_also`.
- `hastemplate:` Cirrus operator move + `articletopic:` companion (was Top Pick #4 / axis I1 + D2) — strategy moves `hastemplate-typed-probe` and `articletopic-classifier-probe`.
- LLM-as-generator move (was item #6 in promotion list / axis D1) — strategy move `llm-fabricate-and-verify`.

**Deprioritized "right now":** the centrality-tools cluster (pageviews / pageassessments / sitelink count — original Top Picks #1, #2, #6). These are kept on the menu below as a record of the brainstorm but are not active promotion candidates; the CLAUDE.md principle "Centrality is AI judgment, not tool computation" applies to centrality-proxy *signal* tools too, not just to direct score-writers. Revisit only if a multi-session signal points specifically at one of them.

The remaining axes / items below are unpromoted and still up for picking.

## Reading guide

- **Top picks** — six leads with the strongest "easy-win" character. Read these first; each could be a Tier 1 entry by next session.
- **The full menu, by axis** — ten axes, ~6 ideas each. Skim by axis name; descend where intriguing.
- **Cross-cutting observations** — patterns I noticed while assembling the menu. The shape of what we *missed* says something.
- **What I'd promote first** — concrete opinion at the bottom.

Each idea carries a one-line cost sketch (`trivial wrap` / `moderate
integration` / `heavy lift`) and notes whether it's a new **move**
(recipe over existing tools) or a new **tool** (new primitive).

The current toolkit's own scope: ~64 MCP tools speaking to MediaWiki
action API, REST `/page/summary`, Wikidata SPARQL + entity API. Cirrus
operators in active use are `morelike:`, `incategory:`, `intitle:`,
`inlanguage:`. Everything outside that ring is unexplored.

---

## Top picks

The six items I'd promote to Tier 1 first if no other context.

### 1. Pageviews API as a centrality / triage signal

**What.** Hit `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/<wiki>/<access>/<agent>/<title>/<granularity>/<start>/<end>` per article (or in bulk via the `top` endpoint) to fetch daily / monthly view counts.

**Why "in retrospect obvious."** View count is the most direct proxy we have for "how central is this article to its topic." A 30-day average of 50,000 views is canonical; 5 views is periphery. We currently rely on AI judgment + sources triangulation + sitelink counts to infer centrality — pageviews is the one signal we *don't* use that almost everyone uses for this purpose.

**Where it helps.**
- **Centrality scoring substrate.** A `score_by_pageviews` move could seed centrality with a power-law-binned default that the AI then refines.
- **Triage on huge corpora.** When a topic ends up at 5,000–10,000 articles (climate-change, orchids), the AI needs to sample for review. "Top 100 by pageviews" + "bottom 50 by pageviews" is a much better sample than alphabetical.
- **Detect orphans.** Articles with literal zero traffic over 90 days are likely off-topic (spam categorization, namespace pollution) or genuinely peripheral. Useful cleanup signal.
- **Surface canonical hubs the AI undervalues.** The AI sometimes misses well-known articles when its rubric is narrow; a high-pageview article in the working corpus is a "double-check this is rubric-aligned" prompt.

**Shape.** New tool `get_pageviews(titles=[...], granularity="monthly", days=90)` returning `{title: {avg_per_day, percentile_in_corpus}}`. Or a corpus-aware variant that ranks all titles in the current topic by pageviews. Trivial wrap.

### 2. Wikipedia 1.0 article quality + importance via `prop=pageassessments`

**What.** MediaWiki's `prop=pageassessments` returns per-article WikiProject judgments: `class` (FA / GA / A / B / C / Start / Stub) and `importance` (Top / High / Mid / Low) per WikiProject that's tagged the article.

**Why "in retrospect obvious."** Wikipedia's editor community has been rating articles for 20 years. Every article in a tagged WikiProject carries a class + importance assessment. We just shipped `preview_wikiproject` for project-level metadata; we haven't surfaced the per-article ratings, which is a much richer signal.

**Where it helps.**
- **Centrality is partly solved already** for any article rated by a relevant WikiProject. "Top-importance" by WikiProject Spaceflight is a strong signal Apollo 11 belongs.
- **Quality-aware export.** "Show me only B-class-or-better articles" — useful for impact-visualizer use cases that want canonical pieces, not stubs.
- **Better triage.** FA / GA articles are usually canonical hubs — surface them first in spot-checks.
- **Cross-WikiProject signal.** An article tagged Top-importance by WikiProject Apollo program AND WikiProject Spaceflight is double-corroborated.

**Shape.** New tool `get_assessments(titles=[...])` returning `{title: [{project, class, importance}]}`. Then a `score_by_importance` move that maps importance → centrality. Trivial wrap.

### 3. "See also" section parsing

**Promoted 2026-04-27 to `backlog/README.md` Tier 1.** The structurally-novel axis the recent main-article ship just opened: the article *itself* still has more curation we don't read. See also is the most curation-dense slice. Active backlog entry has the implementation sketch.

### 4. `hastemplate:` Cirrus operator as a typed-thing finder

**Promoted 2026-04-27 to `backlog/README.md` Tier 1** (bundled with `articletopic:` documentation from D2). Documentation-only first ship; thin wrapper only if dogfood shows the AI doesn't reach for the bare operator.

### 5. Sister-project sitelink crosswalk (especially Commons)

**What.** A Wikidata QID typically has sitelinks to Commons categories (`commonswiki`), Wikiquote (`enwikiquote`), Wikisource, Wikivoyage, Wikibooks, Wikiversity in addition to Wikipedia language editions. Each sister project has its own categorization / authoring community with different gaps.

**Why "in retrospect obvious."** Commons categories for visual/material topics (orchid species, Apollo 11 mission components, climate-change events) are often *deeper* than enwiki categories because Commons has photo-uploading editors who categorize finely. Wikiquote covers people-with-quotes (a clean biography filter). Wikisource has historical authors. Each is parallel curation — and crosswalks back to enwiki via Wikidata.

**Where it helps.**
- **Visual / material topics.** Climate-change run had ~2,500 categorical-tail articles; Commons category `Category:Climate change` and its subtree might surface entities the enwiki tree doesn't tag.
- **Quotable-people biographies.** For humanities topics, Wikiquote's "Category:American philosophers" → sitelinks → enwiki gives a cross-check on enwiki's philosophy biographies.
- **Historical author topics.** Wikisource Author: namespace lists everyone whose works are out-of-copyright — a cleaner author enumeration than category trees that mix critics, biographers, translators, etc.

**Shape.** Two moves and one tool:
- Move: `commons-category-crosswalk` — given topic QID, find Commons category sitelink, list its members, map back to enwiki via QID lookup.
- Move: `wikiquote-biography-crosswalk` — same pattern via enwikiquote.
- Tool: `get_sister_sitelinks(qid, project="commons|wikiquote|wikisource|wikivoyage")` returning the sitelink target on the named sister + its members if it's a category. Moderate integration — Commons has its own MediaWiki API; same shape, same auth-free GET, just a different host.

### 6. Sitelink count as a centrality / canonicalness signal

**What.** Every Wikidata item has a `sitelink_count` (already exposed in our `wikidata_entities_by_property`). For corpus articles, it's available cheaply via `wbgetentities` over the corpus's QIDs.

**Why "in retrospect obvious."** An article that exists on 30+ wikis is, by community consensus, important enough to translate. An article on only enwiki is parochial or recent. Cross-cultural canonicalness is exactly the kind of centrality signal a topic-builder should surface — and it's a single field already in Wikidata.

**Where it helps.**
- **Centrality scoring.** Score 9–10 candidates have sitelink count > 50; score 1–3 candidates often have ≤ 3. Nice rank input.
- **Triage of huge corpora.** "Top 100 by sitelink count" surfaces the canonical hubs.
- **Sanity check on rubric alignment.** When a high-sitelink article is in the rubric's PERIPHERAL band, that's a flag the rubric may be tuned wrong.

**Shape.** Pairs naturally with #1 (pageviews). Could be one tool `get_centrality_signals(titles=[...])` that returns `{pageviews_30d, sitelink_count, importance_max, class}` per title in one round-trip. Trivial — already collecting QIDs via `resolve_qids`; just need to cache the sitelink_count alongside.

---

## The full menu, by axis

### A. Mine article structure beyond links

The recent `seed-anchored-mining-from-canonical-article` move parses
links + categories + templates from the canonical article. The
article still has more structure to mine.

- **A1. "See also" section.** Promoted to Tier 1 backlog 2026-04-27.
- **A2. References / `<ref>` extraction with citation patterns.** The references section enumerates the article's foundational sources. Structured citation parsing (DOIs, Wikidata `cites_work` if present) reveals the canonical bibliography. For academic topics, two articles citing the same paper are likely topically related. Tool: `get_article_references(title)` returning structured citations. Moderate.
- **A3. External links section.** Every article has `==External links==` listing canonical web sources. Multiple articles linking to the same `https://nasa.gov/apollo11.html` are likely topically related. Find via `prop=extlinks`. Trivial wrap.
- **A4. Section-structure introspection.** An article's section headings often enumerate canonical sub-topics. The Apollo 11 article's sections are essentially a curated topic outline. Tool: `get_article_outline(title)` returning the section tree. Trivial via `parse&prop=sections`.
- **A5. Bold-first-phrase / lead-sentence parsing.** Wikipedia's MOS:LEAD requires the bold first phrase to define the article ("Apollo 11 was the **American spaceflight** that..."). Extract the bolded definition + first sentence's ontological frame. Useful for type-classification at scale, especially for ambiguous shortdescs. Trivial via `parse&prop=text` + small regex.
- **A6. Hatnotes and disambiguation chains.** `{{about|X|other uses|Y}}` hatnotes and disambiguation pages encode community-judged "things you might confuse." For a topic, walking hatnote chains finds homonyms to deliberately exclude (or include if they belong). Move: `hatnote-disambiguation-walk`. Trivial.
- **A7. Infobox parameter extraction.** Beyond just *which* infobox, the *parameters* in an infobox (e.g., `{{Infobox film | director = X}}`) name canonical attribute values. Mining `director=` across an infobox category surfaces directors linked from films, even when not explicitly in WikiProject Film's biography list. Moderate — wikitext parsing.

### B. Sister Wikimedia projects

Each is its own MediaWiki instance with the same API surface; the
hard part is QID-mapping back to enwiki.

- **B1. Commons category mining (Top Pick #5).**
- **B2. Wikiquote biographies.** People notable enough to have Wikiquote pages. Covers humanities topics' "people with notable quotes" axis. Trivial.
- **B3. Wikisource authors.** Historical authors with public-domain works — strong for pre-1928 literature, history-of-science, philosophy. Trivial.
- **B4. Wikivoyage geographic hierarchy.** Region → country → city → district hierarchy is hand-edited and often cleaner than enwiki's "Category:Cities of X" mess. Trivial for geography topics.
- **B5. Wikibooks / Wikiversity.** Subject curricula. A Wikibook on cryptography links to dozens of relevant enwiki concepts as "Further reading" or "Prerequisites" — community-curated topic syllabi. Moderate (free-form structure).
- **B6. Wiktionary terminology mining.** For language / etymology / linguistics topics, Wiktionary's translation tables and derived-term lists expose terminology that maps back to enwiki concepts. Niche but cheap. Trivial.
- **B7. Wikinews event coverage.** Time-bounded event coverage for "current events" / "post-cutoff" topics. Trivial.

### C. External authority files & domain databases

These are the single biggest "different ontology" pool. Each has
its own categorization that often disagrees with Wikipedia's, in
useful ways. Most are reachable via Wikidata's external-ID
properties.

- **C1. VIAF (Virtual International Authority File).** Every named person, organization, and creative work tracked by major libraries. Dense for biographies, especially historical. `viaf_id → Wikidata via P214 → enwiki`. Moderate.
- **C2. LCSH (Library of Congress Subject Headings).** Curated subject hierarchy spanning humanities, social sciences. "All works classified under LCSH `Civil rights movements -- United States -- 20th century`" → cross-walk to enwiki via Wikidata P244. Moderate.
- **C3. OpenAlex.** Free 240M-paper academic graph with concepts, authors, institutions. The "concepts" graph is an alternative ontology to Wikidata field-of-study hierarchies; better for STEM coverage. `https://api.openalex.org`. Moderate.
- **C4. GeoNames.** 11M places with admin hierarchy + Wikipedia sitelinks. For geography topics, GeoNames is cleaner than category trees. Trivial.
- **C5. GBIF (Global Biodiversity Information Facility).** Backbone taxonomy ~2M species; deeper than enwiki's category tree for non-charismatic taxa. Moderate.
- **C6. MusicBrainz / Discogs.** For music topics, structured artist→album→track relationships. Trivial.
- **C7. ORCID + DBLP.** Researchers with persistent IDs. Combined with OpenAlex affiliation data, surfaces academics enwiki misses. Moderate.
- **C8. PubMed / MeSH.** Biomedical ontology. MeSH's hierarchical subject headings map to Wikidata. Moderate.
- **C9. IMDb / TVDB / Rotten Tomatoes.** For film/TV. Wikidata has IMDb IDs (P345); a list of "every film with X award nomination from IMDb" → enwiki crosswalk. Trivial.

The general pattern: these are not topic-builder-specific tools. They're "import an external taxonomy / authority list, crosswalk to Wikipedia, use as candidates." A meta-tool `wikidata_external_id_crosswalk(external_property, external_value, return_wiki="en")` would make many of these accessible without per-source plumbing. Single moderate-integration item that unlocks ~10 sources.

### D. AI / ML capabilities applied differently

The current model: AI judges candidates the *tools* surface. New
direction: AI / ML *generates* candidates that tools then verify.

- **D1. LLM-as-generator.** Promoted to Tier 1 backlog 2026-04-27 as `llm-fabricate-and-verify`.
- **D2. ORES `articletopic:` Cirrus operator.** Bundled into the `hastemplate:` Tier 1 entry 2026-04-27 — both are zero-infra Cirrus operator documentation and ship together.
- **D3. ORES quality scores per article.** `https://ores.wikimedia.org/v3/scores/enwiki/` returns per-article ML predictions for FA-likelihood and edit-quality. Triage signal alongside pageviews. Trivial.
- **D4. Sentence / passage embeddings for semantic similarity.** Wikipedia2Vec or sentence-transformers over article descriptions or leads. CirrusSearch's `morelike:` is BM25 — embeddings cluster on semantic meaning. Especially useful for niche-vocabulary topics where word-overlap fails. Heavy lift (vector DB infra), but the value-per-unit-effort might be high once you have a pipeline.
- **D5. Cross-encoder reranker for ambiguous classification.** Today, `auto_score_by_description` is keyword-based; ambiguous cases survive into manual review. A cross-encoder model ("does article X belong to topic Y given rubric Z?") could replace `suggest_removals` and centralize hard cases. Moderate-to-heavy.
- **D6. LLM-driven SPARQL synthesis.** The AI's mental model of SPARQL is patchy. A move that says "describe what you want as a Wikidata query in natural language" → server-side LLM emits SPARQL → execute → return — turns Wikidata into a more accessible probe surface. Moderate.
- **D7. LLM-judged see-also / related expansions.** Ask the AI "given article X's lead and its references, list 20 articles I'd expect to see in the same topic." Verify presence. Different from candidate generation in D1 because it's seed-anchored, not topic-anchored. Trivial.

### E. Community-curation surfaces we don't surface

Wikipedia editors maintain meta-content explicitly designed as topic
maps. We don't read them.

- **E1. Wikipedia Portals (`Portal:X`).** Hand-curated topic gateways. Portal:Apollo 11 (if it existed; Portal:Spaceflight does) typically includes "Selected article" rotations + topic indexes + selected biographies. Trivial — they're standard articles in the Portal namespace.
- **E2. Featured Topics / Good Topics.** Wikipedia's curated meta-collections: a Featured Topic is a hand-vetted *complete coverage* of a topic. Catalog at `WP:FT`. For any topic that has one, it's a hand-vetted bootstrap. Trivial.
- **E3. Vital Articles list.** Wikipedia's 50,000-article community-rated importance tier list. Tier 1 (10) / Tier 2 (100) / Tier 3 (1,000) / Tier 4 (10,000) / Tier 5 (50,000). The intersection of "articles in scope of my topic" ∩ "Vital Articles tier ≤ 4" surfaces likely-canonical-hubs. Moderate (lists are page-based, need parsing).
- **E4. Outline of X / Index of X / Glossary of X.** Three different conventions, all hand-curated, all worth probing as primary sources. Already partially surfaced by `find_list_pages` for "Outline" but not systematically. Move: `outline-index-glossary-trinity-probe`. Trivial.
- **E5. Wikipedia Books namespace.** Largely deprecated but legacy `Book:X` collections still exist for many topics — manually-curated article sets. Trivial.
- **E6. {{Article history}} / GA history / FA history on talk pages.** Records the article's promotion path. Articles that survived FA review = canonical. Move: `fa-ga-history-as-canonicalness`. Trivial.
- **E7. DYK / ITN / OTD history.** "Did You Know" / "In The News" / "On This Day" feature an article on the main page. The pageprops record this. Articles featured on the main page enjoy editorial vetting + spike traffic — both signals of importance. Trivial.
- **E8. WikiProject talk-page activity / size.** For finding adjacent WikiProjects: a WikiProject's talk page has banners listing related WikiProjects. The banner graph encodes editor-judged proximity. Niche but interesting.

### F. Temporal / popularity signals

- **F1. Pageviews API (Top Pick #1).**
- **F2. Article creation timestamp.** `prop=revisions&rvprop=timestamp&rvdir=newer&rvlimit=1`. For event-driven topics, articles created within a window of the event are likely related. For topics-that-evolved (climate change), creation timestamp clusters reveal "the wave." Trivial.
- **F3. Recent changes API (`list=recentchanges`).** Articles created or substantially edited within a window. Solves the "post-training-cutoff" gap on AI-generated candidate lists. Trivial.
- **F4. Edit frequency / last-edit-recency.** A moribund article (no edits in 2 years) vs. an actively-maintained article carries different community-engagement signal. XTools API. Trivial via Toolforge.
- **F5. Page protection level (`prop=info&inprop=protection`).** Protected pages are usually high-traffic / high-controversy → topic-defining. Trivial.

### G. The link graph as a graph

The corpus, once gathered, is a directed graph of articles linking
to each other. We use this only superficially via `browse_edges`.

- **G1. PageRank / centrality on the topic subgraph.** Once we have N candidate articles, compute the subset graph (only links among the N), run PageRank or HITS. Top-PageRank articles are canonical hubs; isolated articles are likely off-topic or peripheral. New tool `compute_centrality(topic)`. Moderate.
- **G2. Bridge / island detection.** Articles with no internal links to/from any other article in the corpus are islands — flag for review. Articles that connect otherwise-disconnected clusters are bridges — high-leverage hubs. Moderate.
- **G3. Co-link / co-citation networks.** Articles that share many *external* link targets (or are linked by many of the same other articles) are likely topically related. New move `co-link-similarity-probe`. Moderate.
- **G4. Random-walk discovery from canonical seed.** N random walks from the topic article through outgoing links, weighted by pagerank — the visit-frequency distribution surfaces neighborhood. Different from `browse_edges` which is breadth-first and unweighted. Moderate.
- **G5. Cluster detection (Louvain / community detection).** On the full topic subgraph, detect communities. Each cluster represents a sub-topic. Useful for shape-axis "layered_shape" assessment, possibly for rubric refinement. Heavy lift but possibly the most valuable per call once built.

### H. Cross-language structure

Beyond `cross_wiki_diff` (Tier 2 backlog), there are other axes.

- **H1. Sitelink count as centrality (Top Pick #6).**
- **H2. Cross-wiki backlink diversity.** An article that's linked *from* 30 different wikis' versions of the topic article is highly canonical. Different from sitelink count (which is about whether it has its *own* page on those wikis). Moderate.
- **H3. Translation candidates query.** Wikidata SPARQL for "items with sitelink to ptwiki, in Category:Orquídeas, but no enwiki sitelink." Identifies what exists on other wikis but not enwiki. Trivial via SPARQL.
- **H4. Title-translation reuse.** A QID's labels in 30+ languages reveal the canonical translation across wikis — useful when matching user-pasted external sources (e.g., a Spanish syllabus mentioning *orquídeas*) to enwiki articles. Trivial.
- **H5. Cross-wiki category-system diff.** Compare zhwiki's "Category:Apollo 11" subtree to enwiki's. zhwiki may have categories enwiki doesn't (or vice versa). Moderate.

### I. Underused MediaWiki / Cirrus / API features

The most embarrassing category — these are already-available knobs
we haven't turned.

- **I1. `hastemplate:` operator.** Promoted to Tier 1 backlog 2026-04-27.
- **I2. `linksto:`** — like backlinks but as a Cirrus filter, composable with other operators: `incategory:Spaceflight linksto:"Apollo 11"`. Moderate-leverage refinement.
- **I3. `insource:/regex/`.** Source-text regex search. Find articles whose wikitext contains specific citation patterns ("PDB:[0-9]+" for protein topics, ISBN regex for specific publishers). Rate-limited but powerful. Moderate.
- **I4. `articletopic:`** (covered as D2).
- **I5. `boost-templates:"Featured_article|10"`** — bias search ranking toward quality. Tweaks `search_articles` to prefer canonical hits. Trivial.
- **I6. `prop=langlinks`** — explicit cross-language link list per article. Currently the only signal is via `wikidata_get_entity` sitelinks; `prop=langlinks` is sometimes faster. Trivial.
- **I7. `prop=iwlinks`** — interwiki links to sister projects (Wiktionary, Wikiquote, etc.) embedded directly in the article wikitext. Different from sitelinks — these are author-placed deep links. Trivial.
- **I8. `prop=images` + `commonswiki` `prop=globalusage`.** Article uses image X → Commons file X is used by which other Wikipedia articles? The image-usage chain finds visual-topic articles that don't share categories. Moderate.
- **I9. REST `/api/rest_v1/page/related/{title}`.** Reader-behavior-derived related pages — different from `morelike:` (text similarity). The "people who read X also read Y" signal. Trivial.
- **I10. REST `/api/rest_v1/page/references/{title}`.** Structured references with DOIs / external IDs. Pairs with A2. Trivial.
- **I11. `prop=pageassessments` (Top Pick #2).**
- **I12. `prop=info&inprop=protection|talkid|watchers`.** Protection level + watcher count. Watcher count is a centrality / engagement proxy. Moderate.
- **I13. `prop=transcludedin`.** Inverse of `prop=templates` — given a template, find all articles using it. Same effect as `hastemplate:` but from the API rather than search. Trivial.

### J. User-as-source

Currently, the user provides scope + rubric + reach probes. The user
could also provide *content* — a syllabus, a textbook ToC, a museum
exhibit list, a domain expert's reading list.

- **J1. Paste-list-and-resolve tool.** `resolve_to_articles(text)` — accept arbitrary user-pasted text (a syllabus, a ToC, a list of names), extract entity-shaped tokens, run `wbsearchentities` + `prop=info` per candidate, return the resolved enwiki titles. Trivial (entity extraction can be a simple heuristic + the AI's own parse).
- **J2. PDF / OCR ingest.** For academic survey papers, a reference section often lists 50–200 canonical works. PDF extraction + crosswalk. Heavy lift (PDF parsing).
- **J3. URL-as-seed.** "Take this https://nasa.gov/topic page and extract its outbound links to Wikipedia (or to canonical entities); resolve each." Useful for mission pages, museum sites, encyclopedia entries. Trivial-to-moderate (HTML parsing).

### K. Wikimedia Toolforge tools we don't wrap

These are services that already do interesting things but live
behind their own URL rather than in our toolkit.

- **K1. PetScan (deferred Tier 3).** Compound category queries with WikiProject + template + Wikidata constraints. The single most powerful "find articles" tool that exists. Trivial wrap. Note: deferred in current backlog because of overlap with `wikidata_query`, but PetScan covers cases SPARQL is awkward for (e.g., depth-N category intersection without enumerating all subcategories). Worth re-evaluating.
- **K2. SuggestBot.** Wikipedia's article-similarity recommender, based on co-edit graph. Different signal than `morelike:` (text) or `prop=related` (reader behavior). Moderate (Toolforge service, requires a wrap).
- **K3. XTools.** Per-article metadata: creation date, top editors, edit count, page assessment history. Centrality-adjacent telemetry. Trivial wrap.
- **K4. Quarry (`https://quarry.wmcloud.org`).** Direct SQL on a sanitized live replica. Queries impossible via API: "all articles created in 2024 in Category:Living people with <500 bytes," joins across `categorylinks`, `pagelinks`, `templatelinks`. Moderate (SQL-as-input).
- **K5. Listeria-bot tables.** SPARQL-backed list articles automatically maintained on enwiki. Often the most complete "list of X" for any Wikidata-covered topic. Detection: search for `{{Wikidata list}}` template usage. Trivial.

---

## Cross-cutting observations

Patterns I noticed while assembling the menu.

### "Read-the-article-harder" is the underexploited axis we just started touching

The `seed-anchored-mining-from-canonical-article` move was the door,
but the article still has more structure than we read: see-also
section (A1), references (A2), section outline (A4), bold lead
(A5), hatnotes (A6). All trivial wraps. All produce different
signals than category / WikiProject / search, and very different
signals from each other.

If the recent main-article ship was the proof-of-concept that
"reading the article" is a real strategy axis, the next iteration
should pull more from the article. Section structure alone could be
worth its own move.

### We've never used a popularity / quality signal of any kind

The current toolkit treats every article as equivalent in
importance until a human assigns centrality. But Wikipedia's
community + readership produce continuous-valued importance signals
*for free*: pageviews, sitelink count, FA/GA status, importance
ratings, ORES quality, watcher count, edit frequency. None of these
inform discovery, triage, or scoring today.

The aggregate cost of adding one tool that returns
`{pageviews, sitelinks, importance, class}` per title is small — it
probably pays for itself on the first 5,000-article topic where the
AI needs to triage.

### Sister projects are an entire parallel curation we ignore

Six sister projects (Commons, Wikiquote, Wikisource, Wikivoyage,
Wikibooks, Wiktionary) plus Wikinews. Each has its own categories,
its own editorial focus, its own gaps. A QID is the bridge. We
already have `wikidata_get_entity` returning sitelinks; we just
don't follow the non-Wikipedia ones.

The Commons category crosswalk in particular is so cheap and so
likely to surface visual-topic articles enwiki cats miss that I
think it's the single highest-value sister-project win.

### CirrusSearch has more knobs than we use

`hastemplate:`, `articletopic:`, `linksto:`, `insource:/regex/`,
`boost-templates:` — all available, all unused. Each is a thin move
documentation away from being usable. The biggest of these is
probably `articletopic:` because it's a free ML topic classifier we
could probe as an additional axis at zero infrastructure cost.

### External authority files are a meta-lever

Each external source (VIAF, LCSH, OpenAlex, GBIF, MusicBrainz, …)
crosswalks to Wikipedia via Wikidata external-ID properties. A
single tool `wikidata_external_id_crosswalk(property, value)` would
unlock ~10 sources at once. The cost is moderate; the leverage is
high for any topic where the external taxonomy is deeper than
Wikipedia's. Biology + libraries + academia are the obvious
beneficiaries.

### The graph-as-graph axis is the only one with real ML/infra cost

Most of the menu is trivial-or-moderate. The exceptions are:
- Embeddings (D4) — needs vector DB + a model
- Cross-encoder reranker (D5) — server-side LLM costs
- PageRank / community detection (G1/G5) — needs scratch graph + algorithms
- PDF ingest (J2) — PDF parsing is always rough

These are real engineering. They'd produce strong signals but
shouldn't be the first thing built.

### The "ML capabilities" framing is partially a misnomer

Several "AI capability" ideas (D1: LLM-as-generator, D7:
LLM-judged related expansion, D6: LLM-driven SPARQL) don't need
new infrastructure — they need a *new posture*. The AI can
fabricate candidate titles right now; we just don't have a *move*
that says "do this and verify with `prop=info`." Adding the move
is free.

---

## What I'd promote first

**Promotion pass 2026-04-27.** The original brainstorm ranked six items; Sage flagged three as easy wins, kept three on the menu, deprioritized the centrality-signals cluster.

**Promoted to Tier 1 (in `backlog/README.md`):**

1. **"See also" section harvest** — trivial wrap, high-precision reach extension structurally different from `morelike:` / category / WikiProject / navbox. Especially valuable on intersectional or movement-shape topics where editorial curation is dense.
2. **`hastemplate:` move documentation + `articletopic:` companion** — zero new code; just named moves with COMMON TASK → TOOL rows. Both unlock typed-thing queries at zero infra cost.
3. **LLM-as-generator move** — free; just adds a documented move with rescue paths. Useful when the topic shape is sparse on canonical surfaces (non-Anglosphere, niche historical, recent events).

The first ship is < 1 day of work each.

**Deprioritized "right now" — pageviews + assessments + sitelink-count cluster.** My original brainstorm framed these as triage signals the AI would consume, but per CLAUDE.md "Centrality is AI judgment, not tool computation" — the principle covers signal-surfacing tools too, not just direct score-writers. Kept on the menu for record-keeping; revisit only on a multi-session signal pointing at one specifically.

**Still on the menu** for later promotion when a signal arrives or a slot opens:

- **Commons category crosswalk** (Top Pick #5 partial). New tool `crosswalk_commons_category(qid)`. Moderate integration. Strongest single sister-project win.
- **External-authority meta-tool** (axis C). `wikidata_external_id_crosswalk(property, value, return_wiki="en")`. Unlocks ~10 external sources with one moderate-integration item. Especially valuable for academic / library / biology shapes that defeat enwiki categorization.
- The article-internals axis (A) still has follow-on items beyond See also — references, external links, section structure, bold-first-phrase, hatnotes — all cheap if a second multi-session signal supports them.

---

## What's not in this doc

- Concrete tool signatures, parameter shapes, error semantics. This is brainstorm; if any item gets promoted to backlog, *that* doc captures the shape.
- Prioritization against existing backlog items. The existing Tier 1 list (`preview_wikidata_property`, type-hinted harvest annotation, confabulation crosscheck widening, exclude_sources investigation, at-pull-time intersection) stays first in line; this is "what to add to the queue *behind* those."
- Items that mostly extend tools we already have. Those go straight to `backlog/README.md` with their evidence.

The list above is meant to outlast a single grooming cycle. Step
through it at whatever rhythm makes sense; promote items as
multi-session evidence builds.
