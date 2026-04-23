# Post-orchids improvements plan

Ordered roadmap derived from the orchids dogfood (2026-04-22). Four orchids-feedback rounds submitted (all rated 8/10): initial enwiki build (18,089 articles), cross-wiki session (adds orchids-zh 1,808, orchids-ja 367, orchids-pt 2,265), the nlwiki extension + reconciliation round (adds orchids-nl 135; primary topic grew to 18,122 via 21 cross-wiki gap-fills), and a Q&A round where the AI answered seven explicit reflection prompts. Plus one independent user feedback from the Kochutensilien (dewiki) build providing a second-persona signal. Sources: the AI-submitted feedback in `/opt/topic-builder/logs/feedback.jsonl`, the AI's own updated `playbook.md` (v2, 120 lines), three transcript segments, and current DB state.

This is a working doc. Sage will step through items in order, decide go/no-go/reshape per item, then we build.

**Status legend:** ☐ not started · ◐ in progress · ☑ shipped · ✗ dropped

**Cross-reference:** items already on `docs/operations-and-backlog.md` are tagged `[backlog:#]`; new items are tagged `[NEW]`.

---

## Stage 1 — Quick ship

Small code changes, orchids-evidenced, each independently shippable. Target: one deploy per item or small group.

### 1.1 ☑ Observability backfill: missing logs + per-call cost fields `[backlog:flagged 2026-04-17 + NEW]`

**Shipped 2026-04-22.** All three parts landed in one commit: log coverage on 16 previously-unlogged tools; `ContextVar`-based per-call counters (`wikipedia_api_calls`, `rate_limit_hits_this_call`) hooked into `wikipedia_api.api_get`; `elapsed_ms` + `timed_out` fields on every log entry; `note: str = ""` parameter on all 27 `@mcp.tool` functions that log. Pre-flight confirmed backoff is real (linear, 3 attempts, honors `Retry-After`); flagged a maxlag-200 detection gap for later follow-up. Existing log entries not backfilled (plan decision — reader tolerates both shapes).


**What (part A — coverage).** Add `log_usage` to the ~16 tools that don't have it: `harvest_list_page`, `add_articles`, `remove_articles`, `remove_by_source`, `remove_by_pattern`, `filter_articles`, `score_all_unscored`, `auto_score_by_title`, `set_scores`, `score_by_extract`, `search_similar`, `browse_edges`, `check_wikiproject`, `find_list_pages`, `list_sources`, `get_articles_by_source`.

**What (part B — cost fields).** Every log entry, new and existing, gains:
- `elapsed_ms` — total tool wall time
- `wikipedia_api_calls` — count of upstream `api.php` hits the call made
- `rate_limit_hits_this_call` — delta rate-limit events attributable to this call (not cumulative)
- `timed_out` — explicit bool, separate from `result` text

This turns `usage.jsonl` from "what happened" into "what happened and what it cost." Benchmark replay + regression testing need the numbers; without them we're arguing about shape not signal.

**What (part C — reflection field).** Every `@mcp.tool`-decorated tool in `server.py` gains an optional `note: str = ""` parameter (in the signature, excluded from the client-visible schema would defeat the purpose — it must be client-visible). When the AI passes `note=...`, the string is captured in the log entry alongside the other fields. Zero-ceremony way for the AI to drop a mid-flow observation at the moment it happens, without the weight of a `submit_feedback` call. Example: `remove_by_source("search:morelike:Orchid Thief", keep_if_other_sources=True, note="morelike went sideways — seed article was adapted into a film, pulled Streep filmography")`.

Scope: add `note` to all tools that call `log_usage` (the gather / mutation / export-shaped ones). Pure read-only queries that don't log don't need it.

Pairs with 2.6 (event-triggered reflection guidance) and 1.18 (auto-nudge on resume). Together these form "reflection instrumentation" alongside part B's "cost instrumentation" — same mental model (richer logs), different axis (AI-provided vs auto-derived).

**Why.** The en orchids topic has 82 logged calls across 8 sessions, but feedback alone references 16 `harvest_list_page` calls plus dozens of mutation calls. Three timeouts happened in orchids with no per-call cost record. Native American scientists session flagged the coverage gap in April. Neither problem goes away on its own.

**Shape.** Coverage part is boilerplate — match the existing `log_usage` pattern. Cost-fields part needs `wikipedia_api.py` to expose a thread-local / contextvar counter that `log_usage` reads at the end of a tool call. Low-intrusion: the counter increments on every outbound HTTP request inside the client; tools don't need to know it exists.

**Open questions.**
- Any PII / large-payload concerns for logging `titles` arrays on `add_articles` / `remove_articles`? Probably fine — log a count and sample, not the full list.
- Do we backfill cost fields on existing 351 entries? No — they stay as-is, new entries get the richer schema. Reader tolerates both.

**Sequencing note.** Ship this first. Everything downstream (1.11, 1.12, benchmarks) reads these fields.

**Pre-flight investigation (before any code).** Read `mcp_server/wikipedia_api.py` end-to-end. Verify that the HTTP client (a) has a clear single place to hook the API-call counter — likely the request wrapper — and (b) actually backs off on Wikimedia rate-limit responses rather than just counting and proceeding. The counter + backoff live in the same file, so both get resolved in one pass. See "Rate-limit backoff review" in the Smaller items section.

---

### 1.2 ☑ `harvest_list_page(main_content_only=True)` `[NEW]`

**Shipped 2026-04-22.** Default True. Uses `action=parse&prop=text` + a stdlib `html.parser.HTMLParser` subclass that walks a proper tag stack, tracks excluded-subtree depth (`navbox`, `sidebar`, `infobox`, `reflist`, `hatnote`, `shortdescription`, `catlinks`, `toc`, `mw-editsection`, etc.), and drops everything past a `See_also` / `External_links` / `References` / `Further_reading` / `Notes` / `Bibliography` heading. Link extraction uses the `title="..."` attribute (not href), which captures **both blue links and redlinks** in one pass — matters on species lists where the majority are redlinks to articles that don't exist yet. Validated against 5 real list-page shapes: SA orchids list dropped 809 of 1,503 as navbox noise (matches plan's 838 estimate); `List of orchid genera` / `Outline of climate change` went from 1 → 819 / 279 because `prop=links` misses transcluded content that HTML rendering includes; `List of orchidologists` kept all 100 with zero false exclusions. Falls back to the old `prop=links` path when `main_content_only=False`, and automatically when the parse endpoint returns empty (e.g., missing page).


**What.** New bool param. When True, only pull links from the article body's tables/lists, skipping navboxes, sidebars, see-also sections, sibling-list meta-navboxes.

**Why.** Single biggest quality issue from the session. `List of Orchidaceae of South Africa` harvested 1,503 links; 838 (68%) were biodiversity-navbox noise — vegetation types, marine protected areas, taxonomic-rank pages, sibling "List of X of South Africa" meta-pages. AI had to write a local Python binomial-classifier and feed back 5 batches of 200 `remove_articles` calls.

**Shape.** Parse via MediaWiki `action=parse&prop=text` → scope link extraction to `.mw-parser-output > *` while excluding `.navbox`, `.sidebar`, `.navbox-group`, `.metadata`, `.reflist`, sections with `id="See_also"` / `id="External_links"` / `id="References"`. Worth testing against 5–10 list-page shapes first.

**Open questions.**
- Default True or False? Leaning True — orchids feedback says "would have reduced 68% noise to near-zero." Users who want navbox content can opt out.
- Does this break the playbook's implicit "preview the list page visually first"? No — this makes that step optional.

---

### 1.3 ☑ `preview_similar` tool `[NEW]`

**Shipped 2026-04-22.** Delegates to `preview_search(morelike:<seed>, ...)` the same way `search_similar` delegates to `search_articles`. Kept as a separate tool (not a commit-flag on search_similar) to match 1.4's `preview_*` naming convention and avoid breaking cached ChatGPT client schemas.


**What.** Read-only sibling to `search_similar` (morelike). Returns titles + descriptions + already-in-topic flags without committing.

**Why.** `search_similar("The Orchid Thief")` pulled Meryl Streep's filmography (she starred in the adaptation); AI reverted immediately. Feedback explicitly asks for this. The PREVIEW BEFORE COMMIT instruction landed 2026-04-17 but the tool to execute it for morelike doesn't exist.

**Shape.** Mirror `preview_search`: `preview_similar(seed_article, limit=50, wiki=None, ctx=None)`. Share as much code with `search_similar` as possible — only the "commit to topic" step differs.

**Open questions.**
- Alternative: flip `search_similar` default to preview-mode with `commit=True` flag. Less risk of the AI forgetting to preview; breaks any existing callers. We don't have many. Either works.
- Sibling to consider: `preview_harvest_list_page` — see 1.4.

---

### 1.4 ☑ `preview_harvest_list_page` and `preview_category_pull` `[backlog:#5 + NEW]`

**Shipped 2026-04-22.** Two new tools with matched `preview_*` naming (Sage confirmed this convention over `dry_run=True` flags). Both share logic with their commit-variant siblings via two extracted helpers: `_fetch_list_page_links(title, wiki, main_content_only)` and `_walk_category_tree(category, depth, exclude_set, max_articles, wiki)`. Scope-drift warning extracted to `_scope_drift_warning()` and now fires on both `get_category_articles` and `preview_category_pull`. Preview tools only fetch descriptions for the sample (default 50), so preview cost stays close to the commit-variant cost even on 10K-article subtrees.


**What.** Dry-run variants of `harvest_list_page` and `get_category_articles`. Return link count + sample of titles + new-vs-overlap ratio without committing.

