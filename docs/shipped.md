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

## Reach-to-gold promotion workflow (2026-04-24)

Zero-risk gold-farming pipeline: each ratchet run's reach list (articles in the run corpus but not in audited gold) can be promoted into `gold.csv` as `on_topic=pending_audit` rows. The scoring script already tracks `pending_audit` separately from `in` / `peripheral` / `out` — those rows don't count toward recall or precision denominators, so promotion is a no-op for the gate but grows the audit queue for later human review.

- **`scripts/promote_reach.py`** — reads `benchmarks/<slug>/gold.csv` and the run topic's live corpus; computes reach = corpus − gold-titles; appends each reach title with `on_topic=pending_audit` and a new `source_run` column (provenance — which run surfaced this title). Idempotent: any title already in gold under any status is skipped, so human classifications always win over re-runs. `--dry-run` flag previews without writing.
- **First-pass promotion** (2026-04-24): 628 titles enqueued for audit across the 5 benchmarks — 456 on orchids, 129 on AA-STEM, 23 on CRISPR, 18 on Apollo 11, 2 on HL-STEM. Next ratchet cycle's reach lists will only contain NEWLY-surfaced candidates, not the re-surfacing carryover from this cycle.
- **Audit workflow.** Edit `gold.csv` directly to change `on_topic` from `pending_audit` to `in` / `peripheral` / `out` at whatever cadence is convenient; scoring picks up changes on the next run. A dedicated audit UI / script (`audit_pending.py`) is deferred — the CSV-edit path is cheap enough that building tooling for it isn't justified until audit volume demands it.
- **Caveat.** Per-benchmark `audit.py` classifiers rewrite `gold.csv` wholesale — re-running one would wipe promoted reach AND manual classification edits. Documented in `promote_reach.py`'s module docstring; fold into `benchmarks/README.md` when the doc-sweep Tier 1 item lands.

## First-pass reach audit (2026-04-24)

Manual classification of all 628 pending_audit rows from the first-pass reach promotion. Across the 5 benchmarks:

| Benchmark | in | peripheral | out |
|---|---:|---:|---:|
| apollo-11 | 10 | 8 | 0 |
| crispr-gene-editing | 16 | 7 | 0 |
| african-american-stem | 76 | 8 | 45 |
| hispanic-latino-stem-us | 1 | 0 | 1 |
| orchids | 296 | 82 | 78 |
| **total** | **399** | **105** | **124** |

- **`scripts/apply_classifications.py`** — reads a `{title: in/peripheral/out}` JSON, applies to `gold.csv`. Skips already-classified rows (human wins over automation).
- **Heavy `fetch_article_leads` use** on intersectional biography audits (AA-STEM) — the tool's design case. Distinguished physician-scientists (IN) from clinical-only physicians (OUT), separated STEM researchers from science communicators / admins (PERIPHERAL), and caught the historical inventors who were easy titles but non-obvious leads (Joseph Winters, William Chester Ruth, etc.).
- **Orchid audit via pattern classifier** — 456 titles reduced to 2 "uncertain" after rule-based classification (scientific-name prefix detection, author-abbreviation matching, non-orchid noise lists). The 2 uncertain got leads.
- **Orchids gold-quality finding**: 10,763 of the 18.3k rows are redlinks on Wikipedia — titles harvested from list pages that have no standalone articles. Flagged by the redirect reconciler (below) but not dropped; awaits a separate remediation pass.

## Redirect resolution + gold reconciliation (2026-04-24)

End-to-end fix for the redirect-blindness discovered during the first-pass audit. Both script-side (for offline gold maintenance) and server-side (for live build pipelines).

**Scripts:**
- **`scripts/redirect_utils.py`** — shared helper, `resolve_redirects(titles, wiki)` → dict[title → canonical | None]. Uses MediaWiki `action=query&redirects=1`, batched at 50 titles per call, rate-limited 100ms. Handles redirect chains (depth ≤ 5) + title normalizations.
- **`scripts/reconcile_redirects.py`** — offline cleanup for each benchmark's `gold.csv`. Resolves every title; partitions into self-canonical / redirect-with-canonical-also-in-gold / redirect-only / missing. Merges duplicates using a decisive-classification winner (in/peripheral/out/true/false beats pending_audit); flags `in`-vs-`out` conflicts for manual review. `--dry-run` flag. Ran on all 5 benchmarks:
    - CRISPR: 3 merged, 1 rewritten (TALEN → canonical long-form).
    - Apollo 11: 3 merged (LLTV/LLRV, LLR singular/plural, Apollo launch umbilical tower → Mobile launcher platform).
    - HL-STEM: 1 conflict flagged for review (Elsa Salazar Cade true vs. William H. Cade false — Wikipedia redirects Elsa's title to her husband's article).
    - AA-STEM: 0 changes needed.
    - Orchids: 365 merged, 11 rewritten, 19 conflicts (mostly my-auto-peripheral vs. original-audit-in for botanist abbreviation/fullname pairs like Lindl./John Lindley — both legitimate readings, need human pick).
- **`scripts/promote_reach.py`** enhanced to resolve redirects before appending. Skips titles whose canonical is already in gold; dedupes reach titles that resolve to the same canonical; skips titles reported as missing. Prevents the re-introduction of redirect-source duplicates on future runs.
- **`scripts/benchmark_score.py`** enhanced to normalize corpus titles to canonical before comparing to gold. Defensive even with gold reconciled — the live run corpus can still contain redirect-source titles from the AI's harvests. Re-running CRISPR scoring with this change bumped gold hits 68 → 88 (+20) after counting redirect-source hits that were previously missed.

**Server-side:**
- **`mcp_server/wikipedia_api.py`** — new `resolve_redirects(titles, wiki, deadline)` + `apply_redirect_map(titles, redirect_map)` helpers. Deadline-aware for cooperative time budgets.
- **New `resolve_redirects` MCP tool** — topic-scoped, additive-only. Rewrites every article title in the current topic to its canonical Wikipedia form; merges duplicates; never drops. Safe to run repeatedly. `dry_run=True` for preview. Added to COMMON TASK → TOOL map + recommended in PIPELINE step 5 of `server_instructions.md`.
- **`filter_articles` safety threshold** — new `max_drop_fraction` (default 0.1) and `force` (default False) parameters. When the redirect phase would drop more than the fraction as "missing on Wikipedia," the tool refuses and returns a preview + sample instead of committing. Closes the 2026-04-24 Tier 1 bug where it silently dropped 11k/18k orchids titles.
- Landing page + server_instructions.md updated. Landing lists the new tool + updated filter_articles description; instructions PIPELINE step 5 recommends `resolve_redirects` first, then `filter_articles` (noting the safety refusal behavior).

## Redirect + redlink status marking in gold (2026-04-24)

Follow-on to the redirect reconciliation pass: instead of silently dropping merged duplicates or flagging missing titles for ad-hoc review, **every row in gold.csv now carries an explicit honest status**. The scoring script excludes redirect/redlink from all denominators so neither corrupts precision or recall.

- **Two new `on_topic` statuses:**
  - `redirect` — title is a Wikipedia redirect source pointing at a canonical row also in gold. Provenance marker; future runs recognize the title as "known, don't re-audit." Notes field records `→ canonical_title`.
  - `redlink` — title has no Wikipedia article (page missing). Original classification preserved in notes as `[was: <original>]` for audit history.
  - Both excluded from `gold_in`, `gold_out`, precision denominator, recall denominator. Tracked in the scoreboard's `Gold status` section with counts + excluded-from-scoring notes.
- **`reconcile_redirects.py`** changed to mark rather than drop/flag. Re-run on all 5 benchmarks: CRISPR 0 marks, Apollo 0, AA-STEM 0, HL-STEM 1 redirect (Elsa Salazar Cade → William H. Cade with warning), Orchids **19 redirect + 10,763 redlink** markings.
- **`promote_reach.py`** changed to add redirect/redlink rows instead of skipping. Re-run against each 2026-04-23 run topic to reconstruct past drops: CRISPR +4 redirects (Base editing / CRISPR-Cas / CRISPR/Cas9 / TALEN), Apollo 11 +2, Orchids +376, AA-STEM + HL-STEM 0.
- **Scoreboard impact (orchids)**: gold size dropped from 18,113 to **7,354** after excluding redlinks — much more honest. Precision 99.0% (was showing 100%), recall 98.1% (was 100%). The prior numbers were inflated by treating 10,763 phantom redlinks as on-topic gold; the new numbers reflect Wikipedia articles that actually exist.
- **Baseline caveat**: baseline.json metrics (100% / 100%) are frozen from pre-redlink-marking. Rebuilding baselines (Tier 1 1.b) will true them up to the new gold composition.

