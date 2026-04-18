# Topic-building strategies by topic type

Working document. Each topic type has its own best-practice call shapes;
what works for intersectional biographies won't work for climate-change
concept articles, or for geographic topics, or for "all papers citing X."

This is advice for the AI (and for humans driving the AI) about which
tools and patterns to reach for first. Observations here are meant to
graduate into `mcp_server/server_instructions.md` once we've seen them
hold up across multiple topics.

## Cross-cutting principles (apply to every topic)

- **Scope first, gather second.** `scope.md`-shaped plain-language
  confirmation before any gather call. Bake ambiguity rulings explicitly;
  re-audit becomes possible later if scope changes.
- **Always `fetch_descriptions` after gathering.** Enables
  `auto_score_by_description`, `remove_by_pattern(match_description=True)`,
  and surfaces lead-level evidence in `get_articles` output. Cheap (~1
  sec per 500 articles), pays back throughout the rest of the session.
- **Preview broad searches.** `preview_search` before `search_articles`
  whenever the query is `morelike:<seed>` or a keyword search expected
  to return >50 results. Cleaning is harder than not committing.
- **Use per-query source provenance.** `remove_by_source("search:morelike:X", prefix_match=True)`
  surgically drops a specific bad pull without blanket-clearing search.
- **Benchmark the topic if it's long-lived.** `benchmarks/<slug>/`
  captures a frozen scope, a scripted call sequence, and a gold set so
  you can measure whether tool/prompt changes improve recall or precision.

## Topic type: Intersectional biography (demographic × profession)

**Examples:** Hispanic and Latino people in STEM in the United States;
women mathematicians; African-American physicists; LGBTQ+ scientists.

**Why these topics are hard:** Wikipedia's category tree doesn't
reliably place a person at the intersection. Someone is typically
categorized by demographic *or* by profession, rarely at the full
intersection. Short descriptions often elide one axis — especially
demographic identity for Americans (shortdesc tends to just say
"American neuroscientist" regardless of Hispanic heritage).

### Recommended call shape

1. **Main intersection category** (if one exists) at `depth=3`.
   - Example: `get_category_articles("Hispanic and Latino American scientists", depth=3)`.
   - Expect ~70% recall from this pull alone if the category is well-curated.

2. **Narrower intersection categories** at `depth=2-3`.
   - Example: Puerto Rican engineers/inventors/women scientists.
   - Higher precision (75-85%) but smaller contribution.

3. **Broad demographic category** at `depth=2` **as last-resort recall**.
   - Example: "Hispanic and Latino American academics" catches people the
     scientists tree missed, but at ~15% precision on unique contribution.
   - Include it *only if* you're also running aggressive downstream
     cleanup (`auto_score_by_description` + description-based pattern
     removal). Otherwise it drags precision hard.

4. **Demographic-anchored CirrusSearch queries** — **one per relevant
   sub-demographic**. Each contributes 2-10 unique gold-IN.
   ```
   search_articles('incategory:"American people of Mexican descent"
                   (scientist OR engineer OR mathematician OR physicist OR
                    biologist OR chemist OR astronaut OR inventor OR
                    technologist OR neuroscientist)')
   ```
   - Cover the full list of relevant nationalities / sub-demographics.
     For Hispanic/Latino US STEM, that's ~12 nationalities. Missing any
     one drops a handful of gold-IN.
   - CirrusSearch caps at 500 results but typical descent × STEM searches
     return 20-100.

5. **Cleanup and scoring:**
   - `filter_articles` — drops redirects, disambiguations, year-in-X
     meta pages.
   - `fetch_descriptions` — populates the description column.
   - `auto_score_by_description` with **profession-only axis** and a
     **broad disqualifying list**. For intersectional topics the
     demographic axis is unreliable (shortdescs elide it); don't use it.
     Disqualifying list should include common off-scope professions
     (actor / politician / economist / etc. depending on your scope).

### What doesn't work

- **`morelike:` searches without post-filter.** Similarity weights
  profession over demographic; seeding from a known Hispanic scientist
  pulls in mostly non-Hispanic scientists. If you use `morelike:`, go
  via `preview_search` and commit only the filtered subset.
- **Cross-profession descent category pulls** (e.g.,
  `"American academics of Mexican descent"`). These turn out to be true
  subsets of what the main tree + descent searches already cover. No
  novel contribution, extra noise.
- **`required_any` demographic axis in `auto_score_by_description`.**
  Cuts too aggressively because shortdescs often don't state Hispanic
  identity; you'd lose ~70% of legitimate IN. Profession axis only.

### Expected benchmark shape for this topic class

Based on the hispanic-latino-stem-us benchmark (our first measured topic
of this type):

- Recall: 83-87% achievable with a 20-call session
- Precision against gold: 48-55% pre-export (high noise because the
  demographic axis can't be filtered algorithmically)
- `auto_score_by_description` eliminates the high-confidence noise
  (~60-70% of non-matches); the residual low-confidence noise requires
  human scoring.
- Expect 30-40 gold-positive misses after a single pass. Those tend to
  be people with Anglicized names whose heritage is mentioned only
  mid-article, and niche nationalities not covered by the descent
  searches.

---

## Topic type: Single-axis biography (e.g., "Nobel laureates in Chemistry")

*Not yet benchmarked. Expected to behave more like a clean category
pull — the axis is explicit in Wikipedia's category structure. Lower
noise, higher precision, less dependence on intersection searches.*

---

## Topic type: Geographic subject (e.g., "Seattle")

*Benchmarked informally via the 2026-04-17 dogfood of "Seattle" (2829
articles). Observations to come after a formal benchmark run.*

---

## Topic type: Concept / scientific field (e.g., "Climate change")

*Not yet benchmarked. Expected to rely more heavily on WikiProject
assessment banners than category trees — concepts/fields have
dedicated WikiProjects with thousands of tagged articles. `morelike:`
from canonical articles in the field is probably less dangerous here
than for biographies, since similarity tends to stay within the
subject area.*

---

## Topic type: Event / time-bounded subject (e.g., "Civil Rights Movement")

*Not yet benchmarked. Will likely involve heavy use of list-page
harvest (e.g., "Timeline of…", "Events in…"), category trees rooted
in the event name, and careful filtering of meta-pages like year-in-X.*

---

## How this document grows

When you benchmark a new topic:
1. Add it under `benchmarks/<slug>/` with `scope.md`, `gold.csv`,
   `calls.jsonl`.
2. Try 3-5 call-sequence variants to identify which strategies
   contribute uniquely (vs. are subsumed by other strategies).
3. Write up the findings here under the appropriate topic type, keyed
   to the specific tools and patterns the topic rewards.
4. When patterns repeat across 2-3 topics of the same type, graduate
   the guidance into `mcp_server/server_instructions.md` so the AI
   sees it on every session.