**Why.** Orchids feedback: "A dry-run mode for `harvest_list_page` would have let me catch the SA contamination before it happened." Already on the backlog for categories (#5, ed-psych feedback).

**Shape.** Matched pair. `preview_harvest_list_page(title, sample_size=50)` returns `{"total_links": N, "already_in_topic": K, "sample": [titles], "navbox_links_detected": M}`. Similar shape for categories.

**Open questions.** Can these be implemented as flags on the existing tools (`dry_run=True`) rather than new tools? Probably, and it's simpler — but matched-sibling naming (`preview_*`) might be clearer to the AI. Pick one convention and stick.

**Sequencing note.** Partial overlap with 1.2 on list-page parsing — ship 1.2 first or together, not before.

---

### 1.5 ☑ `get_articles(title_regex=..., description_regex=...)` + source labels in output `[NEW]`

**Shipped 2026-04-22 (grouped with 1.20).** Added `title_regex` and `description_regex` params with Python `re.search` semantics (case-insensitive). Invalid patterns return a structured error rather than 500. `sources` array was already in the get_articles response — left name unchanged for continuity. Filtering now happens entirely in Python so `total_matching` is accurate across all filters (the old code undercounted when `source` was set and paginated).


**What.** Two new optional filter params on the existing `get_articles` tool, plus include each article's `source_labels` list in the output schema (currently returns title + description only).

**Why.** Orchids SA cleanup: the AI wrote a local Python binomial-classifier (`re.match(r'^[A-Z][a-z]+ [a-z]+$')`) because the tool had no way to filter by title pattern. `remove_by_pattern` has `match_description` but `get_articles` doesn't — breaks the natural "inspect before remove" flow.

The AI's Q5 answer named this "the single biggest gap." Also Q&A-round request: "when I'm paging `get_articles` I can see title + description but not 'this came from category:X AND list_page:Y' — which affects how much I trust its relevance."

**Shape.** SQL-level regex. SQLite's `REGEXP` isn't built in but trivial to register as a Python function at connection time. Keep the filter logic consistent between `get_articles` and `remove_by_pattern`. Source-labels column already exists on the `articles` table — just project it into the response.

**Open questions.** Whitelist vs blacklist semantics — confirm with user a pattern like `title_regex="^[A-Z][a-z]+ [a-z]+$"` filters *to matches*, not *out*.

---

### 1.6 ☑ `fetch_descriptions` defaults + auto-loop `[NEW]`

**Shipped 2026-04-22.** Default `limit` bumped 500 → 2000. Added auto-loop that keeps fetching batches until the topic is fully described or `time_budget_s` (default 60) is exhausted. Return shape gained `batches_run` + `time_budget_exhausted` so the AI knows whether to call again. One call on a fresh topic typically drains the backlog; 18K-article orchids would fit under budget at ~50 Wikipedia API calls.


**What.** Bump default `limit` from 50 → 2000. Add auto-loop: if `remaining_undescribed > 0` after the call, continue paging internally until zero or a timeout budget is exhausted.

**Why.** Feedback: "I kept bumping the limit to 2000 to move faster... make it hard to tell when you're done." On a 18K topic, 50-per-call = 360 round-trips.

**Shape.** Single-call API stays the same from the AI's perspective. Internal loop respects rate-limit + overall time budget.

**Open questions.**
- What's the time budget for the internal loop before we return partial? 60s feels right — keeps it from blocking other calls.
- Do we still return `remaining_undescribed` so the AI knows to re-call? Yes, always.

---

### 1.7 ☑ `remove_articles` auto-chunking + documented limit `[NEW]`

**Shipped 2026-04-22.** Pre-flight: the ~200-cap the orchids AI hit was NOT in server/db code (inspected — db.remove_articles had no cap and looped one title at a time). It was a client-side truncation by the MCP client. Server-side fixes: (a) batched the DB side into `DELETE … WHERE title IN (…)` statements of up to 500 titles each (was one DELETE per title); (b) rewrote the docstring to explicitly point AI at `remove_by_source` / `remove_by_pattern` for large removals, with the observation that some MCP clients cap `titles` around ~200. No code change needed on the tool signature.


**What.** Tool currently has an undocumented ~200-title cap. Either auto-chunk internally or document the limit prominently.

**Why.** AI had to manually split 839 titles into batches of 200 during SA cleanup. Feedback flagged it as undocumented.

**Shape.** Auto-chunk is friendlier; document the internal chunking in the docstring and server instructions so the AI understands the cost.

**Open questions.** Is the 200 cap from a specific DB / HTTP reason, or legacy? If legacy, maybe lift it entirely. Worth checking before deciding auto-chunk vs. lift.

---

### 1.8 ☐ `browse_edges(min_links="auto")` `[NEW]`

**What.** Auto-calibrated threshold that targets 20–50 candidates.

**Why.** Feedback: "I tried 10 seeds at `min_links=5` and got back only 2 candidates — both too general." Threshold semantics aren't intuitive.

**Shape.** Start at `min_links=3`, probe upward until candidate count falls into the 20–50 band. Or reverse-engineer: compute a threshold from the seed count.

**Open questions.** Deferred — low urgency, `browse_edges` wasn't central to orchids. Could slot into Stage 2 if it turns out to be a docstring tweak rather than new logic.

---

### 1.9 ☑ `check_wikiproject` discovery `[NEW]`

**Shipped 2026-04-22.** Part (b) — hard warning on non-en — was already in place; verified. Part (a) added via new `find_wikiprojects(keywords, limit=20)` tool. Uses MediaWiki `list=prefixsearch` on the Wikipedia: namespace to enumerate projects whose names start with "WikiProject <keyword>". Skips task-force / subpage noise by dropping titles containing "/". Hard-enwiki (ignores topic wiki) — returns empty for non-en keywords, matching the "WikiProjects are enwiki-only" reality. Docstring points back to `check_wikiproject` + `get_wikiproject_articles` for the next step.


**What.** (a) Better discovery of en WikiProjects via fuzzy-match or a new `find_wikiprojects(topic_keywords)` that enumerates candidates. (b) A hard warning when `check_wikiproject` is called against a non-en wiki — WikiProjects are an enwiki convention.

**Why.** Orchids transcript: AI probed "WikiProject Plants," saw it was too broad, and skipped WikiProject entirely — never tried "WikiProject Orchids" which exists on en and would have been the cleanest backbone. The pattern "negative first probe → abandon tool" is also on the backlog as the `preview_search` bypass issue.

Updated playbook confirms WikiProjects are essentially en-only — which narrows the design: we don't need cross-wiki WikiProject discovery, we need (i) better en discovery and (ii) clear "this is en-only" signaling on non-en wikis.

**Shape.**
- For en: `find_wikiprojects(keywords, wiki="en")` pulls all `Wikipedia:WikiProject <X>` pages matching; AI picks one. Or fuzzy-match on `check_wikiproject` input.
- For non-en: `check_wikiproject` returns a clear error/warning ("WikiProjects are a Wikipedia-English convention; skip this step for non-en topics") rather than a generic empty result.

**Open questions.** De/nl/fr wikis have limited WikiProject equivalents; not worth surfacing now. Document the gap in instructions instead.

---

### 1.10 ☑ `search_articles(within_category=...)` / scope-narrowed search `[NEW]`

**Shipped 2026-04-22.** Added `within_category: str | None` to both `search_articles` and `preview_search`. Appends `incategory:"<cat>"` to the query via a shared `_apply_within_category` helper. Single-level (CirrusSearch's `incategory:` does not walk subcats); documented in the docstring. Users who want union can pass `"A|B|C"`; users who want recursive should use `get_category_articles` instead. Response surfaces `effective_query` (the actual query sent to Wikipedia) and `within_category` so the AI can cite/audit scope.


**What.** Optional filter param to scope full-text search to a category tree.

**Why.** Reduces false positives from tangential matches. AI repeatedly had to write followup preview-searches to narrow scope.

**Shape.** Wikipedia CirrusSearch supports `incategory:` directly. Thin wrapper — same on `preview_search`.

**Open questions.** Depth handling for category filter — single-level or recursive? Recursive matches how the AI uses `get_category_articles` today.

---

### 1.11 ☑ Pre-flight cost estimates for heavy tools `[NEW]`

**Shipped 2026-04-22.** Pivoted from the plan's original "pre-flight estimation" shape because the `preview_*` tools (1.4) already cover that — the AI can call `preview_category_pull` / `preview_harvest_list_page` for pre-flight counts. What was missing was the AI seeing actual cost **after** a heavy pull so it can calibrate next time. `_cost_report(start_time)` now appends `{elapsed_ms, wikipedia_api_calls}` + a `cost_warning` string (when API calls > 2,500 OR elapsed > 60s) to the response of `get_category_articles`, `harvest_list_page`, `filter_articles`. Thresholds are placeholder — 1.12 adds cross-topic aggregation that'll let us tune them.


**What.** Before the real work, heavy tools cheaply estimate cost and return a soft warning if the estimate exceeds a threshold.

**Applies to.** `get_category_articles`, `harvest_list_page`, `filter_articles` — the three known-heavy offenders that timed out or overran in orchids.

**Why.** The AI's own playbook has the rule "count estimated articles and decide crawl depth" — right now that lives only in the AI's head and requires it to remember to call `survey_categories(count_articles=True)` first. Make the estimate happen automatically, surface it to the AI, let the AI decide.

**Shape.** Each heavy tool does a cheap pre-count:
- `get_category_articles`: run `survey_categories` internally at the same depth, count articles.
- `harvest_list_page`: `action=parse&prop=sections&prop=links` to count outbound links before fetching bodies.
- `filter_articles`: the topic's current article count is already known; estimate time from count.

If the estimate exceeds a threshold (e.g. 2,500 API calls, or 5K articles, or projected 90s elapsed), return a soft warning in the response:
```json
{
  "cost_warning": "This call will make an estimated 2,500 Wikimedia API requests and likely exceed 300s. Consider narrowing scope (lower depth, specific subtree) or accepting partial results.",
  "estimated_api_calls": 2500,
  "estimated_elapsed_ms": 90000,
  ...
}
```

Don't *refuse* — the AI can still proceed. Make the cost visible *before* the timeout happens.

**Open questions.**
- Thresholds. Empirical — needs calibration against real timings once 1.1 ships (so we have elapsed_ms data to fit against).
- Should the AI be able to say "I acknowledged the warning, proceed with higher time budget"? Probably yes via a `force=True` param. Otherwise the AI loops on the same warning every time.
- Does the pre-flight itself become a meaningful API cost? Category-tree surveys can be heavy. Worth checking — may need its own cache.

---

### 1.12 ☑ Per-topic cost surface in `get_status` `[NEW]`

**Shipped 2026-04-22.** `_topic_cost_summary(topic_name)` scans the last 20K lines of `usage.jsonl` and aggregates: `logged_tool_calls`, `lifetime_wikipedia_api_calls`, `lifetime_timeouts`, `rate_limit_hits_total`, plus a `recent_heavy_calls` tail (last 10 calls that exceeded 500 API calls, 30s wall time, OR timed out). `get_status` includes the summary under `cost_summary`. No per-topic materialization; read-from-log is cheap at current corpus sizes. Log entries pre-1.1 missing the cost fields simply contribute 0 — the aggregation degrades gracefully.


**What.** `get_status` aggregates per-topic: total Wikimedia API calls, total timeouts, recent heavy calls, total rate-limit hits.

**Why.** Today rate-limit info is session-scoped (and coarse). A per-topic rollup answers "is this topic being a good Wikimedia citizen?" and gives the AI/user a moment to notice heaviness trending up. Also useful for operational review — which topics are expensive?

**Shape.** Aggregate from `usage.jsonl` on read (once 1.1 ships, cost fields are there). Cheap — one filter over the log. Display as:
```json
{
  "lifetime_wikipedia_api_calls": 42871,
  "lifetime_timeouts": 3,
  "recent_heavy_calls": [
    {"tool": "get_category_articles", "elapsed_ms": 300120, "wikipedia_api_calls": 7421, "timed_out": true, "ts": "..."},
    ...
  ],
  "rate_limit_hits_total": 0
}
```

**Open questions.**
- Storage: compute on read from the log, or materialize into the DB? Read-from-log is simpler; materialize if it becomes slow at scale. Start with read-from-log.
- Does this belong in `get_status` (AI-facing) or a separate admin endpoint? Both, maybe. The AI benefits from seeing recent heaviness; Sage benefits from cross-topic aggregation. Consider splitting if `get_status` starts ballooning.

---

### 1.13 ☑ `auto_score_by_title` rethink → `auto_score_by_keyword(keywords=[...])` `[NEW]`

**Shipped 2026-04-22.** Renamed (Sage confirmed no backward-compat concern). New signature requires explicit `keywords: list[str]` — no topic-name fallback. Params: `score=9` (was `threshold=7`; +2-to-10 implicit mapping dropped; cleaner to expose directly), `match_description=False` (search descriptions too), `overwrite_scored=False`. Error response when `keywords=[]` is structured JSON with a hint steering toward language-appropriate terms (`["ラン","兰","蘭"]` on ja/zh, Latin genera for taxonomy). `session_status.py` gets a legacy alias so old `auto_score_by_title` usage.jsonl entries still classify correctly in status reports.


**What.** `auto_score_by_title` currently does a literal substring match of the topic name against each article title. That's broken for three common cases that the orchids session exposed. Replace or augment it.

**Why.** From the second feedback:
- Non-en wikis: ran on `orchids-zh`, matched 0 of 1,773 — the ASCII string "orchids" doesn't appear in Chinese article titles.
- Suffixed topic names: `orchids-pt` matches nothing — literal "orchids-pt" isn't in any article title.
- Taxonomy topics: on en, "orchids" matched ~100 of 18,000 because species titles are Latin binomials ("Bulbophyllum nutans") that don't contain "orchid".

**Shape.** Accept an explicit `keywords=[...]` list. Either rename to `auto_score_by_keyword` (clearer intent) or add the param to the existing tool for backward compat. Example: `auto_score_by_keyword(keywords=["orchid", "orchidaceae", "orquídea", "ラン", "兰", "蘭", "Bulbophyllum", "Cattleya", ...])`. Match is case-insensitive substring across titles.

**Open questions.**
- Keep the topic-name-derived fallback if no `keywords` passed? Or require keywords explicitly? Probably fallback for continuity, but emit a cost_warning if the derived keyword list looks empty or ASCII-on-non-ASCII-wiki.
- Should this also look at descriptions, not just titles? Probably — and at that point it's close to `auto_score_by_description` with a keyword list. Consider unification.

---

### 1.14 ☑ Source-label slugification for `search_articles` commit variant `[NEW]`

**Shipped 2026-04-22.** `_slugify_for_source_label` preserves `:` operator separators (so `morelike:the-orchid-thief` stays intact), strips Latin combining diacritics, replaces punctuation/whitespace with `-`, and **preserves non-Latin Unicode letters** (CJK, Cyrillic, etc.) — without that escape hatch `morelike:牧野富太郎` would collapse to bare `morelike` and lose all seed info. Truncates at 60 chars; empty input → `"unnamed"`. Applied only at label creation time in `search_articles` — existing DB rows keep their legacy labels (plan decision). morelike-prefixed labels get the same treatment since the helper is query-agnostic.


**What.** Clean up source labels produced by `search_articles(query)`. Today labels preserve the full query string including diacritics and special chars: `search:Laelia orquídea brasileira`. These pollute `list_sources` output and are hard to reference in `remove_by_source`.

**Why.** Second feedback: "Those labels are hard to reference cleanly in subsequent remove_by_source calls and clutter the list_sources output."

**Shape.** Options:
- Slugify the query: `search:laelia-orquidea-brasileira` (lowercase, hyphens, diacritic-strip). Readable + referenceable.
- Hash: `search:a4f2b9`. Short but opaque.
- Sequence: `search:1`, `search:2`, ... with the full query in a metadata field.

Leaning slugify — preserves human readability while making labels tractable. Truncate to ~60 chars.

**Open questions.**
- Backward compat: existing labels in the DB have the old format. Migrate or leave as-is? Probably leave — new searches get new format.
- Same issue affects `search:morelike:<seed>` labels to a lesser degree (seed titles also have spaces/punctuation). Consider applying consistently.

---

### 1.15 ☑ Suppress no-word-overlap warning for obvious taxonomy pulls `[NEW]`

**Shipped 2026-04-22.** `_looks_taxonomic(topic_name, category)` gates `_scope_drift_warning`. Suppresses when (topic name contains a biology keyword like "orchid"/"bird"/"plant"/"fungus"/… OR has a `-aceae`/`-idae`/`-ales`/`-phyta`/`-ae` suffix word) AND the category name matches a Latin-genus pattern (single capitalized ASCII word, 3+ chars). Accepted tradeoff: "Cognition" under an orchids topic gets suppressed (false negative for scope drift), but the plan explicitly called this marginal — the AI catches real noise via post-hoc review regardless.


**What.** The "no word-level overlap between topic name and category name" warning fires on every Latin-genus pull (`category:Bulbophyllum`, `category:Cattleya`, etc.) for a topic named "orchids-pt", because Latin names share no characters with "orchid".

**Why.** Second feedback: "For taxonomy topics the warning is ~100% false-positive rate." The AI learns to ignore all warnings from the tool, which is exactly the opposite of what we want cost warnings to achieve (see 1.11).

**Shape.** Detect taxonomy context and suppress:
- Topic name contains a biological-classification keyword (`orchid`, `plant`, `bird`, `mammal`, `fungus`, `-aceae`, etc.), AND
- The target category name looks like a Latin-binomial-producing node (single capitalized word matching typical genus pattern)
→ suppress the warning.

Alternative / additive: learn from context — if the topic already contains 100+ Latin-binomial titles, don't warn on category pulls.

**Open questions.**
- False negatives (suppressing a warning that should fire)? Marginal — a topic with orchid keywords pulling an unrelated Latin genus is rare and the AI catches it via noise review anyway.
- Does this generalize to other false-positive warnings? Probably — worth auditing all warnings in the server once we're in here.

---

### 1.16 ☑ Export CSV enrichment `[NEW]`

**Shipped 2026-04-22.** Added `enriched: bool = False` param. Default behavior unchanged (two-column `title, description`, no header — matches Impact Visualizer import). When `enriched=True`, writes a five-column CSV with a header row: `title, description, score, source_labels, first_added_at`. `source_labels` is pipe-separated to avoid collision with comma in label names. `wikidata_qid` skipped until 5.6 populates QIDs. Enriched file gets a `-enriched` suffix so both variants can coexist in the exports dir. IV compat check deferred per Sage — the opt-in flag preserves the IV path.


**What.** `export_csv` currently outputs `title, description`. Add columns: `source_labels`, `score`, `wikidata_qid`, `first_added_at`.

**Why.** Second feedback: "Trivial to add and enables much richer downstream workflows." `source_labels` especially — preserves provenance for whoever consumes the CSV. `wikidata_qid` unlocks cross-wiki joins downstream without re-resolving.

**Shape.** Trivial column additions. `wikidata_qid` depends on 5.6 (QID on working list) being populated; until then the column stays empty or gets resolved at export time.

**Open questions.**
- CSV column order + compatibility. Impact Visualizer's import path: does it tolerate extra columns or does it need exactly `title, description`? Check IV's `docs/impact-visualizer-handoff.md` before shipping. If IV breaks, make enrichment opt-in via an `export_csv(enriched=True)` flag.
- `source_labels` is a list — comma-separate within the field? Pipe-separate? JSON-encode? Use a delimiter that won't collide with typical label contents (no colons, no commas — pipe is safest).

---

### 1.17 ☑ Non-English description fallback via REST page summary `[NEW — promoted from deferred]`

**Shipped 2026-04-22.** New `fetch_descriptions_with_fallback(titles, wiki)` in `wikipedia_api.py`: first pass Wikidata short-desc (unchanged), then on non-en wikis retries empty titles via `/api/rest_v1/page/summary/{title}` and stores the extract's first sentence. Applied to `fetch_descriptions`, `preview_search`, `preview_harvest_list_page`, `preview_category_pull`, and `export_csv`. Skipped on enwiki (Wikidata coverage there is comprehensive; no need to double API cost). First-sentence extraction uses a 30-char abbreviation guard + 200-char cap.


**What.** When Wikidata short-desc is empty on a non-en wiki, fall back to the first-sentence of the article intro via the MediaWiki REST page-summary endpoint.

**Why.** Second feedback: "`fetch_descriptions` returned all-empty on zhwiki (0 non-empty out of 1,773)." Wikidata short-descs are predominantly English-only. Without a description, the AI can't judge relevance on non-en wiki builds, which cripples the cross-wiki strategy — it has to run titles-only.

**Shape.** Extend `fetch_descriptions`:
1. First pass: Wikidata short-desc (current behavior).
2. If empty AND topic wiki is non-en: second pass via REST `/page/summary/{title}` endpoint; store the `extract` field's first sentence.
3. Mark source of the description (`wikidata` vs `rest_intro`) in an internal field — useful for later quality analysis.

**Open questions.**
- REST endpoint rate limits vs Wikidata query limits — different envelopes, probably fine, but verify.
- First-sentence extraction: naive split on `. ` works 95% of the time but trips on abbreviations. Use a light heuristic; acceptable.

---

### 1.18 ☑ Auto-nudge on `resume_topic` after a feedback-less session `[NEW]`

**Shipped 2026-04-22.** `_feedback_nudge_for_resume(topic_name)` scans usage.jsonl for tool calls on this topic. Fires when: (a) the most recent non-resume/non-start/non-feedback call is >24h ago, AND (b) no submit_feedback has been logged after that call, AND (c) the topic has ≥5 prior anchor calls (skip new / shallow builds — no point nudging someone who only did 2 calls yesterday). `resume_topic` returns a JSON envelope with `resumed` + `feedback_nudge` when the nudge fires; otherwise returns the plain start_topic string unchanged. Natural once-per-gap behavior falls out of the "last anchor ts" check — if the user resumes and does work, the anchor advances past 24h from the next resume.


**What.** When `resume_topic` is called, check whether the previous session on this topic ended without a `submit_feedback` call. If so, and if the gap since last activity is more than ~24 hours, include a gentle prompt in the response.

**Why.** Most topics never get feedback (4 submissions across 17 topics). Abandonment typically happens *after* something frustrated the user, not during — so a hard gate mid-session doesn't catch it. Resumption after a gap is the moment where the user (and the AI) have perspective on what last session felt like. Lowest-friction place to ask.

**Shape.** On resume, look at the usage log for this topic:
- Find the most recent tool call.
- If > 24h ago AND no `submit_feedback` between it and the resume → surface a prompt.
- Prompt wording (in the response body): `"Note: your last session on this topic ended N hours ago without feedback. If there were frictions worth capturing from that session (tools that misbehaved, patterns that surprised you, strategies that worked well), this is a good moment to call submit_feedback before continuing."`

Pairs with 2.6 (instructions-side guidance on *when* to call submit_feedback, covering the moments mid-session as well as on resume).

**Open questions.**
- Should this fire on every resume after a gap, or only the first? Probably only once per gap — if the AI sees it and declines, don't re-nag on the next resume within the same working session.
- What's "too short a session to deserve a nudge"? < 5 tool calls probably doesn't — the nudge would feel silly.

---

### 1.19 ☑ Nudge on repeated bare `manual` source labels `[NEW]`

**Shipped 2026-04-22 (grouped with 2.1).** Per-session counter `_session_bare_manual_counts` ticks up on every `add_articles(source="manual", ...)`. On the second such call, the response gains a `label_hint` field with concrete examples (`manual:veitch-cluster`, `manual:cross-wiki-reconciliation-nl`, `manual:spot-check`). Labeled calls (`source="manual:foo"`) don't tick the counter. Also: `add_articles` now returns structured JSON (was plain text) so the hint has somewhere to live without changing the prose return.


**What.** When `add_articles(source="manual", ...)` is called for the second time in a session, return a soft warning in the response recommending a specific `manual:<context>` label.

**Why.** Q3 answer in the Q&A round: "The tool could even nudge this — on the second `add_articles(source='manual', ...)` call in a session, warn 'you're reusing the generic manual label; consider a specific one for better audit-ability.'" Pairs with the 2.1 instruction convention and the docstring update — instruction + in-band prompt + docstring together make the pattern hard to miss.

**Shape.** Server-side check: if the topic already has articles labeled bare `manual` from this session, include a `label_hint: "consider 'manual:<context>' for better audit trail — see list_sources for existing labels"` in the response. Don't block the call; just hint.

**Open questions.** Session scoping — trigger on repeat within session, or repeat within topic lifetime? Probably within session; cross-session triggers would nag too much. Session-boundedness depends on `id(ctx.session)` which we already track.

---

### 1.20 ☑ Source-intersection query on `get_articles` `[NEW]`

**Shipped 2026-04-22 (grouped with 1.5).** `sources_all: list[str] | None` param added. Uses AND semantics; composes with the existing `source` OR filter. Example: `sources_all=["category:Orchidaceae", "wikiproject:Orchids"]` returns the high-confidence core hit by both a category crawl and a WikiProject pull.


**What.** New optional param `sources_all=[...]` on `get_articles`: return only articles that appear under *all* named sources (intersection, not union).

**Why.** Q5 answer: "**Source-intersection query** — 'articles appearing in BOTH category:X AND list_page:Y' = the core-confidence set." This is the AI's ask for a "high-confidence subset" diagnostic. Two sources converging on an article is strong evidence it's on-topic; finding the intersection by eye across paginated results is awkward.

**Shape.** The existing `source` param filters to articles with *any* of the named sources (union / OR). Add `sources_all=[...]` for *all* (intersection / AND). SQL side: check the JSON sources column contains every named label. Keep both params; they compose (`source=[A, B], sources_all=[C, D]` → in A or B, AND in C and D).

**Open questions.** API shape — is `sources_all` the clearest name? Could be `source_intersection` or `require_all_sources`. Pick one, document both in the docstring as aliases if needed.

---

### 1.21 ☑ `describe_topic` diagnostic `[NEW — medium]`

**Shipped 2026-04-22.** In-process aggregation over the working list (no Wikipedia API calls). Returns: `title_length_distribution` (1-word, 2-words, …), `top_first_words` (default top 20 — spots dominant genera in taxonomy topics), `articles_without_description`, `suspicious_patterns` (year-or-date, all-caps, one-word, very-short), and `source_shape` (distinct sources, single-vs-multi-source articles). Skipped the `include_clusters=True` Levenshtein path for now (stdlib has no Levenshtein; would need a small dep or hand-rolled implementation). If that use case shows up, add as follow-up.


**What.** New tool that returns a shape-of-corpus overview of a topic. Summary statistics across titles, descriptions, and sources.

**Why.** Q5 answer: "**A `describe_topic` diagnostic.** Like `DataFrame.describe()` for a topic: word-count histogram of titles, top first-words, articles lacking descriptions, titles-that-look-like-dates/numbers, near-duplicate clusters via Levenshtein. A one-call shape-of-the-corpus overview." The AI kept writing local scripts for this during the orchids build (detecting template contamination, counting unique genera in a source, finding single-word noise titles).

**Shape.** `describe_topic(topic=None, include_clusters=False)` returns:
```json
{
  "total_articles": 18122,
  "title_length_distribution": {"1_word": 127, "2_words": 14231, "3_words": 2934, ...},
  "top_first_words": [{"word": "Bulbophyllum", "count": 2036}, ...],
  "articles_without_description": 10628,
  "suspicious_patterns": {
    "year_or_date_titles": 47,
    "all_caps_titles": 3,
    "one_word_generic_titles": 112
  },
  "source_shape": {
    "total_sources": 32,
    "articles_with_single_source": 10234,
    "articles_with_multiple_sources": 7889
  }
}
```
With `include_clusters=True`, compute near-duplicate clusters via Levenshtein (more expensive — opt-in).

**Open questions.**
- Compute complexity on 18K articles — title stats are cheap, Levenshtein clustering is not. Levenshtein is the opt-in flag; all other stats should be sub-second.
- What's the right set of "suspicious patterns"? Start small (year titles, single-word, all-caps) and expand based on what turns up useful.
- Does this conflict with 1.12 (per-topic cost surface in `get_status`)? Complementary — `get_status` answers "what did I do to Wikimedia?"; `describe_topic` answers "what's the shape of my corpus?"

---

### 1.22 ☑ Sticky rejection list `[NEW — medium]`

**Shipped 2026-04-22.** DB: new `rejections(topic_id, title, reason, rejected_at)` table, topic-scoped, ON DELETE CASCADE. Three new tools: `reject_articles(titles, reason, also_remove=True)`, `list_rejections()`, `unreject_articles(titles)`. Gather integration: `get_category_articles`, `harvest_list_page`, `search_articles`, `get_wikiproject_articles`, and `add_articles` all consult `db.get_rejected_titles(topic_id)` before adding and return `rejected_skipped: N` in the response. `also_remove=True` default on `reject_articles` (matches plan's open-question recommendation). No `filter_articles` integration yet — kept minimal; revisit if it comes up.


**What.** `reject_articles(titles: list, reason: str = "")` that persists rejected titles separately from the working list. Repeat-gather tools (`get_category_articles`, `harvest_list_page`, `search_articles`, `search_similar`) auto-skip rejected titles on future calls.

**Why.** Q5 answer: "**Sticky rejection list.** When I removed 'Oakes Ames' (the politician), nothing stops a future `search_articles` from re-adding him. I'd want `reject_articles(titles)` that persists so repeat-gather tools skip rejected titles." Currently, `remove_articles` only drops from the working list — a subsequent gather can re-introduce the same noise. The AI has to remember what it previously rejected, across sessions.

Flagged in round 1 feedback as "a way to attach a 'rejection note' to removed titles"; Q&A round crystallized it.

**Shape.**
- New DB table: `rejections(topic_id, title, reason, rejected_at)`.
- New tools: `reject_articles(titles, reason)`, `list_rejections(topic)`, `unreject_articles(titles)`.
- Gatherer integration: each gather tool consults `rejections` for the topic and filters out rejected titles from its results before adding. Returns `rejected_skipped: N` in the response so the AI knows.

**Open questions.**
- Topic-scoped or cross-topic? Probably topic-scoped — rejections in "orchids" shouldn't affect "climate change." Cross-topic sharing could be a future option via a separate mechanism.
- When rejecting, also `remove_articles`? Probably yes as a default — the AI almost always wants both. Make it one tool call: `reject_articles(titles, reason, also_remove=True)` with `True` default.
- Interaction with `filter_articles`: should rejections show up in its output? Yes — as a separate "skipped due to prior rejection" count.

---

## Stage 2 — Instruction updates

No code. Edit `server_instructions.md` + redeploy. Low risk, fast feedback.

### 2.1 ☑ Document the `manual:<label>` convention `[NEW]`

**Shipped 2026-04-22 (grouped with 1.19).** server_instructions.md gained a dedicated `manual:<label> CONVENTION` bullet right after the source-label one. Covers the motivation (label documents *reason or method*, not just "by hand"), four concrete examples, and the signal about the in-band hint. add_articles docstring got the recommendation in commit [plan 1.1]. All three reinforcement points now in place.


AI organically invented `manual:culture`, `manual:veitch-cluster`, `manual:biographies`, `manual:national-flowers`, `manual:thief-cluster` in the first batch of sessions, and later invented `manual:cross-wiki-reconciliation` when walking non-en topic additions back to enwiki. That last one is a particularly strong exemplar — the label documents not just "I added these by hand" but the specific methodology that surfaced them, making the audit trail self-describing.

Name the pattern in three places so the next AI does it deliberately:
1. **Server instructions** — "use `manual:<descriptive-label>` to keep audit trail clean when adding small curated sets; never use just `manual` unlabeled. Label should describe the *reason or method*, not just the content — e.g. `manual:cross-wiki-reconciliation` is better than `manual:chinese-additions` because it encodes how they were found."
2. **`add_articles` docstring** — explicit recommendation. Current docstring says `source: Source label (e.g., "manual", "edge_browse", "search")`; updated version should say `source: Source label. For hand-curated additions prefer 'manual:<context>' over bare 'manual' — e.g. 'manual:veitch-cluster', 'manual:cross-wiki-reconciliation-nl'. The <context> makes the audit trail self-describing and enables selective undo via remove_by_source.`
3. **In-band nudge** — when the AI calls `add_articles(source="manual", ...)` repeatedly, the server responds with a hint recommending a specific label (see 1.19).

Three reinforcement points (instruction + docstring + in-band hint) because the first Q&A round showed the AI itself recommended exactly this: "I'd suggest for the docstring of `add_articles`: explicitly recommend the `manual:<context>` convention. The tool could even nudge this — on the second `add_articles(source='manual', ...)` call in a session, warn..."

### 2.2 ☑ Noise taxonomy into instructions `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** Added `NOISE TAXONOMY` bullet covering category crawls / genus-species lists / geographic lists / biography lists / `search_similar` as seed-topology-function / `browse_edges`. All five patterns documented with concrete numbers and exemplars from the orchids session.


Port the playbook's hard-won pattern recognition into server_instructions.md:
- Category crawls: usually clean (editor discipline is decent)
- Genus-species lists: very clean (<1% noise, structural tables)
- Geographic lists: highly variable — navbox-heavy pages 60–70% noise, plain tables near-zero
- Biography lists (e.g. "List of orchidologists"): ~30% noise from reference links
- `search_similar`: noise is a **function of seed topology**, not inherent to the tool:
  - **Pure topic node** (event, concept, specific work): near-zero noise. Example: `morelike:兰亭集会` → 20/20 on-topic.
  - **Biographical hub node** (person with many non-topic edges): ~50% noise. Example: `morelike:牧野富太郎` → Linnaeus, Siebold, Zelkova trees, date articles — pulled by Makino's broad biographical edges, not his orchid-taxonomy specialty.
  - Rule for the AI: pick seeds *about* the topic (events, concepts, works) rather than *people associated with* the topic. Avoid polymath or politically-prominent figures. Test on limit=10–15 first, inspect, commit or revert.
- `browse_edges`: typically clean but thin, low yield if category coverage is dense

Orchids session proved all of these the hard way. Next AI shouldn't have to.

### 2.3 ☑ Cross-wiki guidance `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** `CROSS-WIKI WORKFLOW` section added after `WIKI SELECTION`. Covers the "completeness-check" framing (21 missed enwiki articles only reachable via non-en walk-back), the six-step workflow pattern, the ~1–2h-per-wiki budget, and the four per-wiki structural fingerprints verbatim (zh/ja/pt/nl). Explicit note that reconciliation is manual until `cross_wiki_diff` (5.2) ships.


The second orchids session demonstrated that cross-wiki work isn't just duplication prevention — it's a **completeness-check mechanism for the primary wiki**. Eight sessions of English-language discovery still missed 21 enwiki articles (including João Barbosa Rodrigues, father of Brazilian orchidology, and Qu Yuan, whose Li Sao established orchid symbolism in the Chinese canon). They're only reachable by following culturally-native chains of association from the orchid concept in that language.

Bake this framing and the concrete workflow into instructions:

**When to spin up parallel topics.** Any topic where cultural / biographical / regional context matters (not pure taxonomy). The AI's finding: "If I were starting over I'd do a small zhwiki/jawiki probe before finishing the enwiki build, then feed cross-wiki finds back as enwiki search seeds."

**The workflow pattern.**
1. Build the primary-wiki topic through category crawls, lists, searches.
2. Spin up small parallel topics on culturally-relevant wikis (zh/ja for East-Asian angles, pt/es for Neotropical, de/nl for colonial-era European).
3. Category-crawl each non-en wiki, then `preview_search` for native-language cultural clusters.
4. For each cultural cluster on the non-en wiki, walk to the primary wiki: does this article exist? Is it in my topic?
5. Add genuine gaps under `manual:cross-wiki-reconciliation`.
6. Reverse check: which non-en items have *no* primary-wiki article at all? Those are the genuinely novel content that only exists in that wiki — worth cataloging separately.

**What to look for on each wiki.** The zh Orchid Pavilion Gathering cluster (10+ interconnected articles around 兰亭) is the exemplar: a foundational cultural event whose Wikipedia coverage scales with cultural ownership. Equivalent patterns on ja (Edo-period 古典園芸), pt (Brazilian orchid hunters, Atlantic Forest institutions), nl (Dutch colonial orchid hunters in the East Indies — Rumphius).

**Budget.** ~1–2 hours per parallel wiki. Much cheaper than the primary build because the corpus is smaller and you're curating to surface cultural seeds, not to enumerate.

**Per-wiki structural fingerprints** (so the AI doesn't have to re-discover these):
- **zhwiki**: typical hierarchical by subfamily; depth 4 works; ~2K orchid articles.
- **jawiki**: small but well-curated (~350). Focus on native-cultivar traditions (富貴蘭 / 春蘭 / 寒蘭) and Edo-period 古典園芸.
- **ptwiki**: **flat** category structure — 313 genus categories are direct children of Orchidaceae, no subfamily nesting. Root crawl times out on breadth alone at depth=2. **Pull per-genus, not root.**
- **nlwiki**: small (~100) but yields unique colonial-Indonesia content impossible to find via English search.

**Current limitation.** Reconciliation is manual today — per-article preview_search against the primary wiki. Collapses to one call once `cross_wiki_diff` (5.2) ships.

### 2.4 ☑ Pipeline order from playbook `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** Replaced the terse 6-step list at the top of instructions with a 14-step opinionated pipeline. Strengthened the WikiProject step explicitly: added a standalone paragraph after the pipeline telling the AI NOT to skip on a first-probe negative, and calling out `find_wikiprojects` as the discovery primitive.


The playbook's "recommended pipeline order" (survey → wikiproject → category → filter → fetch_descriptions → list-pages → targeted search → morelike → browse_edges → cleanup → score → export) is solid. Migrate to instructions. Current workflow doc is looser.

**Strengthen the WikiProject step specifically.** The Q2 Q&A answer confirmed the AI itself skipped `check_wikiproject` on the orchids main build "based on an unverified assumption that category+list-page coverage would subsume it" — violating its own playbook. The instruction needs to push harder:

> *"Always probe `check_wikiproject(<topic_name>)` explicitly as step 2, even if you believe category coverage will subsume it. Don't skip based on the assumption that a first-probe negative ('WikiProject Plants is too broad') means WikiProject is unhelpful — try the specific topic WikiProject (e.g., 'WikiProject Orchids') before concluding. WikiProject-tagged articles often include biographies and cultural content that category trees miss."*

Then decide based on actual yield, not assumption.

### 2.5 ☑ Cost-awareness guidance `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** `COST AWARENESS` bullet added, anchored on 1.11's `cost_warning` field and 1.12's per-topic cost summary. All five plan bullets ported; last one "good citizen of Wikimedia infrastructure" stays verbatim.


Once 1.11 surfaces cost estimates to the AI, instructions should teach the AI to reason about them rather than ignore the warnings.

Specific bullets to add:
- Before a category crawl on an unknown tree, `survey_categories(count_articles=True)` first. Over ~5K articles at depth=5 is a timeout risk.
- Prefer narrower scope and iterate — partial results lose information about *what's missing*.
- If a tool returns `timed_out: true` or a `cost_warning`, don't retry naively. Narrow scope first, or accept partial and document the gap.
- Batch where possible: `fetch_descriptions` auto-loops; heavy removes should be chunked; big list-page harvests should be previewed.
- We are a good citizen of Wikimedia infrastructure. Heavy queries cost real money and rate-limit budget for all users.

This used to be tribal knowledge the AI re-derived every build. With 1.1 + 1.11 + 1.12 in place, the AI has real numbers to reason from.

### 2.6 ☑ Event-triggered reflection guidance `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** `REFLECTION` bullet added with two subsections: "Drop a `note=` when" (4 triggers including timed_out, morelike-gone-sideways, unexpected noise, docstring gap) and "Call submit_feedback when" (4 triggers including first export_csv, major cleanup, resume nudge, wrap-up). Explicit framing: reserve notes for genuine surprise, not routine narration. Pairs with 1.1C (`note=`) and 1.18 (resume nudge).


Pure instructions update. Nominates specific moments when the AI should capture an observation — either via the lightweight `note=` parameter on a tool call (1.1 part C) or via a proper `submit_feedback` call.

**Context.** We have 4 feedback submissions across 17 topics. Most sessions end without reflection captured, and the feedback we do get skews to wrap-up summaries — missing the mid-session "huh, that's surprising" moments that are often the richest tool-design signal.

**The approach.** Not a hard gate (every-N-calls forcing would just produce shallow filler). Instead, instructions name specific *objective* moments where reflection is high-yield and cheap:

**Drop a `note=` inline when:**
- A tool returns `timed_out: true` or a `cost_warning` — capture what you tried and why it surprised you.
- A `search_similar` / morelike pull goes sideways and you revert it — capture the seed's failure mode (the Orchid Thief → Streep filmography pattern is the exemplar).
- A harvest or search produced unexpected noise (template contamination, cross-referenced junk) — capture the pattern.
- A tool's behavior doesn't match what you expected from its docstring — capture the gap.

**Call `submit_feedback` when:**
- After the first successful `export_csv` in a session — you have a natural retrospective moment.
- After a major cleanup pass (e.g., `remove_by_source` clearing ≥500 articles) — you've just closed a loop.
- On `resume_topic` after a long gap without prior feedback (see 1.18).
- When the user signals wrap-up or topic change.

**Framing for the AI.** Not every tool call deserves a note — reserve them for genuine surprise or friction. The goal is a `usage.jsonl` that's readable as "here's what the AI noticed," not narration of what the AI did.

Pairs with 1.1 part C (the `note=` field itself) and 1.18 (resume-time nudge).

### 2.7 ☑ "Common task → tool" mapping in instructions `[NEW]`

**Shipped 2026-04-22 (Stage 2 bundle).** `COMMON TASK → TOOL` table added near the top (right after PIPELINE). 12 rows — covers the shipped tools plus three placeholders for Stage 5's `petscan_*`, `cross_wiki_diff`, `completeness_check` with italic "not yet built" markers and the closest-current-primitive for each. Explicit header note tells the AI to surface the not-yet-built state rather than fake the functionality.


A short lookup table of user-verbalized intents to the right tool. Instructions-only.

**Why.** Two observed failures where the AI didn't reach for the correct tool despite it existing:
1. Orchids main build — AI skipped `check_wikiproject` after one discouraging probe.
2. Kochutensilien (dewiki) — user complained in feedback about "no direct tool support for extracting link targets from a Wikipedia list page," which is literally what `harvest_list_page` does. Either they didn't find it or didn't think of it.

**Shape.** A short section in server instructions, keyed on what the user says they want:

| User says... | Reach for |
|---|---|
| "all articles in a category" | `get_category_articles` (preview first with `survey_categories(count_articles=True)`) |
| "extract links from this list page" / "harvest this list" | `harvest_list_page` (preview via 1.4 when it ships) |
| "find articles like this one" / "more similar" | `preview_similar` (1.3), then `search_similar` if preview is clean |
| "search for articles matching [keywords]" | `preview_search` (commit via `add_articles`, not `search_articles`) |
| "compound category query" / "intersection of two categories" | `petscan_*` (5.4) when shipped |
| "cross-wiki comparison" / "what's on zhwiki but not enwiki" | `cross_wiki_diff` (5.2) when shipped |
| "is this topic complete?" | `completeness_check` (5.3) when shipped; also `browse_edges`, spot-check |
| "shape of my corpus" / "suspicious titles" | `describe_topic` (1.21) when shipped |
| "remove noise from this source" | `list_sources` → `remove_by_source(dry_run=True)` → `remove_by_source` |
| "topic build is saved? can I come back?" | `resume_topic(name)` |

**Open questions.** Keep the table tight — 10 rows max. Longer = noise. Revisit quarterly as new tools ship.

---

## Stage 3 — Medium project: cooperative time budget + resumable long ops

`get_category_articles(depth=5)`, `filter_articles` (at 18K articles), and `get_category_articles` on pt-wiki all timed out at 300s on orchids, leaving the AI guessing what was done. Partial progress is persisted but not resumable. Stage 1.11 warns before the timeout; Stage 3 makes the timeout recoverable.

**Shared abstraction.** One continuation-token pattern, applied across four tools:
- Each heavy loop respects a cooperative time budget (default ~240s, leaving margin under the 300s hard cap).
- When the budget is exhausted, return partial result + opaque continuation token + `timed_out: true`.
- AI calls the same tool again with the token to resume from where the previous call stopped.
- Token format: opaque string (base64 JSON internally), scoped to the tool + topic. Not persisted — if the AI doesn't resume within the session, the state is lost (acceptable).

**Diagnostic quality requirement.** Partial-return messages must describe *what was covered*, not just "timed out." Second feedback called this out: on ptwiki, `get_category_articles` timed out on the root (313 direct subcategories) with no hint — AI couldn't tell whether to lower depth, narrow subtree, or retry. Each tool's partial-return schema should include counts like `subcategories_visited: 87, subcategories_pending: 226, articles_added_this_call: 1218`. The continuation token carries the state; the response carries human- and AI-readable progress.

### 3.1 ☐ Chunked/resumable `get_category_articles` `[NEW]`

Continuation state: set of visited categories + queue of pending categories. Token encodes both. Partial-return surfaces: direct subcategories fully crawled vs. pending vs. untouched (for the breadth-overrun case ptwiki exposed). Also include the list of fully-covered branch names so the AI can decide to retry specific branches independently.

**Explicit `exclude=` resume idiom** (Q7 answer confirms this shape): in addition to opaque continuation tokens, the partial-return should include a list of fully-covered subcategories. The AI can then call `get_category_articles(category=<root>, exclude=[A, B, C, D])` to retry the uncovered branches. Simple, transparent, AI-legible — the AI's own wish: *"Crawled subcategories A, B, C fully; D partially (47/150); E, F, G not yet touched. Then I could retry with exclude=[A, B, C, D] to resume."*

### 3.2 ☐ Chunked/resumable `filter_articles` `[NEW]`

Continuation state: "already processed up to offset N." Simpler — linear scan.

### 3.3 ☐ Cooperative time budget on `harvest_list_page` `[NEW]`

Rare but possible on very large list pages. Same pattern — return partial + token.

### 3.4 ☐ Cooperative time budget on `fetch_descriptions` auto-loop `[NEW]`

Already multi-call internally after 1.6. Add budget + partial-return discipline so it plays nice with other work in the same session. Continuation in this case is trivially "call again" — the tool already knows what's undescribed.

**Sequencing note.** Build the shared abstraction first, then apply. Don't reinvent four times.

---

## Stage 4 — Design decision: scoring at scale `[backlog:design Q #7 — RESOLVED by Q&A round 3]`

**Decision: option (a) — drop scoring from the default workflow, keep as opt-in quality cut, fix documentation gap.**

The AI's Q1 answer resolved this directly:

> "I treated scoring as a mechanical requirement for export rather than a meaningful relevance gradient. My cleanup pattern was binary — if something was noise I removed it via `remove_articles`; if it survived audits it was on-topic enough... For a single-reviewer taxonomy build with clear boundaries and no signal about downstream weighting semantics, scoring was overhead and I routed around it."

The AI also named the cases where 1–10 *would* earn its keep: contested-boundary topics, multi-reviewer workflows, core/extended distinctions on broadly-construed topics, and **downstream consumers that weight by score** — but only if the docs communicate the semantics. Key quote: *"If the tool docs said 'Impact Visualizer surfaces score-9+ articles first' or similar, I'd have been more deliberate."*

**What this implies for the build:**

### 4.1 ☐ `export_csv` works without scoring by default

Drop the implicit requirement that `score_all_unscored` run before export. CSV exports whatever's in the topic; score column populates where scored, blank otherwise.

### 4.2 ☐ Instructions guide on when scoring is valuable

Add a short rubric to `server_instructions.md`:
- **Skip scoring** for: taxonomy topics with clear membership rules, species-dominated corpora, single-reviewer builds where the decision is binary in-or-out.
- **Use scoring** for: biography-heavy topics with judgment calls, broadly-construed topics where you want core/extended distinction, any topic destined for a downstream consumer that weights by score.
- **If using scoring,** consider a simple rubric: 9–10 canonical / core, 6–8 expanded / cultural-tangent, 3–5 speculative or borderline. Don't bother with fine gradients between 7 and 8 — they're indistinguishable downstream.

### 4.3 ☐ Document downstream scoring semantics

Impact Visualizer handoff doc (`docs/impact-visualizer-handoff.md`) is the place to spell out how IV actually uses the score column — or that it doesn't. Once that's clear, the score field's meaning follows.

**What this does NOT change.** Existing scoring tools stay — `score_by_extract`, `auto_score_by_title` (after 1.13 fix), `auto_score_by_description`, `set_scores`, `score_all_unscored`. They're still useful for the cases above. What changes is that the AI is no longer pushed toward them as a wrap-up formality.

---

## Stage 5 — Big build: Wikidata layer

Consolidates backlog items #3 (Wikidata/SPARQL), #4 (PetScan), plus two new orchids-driven items. One substrate, four user-facing tools.

### 5.1 ☐ `wikidata_query` / `wikidata_entities_by_property` `[backlog:#3]`

**What.** SPARQL query tool + higher-level helper.

**Why.** Feedback's #1 missing capability. Enables:
- "All articles whose Wikidata item has `parent taxon: Orchidaceae`" — canonical ground truth for species articles
- "People whose `field of work` includes orchidology" — biographies not in any category tree
- "zhwiki articles with no enwiki sitelink in this class" — cross-wiki gap-finding

**Shape.** Thin wrapper around `query.wikidata.org/sparql`. The helper `wikidata_entities_by_property(property, value, wiki="en")` builds the common case; `wikidata_query(sparql)` for full power.

**Open questions.**
- Does AI draft SPARQL directly, or do we expose higher-level primitives only? SPARQL is expressive but easy to get wrong. Start with helpers; add raw SPARQL if needed.
- Rate limits on query.wikidata.org are real. Budget + caching.

### 5.2 ☐ `cross_wiki_diff(topic_a, topic_b)` `[NEW]`

**What.** Take two topics on different wikis, return articles in A that have a sitelink to wiki B but aren't in topic B ("potential gap-fills"), and separately articles in A with no sitelink to B at all ("genuinely unique-to-A content"). Both directions useful.

**Why.** Direct evidence from the second orchids session: the AI walked the zh/ja/pt cultural clusters back to enwiki manually and **recovered 21 enwiki articles that 8 sessions of English-language discovery had missed** — including João Barbosa Rodrigues (father of Brazilian orchidology!) and Qu Yuan (whose Li Sao established orchid symbolism in the Chinese canon). The reverse walk found 14 zhwiki-only items, 3–4 jawiki-only, and 5 ptwiki-only items with no enwiki equivalent at all — distinct cultural content preserved only in that language's Wikipedia.

Without this tool, the methodology works but is tedious — N preview_search calls per non-en topic. With it, the whole reconciliation collapses to one call per direction.

**Shape.** For each article in topic A:
- Look up Wikidata QID (cheap once 5.6 ships — otherwise resolve via pageprops).
- Check sitelink to wiki B.
- Classify into three partitions:
  - **`gap_fills`** — article has a B-wiki sitelink AND that B-title is *not* in topic B. Most valuable output: real articles on B that are missing from the user's B-topic. Candidates to add.
  - **`unique_to_a`** — article has no sitelink to B at all. No corresponding article exists on B. These are the culturally-unique-to-A items — great for cataloging what only lives in that wiki.
  - **`translation_candidates`** — articles that have no B sitelink AND whose title/description suggest they'd be valuable on B (e.g. species articles present on A with no B equivalent). Downstream handoff for a translation project. Not add candidates for B-topic (they don't exist yet on B), but worth surfacing as a distinct list.

The AI's Q4 walkthrough made this partitioning explicit: "partition by title pattern heuristically (cheap): species (~60% of results) → translation candidates; cultural concepts (~25%) and biographies (~15%) → gap-fill candidates after a preview_search confirms relevance."

**Open questions.**
- Standalone via MediaWiki langlinks API vs. waiting for SPARQL (5.1). Langlinks is simpler and orchids needs it now; SPARQL version can come later. Ship standalone first.
- Separating `gap_fills` from `translation_candidates` needs a heuristic for "would this be valuable translated?" Probably: title looks like a species / formal name / institution → translation candidate if no B sitelink. Needs tuning with real data.
- How does the AI know which direction to run first? Instruction guidance: "if your primary wiki is en and you have non-en parallel topics, run `cross_wiki_diff(non_en, en)` to find gap-fills to add to your en topic; run the reverse to catalog unique content."
- Output size on big topics: 18K-article en topic diffed against 2K zh topic is 2K checks — manageable. En → pt with a full 18K sweep is bigger. Consider pagination / limit param.

### 5.3 ☐ `completeness_check(topic)` `[NEW]`

**What.** Compare a topic's contents against a Wikidata ground-truth count for its canonical class.

**Why.** Turns "is my list complete?" from vibe-check into an answerable question. Feedback: "Wikidata says ~28K orchid species exist; your topic has 13K species; here are the top 100 species by sitelink count that you're missing."

**Shape.** Needs a "canonical class" per topic — either explicitly configured by the AI (`completeness_check(topic, wikidata_class="Q25308")` for Orchidaceae) or inferred from topic sources.

**Open questions.** How does the tool know what "class" the topic is? Inference from dominant categories? Explicit AI-provided? Probably explicit, documented in instructions.

### 5.4 ☐ PetScan-style intersection `[backlog:#4]`

**What.** Compound category queries. "Articles in Category:Orchidaceae genera AND Category:Plants described in 1834."

**Shape.** Could wrap the existing `petscan.wmcloud.org` HTTP API, or build natively using `categorymembers` API with intersection logic.

**Sequencing note.** Arguably subsumed by SPARQL in 5.1 (Wikidata supports category intersection queries). Decide after 5.1 scope is set — if SPARQL covers it, drop this; if not, keep.

### 5.5 ☐ `resolve_category(wikidata_qid)` — per-wiki category-name helper `[NEW]`

**What.** Given a Wikidata QID (e.g. `Q25308` for Orchidaceae), return the category name on each wiki. Also per-wiki sitelink to the canonical article.

**Why.** Second feedback and updated playbook both spell out what this replaces. For Orchidaceae alone, the AI had to independently discover:
- `Category:Orchidaceae` on en, pt, es
- `Category:Orchideen` on de
- `Category:Orchideeënfamilie` on nl (plain "Orchidaceae" returned empty)
- `Category:ラン科` on ja
- `Category:兰科` on zh

Six wikis, six different names, one QID underneath. Each wrong guess costs a round-trip. The playbook's explicit note: "No shortcut without Wikidata." With this helper, cross-wiki category-level work collapses from N guess-retries to one call.

**Shape.** Wikidata sitelinks API. `resolve_category(qid, wikis=["en","zh","ja","pt","de"])` returns `{"en": "Category:Orchids", "zh": "Category:兰科", ...}`. Category namespace is per-wiki (`Category:` on en, `Kategorie:` on de, etc.) — tool handles translation.

**Open questions.**
- What about articles, not just categories? Same shape: `resolve_article(qid, wikis=[...])`. Low cost to support both. Might be a single tool `resolve_wikidata_item(qid, as_type="category"|"article", wikis=[...])`.
  - Evidence this matters: the second orchids session found that Guido Pabst and Hoehne (both major Brazilian orchidologists) returned zero via direct title search on ptwiki, likely because they're titled differently under Portuguese conventions. `resolve_article(qid)` would find them by QID regardless of title convention — unblocks cross-wiki bio discovery in general.
- Dependency: needs Wikidata API access (same infra as 5.1). Ship under the Wikidata layer.

### 5.6 ☐ Per-article Wikidata QID on the working list `[NEW — data-model change]`

**What.** Every article in a topic's working list gains a `wikidata_qid` field, resolved at add-time.

**Why.** Second feedback: "Right now the working list is just titles. If each article stored its QID (resolved on add), I could: dedupe across sources cleanly; cross-reference to other wikis without a separate topic build; slice by Wikidata properties."

**Shape.**
- DB schema: add `wikidata_qid TEXT` column to `articles` table. Migration is a nullable add; existing rows stay NULL and resolve lazily.
- Resolution: when `add_articles` runs, call `action=query&prop=pageprops&ppprop=wikibase_item` on the title list (batched, 50/call). Populate `wikidata_qid` where present.
- Lazy backfill: a `resolve_qids(topic)` tool that processes NULL-QID rows in batches. Run once per topic after this ships.

**Why it's infrastructure.** Many downstream tools get simpler once QIDs are on the working list:
- `cross_wiki_diff` (5.2): compare by QID, not title — handles title-variant cases automatically.
- `completeness_check` (5.3): join topic to Wikidata class members by QID.
- Export CSV enrichment (1.16): QID column ships for free.
- Dedup across sources: title variants that point to the same QID are obviously the same entity.

**Open questions.**
- Cost: 50 titles per `pageprops` call. On 18K orchids, that's 360 calls. Not trivial but one-time. Respect Stage 1 cost budgets.
- Not all articles have QIDs (brand-new pages, redirects, disambiguation pages). NULL is fine; downstream tools tolerate it.
- Sequencing: ship before 5.2 and 5.3 — those become much simpler with QIDs available.

---

## Stage 6 — Speculative / later tier

Items worth keeping on the roadmap but not committing to pre-build. Revisit after Stages 1–5 ship.

### 6.1 ☐ `get_category_articles_bulk(categories=[...])` batch variant `[NEW]`

**What.** One tool call that pulls multiple categories in sequence, returning merged results.

**Why.** Second feedback: "Would let me pull 20 ptwiki genus categories in one call instead of 20 sequential calls. Most took under 10 seconds, but network overhead adds up." The per-genus fallback (when a root category is too broad to crawl at depth) becomes friction-free.

**Shape.** Internally a loop over existing `get_category_articles`; respects cost budget from Stage 1.11 and the cooperative time budget from Stage 3. Returns per-category sub-results + merged article list.

**Sequencing note.** Easy to add after Stage 3's shared abstraction lands. Could arguably slot into Stage 1 if we decide it's high-leverage; parking in Stage 6 until real demand confirms.

### 6.2 ☐ `suggest_removals(source, max=50)` — LLM-assisted review `[NEW]`

**What.** A tool that uses an LLM on the server side to flag likely-noise articles in a source, surfacing a ranked list for the calling AI to review.

**Why.** Second feedback: "Given the source audit pattern I kept using manually (`get_articles_by_source(exclude_sources=[everything else])` then eyeball), there's probably a tool-level primitive."

**Shape.** Server-side LLM call per batch, with a rubric derived from the topic's scope + existing on-topic sources. Returns `{title, flag_reason, confidence}` list. AI decides what to actually remove.

**Open questions / caution.**
- Costs $. Server-side LLM calls add ongoing operating expense, not just build time. Worth it only if the human-speed review step is the real bottleneck.
- Could also be done client-side: give the AI enough context and it runs its own review via `get_articles_by_source`. May not need a server-side primitive at all.
- Model choice, prompt robustness, rubric construction — real engineering, not trivial.

Leaning: wait to see if Stage 1 regex filters (1.5) + better cost telemetry actually leave this as the cleanup bottleneck. If not, skip.

### 6.3 ☐ Save-query presets / macros `[NEW]`

**What.** Let the AI save a parametrized search as a named macro. E.g. `probe_botanist("Barbosa Rodrigues")` runs the `<name> botanist <domain>` search templates the AI already constructs ad-hoc.

**Why.** Q5 answer: "I ran '<BotanistName> botanist orchid' templates many times across zh/ja/pt/nl probing for biographies. A saved parametrized query would let me `probe_botanist('Barbosa Rodrigues')` as a macro."

**Shape.** Tentative: a registry of named search templates scoped to a topic. `define_search_template(name, query_pattern)` then `run_template(name, args)`. Or simpler: a per-topic "search presets" table stored alongside rejections.

**Sequencing note.** Speculative. Not orchids-urgent. Revisit if we see the AI repeatedly constructing the same search shape across topics.

### 6.4 ☐ Per-session watch / diff `[NEW]`

**What.** "What articles are in `category:Orchids` today that weren't last session?" — a delta operator over a topic's corpus across time.

**Why.** Q5 answer: "Topic maintenance over time." Useful when a topic is meant to be kept current (e.g., an initiative tracking Wikipedia's growing coverage of women in STEM over the course of a year).

**Shape.** Snapshot + diff. `snapshot_topic(topic, name)` captures current state; `diff_snapshots(topic, name_a, name_b)` returns added/removed/changed articles. Could also diff against an implicit "last snapshot."

**Sequencing note.** Speculative. Useful when long-lived topics become a real use case — currently topics are largely one-off builds.

### 6.5 ☐ Graph view of topic via internal links `[NEW]`

**What.** Visualize how articles in a topic are connected via Wikipedia's internal link structure. Expose islands (disconnected subsets = likely orphan additions or noise) and bridges (articles linking many clusters = likely on-topic hubs worth expanding around).

**Why.** Q5 answer: "The deepest one: I wanted a graph view of the topic showing how articles cluster via Wikipedia's internal links. Islands would flag orphan additions, bridges would flag on-topic content that wasn't pulled in. Very far from current tool scope but would be the right debugging primitive for completeness."

**Shape.** Fetch per-article outgoing links, build a subgraph restricted to the topic's article set, compute connected components + centrality. Output as JSON (cluster IDs, bridge candidates) or ultimately a visualization.

**Sequencing note.** Far future. Needs a lot of Wikimedia API traffic (links per article) and a visualization layer. Not orchids-urgent. Park here as a north-star primitive for completeness debugging.

### 6.6 ☐ Empty-topic detection and nudge `[NEW]`

**What.** If a topic is created but has zero articles after N subsequent tool calls (or N minutes), surface a hint on the next tool call: "topic X is still empty — common starting points are `get_category_articles`, `harvest_list_page`, `search_articles`. What are you trying to do?"

**Why.** Kochutensilien dogfood pattern: 4 `start_topic` calls on 2026-04-21, only one reaching 43 articles — the other 3 remained empty. Looks like the user was struggling to find the right starting tool. An empty-topic nudge catches this specific friction.

**Shape.** On each tool call for a topic, check whether the topic is > 5 minutes old AND has zero articles AND had no add-shaped call attempted. If all true, include a suggestion in the response.

**Sequencing note.** Speculative until we see more of this pattern in the wild. Adjacent to 1.18 (resume nudge) but with a different trigger. Skip if 1.18 + 2.7 (common-task-to-tool mapping) resolve the issue.

---

## Smaller items considered and deferred

- **Source-label escaping for labels with colons/quotes.** Partially addressed by 1.14's slugification for `search_articles` labels, but `search:morelike:<seed>` labels with spaces/punctuation may still need attention. Revisit after 1.14 ships.
- **`list_topics` per-user scoping.** Waits on auth. Re-flagged by the second feedback as a privacy concern ("I could see topics belonging to other users — Kochutensilien, Native American scientists, Seattle, educational psychology, upright bass"). `[backlog:#1]`
- **Lower `survey_categories` warning threshold.** Didn't come up in orchids. Keep on backlog.
- **Rate-limit backoff review.** Before shipping 1.1, read `wikipedia_api.py` and confirm that hitting a Wikimedia rate limit triggers actual exponential backoff, not just a counter increment. If the client is already doing the right thing, no work needed. If not, fix before cost-field logging lands — otherwise we'll be counting hits instead of avoiding them. `[NEW — investigate during 1.1]`
- **`harvest_list_page` behavior on dewiki.** Kochutensilien user feedback (2026-04-22) complained "no direct tool support for extracting link targets from a Wikipedia list page" — which is literally `harvest_list_page`'s job. Either (a) they didn't discover the tool (addressed by 2.7 common-task-to-tool mapping), (b) they mean "display text vs. link target" in a way that suggests a dewiki-specific parsing quirk, or (c) the tool silently underperformed on their target page. Once 1.1 logging backfill lands, we'll be able to see whether this user actually invoked the tool. Investigate post-1.1. `[NEW — investigate post-1.1]`
- **Hierarchical topic architecture (`start_topic(parent_topic=...)` + `reconcile_to_parent()`).** Considered and deferred. The Q6 answer in the third feedback round suggested parallel topics should be first-class children of a parent topic, with reconciliation baked into the API. **Decided to take the light-touch path instead:** `cross_wiki_diff` (5.2) stays the only new primitive; parallel topics remain siblings; users / AI compose the workflow. Reasoning: the cost of adding parent/child concepts to the schema and API surface outweighs the benefit until we see the manual composition pattern prove too friction-heavy in real use. Revisit if (a) cross-wiki is done with 5.2 and the AI still struggles to assemble the workflow, or (b) a user shape emerges where hierarchical topic relationships are central (e.g., long-running multi-wiki research projects). `[NEW — deferred 2026-04-22]`

---

## Open questions for the live AI (before session ends)

Useful to ask before the session ends, to inform Stage 1 / 4:

1. Why `score_all_unscored(8)` as the closing move? Is 1–10 scoring ever useful for taxonomy topics, or overhead?
2. Did you consider `check_wikiproject("Orchids")` specifically (not just "Plants")? Why skip after the first negative?
3. `manual:<label>` clusters — was this deliberate pattern, or emergent?
4. What would cross-wiki diffing look like if you *could* query sitelinks? Walk through the next move on orchids-zh.
5. What tools did you want that you didn't know existed?

---

## How to use this doc

- We'll work top to bottom. Each item: discuss shape, resolve open questions, decide go/no-go/reshape, then build.
- Mark status inline as we go (`☐` → `◐` → `☑`).
- As items ship, migrate a one-line summary to `operations-and-backlog.md` under "Recently shipped" and check off here.
- If a later item's evidence changes as we ship earlier ones, re-open the question — no strict commitment until the build starts.