## Tier 1 1.c: benchmark_score.py api_calls=0 gate fix (2026-04-24)

Small one-branch fix. When a baseline records `total_api_calls = 0`, that axis is treated as UNRECORDED (missing data from pre-logging-backfill runs) and skipped from the cost-improvement gate. The scoreboard Cost table labels the axis `"no (baseline unrecorded)"` so the omission is visible. HL-STEM gate verdict moved from "did not improve" to "improved" after the fix — tool_calls dropped 108→62 on the run but was masked by the phantom api_calls "regression" against the 0 baseline.

## Tier 1 1.a: Brief durability pass + template mechanism (2026-04-24)

Locks the thin-variant brief as the measurement contract. Everything that might evolve over ratchet cycles moves to the substrate (server instructions, feedback schema); the brief stays frozen. Enables unlimited re-runs of the same task without name collisions or prompt edits.

- **Template rendering.** Both `run_topic_name_template` and `brief_markdown` are stored as templates containing `{ts}`. `fetch_task_brief` renders `{ts}` to the current minute-UTC (`YYYYMMDDTHHMM`) at call time, returning concrete `run_topic_name` + `brief` strings. Two fetches in the same minute get the same name; fetches ≥1 minute apart get fresh names.
- **DB schema.** New `run_topic_name_template` column on `dogfood_tasks`. Migration-safe via `ALTER TABLE ADD COLUMN` + `UPDATE ... WHERE IS NULL`. Legacy `run_topic_name` kept populated for the NOT NULL constraint; consumers read from the template column.
- **Structured feedback fields** on `submit_feedback`: `strategies_used` (list of tool-family tags), `spot_check` (dict with probe counts + miss classifications), `sharp_edges_hit` (list of KNOWN SHARP EDGE tags), `tool_friction` (list of tagged friction one-liners). All optional, schema-documented with suggested vocabularies. The brief names them so AIs populate; schema can evolve without brief edits.
- **Brief bodies stripped of operational details.** No more "~15–25 niche candidates" probe counts, no CENTRAL/PERIPHERAL/OUT rubric framework inlined — all of that was already in `server_instructions.md` and the briefs now reference it ("follow the SCOPE RUBRIC framework"). Keeps briefs fully general so subsequent instruction changes don't require brief edits.
- **Scoring script `--task` alternative**: `python3 scripts/benchmark_score.py --task apollo-11-thin [--nth N]` resolves the task's template from the DB on the server, finds matching run topics by regex, picks the Nth-most-recent, and scores it. Direct positional `<slug> <run-topic-name>` form still works.
- **Source-of-truth markdown** at `dogfood/tasks/*.md` uses new frontmatter key `run_topic_name_template` (legacy `run_topic_name` accepted for back-compat). `dogfood/tasks/README.md` fully rewritten to explain the durability contract + template rendering + thin-vs-informed variant split.

## Nginx timeout bump + Tier 1 1.b rebuild baselines + reach audit (2026-04-24)

Three tasks shipped as a bundle after the first 5 thin-variant runs completed.

- **Nginx proxy timeouts raised to 300s** on `/mcp` (from default 60s). Absorbs the ceiling that was returning 504 bursts when a heavy single-worker tool call held the event loop > 60s. No Python restart; `deploy.sh` writes the new config and reloads nginx. Multi-worker + session-sticky routing remains as a Tier 1 backlog item (needs systemd template + nginx upstream with `hash $http_mcp_session_id consistent`) — the timeout bump is the safe half of that fix.
- **Tier 1 1.b: baselines rebuilt from thin runs.** New helper `scripts/update_baseline_from_run.py` lifts each thin run's metrics (precision / recall / cost / source-count stats / AI self-rating / coverage_estimate confidence) into `benchmarks/<slug>/baseline.json`. Previous baselines archived as `baseline-archive-20260424.json`. New baselines:
    - apollo-11: 92 articles, precision 0.5543, recall 0.3312, reach 0
    - crispr-gene-editing: 58 articles, precision 1.0, recall 0.5196, reach 5
    - african-american-stem: 863 articles, precision 0.9931, recall 0.8537, reach 114
    - hispanic-latino-stem-us: 199 articles, precision 0.9536, recall 0.5892, reach 5
    - orchids: 5,044 articles, precision 1.0, recall 0.5014, reach 0
  These are the new measurement substrate. Future thin-variant runs compete against these numbers, not the fat-variant 2026-04-23 baselines (which are preserved as archives).
- **Reach audit: 124 candidates classified** (CRISPR 5, HL-STEM 5, AA-STEM 114). Batched `fetch_article_leads` on all 124 + applied via `scripts/apply_classifications.py`. AA-STEM split: 60 in / 8 peripheral / 46 out. HL-STEM: 4 in / 1 out (Natasha Batalha OUT per Brazilian-heritage scope exclusion). CRISPR: 3 in / 2 peripheral. Gold now has 60+4+3 = 67 new in/peripheral additions across the three benchmarks; next-cycle recall measurements will reflect these.

## Tier 1 1.d: abstract shape-strategy wisdom into server_instructions (2026-04-24)

Moves cross-topic-shape wisdom from the 2026-04-23 fat-variant kickoff prompts into the canonical instructions, so thin-variant runs benefit automatically without operator pre-hinting. This is the first content change sequenced AFTER the thin baselines landed (1.b), so its effect on the ratchet can be measured in the next cycle.

- **Expanded `SHAPE → WIKIDATA PROPERTY` table** with a new "High-leverage first move" column naming the best first gather reach per topic shape (navbox on parent-program for historical events; list-page harvest for taxonomy; category pull for geography; etc.). Added a row for **Intersectional biography** covering the demographic × discipline shape that hadn't been in the table. Added a closing paragraph explicitly framing Wikidata probes as **ADDITIVE only** — never as subtractive filters — citing the Wikidata-incompleteness principle.
- **New `SOURCE-TRUST` bullet** in the IMPORTANT GUIDELINES section: when an article was pulled from a topic-definitional source (category named after the topic, list-page authored by topic specialists, dedicated WikiProject), trust provenance over thin / blank shortdescs. Explicit carve-outs: broad parent categories, search-based sources, similarity seeds, and manual labels don't qualify. Counterbalance: the absence of such a source is NOT a reason to drop an article.
- **Reinforced `INTERSECTIONAL TOPICS`** section with an explicit `fetch_article_leads` pointer as the disambiguation workhorse on that shape: Wikidata shortdescs frequently mislead on intersectional biographies (generic "academic" hiding a STEM sub-field; STEM-sounding label covering a clinical-only physician out of scope), so reach for leads before scoring or rejecting. Cheap + decisively better signal than shortdesc alone.
- Deployed to the live server; `server_instructions.md` at 49,705 chars.

## Multi-worker MCP server with sticky nginx routing (2026-04-25)

Two Python processes on distinct ports behind nginx, sticky session routing by client IP. Absorbs cross-operator concurrency: heavy tool calls on one operator's session no longer stall handshakes on another operator's session.

- **Systemd template unit** `topic-builder@.service` accepts `%i` as the port. Both `topic-builder@8000` and `topic-builder@8001` enabled and started. `server.py` reads `PORT` from env and sets `mcp.settings.port` accordingly.
- **nginx upstream** `topic_builder_backend` block with `ip_hash` directive routes both ports. `proxy_pass http://topic_builder_backend` on `/mcp`. Initial implementation tried `hash $http_mcp_session_id consistent` but that was structurally broken: the worker that handles the initial init request (no session ID, hashes empty string to a fixed worker) generates a session ID that may hash back to the OTHER worker for follow-up requests → 404 'Session not found'. `ip_hash` sidesteps this entirely — all requests from one client IP land on one worker, init and follow-ups always agree.
- **MCP 1.27 DNS-rebinding-protection blocker.** The deploy's `pip install -q -r` upgraded MCP to 1.27, which enables DNS rebinding protection by default with an empty `allowed_hosts` list (rejects every Host header). Fixed by configuring `TransportSecuritySettings(allowed_hosts=[...])` with the public hostname plus loopback aliases used by smoke tests.
- **Known limit (documented in dogfood/README.md):** `ip_hash` means multiple sessions from the SAME client IP all land on one worker. Cross-operator parallelism works; same-operator parallelism (firing 2+ sessions from one laptop) bottlenecks on one worker. Operationally fine for our 5–10-operator workload; the durable fix is **cooperative async yielding in heavy tools** (now Tier 3 backlog, not high priority).
- Verified end-to-end: HTTPS POST `/mcp` initialize returns 200 with session ID; 7 sequential follow-up requests with the session ID all 200. Both workers responding on their ports.

