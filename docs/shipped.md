# Shipped log

Compact record of items shipped from the improvements plan.
For the remaining open backlog, see `backlog/README.md`; for the full
historical plan with Shape / Why / Open-questions per item, see
the `docs/post-orchids-plan.md` snapshot in git history before
2026-04-23's split.

---

## Stage 1 — Quick ship

- **1.1** — Observability backfill: missing logs + per-call cost fields
  **Shipped 2026-04-22.** All three parts landed in one commit: log coverage on 16 previously-unlogged tools; `ContextVar`-based per-call counters (`wikipedia_api_calls`, `rate_limit_hits_this_call`) hooked into `wikipedia_api.api_get`; `elapsed_ms` + …
- **1.2** — `harvest_list_page(main_content_only=True)`
  **Shipped 2026-04-22.** Default True. Uses `action=parse&prop=text` + a stdlib `html.parser.HTMLParser` subclass that walks a proper tag stack, tracks excluded-subtree depth (`navbox`, `sidebar`, `infobox`, `reflist`, `hatnote`, `shortdescription`, `…
- **1.3** — `preview_similar` tool
  **Shipped 2026-04-22.** Delegates to `preview_search(morelike:<seed>, ...)` the same way `search_similar` delegates to `search_articles`. Kept as a separate tool (not a commit-flag on search_similar) to match 1.4's `preview_*` naming convention and a…
- **1.4** — `preview_harvest_list_page` and `preview_category_pull`
  **Shipped 2026-04-22.** Two new tools with matched `preview_*` naming (Sage confirmed this convention over `dry_run=True` flags). Both share logic with their commit-variant siblings via two extracted helpers: `_fetch_list_page_links(title, wiki, main…
- **1.5** — `get_articles(title_regex=..., description_regex=...)` + source labels in output
  **Shipped 2026-04-22 (grouped with 1.20).** Added `title_regex` and `description_regex` params with Python `re.search` semantics (case-insensitive). Invalid patterns return a structured error rather than 500. `sources` array was already in the get_ar…
- **1.6** — `fetch_descriptions` defaults + auto-loop
  **Shipped 2026-04-22.** Default `limit` bumped 500 → 2000. Added auto-loop that keeps fetching batches until the topic is fully described or `time_budget_s` (default 60) is exhausted. Return shape gained `batches_run` + `time_budget_exhausted` so the…
- **1.7** — `remove_articles` auto-chunking + documented limit
  **Shipped 2026-04-22.** Pre-flight: the ~200-cap the orchids AI hit was NOT in server/db code (inspected — db.remove_articles had no cap and looped one title at a time). It was a client-side truncation by the MCP client. Server-side fixes: (a) batche…
- **1.9** — `check_wikiproject` discovery
  **Shipped 2026-04-22.** Part (b) — hard warning on non-en — was already in place; verified. Part (a) added via new `find_wikiprojects(keywords, limit=20)` tool. Uses MediaWiki `list=prefixsearch` on the Wikipedia: namespace to enumerate projects whos…
- **1.10** — `search_articles(within_category=...)` / scope-narrowed search
  **Shipped 2026-04-22.** Added `within_category: str | None` to both `search_articles` and `preview_search`. Appends `incategory:"<cat>"` to the query via a shared `_apply_within_category` helper. Single-level (CirrusSearch's `incategory:` does not wa…
- **1.11** — Pre-flight cost estimates for heavy tools
  **Shipped 2026-04-22.** Pivoted from the plan's original "pre-flight estimation" shape because the `preview_*` tools (1.4) already cover that — the AI can call `preview_category_pull` / `preview_harvest_list_page` for pre-flight counts. What was miss…
- **1.12** — Per-topic cost surface in `get_status`
  **Shipped 2026-04-22.** `_topic_cost_summary(topic_name)` scans the last 20K lines of `usage.jsonl` and aggregates: `logged_tool_calls`, `lifetime_wikipedia_api_calls`, `lifetime_timeouts`, `rate_limit_hits_total`, plus a `recent_heavy_calls` tail (l…
- **1.13** — `auto_score_by_title` rethink → `auto_score_by_keyword(keywords=[...])`
  **Shipped 2026-04-22.** Renamed (Sage confirmed no backward-compat concern). New signature requires explicit `keywords: list[str]` — no topic-name fallback. Params: `score=9` (was `threshold=7`; +2-to-10 implicit mapping dropped; cleaner to expose di…
- **1.14** — Source-label slugification for `search_articles` commit variant
  **Shipped 2026-04-22.** `_slugify_for_source_label` preserves `:` operator separators (so `morelike:the-orchid-thief` stays intact), strips Latin combining diacritics, replaces punctuation/whitespace with `-`, and **preserves non-Latin Unicode letter…
- **1.15** — Suppress no-word-overlap warning for obvious taxonomy pulls
  **Shipped 2026-04-22.** `_looks_taxonomic(topic_name, category)` gates `_scope_drift_warning`. Suppresses when (topic name contains a biology keyword like "orchid"/"bird"/"plant"/"fungus"/… OR has a `-aceae`/`-idae`/`-ales`/`-phyta`/`-ae` suffix word…
- **1.16** — Export CSV enrichment
  **Shipped 2026-04-22.** Added `enriched: bool = False` param. Default behavior unchanged (two-column `title, description`, no header — matches Impact Visualizer import). When `enriched=True`, writes a five-column CSV with a header row: `title, descri…
- **1.17** — Non-English description fallback via REST page summary
  **Shipped 2026-04-22.** New `fetch_descriptions_with_fallback(titles, wiki)` in `wikipedia_api.py`: first pass Wikidata short-desc (unchanged), then on non-en wikis retries empty titles via `/api/rest_v1/page/summary/{title}` and stores the extract's…
- **1.18** — Auto-nudge on `resume_topic` after a feedback-less session
  **Shipped 2026-04-22.** `_feedback_nudge_for_resume(topic_name)` scans usage.jsonl for tool calls on this topic. Fires when: (a) the most recent non-resume/non-start/non-feedback call is >24h ago, AND (b) no submit_feedback has been logged after that…
- **1.19** — Nudge on repeated bare `manual` source labels
  **Shipped 2026-04-22 (grouped with 2.1).** Per-session counter `_session_bare_manual_counts` ticks up on every `add_articles(source="manual", ...)`. On the second such call, the response gains a `label_hint` field with concrete examples (`manual:veit…
- **1.20** — Source-intersection query on `get_articles`
  **Shipped 2026-04-22 (grouped with 1.5).** `sources_all: list[str] | None` param added. Uses AND semantics; composes with the existing `source` OR filter. Example: `sources_all=["category:Orchidaceae", "wikiproject:Orchids"]` returns the high-confide…
- **1.21** — `describe_topic` diagnostic
  **Shipped 2026-04-22.** In-process aggregation over the working list (no Wikipedia API calls). Returns: `title_length_distribution` (1-word, 2-words, …), `top_first_words` (default top 20 — spots dominant genera in taxonomy topics), `articles_without…
- **1.22** — Sticky rejection list
  **Shipped 2026-04-22.** DB: new `rejections(topic_id, title, reason, rejected_at)` table, topic-scoped, ON DELETE CASCADE. Three new tools: `reject_articles(titles, reason, also_remove=True)`, `list_rejections()`, `unreject_articles(titles)`. Gather …

## Stage 2 — Instruction updates

- **2.1** — Document the `manual:<label>` convention
  **Shipped 2026-04-22 (grouped with 1.19).** server_instructions.md gained a dedicated `manual:<label> CONVENTION` bullet right after the source-label one. Covers the motivation (label documents *reason or method*, not just "by hand"), four concrete e…
- **2.2** — Noise taxonomy into instructions
  **Shipped 2026-04-22 (Stage 2 bundle).** Added `NOISE TAXONOMY` bullet covering category crawls / genus-species lists / geographic lists / biography lists / `search_similar` as seed-topology-function / `browse_edges`. All five patterns documented wit…
- **2.3** — Cross-wiki guidance
  **Shipped 2026-04-22 (Stage 2 bundle).** `CROSS-WIKI WORKFLOW` section added after `WIKI SELECTION`. Covers the "completeness-check" framing (21 missed enwiki articles only reachable via non-en walk-back), the six-step workflow pattern, the ~1–2h-per…
- **2.4** — Pipeline order from playbook
  **Shipped 2026-04-22 (Stage 2 bundle).** Replaced the terse 6-step list at the top of instructions with a 14-step opinionated pipeline. Strengthened the WikiProject step explicitly: added a standalone paragraph after the pipeline telling the AI NOT t…
- **2.5** — Cost-awareness guidance
  **Shipped 2026-04-22 (Stage 2 bundle).** `COST AWARENESS` bullet added, anchored on 1.11's `cost_warning` field and 1.12's per-topic cost summary. All five plan bullets ported; last one "good citizen of Wikimedia infrastructure" stays verbatim.
- **2.6** — Event-triggered reflection guidance
  **Shipped 2026-04-22 (Stage 2 bundle).** `REFLECTION` bullet added with two subsections: "Drop a `note=` when" (4 triggers including timed_out, morelike-gone-sideways, unexpected noise, docstring gap) and "Call submit_feedback when" (4 triggers inclu…
- **2.7** — "Common task → tool" mapping in instructions
  **Shipped 2026-04-22 (Stage 2 bundle).** `COMMON TASK → TOOL` table added near the top (right after PIPELINE). 12 rows — covers the shipped tools plus three placeholders for Stage 5's `petscan_*`, `cross_wiki_diff`, `completeness_check` with italic "…

## Stage 3 — Medium project: cooperative time budget + resumable long ops

- **3.1** — Chunked/resumable `get_category_articles`
  **Shipped 2026-04-22.** `_walk_category_tree` now accepts an optional `deadline: float` (time.monotonic() scale) and returns a 4-tuple: `(articles, fully_crawled, pending, timed_out)`. Budget checks happen at the top of the BFS loop; one category's a…
- **3.2** — Chunked/resumable `filter_articles`
  **Shipped 2026-04-22.** Reshape from plan's "offset-based resume" to "phase-based resume" after reading the code — resolve_redirects builds a full map before applying it, so mid-phase partial-map application would give inconsistent state. New shape: …
- **3.3** — Cooperative time budget on `harvest_list_page`
  **Shipped 2026-04-22 (shallow variant per kickoff reshape).** `_fetch_list_page_links` accepts `deadline` and returns a `timed_out` flag. Only the `prop=links` fallback path can actually time out — the `main_content_only=True` default is a single API…
- **3.4** — Cooperative time budget on `fetch_descriptions` auto-loop
  **Shipped retroactively — already in place from 1.6 (commit `e594d0e`).** `fetch_descriptions` has `time_budget_s=60` (lower than the Stage 3 240s default because description fetch batches return fast — 60s drains most topics without burning through …

## Stage 4 — Two-axis topic model: inclusion × centrality `[reshaped 2026-04-22 from "scoring at scale" design-decision stage]`

- **4.1** — `export_csv` works without scoring by default
  **Shipped retroactively** in 1.16 — `min_score=0` default includes unscored articles; `enriched=True` emits the score column blank when NULL. No new work in this stage.
- **4.2** — Instructions rewrite around centrality-gradient model
  **Shipped 2026-04-22 (Commit B).** Rewrote the scoring bullets in `server_instructions.md`:
- **4.3** — IV handoff doc — centrality roadmap
  **Shipped 2026-04-22 (Commit B).** Added `## Centrality score — current state and roadmap` section to `docs/backlog/impact-visualizer.md`:
- **4.4** — Rewrite `auto_score_by_description` to reject instead of writing score=0
  **Shipped 2026-04-22 (Commit A).** Switched from `db.set_scores({t: 0})` to `db.add_rejections(titles, reason="auto_score_by_description: <marker>")` plus `db.remove_articles(titles)`. Each rejection carries its specific reason (disqualifying:actor, …
- **4.5** — `score_all_unscored` deprecation note in docstring
  **Shipped 2026-04-22 (Commit A).** No behavior change. Docstring now leads with "prefer leaving articles unscored" and frames the tool as "for deliberately stamping the remainder at a chosen centrality after review" — not a closing ceremony. Named th…
- **4.6** — Rejection sample in gather responses
  **Shipped 2026-04-22 (Commit A).** Added `_apply_rejections(topic_id, candidates)` helper in `server.py` — uniform accounting across `get_category_articles`, `get_wikiproject_articles`, `harvest_list_page`, `search_articles`, `add_articles`. Response…
- **4.7** — Sweep for leftover old-model references
  **Shipped 2026-04-22 (Commit B).** Greps confirmed no stale references in `mcp_server/` or `docs/` — legacy references all in intentional explanatory context ("this tool used to write score=0") or in `development-narrative.md` (explicitly historical,…

## Stage 5 — Big build: Wikidata layer

- **5.1** — `wikidata_query` / `wikidata_entities_by_property`
  **Shipped 2026-04-22.** Two tools (`wikidata_entities_by_property` helper, `wikidata_query` raw SPARQL) backed by a shared `wikidata_sparql()` wrapper in `wikipedia_api.py`. Reuses `api_get` so per-call counter + rate-limit backoff come for free. 1h …
- **5.1a** — `wikidata_search_entity` — QID/PID discovery helper
  **Shipped 2026-04-22.** Label-search wrapper around Wikidata's `wbsearchentities` action. Returns candidate entities (or properties — `entity_type="property"`) with QID/PID + label + description + aliases + match type. Single API call (~100ms), no SP…
- **5.6** — Per-article Wikidata QID on the working list
  **Shipped 2026-04-22.** DB migration adds nullable `wikidata_qid TEXT` column to `articles` (new-DB schema + `init_db` migration hook for existing DBs). New `resolve_qids(limit=2000, time_budget_s=60)` MCP tool — lazy backfill via pageprops (1 call p…

## Post-orchids dogfood chunks (2026-04-23)

Emergent tool fixes from the 5-topic Codex dogfood arc, deployed
iteratively via `deploy.sh` and batched into git commit `e19ea36`.

- **Chunk 1 — `intitle:OR` silent-empty fix.** Cirrus returns 0 on compound `intitle:` clauses; `_split_intitle_or_query` splits and merges.
- **Chunk 2 — `find_list_pages` widen + disambiguation filter.** Broader query, strips `(disambiguation)` hits.
- **Chunk 3 — `harvest_list_page` caption-as-title fix.** Uses actual link target, not the display caption, as the article title.
- **Chunk 4 — `wikidata_entities_by_property` sitelink_count + auto-trim.** Adds per-result sitelink count and trims when the response exceeds size cap.
- **Chunk 5 — `wikidata_query` auto-truncate.** Oversized SPARQL responses truncated with a clear marker instead of blowing the transport.
- **Chunk 6 — `fetch_descriptions` REST fallback on enwiki + deadline-aware.** Was non-en only; enwiki also has ~20% blank shortdescs on older biographies. Deadline lets large batches bail without locking titles as permanently empty.
- **`harvest_navbox` primitive.** Extract article lists from navbox/infobox templates.
- **`filter_articles` drops unresolved titles** instead of silently keeping them.
- **Triangulation warning at export.** Flags low source-overlap when exporting.
- **`find_wikiprojects` / `check_wikiproject` output shape harmonized.**

Rubric system (same batch commit):

- **`set_topic_rubric` / `get_topic_rubric` tools** + `centrality_rubric` column on `topics` (with migration). AI drafts a three-tier rubric (CENTRAL / PERIPHERAL / OUT) in its own voice at scoping time; persists across sessions.
- **Rubric is MANDATORY before any gather call** — enforced in `server_instructions.md`.
- **Shape → Wikidata property table** added to instructions (P166 awards, P31/P279*+P17 geographic, P101 discipline, P135 art movement).
- **Main-article-as-list-page fallback pattern** documented for topics where `find_list_pages` returns nothing useful (awards, art movements, events).
- **SPOT CHECK + GAP CHECK wrap-up discipline** added to instructions.

## Benchmark ratchet infrastructure (2026-04-23)

Scaffolding for measuring tool-change impact across 5 reference topics.
Commit `8cc5e31`.

- **5 benchmark scaffolds** — `apollo-11`, `crispr-gene-editing`, `african-american-stem`, `hispanic-latino-stem-us`, `orchids`. Each has `scope.md`, `rubric.txt`, `baseline.json`, human-written `audit_notes.md` (tracked) + local-only `gold.csv` / `audit.py` / `audit_summary.md` (gitignored — pair names with judgments).
- **`scripts/bootstrap_benchmark.py`** — dumps baseline.json + gold.csv for a new benchmark topic from live server state.
- **`scripts/benchmark_score.py`** — the scoreboard. Gate: precision + recall don't regress (1e-3 tolerance), ≥1 cost metric (wall_time / api_calls / tool_calls) strictly improves. Reach (audited on-topic reach beyond prior gold) tracked but non-gating.
- **`.gitignore` hygiene** — tightened to allow `audit_notes.md` (was caught by overbroad `audit*.md` pattern).

## Repo reorganization (2026-04-23)

Commit `38f1cba`.

- Split `docs/post-orchids-plan.md` (1001 lines) into `docs/shipped.md` + `docs/backlog/README.md`; add `docs/ratchet-plan.md` as the consolidated benchmark workflow entry point.
- Move deferred plans into `docs/backlog/`: `auth.md`, `impact-visualizer.md`.
- Rename `docs/operations-and-backlog.md` → `docs/operations.md`; drop redundant Backlog section.
- Delete `docs/topic-strategies.md` (wisdom absorbed into `server_instructions.md`), `docs/development-narrative.md` (git history is the record), `skill.md` (prototype, superseded).
- Move pre-MCP script one-offs into `scripts/legacy/`.
- Dogfood tooling landed separately (commit `918f2ef`): `scripts/monitor_dogfood.sh`, `scripts/smoke.sh`, and `dogfood/task.md` autonomous-prompt tweaks.

## Tier 1 ratchet bundle (2026-04-23+)

First ratchet cycle after the backlog reorg. Small, independent
items; ship individually, re-run the 5-benchmark ratchet after all
three land.

- **`coverage_estimate` field on `submit_feedback`.**
  **Shipped 2026-04-23.** Optional `coverage_estimate: dict | None` parameter, shape `{"confidence": 0.0–1.0, "rationale": str, "remaining_strategies": [str, ...]}`. Stored in the feedback entry alongside the existing fields; `confidence` also added to the `usage.jsonl` log params so it's trendable without re-reading feedback.jsonl. Contrast with `missed_strategies`: this one is for tool shapes that *exist* but weren't applied this session (a coverage signal), while `missed_strategies` is for tool shapes we wished existed (a backlog signal).

- **Surface known-bug workarounds in `server_instructions.md`.**
  **Shipped 2026-04-23.** New `KNOWN SHARP EDGES` section between the `morelike:` danger bullet and `NOISE TAXONOMY`. Four gotchas the AI should recognize even when the call site isn't auto-fixing them: (1) compound Cirrus operators (`intitle:A OR intitle:B`, likely same for `incategory:` / `hastemplate:`) silently return 0 — split and merge; (2) `auto_score_by_description(disqualifying=[...])` substring-matches inside proper-noun phrases (Kansas City Star / Orange County Register); (3) empty `survey_categories` on an existing category usually means container/redirect, look for a sibling; (4) Wikidata short-descs are empty, truncated, or misleading often enough that they shouldn't be a sole signal when assigning centrality. Also mentions that large SPARQL / `wikidata_entities_by_property` responses auto-truncate and the AI should recognize the truncation marker.

- **`fetch_article_leads` tool.**
  **Shipped 2026-04-23.** New standalone MCP tool: `fetch_article_leads(titles, sentences=3, wiki=None)`. Wraps MediaWiki `prop=extracts&exintro=1&exsentences=N&explaintext=1` in batches of 20 (the `exlimit` cap when `exsentences` is in use); follows normalizations + redirects. Distinct from `fetch_descriptions`: non-persistent, explicit titles list (no backlog drain), targeted disambiguation use case. `sentences` param capped at 5 (default 3, per Sage). Added to `COMMON TASK → TOOL` mapping in `server_instructions.md`; the `KNOWN SHARP EDGES` shortdesc-reliability bullet now points at it as the disambiguation primitive. Direct response to the 2026-04-23 AA-STEM audit (Gloria Chisum "American academic" / Meredith Gourdine "American long jumper" / William Hallett Greene truncated-shortdesc cases).

## Dogfood task entry-point tool (2026-04-23)

Infrastructure for automating benchmark / dogfood runs: the operator's kickoff prompt becomes "Call `fetch_task_brief(task_id='X')`, follow its instructions" instead of copy-pasting a long markdown file. Lays groundwork for the eventual claude.ai guided-mode skill (same tool can serve it).

- **New `dogfood_tasks` DB table.** Columns: `task_id` (UNIQUE lookup key), `variant` (`thin` / `fat` / ...), `benchmark_slug` (nullable; links to `benchmarks/<slug>/` for scoring), `run_topic_name` (exact `start_topic` name — distinct from baseline), `brief_markdown` (full verbatim text served to the AI), `metadata_json`, `created_at`, `updated_at`. Migration-safe via `CREATE TABLE IF NOT EXISTS` in `init_db`. CRUD helpers in `db.py`: `upsert_dogfood_task`, `get_dogfood_task`, `list_dogfood_tasks`.
- **Two new MCP tools.** `fetch_task_brief(task_id)` returns the full brief + run-topic name + metadata. `list_tasks(variant=None, benchmark_slug=None)` returns metadata only (discoverability). Both are read-only; clearly scoped to research / benchmark runs via docstring ("don't call outside that context") + labeled on the landing page with the same caveat.
- **Source-of-truth markdown files** under `dogfood/tasks/`: YAML-lite frontmatter + markdown body. Five thin-variant briefs seeded for the 2026-04-23 ratchet (apollo-11, crispr-gene-editing, african-american-stem, hispanic-latino-stem-us, orchids). Thin = one-paragraph scope + session protocol only; no rubric, no reach targets, no topic-specific guardrails. Tests the tool surface under realistic-user guidance.
- **Seed script.** `scripts/seed_dogfood_tasks.py` reads the markdown files, parses frontmatter, and upserts. Idempotent. Looks for tasks at `/tmp/dogfood_tasks/` (host) → `dogfood/tasks/` (local repo); operator pre-scp's the directory before running via `smoke.sh`.