## Tier 1: argumentless `fetch_task_brief` with auto-dispatch (2026-04-25)

`fetch_task_brief()` (no `task_id`, default `variant="thin"`) atomically picks the staleest matching task — smallest `last_dispatched_at`, NULLs winning, ties broken by `task_id` — bumps `last_dispatched_at` to now under `BEGIN IMMEDIATE`, and serves the brief. Simultaneous parallel callers within seconds get DIFFERENT tasks (round-robin coverage). The operator's kickoff collapses to one universal line: `Call fetch_task_brief(), then follow its instructions.` Direct mode (explicit `task_id`) preserved for back-compat.

- New `last_dispatched_at` column on `dogfood_tasks` (migration-safe, NULL = never dispatched).
- `db.pick_and_dispatch_dogfood_task(variant)` does atomic SELECT-then-UPDATE under SQLite's default locking via `BEGIN IMMEDIATE`.
- Edge cases: no tasks seeded → error with setup hint. All tasks filtered out by variant → error with `available_variants` list.
- `dogfood/README.md` now recommends the universal kickoff.

## Two-phase dogfood + structured reflection on `submit_feedback` (2026-04-25)

Five thin briefs rewritten as two-phase (thin build with prep checklist → submit_feedback phase=1 → reach extension via REACH EXTENSION meta-tactics → submit_feedback phase=2 with structured reflection). Informed-variant briefs retired (5 .md files removed; `scripts/retire_informed_tasks.py` cleared the matching DB rows).

- **`submit_feedback` schema additions** (all optional, backwards-compatible): `phase` (1/2), `prep_calls_made` (phase-1 retrospective accountability for the prep checklist), `prep_calls_skipped` (phase-2 reflection on phase-1 prep gaps), `phase_1_misses` (list of `{pattern, guidance_that_would_help}` dicts — class-level patterns, not literal article titles per the privacy invariant), `phase_1_confidence_recalibration` (delta between phase-1 self-rated confidence and retrospectively-true confidence after seeing phase-2 finds).
- **Server-instructions update:** new FREE VS METERED TOOLS principle (free preparatory tools cost no API quota — spend liberally) + new REACH EXTENSION section (cross-language sweeps, eponym chains, niche-example probes, ask-the-user reach probes, diminishing-returns budget framing).
- **Validation:** three two-phase runs landed 2026-04-25. Calibration deltas reproduced consistently at −0.03 to −0.07. The orchids dogfood demonstrated the flywheel concretely — the AI applied the source-trust principle from the orchids exemplar to recover articles it had over-pruned in phase 1.

## Ship 2: exemplar tools + 5 worked-example exemplars (2026-04-25)

Two new MCP tools — `list_exemplars(topic)` and `get_exemplar(slug, topic, allow_own=False)` — plus 5 authored exemplars under `dogfood/exemplars/<slug>.md`, plus a preparatory-phase posture in `server_instructions.md` that makes consulting them a checklist the AI checks off rather than a hint it routes around.

- **Schema:** `dogfood_exemplars` table (slug UNIQUE, title, shape, body_markdown, last_validated_against, metadata_json). `scripts/seed_dogfood_exemplars.py` mirrors the task-brief seed pattern. `scripts/scp_exemplars.sh` + `scripts/scp_tasks.sh` keep deploys hand-roll-free.
- **`list_exemplars(topic)`** returns the menu-card section of every exemplar EXCEPT the one matching the caller's topic slug (measurement-integrity gate). Includes a static off-shape framing line so the AI doesn't over-anchor when no shape match is close.
- **`get_exemplar(slug, topic, allow_own=False)`** returns the full case study. Refuses self-fetch unless `allow_own=True` — phase-2 unlocks this; phase-1 must not.
- **Menu-card schema** (validated by a fresh-agent pressure-test before locking): structured shape axes (`structural`, `scale` order-of-magnitude buckets, `layered_shape` sub-typed `single` / `concentric` / `core+periphery` / `taxonomy+cultural`, `non-Anglosphere depth`, `biography density`, `canonical category coverage`, `recall_ceiling_driver`) + required "Doesn't apply when" counter-examples + 2–3 high-leverage move teasers + headline numbers + 2–3 sentence summary. Pressure-test: 4 unseen test topics matched expected exemplar at high confidence.
- **Server-instructions PREPARATORY PHASE checklist:** `list_exemplars` → `get_exemplar` on 1–2 most-relevant → compare to rubric → sketch strategy. AI follows phase-level structure well; sub-step short-circuits don't, so the checklist is numbered and explicit.
- **Brief restructure:** all 5 thin briefs reference the prep checklist + the phase-2 unlock path (`get_exemplar(slug=<own>, allow_own=True)`).
- **Runtime metadata field** `runtime: {agent, model, effort}` on `submit_feedback` so we can trend results across claude-code-opus-4.7 vs codex-gpt-5 vs different effort levels. Was filename-only before. Briefs ask the AI to populate from self-knowledge.
- **Deferred:** full case studies for the 4 sibling exemplars (orchids has full; the rest are menu-card stubs). The crispr Codex run flagged this as `tool_friction: "own_exemplar_full_case_study_empty"` — real signal that authoring the rest is value, not polish.

## climate-change benchmark + dogfood task + exemplar (2026-04-25)

The project's origin topic — climate change was the test subject for the 2026-04-16 development phase that produced the project's load-bearing design principles (LLM-as-quality-gate, centrality-not-binary, periphery-edge-browsing, multi-strategy gather; see `docs/development-narrative.md`). The original build, executed via standalone Python scripts before the MCP server existed, reached 5,349 articles. This addition reproduces it through the current MCP tool surface and lands it as a full benchmark + brief + exemplar.

- **Build (autonomous, MCP-server end-to-end):** 6,562 articles at 32% multi-source triangulation, 83 tool calls / 2,476 API calls / ~17 min wall, AI self-rating 8 / coverage 0.85. Strategies fired: WikiProject Climate change (4,453), depth-3 category sweep with chemistry-drift branches pruned (+1,402 net new), 7 list/index/glossary/outline harvests (+~700), CirrusSearch intitle/morelike (+~400), Wikidata P31/P101/P106 probes (+~140), edge-browse from periphery seeds (+72). Cleanup: redirect-resolution merged 436 dupes, filter dropped 256 disambig/list/meta, 42 Toyota-vehicle pattern, 70 "Geography of [country]" pattern, 18 hand-rejects. Exceeded the original 5,349-article build by ~1,200 via WikiProject + Wikidata-property + edge-browse layers the original couldn't reach.

- **Benchmark scaffold:** `benchmarks/climate-change/{scope.md, rubric.txt, README.md, baseline.json, audit.py, runs/}` committed; `gold.csv` + `audit_summary.md` + `audit_notes.md` gitignored. First-pass keyword classifier landed 1,770 IN / 4,276 PERIPHERAL / 435 OUT / 81 uncertain (~1.2% uncertain — manageable for human follow-up). Sample-precision audit pending. `audit.py` follows the orchids source-trust pattern with chemistry-drift / Toyota / Geography / fluorocarbon-refrigerant exclusions, plus a noise-channel-gated geography-OUT rule that protects WikiProject-tagged articles from over-classification (Antarctica, the Africa Initiatives, etc.).

- **Dogfood task brief:** `dogfood/tasks/climate-change-thin.md` follows the standard two-phase protocol; seeded into `dogfood_tasks` DB.

- **Exemplar:** `dogfood/exemplars/climate-change.md` — full case study (391 lines), grounded in the actual run. Shape axes: well-organized public-policy + science + movement, scale "thousands," `layered_shape: multi-layered` (science core + institutions + movement + regional + mitigation tech + cultural tail), high non-Anglosphere depth, medium biography density, high canonical category coverage. Recall-ceiling driver: cross-wiki periphery + PetScan-style category∩template intersection (both unexploited in baseline). Seeded into `dogfood_exemplars` DB.

- **Doc updates:** `docs/adding-exemplars.md` written as the recipe for future additions (covers shape-only exemplar / brief-only / full benchmark paths). `benchmarks/README.md`, `docs/ratchet-plan.md`, and `CLAUDE.md` updated to drop the fixed-five framing — suite size isn't sacred; new shapes get added when worth measuring.

- **Ratchet inclusion:** deferred. Adds a "well-organized academic + movement" shape the existing five don't cover, but the per-cycle cost is meaningful (~2,500 API calls). Decision lives in operator hands per the rubric in `docs/adding-exemplars.md`.

## Three follow-ups from the 2026-04-27 ChatGPT apollo-11 dogfood (2026-04-27)

Three items derived from analyzing the autonomous ChatGPT run on
apollo-11-thin (32 tool calls, 255-article corpus, ratings 7/8) — see
the dogfood synthesis in conversation logs around 2026-04-27.

### `audit_progress` strategy detection: per-call navbox attribution

The Apollo 11 run called `harvest_navbox` four times — `Apollo11series`,
`Apollo program`, `Lunar landers`, `Moon spacecraft` — and the AI
correctly executed both founder-cascade AND parent-program-navbox
moves. But `_TOOL_TO_MOVE` mapped `harvest_navbox` to a single
strategy (`founder-navbox-cascade`), so `audit_progress` 11 minutes
later listed `parent-program-navbox` as unused-but-applicable, when
it had actually been done.

Fix: `_TOOL_TO_MOVE` now accepts callable values
`(entry, topic_name) → list[str]`. `harvest_navbox` uses a callable
that picks `founder-navbox-cascade` when the template name contains
the topic stem (Apollo11series → "apollo" + "11" both present),
`parent-program-navbox` otherwise (Apollo program, Lunar landers).
The variant-tail tokens (`-thin`, `-informed`, `-efficiency`) are
stripped from the stem so benchmark templates don't carry the variant
into the match. Loop in `_topic_strategy_summary` updated to handle
both string and callable values.

### `topic_diff(topic_a, topic_b)` — same-wiki two-topic comparison

Multi-session evidence (4 sessions across AA-STEM, orchids,
climate-change, and the apollo-11 ChatGPT run, all asking for some
form of cross-topic comparison primitive). Ships the corpus-diff
variant: partition the union of two ingested topics' titles into
`only_a` / `only_b` / `both`, with counts + alphabetical samples per
bucket. `by_source=True` adds an `only_a_by_source` map showing which
sources contributed each title that's in A but not B — useful for
ratchet "where did the extra 200 titles come from?" diagnostics.

Read-only DB query (set partition on `articles.title`); ACL-aware via
`_require_topic(mode='read')` for both topics. Same-wiki not
enforced — AI is responsible for not diffing across wikis (a cross-
wiki diff would treat translated titles as different).

The at-pull-time intersection variant (cat × WikiProject without
ingesting all of WP) — what the apollo-11 run actually wanted — is
NOT shipped here; tracked as a sub-item in the same backlog entry.

### `submit_feedback` confabulation crosscheck against `usage.jsonl`

Measurement-integrity item. The Apollo 11 ChatGPT feedback claimed
`wikidata_property` as a strategy used in BOTH phases,
`strategy_execution.moves_succeeded` listed `wikidata-property-probe-
additive`, `sharp_edges_hit` included `wikidata_filtered_entity_call_
blocked` and `filter_articles_refusal`, and an `add_articles` note
described "committing enwiki sitelinks from phase-2 Wikidata
P361=Q43653…" — but the usage log shows zero `wikidata_*` calls and
the one `filter_articles` call succeeded. The AI fabricated the
sitelinks from internal knowledge and reported them as if a tool call
had happened. Same run also fabricated a "Developer-directed" framing
in 19 of 32 call notes — it was a fully-autonomous run with zero
operator direction.

Implementation:
- New mapping tables: `_STRATEGY_FAMILY_EVIDENCE`
  (`{family_tag: [tool_names]}`) and `_SHARP_EDGE_EVIDENCE`
  (`{edge_name: {tools, result_pattern}}`). Conservative coverage —
  judgment-shaped sharp-edges (`shortdesc_misleading`, `list_page_noise`)
  are intentionally NOT mapped, so they're never flagged.
- New helper `_observed_signals_from_log(topic_name)` returns
  `{tool_call_counts, tool_call_results}` for the topic.
- `_compute_confabulation_flags(strategies_used, sharp_edges_hit,
  prep_calls_made, observed)` returns structured flag dicts
  `{field, claim, expected_evidence, observed}`.
- `submit_feedback` runs the crosscheck after entry construction;
  persists `confabulation_flags` on the record (when non-empty);
  surfaces a "⚠ Cross-checks against usage.jsonl flagged N self-report
  mismatches" block in the response with the first 6 flags as
  bullets.
- Mental ops on `prep_calls_made` (`rubric_reread`, `strategy_sketch`,
  `scope_review`, `rubric_redraft`) are unverifiable and never flagged.

Verified by replaying the apollo-11 ChatGPT confabulation: produces
exactly the 8 expected flags (3 strategies, 2 edges, 3 prep calls);
no false positives on corroborated strategies (`navbox`,
`category_crawl`, `list_harvest`, etc.) or judgment edges
(`broad_navbox_overpull`, `list_page_noise`, `shortdesc_misleading`).

`tool_friction` not yet crosschecked — value strings are too
unstructured for a clean predicate table; deferred as a Tier 2
follow-up.

## Pagination for `get_article_links` / `get_article_backlinks` (2026-04-26)

Tier 1 backlog item. Both seed-mining tools previously stopped at
`limit` items and dropped a one-shot `truncated` flag; on prominent
articles (Apollo 11 has 1000+ links and ~15K backlinks) there was no
way to walk past the first window. Fix: added an opaque
`continue_token` round-trip. The tool now caps `pllimit` / `bllimit`
per API page at `min(limit, 500)` so it stops on a clean page
boundary, captures `data['continue']` at the truncation point,
JSON-encodes it as the response's `continue_token`, and accepts that
token back as a parameter to resume on the next call. Updated tool
docstrings (FastMCP schema) AND the COMMON TASK → TOOL row in
`server_instructions.md` so ChatGPT clients with cached schemas
still learn about the new param via session-init instructions.

## Exemplar integrity gate fix — slug-normalization leak (2026-04-26)

Surfaced mid-run in the 2026-04-26 apollo-11 dogfood: the AI saw an
`apollo-11` card in `list_exemplars` while running the apollo-11
benchmark and recognized it as a measurement-integrity leak the gate
should have caught. Root cause: `_slugify` doesn't fold hyphens, so
templated run-topic names like `apollo-11-thin 20260426T0123` slugify
to `apollo-11-thin_20260426t0123` and never equal exemplar slug
`apollo-11` under exact match. Fix: new `_topic_matches_exemplar`
helper that accepts exact match plus prefix-followed-by-`-`-or-`_`,
applied in both `list_exemplars` (filter) and `get_exemplar` (gate).
Commit `c4e70d0`.

## Composable strategy guidance — Ships 1 + 2 + 3 (2026-04-26)

Three sequenced ships landing the decompositional strategy layer
designed in `docs/backlog/composable-strategy-guidance.md`.
Subsumes 2026-04-24-proposed items A (force-shape-first-move),
B (calibrate-vs-signals), C (shape-typed wrap-up checklist),
D (surface triangulation).

### Ship 1 — info architecture, no server feature work

- **`mcp_server/shape_axes.md`** (new, 17k chars) — canonical 8-axis
  vocabulary used across exemplars, moves, failure modes, and
  calibration. Per Sage's reframe, the `recall_ceiling_drivers`
  axis is multi-valued + open-ended + AI-perceived (not a closed
  enum), with 10 anchor names but explicit invitation to name
  novel drivers including out-of-tool strategies.
- **`mcp_server/strategy_moves.md`** (new, 26k chars) — 27 named
  atomic strategy moves in 6 phases (recon, bulk gather, reach,
  similarity, cleanup, audit). Each move has preconditions keyed
  to shape axes, sequence, expected yield + noise, rescue.
  Authored by synthesis from existing dogfood notes (orchids
  exemplar + 2026-04-23 run-2 + 2026-04-24 thin-variant +
  2026-04-25 nine-topic survey + SHAPE→PROPERTY table); every
  entry maps to at least one observed case.
- **`mcp_server/failure_modes.md`** (new, 22k chars) — 19 named
  anti-patterns in 6 groups (topic-shape modeling, source-trust,
  identity collisions, tool misuse, workflow/state, metacognitive).
  Same authoring principle: every entry grounded in observed
  evidence.
- **`mcp_server/server_instructions.md`** (restructured, 50k → 55k)
  — 13 thematic `##` section headers replacing the single
  IMPORTANT GUIDELINES blob; SHAPE→WIKIDATA PROPERTY table
  replaced with shape→moves index pointer; PREPARATORY PHASE
  expanded to include topic-profile commit + move catalog browse
  + failure-mode forecast; KNOWN SHARP EDGES preamble
  cross-references the failure-mode catalog.
- **`mcp_server/server.py`** — `_load_instructions()` reads the
  three companion files at startup and concatenates with
  `# Companion: <path>` separators so production MCP clients see
  the catalogs in the instructions stream rather than as dead
  file references. `mcp_server/deploy.sh` updated to bundle the
  companion files.

### Ship 2 — active scaffolding

- **`set_topic_rubric` accepts `topic_profile: dict`** — the AI
  commits its axis profile at the natural commit point; response
  returns `applicable_moves` (catalog moves whose preconditions
  match), `relevant_failure_modes`, `recommended_first_move` with
  rationale, and `recall_ceiling_estimate` echoing AI-named
  drivers. Powered by `_strategy_recommendations(profile)` helper
  with explicit if/elif rules; back-compat preserved (omitting
  `topic_profile` returns today's response).
- **`describe_topic` adds 6 synthetic signals**: `triangulation_pct`
  (always), `top_single_source_contributors` (always), full
  `redirect_collapse` block from persisted metadata, full
  `strategy_execution` block (`shape_strategies_attempted` from
  `_TOOL_TO_MOVE` map of 24 tools, `shape_strategies_unused_but_applicable`
  when profile is committed, `yield_last_n_calls` with
  rising/plateau/declining/exhausted classifier requiring ≥4 samples).
- **New `audit_progress(topic)` MCP tool** — read-only synthesis
  of corpus state + usage log + catalogs into:
  attempted_moves / unused_but_applicable / detected_failure_modes
  (best-effort scanner covering ~8 of 19 catalog entries) /
  yield_last_n_calls / one-paragraph recommendation. Cheap (~40ms,
  zero API calls). Recommended pre-export gate; mid-build pivot
  signal when yield trends declining.
- **DB**: `metadata_json` column on topics with auto-migration;
  `db.get_topic_metadata` / `db.update_topic_metadata` helpers.
  `set_topic_rubric` persists profile; `resolve_redirects` writes
  `last_redirect_collapse_pct` + timestamp + pre/post counts on
  committed runs.

### Ship 3 — decomposed calibration

- **`submit_feedback` server-derives calibration band** —
  `_compute_calibration_signals(topic_id, topic_name, spot_check)`
  pulls triangulation_pct, attempted/applicable counts,
  spot_check_hit_rate, redirect_collapse_rate, yield_trajectory
  from corpus state + usage log + persisted metadata.
  `_calibration_band(signals)` maps to low/moderate/high with
  explicit thresholds (triangulation < 20% OR coverage < 50% →
  low; ≥40% AND ≥75% AND not rising → high; else moderate;
  tiny-corpus override skips triangulation rule for <50 articles).
- **`coverage_estimate` accepts both old and new shapes**.
  Old `{confidence, rationale, remaining_strategies}` works
  unchanged; new `{ai_override, ai_override_rationale,
  remaining_strategies}` is preferred and lets the AI override
  the band-derived estimate while the override is captured
  separately for trend analysis. Server response surfaces the
  band + rationale + flags AI/server disagreement at submit time.
- **New `strategy_execution` field on `submit_feedback`** —
  AI supplies `moves_attempted` / `moves_succeeded` /
  `moves_skipped_reason` / `failure_modes_observed`; server
  auto-augments with `moves_observed_from_log` (from the
  `_TOOL_TO_MOVE` map). Both stored for cross-reference; intent
  vs observation comparison is itself a signal.
- **`scripts/analyze_calibration.py`** (new) — post-hoc analysis
  joining feedback records (with band + signals) to gold-derived
  recall (where benchmarks exist). Tabulates band vs actual
  recall + per-band summary; surfaces residual error against the
  band-derivation thresholds. Reuses `benchmark_score.py`'s
  `load_env` / `ssh_cmd` / `fetch_run_state`. The empirical input
  for tuning the band thresholds; threshold values in
  `_calibration_band` are explicit constants, tuned by residuals
  not intuition.

### Validation

- **Ship 1 validation** (2026-04-25, before Ships 2+3): Brutalist
  architecture build (841 articles, 12% triangulation). Confirmed
  prep checklist works as a felt experience; mid-build profile
  correction triggered cleanly when canonical_navbox=True profile
  forecast was wrong (no Template:Brutalist architecture). Two
  catalog refinements landed from this run:
  `lossy-redirect-bio-to-non-bio` generalized to
  `lossy-redirect-target-meaning-divergence`; `wp-intersect-category`
  got a small-canonical-category caveat.
- **Ships 2–3 validation** (2026-04-26): on-host smoke against
  the validated Brutalist topic. `audit_progress` correctly
  flagged `cross-wiki-gap-probe-lightweight` as
  unused-but-applicable (matching the recall-ceiling driver named
  pre-build) and named `wp-broader-than-topic` failure mode from
  the profile's `dedicated_wp=broader-only` declaration.
  `submit_feedback` band derivation: triangulation 12% → "low" with
  rationale "triangulation 12.2% < 20% threshold."
  Empirical end-to-end validation against an actual benchmark
  (apollo-11 thin-variant) is the next test; `analyze_calibration.py`
  will tabulate band vs gold-derived recall once that lands.

### Known limitations / follow-ups

- **Failure-mode auto-detection covers ~8 of 19 catalog entries.**
  The rest need human judgement (eponym collisions, ambiguous
  namesakes, adversarial categories without explicit profile flag,
  list-page prose contamination, etc.). Catalog stays
  authoritative; the scanner is a fast filter.
- **Tool→move mapping is coarse** in `_TOOL_TO_MOVE`:
  `harvest_navbox` always maps to `founder-navbox-cascade`, never
  `parent-program-navbox`, even though Apollo-shape calls would
  be the latter. Disambiguating requires parsing the template-name
  parameter from the log entry.
- **Recommendation logic is hardcoded if/elif rules**, not
  catalog-parsed preconditions. Adding a move to
  `strategy_moves.md` requires also adding a rule in
  `_strategy_recommendations`. Maintenance discipline issue.
- **Pre-Ship-2 topics** built before today won't have
  `last_redirect_collapse_pct` populated until a fresh
  `resolve_redirects` fires. Degrades to null cleanly; no
  retroactive backfill needed.
- **`yield_last_n_calls.trend` requires ≥4 samples** before it
  classifies; tiny topics show "unknown" until enough corpus-
  affecting calls have fired.
- **Axis vocabulary doesn't distinguish topic-own-navbox vs
  parent-program-navbox.** For Apollo-shape topics with
  `canonical_navbox=True`, the recommended first move is
  `parent-program-navbox`, but that move's rationale assumes a
  parent program exists. Tweak for v2: add a
  `parent_program_navbox_exists` sub-flag.

## Ratchet gate logic — quality-first, cost as tiebreaker (2026-04-25)

Earlier formulation ("must improve at least one cost metric without regressing quality") punished runs that legitimately improved recall at higher cost. CRISPR (52 → 92.5% recall) and orchids (50 → 96.9% recall) failed the gate despite being clear product wins. Wrong incentive. New formulation:

A run **passes** if EITHER:
1. **Quality up** — at least one of `precision` / `recall` strictly improves AND neither regresses (within ±0.5pp tolerance), OR
2. **Efficiency up** — neither quality axis regresses AND at least one of `api_calls` / `tool_calls` strictly improves.

Cost is the bonus axis when quality holds, NOT a co-equal hurdle. Verdict text in `format_scoreboard` updated to surface which clause triggered (or which conditions failed). Tolerance moved from 0.001 (0.1pp) to 0.005 (0.5pp) for noise.

CRISPR + orchids baselines reset to the 2026-04-25 two-phase runs (354/91%/92.5% and 7138/100%/97% respectively); apollo-11 baseline left as-is (regressed precision; gate-fail is honest there).

## Auth Phase 1 + 2 cutover (2026-04-27)

End-to-end Wikimedia OAuth-based authentication shipped after a one-day cutover sprint. Retires the design plan that previously lived at `docs/backlog/auth.md` — Phases 0/1/2 all landed; Phase 3 (`AUTH_ENFORCEMENT=all` + read-mode wiring) and Phase 4 polish remain as one-line backlog entries.

**OAuth flow** (`mcp_server/oauth.py`, mounted on the FastMCP Starlette app at `/oauth/login`, `/oauth/start`, `/oauth/callback`, `/oauth/revoke`):

- Wikimedia OAuth 2.0 consumer registered on Meta-Wiki (confidential client, authorization-code grant only). Auto-approved.
- User visits `/oauth/login` → approves at meta.wikimedia.org → `/oauth/callback` exchanges code for a Wikimedia access_token, fetches the username via the userinfo endpoint, and discards the access_token. Server mints a `tb_<32 hex>` bearer token (`secrets.token_hex`), stores SHA-256 hash in `auth_tokens`, and shows the raw value once on a token-display page. User pastes the line into chat.
- **User-Agent fix**: Wikimedia's WAF (T400119) was blocking the default `Python-urllib/3.x` UA on the token + profile endpoints — both calls now send `WikipediaTopicBuilder/1.0`. The opaque "HTTP 4xx Forbidden" failure mode is also fixed: `_exchange_code` reads the OAuth 2.0 error_body so failures surface the real error code (`invalid_client`, `unauthorized_client`, etc.) instead of just the status line.

**Token model** (`db.py`):

- 30-day **sliding TTL**: `lookup_auth_token` slides `expires_at` to "now + 30 days" on every successful lookup (RETURNING-based, host SQLite is 3.46.1). Active users never re-auth; abandoned tokens die naturally. Rationale: our `tb_` tokens authenticate only against this server (no Wikimedia-side privileges), so the only security property expiry buys is leak hygiene against abandoned-but-leaked tokens — sliding gives that without periodic friction.
- Self-revoke via new `revoke_my_token(token)` MCP tool (also reachable via `/oauth/revoke` POST form on the token-display page).
- Tokens are SHA-256 hashed at rest. A leaked DB doesn't yield active tokens.

**Three-tier visibility model** (per-topic):

- `private` (default), `public_read` (anyone reads, owner writes), `public_edit` (anyone authenticated reads + writes). Per-topic `owner_username` + `visibility` columns on `topics`. Permission rules in `_can_read` / `_can_write`; integration via `_require_topic_with_access`. New tools `set_topic_visibility(visibility)` and `get_topic_visibility()`.

**Enforcement** (env-flagged):

- `AUTH_ENFORCEMENT=none` — legacy default, no checks (back-compat).
- `AUTH_ENFORCEMENT=writes` — mutations require auth + ownership; reads stay open. **Production state.**
- `AUTH_ENFORCEMENT=all` — both reads and writes gated. Available; deferred to Phase 3.

**Migration of legacy topics**: on every boot, if `MIGRATION_DEFAULT_OWNER` is set, `db.init_db` backfills any topic with NULL `owner_username` to that value (idempotent). At cutover, all 66 existing topics got `owner_username='Sage (Wiki Ed)'`, `visibility=private`.

**AI-facing instructions** (`server_instructions.md` AUTHENTICATION & CROSS-SESSION TOKENS section):

- Differentiates **stateful** (Claude — call `authenticate()` once; session caches identity) vs **stateless** (ChatGPT — opens a fresh session per tool call; pass `auth_token=` directly on every call). The "when unsure, just pass `auth_token=` per call" closer is a safe default that works for both.
- Tells the AI to check long-term memory for a saved token before prompting; offer to save on first authenticate; revoke on logout intent.
- Always direct the user to the **full** `/oauth/login` URL — ChatGPT reproduces bare paths verbatim and leaves the user without a clickable link.

**Landing-page rewrite** (`landing.html`):

- New "Sign in" section with the chat-side OAuth flow.
- New "Getting a more complete topic" section: five high-leverage user moments (push back during scoping; don't accept first "looks done"; run complementary strategies; spot-check before exporting; bring domain expertise to edges) plus a closer noting the built-in strategy menu isn't a fence.
- Hero tagline: "No authentication required" → "Sign in with your Wikimedia account to build."
- Four connector-config blurbs clarify "auth in chat, not connector."
- Five new auth tools added to the tools-grid (`authenticate`, `whoami`, `revoke_my_token`, `get_topic_visibility`, `set_topic_visibility`).

**Operational hardening** (post-cutover, after a same-day incident):

- `/etc/topic-builder.env` (the production credentials file) is marked operator-owned. AI is denied any Bash command that names it via `.claude/settings.json` (deny pattern matches the local Bash command string before SSH wraps it). `CLAUDE.md` documents the policy and what AI does instead: propose lines for the operator to add; verify via `/proc/<pid>/environ` (loadable through `bash scripts/smoke.sh`) or observable side effects (HTTP responses, DB state). Triggered by a redundant `cat` that printed the OAuth client secret into a transcript; secret was rotated. The deny rule is self-applicable — committing this very change required routing the message through a file because the path appears multiple times in the body.
- `.gitignore` switched from `.claude/` (whole dir) to `.claude/*` + `!.claude/settings.json`, so the project-level deny rule is committed and shared per Claude Code's own convention.

**Commits**: `51a2e72` (Auth Phase 2: enforce writes, sliding TTL, landing-page rewrite); `5c7da40` (operator-owned guardrails).

## Three picks from the 2026-04-27 strategy brainstorm (2026-04-28)

Three Tier 1 items from `docs/backlog/strategy-brainstorm.md` —
"in-retrospect-obvious" topic-discovery directions sister to the
recent `seed-anchored-mining-from-canonical-article` ship. The shared
theme: read the article harder, use Cirrus operators we've been
ignoring, and let the AI's own training data generate candidates that
tools then verify.

### `get_article_see_also` — read the editor-curated semantic neighborhood

New MCP tool. Two cheap action-API calls (`parse&prop=sections` to
find the section index, then `parse&prop=links&section=N` for that
section's mainspace links). Returns
`{section_present, count, see_also: [...]}`. Distinct from
`get_article_links` (which mixes See also entries with passing-mention
links from the body) and from `morelike:` (BM25 over the whole
article). Higher precision than either on niche topics where editor
curation is dense.

Default `section_name="See also"` matches enwiki convention; non-en
wikis pass the local equivalent (`Véase también`, `Siehe auch`,
`관련 항목`, etc.) — match is case-insensitive and trims whitespace.
Returns `section_present: false` cleanly when the article has no
matching section (Climate change is a real example — no See also).

Folded into the `seed-anchored-mining-from-canonical-article` move
in `strategy_moves.md` between the Wikidata probe and the
outgoing-link harvest, with revised yield estimates: see-also
~85-95% on curation-dense topics, vs. outgoing links 70-90%.
COMMON TASK → TOOL row in `server_instructions.md`. Landing-page
entry in `landing.html`.

Smoke against the deployed venv: Apollo 11 → 5 entries
(Apollo in Real Time, Exploration of the Moon, List of missions to
the Moon, ...); Phenomenology (philosophy) → 8 (Existentialism,
Hard problem of consciousness, Heterophenomenology, ...); Climate
change → 0 (no See also, handled cleanly); eswiki Apolo 11 with
`section_name="Véase también"` → 7. Production logs confirm 2 API
calls per success, ~250-700ms elapsed.

### `hastemplate-typed-probe` + `articletopic-classifier-probe` — Cirrus operators we've been ignoring

Two new strategy moves in `strategy_moves.md` Bulk gather section,
plus matching COMMON TASK → TOOL rows in `server_instructions.md`.
Pure documentation ship — the operators already work inside
`search_articles`; this surfaces them.

`hastemplate-typed-probe`: `hastemplate:"Infobox X"` finds every
article using a given template — the infobox registry is a free
typed-entity ontology editors maintain. `{{Infobox botanist}}` marks
every botanist; `{{Infobox spaceflight}}` every spaceflight.
Precision typically 90-99%; recall depends on template adoption.
Carries the existing compound-OR sharp-edge warning (split
`hastemplate:"A" OR hastemplate:"B"` into separate calls).

`articletopic-classifier-probe`: `articletopic:STEM.Physics.Astronomy`
filters to ORES topic-classifier categories — a free deterministic
ML topic-tag layer we hadn't probed. Best as a *coarse filter* on a
noisy probe (`morelike:"<seed>" articletopic:STEM.Physics`) more
than as a primary gather. Full taxonomy at
`mediawiki.org/wiki/ORES/Articletopic`. Coverage uneven (sparse on
stubs, historical figures, post-cutoff topics); treat as candidates
needing review, never as a subtractive filter.

### `llm-fabricate-and-verify` — AI as candidate generator, tools as verifier

New strategy move in `strategy_moves.md` Reach section. Inverts
today's posture (tools surface candidates → AI judges) into AI
fabricates → tools validate. The AI is trained on Wikipedia; for
sparse-canonical-surface topics (no dedicated WikiProject, sparse
categories, incomplete Wikidata, non-Anglosphere depth), the AI's
training-data recall often beats what structural tools surface.

Sequence: sketch 50-100 candidate titles grouped by subdomain →
PRE-VALIDATE via batched `preview_search(query='intitle:"<Title>"')`
→ commit verified hits with `source="llm-fabricate:<topic-stem>"` so
contribution is auditable → optional 2nd round asking "what category
of articles did I miss?" Cap rounds at 2-3 (diminishing returns).
Hallucination rate on unverified titles is 10-30%; pre-validation
drops it to ~0%.

Distinguished from the existing `niche-example-fabrication-spot-check`
move (wrap-up coverage probe, smaller N, structured by subdomain) by
mid-build timing and commit-orientation.

### What didn't ship from the brainstorm

The pageviews / WikiProject importance / sitelink-count cluster
(originally Top Picks #1, #2, #6 in the brainstorm) was deprioritized
per the CLAUDE.md "Centrality is AI judgment, not tool computation"
principle — the principle covers signal-surfacing tools too, not just
direct score-writers. Kept on the brainstorm menu for record-keeping;
revisit only on a multi-session signal pointing at one specifically.
Sister-project crosswalk and external-authority meta-tool stay on the
brainstorm menu as the strongest unpromoted entries.

## Sharp-edge / existing-tool improvement bundles (2026-04-28)

Three bundles of small, high-leverage edits to existing tool surfaces
+ AI-facing instructions, all driven by recent dogfood evidence
(climate-change exploratory id=71, orchids exploratory id=72,
cybersecurity 2026-04-27, apollo-11 ChatGPT 2026-04-27,
4-of-4 PREP short-circuits across 2026-04-28 runs). Sage approved
proceeding while flagging that costly fan-out shapes need a deliberate
review before more accumulate; that review is parked as
`memory/project_tool_cost_review.md`.

### Bundle A: tool surfaces

- **`preview_wikidata_property`** — titles-only sibling of
  `wikidata_entities_by_property`. Returns `{qid, title, sitelink_count}`
  per row, sorted by sitelink_count desc. Fits well under the MCP
  transport cap on properties with hundreds of entities (orchids
  P171=Q25308 with limit=500 was hard-erroring on the full-body
  variant). Tighter SPARQL drops `?itemLabel` and `?description`.
- **`harvest_list_page` / `preview_harvest_list_page` `annotate_types=`** —
  opt-in flag that runs a Wikidata-batched type resolution across all
  harvested titles and returns an `annotation_summary` histogram (and
  per-row `inferred_type` on preview). Vocabulary:
  `person / taxon / place / organization / work / concept / meta /
  other / unknown`. `unknown` covers both "no Wikidata page" and "no
  P31 statement" — never silently coerced. **Cost shape:** ~3-5
  batched API calls regardless of harvest size (one
  `fetch_wikidata_qids` paginated langlinks + one SPARQL `VALUES`
  query for all P31s, chunked at 500 QIDs). The per-title fan-out
  shape that would have cost 500 round-trips on a 500-row list was
  ruled out per Sage's pushback.
- **`get_articles_by_source` `prefix_match=` and `only_source=`** —
  diagnosed as docstring/semantics mismatch: example used family
  names like `"list_page"` but impl did exact-string match against
  full labels like `"list_page:Foo"`. Added `prefix_match` (mirror
  `remove_by_source`) and `only_source` for the "isolate to X only"
  intent the cybersecurity AI couldn't express. Default behavior
  unchanged for existing callers; docstring rewritten with concrete
  working examples.
- **`find_list_pages` `relax_disambiguation_filter=`** — opt-in flag
  to skip the title-must-contain-subject-token filter. Default False
  preserves precision; True surfaces sub-class lists (per-genus
  taxonomy lists, per-country geographic lists) that are the high-
  yield reach surface for cosmopolitan topics. Orchids exploratory
  found Western Australia's orchid list (25 net-new at ~95% precision)
  only after working around the default filter; the flag makes that
  the documented path.

### Bundle B: validators + directives

- **Confabulation crosscheck widening** — replaced the static
  `_STRATEGY_FAMILY_EVIDENCE` dict with a derived registry built from
  three sources: inversion of `_TOOL_TO_MOVE`, headings parsed from
  `strategy_moves.md`, and legacy short-tag aliases. Claim strings
  are normalized (`_normalize_claim`: lowercase + collapse non-
  alphanumerics) before lookup, so `wikiproject-recon`,
  `wikiproject_recon`, and `WikiProject Recon` all resolve to the
  same key. New `_UNCHECKABLE_MOVES` set marks
  cross-wiki-gap-probe-lightweight, parallel-wiki-build-and-walk-back,
  and judgment-shaped reflection moves as recognized-but-not-flagged.
  Added `spot_check.probes_count` crosscheck — claiming probes
  happened means at least one probe-shaped tool call (preview_search,
  preview_similar, search_articles, search_similar) must be in the
  topic's log. Replay results: cybersecurity 5→2 flags (the lone
  remaining strategy flag is a free-form ambiguous label; the
  spot_check confab is correctly surfaced); climate-change-
  exploratory 9→1 / 19→2 (only PREP-not-actually-called remains);
  orchids-exploratory 12→1 / 21→4 (PREP + 4 strategy names that ARE
  truly new — Bundle C catalog refinements add them).
- **`authenticate()` save-to-memory directive** — renamed
  `cross_session_persistence_tip` → `next_action_for_ai`; rephrased
  from permissive ("you can offer to save…") to imperative ("Ask the
  user, verbatim: 'Should I save this token to your long-term memory
  so future sessions can authenticate automatically?' Save only on
  explicit yes."). Tightened AUTHENTICATION rule 2 in
  `server_instructions.md` to spell out the verbatim prompt instead
  of saying "the response includes a phrasing tip."
- **PREP-checklist short-circuit fix** — three moves: (a) PREP
  section in `server_instructions.md` now uses imperative phrasing
  ("Run X. Do not skip; do not simulate.") with a new
  **Accountability** subsection explaining the rejection contract;
  (b) `submit_feedback` hard-rejects phase-1 submissions whose
  `prep_calls_made` claims tools that aren't in the topic's usage
  log — submission fails with a structured error listing the
  rejected claims; (c) docstring updated to make `prep_calls_made`
  cover any-time-in-history calls (mid-build PREP counts), not just
  pre-phase-1.

### Bundle C: catalog refinements (`strategy_moves.md`)

Driven by per-move yield/noise data from the 2026-04-28 climate-
change + orchids exploratory calibrations. Pure documentation;
deploy reloads via the FastMCP `instructions=` string at server
start.

- **`articletopic-classifier-probe` example syntax fixed** — replaced
  `articletopic:STEM.Physics.Astronomy` (dot-separated subtopics
  return zero on enwiki today) with the working broad-domain form
  `articletopic:biology orchid -incategory:Orchids`. Added
  precondition note: useful when canonical category coverage is
  fuzzy/incomplete; near-zero net-new on well-categorized topics.
- **`harvest_navbox`-related stanzas** (`founder-navbox-cascade`,
  `parent-program-navbox`) now warn that mature dedicated WikiProject
  coverage makes the move near-zero-net-new — climate-change run
  showed 0 of 225 net-new from the Global warming navbox against the
  4114-article WP corpus.
- **`llm-fabricate-and-verify` reframed as gap-detector** — preconditions
  expanded to ANY topic where structural moves have run; expected-
  yield section updated with the 30-50% novel net-new on well-curated
  topics (climate-change 31% gap-detect rate, orchids 51%). The
  "spot-check" framing was undercutting a strong gap-detector signal.
- **`auto-reject-by-disqualifying-shortdesc` warning** — added a
  new WARNING about single-word markers firing on canonical
  articles ("Climate change video game") and legit periphery (battery
  manufacturers, electric tractor manufacturers). Recommends phrase
  markers or paired markers, with mandatory dry-run.
- **New move `leads-confirm-disqualifying`** — sample-then-verify
  cleanup for noisy bulk sources where shortdescs are too thin.
  Generalizes the climate-change run's ad-hoc lead-fetch on Toyota-
  vehicle articles into a documented move.
- **New move `country-level-list-page-harvest`** — for topics with
  scale=large/huge AND geographic_distribution=cosmopolitan
  (taxonomy, ecological / cultural phenomena). Pairs with the new
  `find_list_pages(relax_disambiguation_filter=True)` flag (without
  which the move's input surface is hidden by default).
- **`morelike-from-cluster-anchor` split** — added two new stanzas
  with distinct preconditions and yield expectations:
  `morelike-from-niche-anchor` (~85-95% on-topic, precision-priority;
  orchids: Veitch Nurseries → 28/30 net-new) and
  `morelike-from-generic-cultural-anchor` (~50-60% on-topic, expect
  cultural-tail noise; orchids: Orchidelirium → 18/30 net-new but
  pulls Tulip mania, Bibliomania, Bookworm).
- **`peripheral-edge-browse` precondition refined** — now warns the
  move is near-useless on taxonomy-dominated topics where species
  sit on parallel-not-overlapping branches (orchids: 5 candidates
  from 5 periphery seeds, 4 near-noise).
- **`-incategory:` Cirrus single-level limitation documented** — note
  added to articletopic-classifier-probe (and referenced for sibling
  Cirrus-using moves): excludes only direct members of X, NOT
  subcategory members; no clean Cirrus form for "anywhere under X".
- **COMMON TASK row update** — taxonomy row now lists
  `country-level-list-page-harvest` for cosmopolitan distributions.

## Impact Visualizer handoff — TB side (2026-05-01)

First end-to-end alternative to the CSV-then-rake pipeline. New
`prepare_iv_handoff` + `publish_topic` MCP tools mint a `tbp_<...>`
handle that snapshots the article list (with centrality scores) plus
IV configuration into a frozen package row. New
`GET /packages/<handle>` Starlette endpoint serves the JSON snapshot
to Impact Visualizer (server-to-server; auth is handle
unguessability — the URL is a capability). Two-step flow: AI calls
`prepare_iv_handoff` to preview the would-be config + first 10
articles + centrality histogram, shows the user, then calls
`publish_topic` after confirmation. Returns an `import_url` (path-
segment style, `https://impact-visualizer.wmcloud.org/imports/<handle>`)
plus a one-sentence `user_instruction`.

- **DB:** new `iv_packages` table (handle PK, topic_id FK, config_json,
  articles_json, source_topic, publisher_user, created_at, consumed_at,
  expires_at, schema_version=1). 30-day TTL; `consumed_at` is set on
  the first `/packages/<handle>` fetch (multi-use; only the first
  records `consumed_first_time=true` in the JSONL log).
- **Helpers in `db.py`:** `mint_iv_handle`, `create_iv_package`,
  `get_iv_package`, `mark_iv_package_consumed`,
  `list_iv_packages_for_topic`, `cleanup_expired_iv_packages`,
  `append_package_event` (writes `${LOG_DIR}/packages.jsonl` parallel
  to `feedback.jsonl`).
- **Module:** new `mcp_server/iv_packages.py` registers
  `GET /packages/{handle}`. 404 protocol returns the same body for
  unknown / expired / bad-prefix; the reason rides on the JSONL log
  line, not the response (no enumeration distinction).
- **nginx:** new `location /packages/` block in `deploy.sh` proxies
  `/packages/*` to the worker pool with default timeouts.
- **Verification:** py_compile clean; local smoke (temp DB) +
  host-side smoke against production both pass — handle roundtrip,
  consumed-at idempotency, JSON shape, `packages.jsonl` line shape,
  unknown-handle 404.
- **Auth:** the new MCP tools use `mode='write'` on `_require_topic`,
  so under `AUTH_ENFORCEMENT=writes` only the topic owner (or
  public_edit-tier callers) can publish. The `/packages/<handle>`
  fetch is intentionally unauthenticated.
- **Frozen at publish time.** Edits to the topic after `publish_topic`
  do not propagate. Re-publish to mint a fresh handle. IV becomes
  source-of-truth post-import; future "atomic edits" tool
  (`patch_iv_topic`, deferred) would push targeted updates back to a
  live IV topic via IV's API rather than re-snapshot.

IV-side import UI ships separately (landed 2026-05-08; see next entry).

## Impact Visualizer handoff — IV side + first end-to-end (2026-05-08)

Closes the loop opened on 2026-05-01: a `tbp_<handle>` minted on TB
now imports cleanly into Impact Visualizer. Tracked from the IV side
in `impact-visualizer/docs/topic-builder-handoff-status.md`; the TB
spec doc at `docs/backlog/impact-visualizer.md` flips its IV-side
rows to ☑ shipped.

- **IV PR #55** — `GET /imports/<handle>` preview page,
  `POST /imports/<handle>` import handler (admin-gated, server-side
  re-fetches the package, hard-fails on `schema_version != 1`,
  resolves `wiki_id` from IV's own wikis table),
  `ArticleBagArticle.centrality` nullable column,
  `Topic.tb_handle` nullable column.
- **End-to-end run, 2026-05-08** — 6562-article climate-change topic
  imported from TB prod (topic-builder.wikiedu.org) into IV on
  wmcloud and wiki-ed prod. First feature run at production scale.
- **IV PR #56 (scaling support)** — parallelized
  `GenerateArticleAnalyticsJob` (3 threads), Wikimedia OAuth 2 bearer
  auth on Action + REST APIs, 429 retry jitter widened 0–0.5s → 0–3s,
  sequential analytics → incremental timepoint chain. Made the 6562-
  article run finish in a reasonable window; not strictly on the
  handoff spec but load-bearing for any topic of meaningful size.
- **IV branch `eager-load-article-timepoints`** —
  `TopicTimepointStatsService` N+1 fixes (eager-load
  `article_timepoint`, read `attributed_creator_id` directly, drop
  redundant `update_details_for_article`, memoize revision lookups,
  swap to `prop=contributors`).
- **IV branch `topic-article-analytics-nil-bag-fix`** —
  `TopicsController#topic_article_analytics` nil-bag guard (Sentry
  IMPACT-VISUALIZER-1K).

Open from the IV-side rollup, all tracked on the spec doc:
- TB → IV user list (TB doesn't emit users yet; IV's TB-topic UI
  hides the Users panel rather than carrying a placeholder).
- Schema-version bump path (IV hard-fails on `schema_version != 1`;
  coordination story needed before TB ships v2, likely paired with
  atomic edits).
- Non-admin (authenticated editor) imports — v1 is admin-only on
  POST; broadening is straightforward.
- Atomic edits (`patch_iv_topic`) — still deferred.

## PetScan compound-query primitive (2026-05-02)

General PetScan wrapper. Subsumes both the Tier-1 "at-pull-time
category × WikiProject intersection" item AND the Tier-3
"PetScan-style intersection" item — single tool surface, broader
leverage than either narrow primitive would have given.

- **Helper:** new `petscan_query(params, timeout=60) → (rows, meta)`
  in `wikipedia_api.py`. Reuses `api_get` so PetScan calls inherit
  User-Agent + rate-limit backoff + per-call counters. One PetScan
  call counts as one `wikipedia_api_calls` entry — fair from a
  network-cost POV even though one call substitutes for many
  MediaWiki round-trips. JSON envelope `data["*"][0]["a"]["*"]` is
  the row list; titles come underscored and are normalized via
  `normalize_title`.
- **MCP tool:** `petscan(params=…, psid=…, commit=False,
  source_label=…, max_results=10000, sample_size=20)`. Single tool
  with a commit flag — matches the smallest-primitive principle.
  `commit=False` returns count + sample for preview; `commit=True`
  requires explicit `source_label` (no auto-derivation; AI is the
  right judge of label) and writes mainspace results to the working
  list with the standard `_apply_rejections` + cost report + undo
  hint pattern. `psid` shortcut runs a saved PetScan query (e.g.,
  `psid=32906566` is the hispanic-latino-stem-us baseline).
- **Sharp edge documented:** `templates_yes` matches the article
  namespace by default. WikiProject tags live on talk pages, so the
  cat ∩ wp pattern requires `templates_use_talk_yes: "1"` paired
  with `templates_yes: "WikiProject <X>"`. The `projects[]` /
  `wpiu` form fields you'd guess at are silently ignored (verified
  via probe: bogus and real values both returned the unfiltered
  count). Documented in server_instructions.md sharp-edges section.
- **Strategy move:** new `category-intersect-wikiproject` in
  `strategy_moves.md` — the pull-time alternative to the existing
  `wp-intersect-category` (which ingests both sides as full topics
  before intersecting). Use the new move when the broader WP is
  too big to ingest (Spaceflight, Plants, Biography); use the
  existing move when both sides fit. Cross-references between the
  two.
- **Instructions update:** COMMON TASK → TOOL row for "compound
  category query / intersection of categories" now points at
  `petscan` instead of saying it's not yet built. GAP CHECK guidance
  shifted: PetScan-style compound queries move from "capture in
  missed_strategies" to "act on directly via petscan."
- **Surface:** new entry in `landing.html` Available tools section,
  positioned next to `wikidata_query` (the other compound-query
  primitive).
- **Verification:** two-stage smoke before implementation —
  `/tmp/probe_petscan.py` locked the JSON shape; `/tmp/probe_petscan2.py`
  disambiguated the WikiProject filter (proved `projects[]` was
  silently ignored, confirmed `templates_use_talk_yes=1` is the real
  primitive). Apollo 11 cat depth=0 ∩ talk:WikiProject Spaceflight
  returned 30 of 58 candidates — the high-confidence core the
  Apollo-11 ChatGPT autonomous run (2026-04-27) explicitly
  asked for.

Backlog items removed: Tier 1 "At-pull-time category × WikiProject
intersection" (multi-session signal from Apollo 11 + climate-change),
Tier 3 "PetScan-style intersection." Both subsumed by the general
wrapper.
