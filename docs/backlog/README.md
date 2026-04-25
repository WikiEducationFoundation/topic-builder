# Backlog — open items

Pending items from the improvements plan, grouped by priority tier.
Shipped items are logged in `../shipped.md`. `../ratchet-plan.md` is
the "what to work on next" entry point and draws its shortlist from
this doc.

Sibling docs in this directory hold larger plans (deferred or in review):
- `auth.md` — Wikipedia OAuth + paste-in-chat token flow.
- `impact-visualizer.md` — publish_topic handle → Impact Visualizer import.
- `exemplars-and-reach-pass.md` — `list_exemplars` + `get_exemplar` + `start_reach_pass` tools; two-phase dogfood (in review).

Add new items here as signals come in; promote items to
`../shipped.md` when they land.

**Status legend:** ☐ not started · ◐ in progress · ☑ shipped · ✗ dropped

**Tier meaning:**
- **Tier 1** — small, high-leverage; ship as a bundle when convenient.
- **Tier 2** — medium effort, multi-session-validated; ship individually.
- **Tier 3** — deferred / speculative; revisit after Tier 1–2 land or as specific signals confirm.
- Smaller one-liners that have been considered and deliberately deferred live at the bottom.

---

## Tier 1 — small, high-leverage

### ☐ Multi-worker MCP server with session-sticky nginx routing `[NEW — 2026-04-24 three observations; nginx-timeout half shipped]`

**Context.** Partial fix shipped 2026-04-24: nginx `proxy_read_timeout` + `proxy_send_timeout` bumped to 300s (from default 60s) on `/mcp`. This absorbed the 60s → 504 ceiling that was returning bursts of 504s to clients during 2–3 concurrent sessions. Remaining: the backend is still single-threaded-async, so heavy tool calls can still delay new handshakes by tens of seconds (18s observed) and serialize all concurrent sessions behind one coroutine. Below is the proper durable fix.

**What.** Run N Python processes (start N=2) on distinct ports behind nginx with session-header-based sticky routing:
1. **Systemd template unit** `topic-builder@.service` accepts `%i` as the port (8000, 8001). Enable both `topic-builder@8000` + `topic-builder@8001`. Each runs the current `python server.py` with a PORT env var.
2. **`server.py`** reads `PORT` from env (default 8000).
3. **nginx `upstream topic_builder_backend`** block with both 127.0.0.1:8000 + 127.0.0.1:8001 and `hash $http_mcp_session_id consistent;` directive — routes same-session requests to same worker.
4. **`/mcp` location** changes `proxy_pass http://127.0.0.1:8000` → `proxy_pass http://topic_builder_backend`.

Sticky routing is load-bearing: MCP's `StreamableHTTPSessionManager._server_instances` is an in-memory dict per-process, keyed by `mcp_session_id` header. Without header-based stickiness, a session started on worker A could have subsequent requests land on worker B, which would treat them as unknown session IDs and error.

**Why.** Even with the 300s nginx bump, heavy tool calls still delay incoming handshakes on the same worker. Two workers = two event loops = one busy session doesn't stall the other. Concrete evidence already in the feedback log: three of five 2026-04-24 thin runs flagged `*_504_transient` or `*_transport_timeout` in `tool_friction`.

**Shape.** Changes concentrated in `mcp_server/deploy.sh`:
- Rewrite the systemd block as a template (`[Service]` with `Environment=PORT=%i`, `WorkingDirectory=/opt/topic-builder/app`, `ExecStart=... server.py`).
- Enable + start both port instances.
- Rewrite the nginx server block to add an `upstream topic_builder_backend { server 127.0.0.1:8000; server 127.0.0.1:8001; hash $http_mcp_session_id consistent; }` — and change `proxy_pass` to that upstream.
- `server.py` already calls `mcp.run(transport="streamable-http")`; need to pass `port=int(os.environ.get("PORT", 8000))` — check FastMCP's `.run()` signature.

**Open questions.**
- Does the first request of a new session (no `Mcp-Session-Id` header yet) land predictably? With `hash` and empty header value, all new sessions hash to the same worker — imbalanced but harmless. Could add a second-level discriminator like `$request_id` for new sessions specifically. Defer unless load imbalance becomes visible.
- Module-global state in `wikipedia_api.py` (rate-limit counters, last-request timestamp) is per-worker now. Trivial: each worker rate-limits itself; the total rate-limit budget is effectively N× larger. Since we're nowhere near Wikipedia's ceiling and WMF servers see our aggregate anyway, this is fine.
- Per-session `_session_topics` dict in `server.py` is already per-process; with sticky routing, a session's state lives on one worker consistently.

**Sequencing.** Ship when no runs are active (requires Python restart, drops sessions). Monitor `usage.jsonl` and `nginx/error.log` for 504 frequency + handshake latency before/after.

### ☐ Argumentless `fetch_task_brief` with auto-dispatch `[NEW — 2026-04-24]`

**What.** `fetch_task_brief()` with no `task_id` auto-picks the task whose previous run is oldest and returns that one's brief. The operator's kickoff collapses from per-task `fetch_task_brief(task_id="apollo-11-thin")` to a single universal line:

```
Call fetch_task_brief(), then follow its instructions.
```

Simultaneous sessions (multiple agents calling within seconds) get DIFFERENT tasks — each call updates `last_dispatched_at` atomically on the selected task, so the next caller sees a different "oldest" and picks the next one in the round-robin.

**Why.** Operator ergonomics + parallelism scale-up. Firing 5 Codex sessions in quick succession should cover all 5 benchmarks with zero configuration; today the operator has to hand each session a distinct task_id. Also: auto-dispatch biases the ratchet toward covering under-exercised benchmarks over time (natural round-robin), which is what you want when the benchmarks should all be kept roughly fresh.

**Shape.**
- Schema: add `last_dispatched_at` column on `dogfood_tasks` (nullable; NULL = never dispatched).
- Optional follow-up: add `last_completed_at` column, populated when a `submit_feedback` matches a task's template. MVP can rely on `last_dispatched_at` alone (atomic-on-fetch is sufficient for race resistance and round-robin ordering; completed-vs-abandoned distinction is rare enough to defer).
- Tool change:
  - `fetch_task_brief(task_id: str | None = None, variant: str = "thin", ...)` — if `task_id` is None, pick the task with the smallest `last_dispatched_at` (NULL sorts first → never-dispatched tasks win). Filter by `variant` (default `thin` so the standard measurement mode is what auto-dispatch produces).
  - Selection + update must be atomic (single `UPDATE ... WHERE id = (SELECT id FROM ... ORDER BY last_dispatched_at LIMIT 1) RETURNING *` or equivalent transactional SELECT-then-UPDATE under SQLite's default locking).
  - Log the dispatch with task_id + staleness (`hours_since_last_dispatch`) so we can see in `usage.jsonl` whether round-robin is working.
- Ties (multiple never-dispatched tasks): break by `task_id` alphabetical for determinism.
- Edge cases:
  - No tasks seeded → error with setup hint.
  - All tasks filtered out by variant → error with list of available variants.
  - Existing `task_id` arg still honored (back-compat; direct mode stays).

**Open questions.**
- `variant` default: `thin` (ratchet-standard) vs. fully auto (pick any). Lean `thin` — the operator usually wants the measurement variant; `informed` is a deliberate choice.
- `last_completed_at` scoreboard wiring: nice-to-have. If included, completion recomputes run-topic match against the task's template regex, sets `last_completed_at = now` on match. Could live in a sibling `mark_completion` helper or get wired into `submit_feedback` when the topic name matches a known template. Defer; MVP uses dispatched-only.
- Capacity to fire >5 parallel sessions with 5 tasks: 6th call would get the first task re-dispatched with a <1-minute gap. Fine — tasks can be re-run that quickly with the `{ts}` templates producing unique topic names. If we want stricter "no duplicate active runs" we'd need a concept of live sessions, which is overkill for now.

**What.** Annotate harvested titles with a Wikidata-inferred type tag without filtering anything out by default. `harvest_list_page` (and `preview_harvest_list_page`) grow an optional `annotate_types=True` flag that, post-harvest, resolves P31 on each title via `fetch_wikidata_qids` + lookup, and returns `{title, inferred_type, confidence}` tuples. `inferred_type ∈ {person, plant, place, concept, ..., unknown}`; `unknown` is the explicit bucket for "no Wikidata P31 set" OR "Wikidata item doesn't exist" — never silently conflated with a positive type.

Convenience wrappers (`persons_only=True`, `exclude_persons=True`) can be added later, but they MUST document the limitation clearly in their docstrings: _"Keeps titles tagged `person`; DROPS titles tagged as other types AND titles tagged `unknown`. Wikidata coverage is incomplete — real persons with no Wikidata P31 will be dropped silently. Prefer `annotate_types=True` for surfacing-without-filtering semantics."_

**Why.** Two sessions in two days flagged the same friction:
- AA-STEM ratchet run (2026-04-23): "List-page discovery looked promising but the obvious pages were noisy enough that I did not trust a bulk harvest without a person-only extraction mode."
- Orchids ratchet run (2026-04-24): "Large species list pages, especially Dendrobium, leak unrelated biographies via eponym/name collisions."

Same shape complaint, orthogonal directions (biography lists leaking non-bios, taxonomy lists leaking bios). Type-hinted annotation solves both AS-A-SIGNAL without introducing the silent-drop risk of a hard filter.

**Shape.** Post-harvest step: `fetch_wikidata_qids` on all titles (already shipped), then per-QID lookup of P31 via `wikidata_query` (or cached batch resolution). Returns annotated tuples. Caller decides what to do — keep all, filter in code, feed to `remove_by_pattern`, or just eyeball.

**Why not `persons_only=True` as the primary shape.** Wikidata is incomplete (see `memory/feedback_wikidata_incomplete.md`). A real biography without Wikidata P31=Q5 would be silently dropped by a hard persons-only gate. The failure mode is indistinguishable from the tool working correctly, which is exactly the silent-drop shape we want to design away from. Annotation preserves optionality; filter-wrappers can be added on top with loud docstring warnings.

**Open questions.**
- Cost: QID-resolve step post-harvest adds API work on big list pages. Make annotation opt-in; preview-variant resolves only a sample.
- Type vocabulary: start narrow (`person` / `plant` / `place` / `organization` / `work` / `concept` / `unknown`) or expose raw QID chains? Start narrow; generalize when demand surfaces.

---

### ☐ Same-wiki topic diff / intersection primitive `[NEW — 2026-04-24 multi-session: AA-STEM + orchids]`

**What.** A `topic_diff(topic_a, topic_b)` or `topic_intersect(topic_a, topic_b)` tool for same-wiki topic comparison, returning set partitions (`only_a` / `only_b` / `both`). Distinct from the Tier 2 `cross_wiki_diff` (different wikis).

**Why.** Two multi-session wishes:
- AA-STEM (2026-04-23): "I felt the absence of an easy cross-topic intersect/diff against the AA medicine blocklist and the frozen baseline; that would have made cleanup and audit faster and more defensible." — wanting to compare `african-american-stem` against `AA STEM medicine blocklist` to surface likely-clinical-physician false positives.
- Orchids (2026-04-24): "A corpus-diff tool against another topic/source set (for example baseline topic vs current topic, or category/list harvest vs Wikidata sitelinks) would also make gap and noise review much faster." — wanting to compare ratchet-run corpus against the frozen baseline corpus to surface exactly the additions and removals.

Second use case is especially useful as a ratchet diagnostic: the scoring script shows metrics, but a human-readable "here are the 456 titles this run added that baseline didn't have" is more auditable than a percentage.

**Shape.** Read-only SQL over `articles` table scoped to two topic IDs. Partition into three buckets. Return counts + optional per-bucket sample. May want a `by_source=True` mode that surfaces which sources contribute to each bucket.

**Sequencing note.** Simpler than `cross_wiki_diff` (no langlinks / Wikidata roundtrips needed). Could ship standalone. If it proves useful, the cross-wiki case could become a wrapper that normalizes topics-on-different-wikis to QIDs first and then calls this.

---

### ☐ Benchmark system polish (6 sub-items) `[NEW — 2026-04-23]`

Bundle of small changes around the benchmark / ratchet system now that `fetch_task_brief` + thin variants exist and today's fat-variant runs exposed baseline-quality issues. Sub-items are independently ship-able but share sequencing constraints (see below). Each ships as its own commit.

**Sequencing.**
- **1.a MUST ship first.** ☑ shipped 2026-04-24. Locks the thin-prompt shape via template rendering; adds structured submit_feedback fields.
- **1.b (rebuild baselines)** ships after 1.a, as each thin run lands.
- **1.c (api_calls=0 gate fix)** ☑ shipped 2026-04-24. Small and independent.
- **1.d (abstract shape wisdom)** ☑ shipped 2026-04-24 (after 1.b). First measurable ratchet cycle starts here: next thin runs are the "after" against the thin-variant baselines we just landed.
- **1.e (informed variant)** ☑ shipped 2026-04-24. Five `<slug>-informed` briefs seeded alongside the thin variants; same protocol, adds a "Baseline + gold snapshot" section with the current gold_in count + baseline precision/recall/corpus-size + a one-sentence read.
- **1.f (doc sweep)** ☑ shipped 2026-04-24. Updated ratchet-plan, benchmarks/README, CLAUDE.md, dogfood/README, dogfood/tasks/README; added dogfood/kickoffs/README framing the fat-variant files as legacy.

#### 1.a `[☑ shipped 2026-04-24]` Brief durability pass + template mechanism

**What.** Lock the shape of the thin-variant prompt so it can stay frozen across many ratchet cycles. Changes:

1. **Brief-as-template with server-side rendering.** Both the `run_topic_name` AND the `brief_markdown` body are templates. `fetch_task_brief` runs one substitution pass at call time:
   - `{ts}` → current minute-UTC (`YYYYMMDDTHHMM`).
   - (Future variables like `{task_id}` / `{benchmark_slug}` can share the same pass if we need them; ship `{ts}` only for now.)

   DB stores the templates; tool returns the rendered strings. The brief body naturally uses the rendered name in step 1 (`start_topic(name="apollo-11-thin 20260424T0013", ...)`) because that literal line is produced by the same substitution pass. Brief source stays frozen; output is unique per fetch. Operators no longer know the exact run-topic name from the prompt source alone — they see it in the returned brief or via 1.a.2 scoring tooling.
2. **Scoring script `--task <task_id>` alternative.** `scripts/benchmark_score.py` grows a mode where you pass a task_id and it picks the most recent run-topic matching the template's stem (plus optional `--nth N` for older runs). Preserves the explicit `<run-topic-name>` positional arg for back-compat.
3. **Strip operational details out of briefs, into `server_instructions.md`.** Anything that might evolve (spot-check probe counts, rubric tier framework, etc.) moves out of the brief into the canonical instructions. Brief just says "do the SPOT CHECK and GAP CHECK per server instructions" and "draft a rubric following the SCOPE RUBRIC framework" — no numbers or tier names. Audit fragile references; replace specific tool names with "the server's pipeline" where appropriate. Keep stable-API references (`start_topic`, `set_topic_rubric`, `submit_feedback`, `export_csv`).
4. **Enrich `submit_feedback` schema with structured optional fields** that we want to trend over time. Brief names them so AI populates; schema evolves server-side without brief edits:
   - `strategies_used: list[str]` — tool-family tags (`category_crawl`, `list_harvest`, `navbox`, `wikidata_property`, `search`, `similarity`, `edge_browse`, `fetch_leads`). Lets us track strategy diversity per topic shape over time.
   - `spot_check: dict` — `{"probes_count": N, "hits": M, "misses_redirect": X, "misses_hallucination": Y, "misses_real_gap": Z}`. Structured spot-check results.
   - `sharp_edges_hit: list[str]` — enum of KNOWN SHARP EDGES tags the AI actually hit this session. Tells us which warnings are live-saving vs. theoretical.
   - `tool_friction: list[str]` — tagged one-liners (`"fetch_descriptions_timeout"`, `"harvest_navbox_empty"`). Aggregates mid-run surprises; complements `note=` on individual calls.
5. **Mode statement stays** ("deep consultative, completeness-seeking") — it's the mode we've chosen to measure under. Document the why in a tasks/README section so future-us doesn't wonder.

**Why.** Sage's framing (2026-04-23): "we don't want to have to change these. if the only changes are server instructions and tools, while the prompts are static, that'll be the cleanest way to ratchet up." A frozen prompt makes longitudinal measurement possible; every movement in the metrics attributes to a specific code/instruction change, not to operator drift.

**Open questions** (resolve before shipping):
- `spot_check.misses_*` enum — fixed vocabulary (`redirect` / `hallucination` / `real_gap`) or freeform? Fixed trends better; freeform captures edge cases. Lean: fixed, with `other` fallback.
- Brief body template variables beyond `{ts}` — probably not, keep minimal.
- Is `strategies_used` AI-self-reported or computed from `usage.jsonl`? Self-report for intent ("I tried X first because..."); parallel usage-log telemetry can validate later.

**Shape.** DB migration (one column), tool-render logic in `fetch_task_brief`, scoring script alternative, 5 brief rewrites, `submit_feedback` schema addition, `server_instructions.md` additions for stuff that left the briefs (spot-check probe count guidance). Ship as one cohesive commit or small bundle; partial ship leaves the system inconsistent.

#### 1.b `[☐]` Rebuild baselines from thin runs

**What.** Today's `baseline.json` files encode pre-logging-backfill runs with data-quality issues (api_calls=0 on AA-STEM / HL-STEM, mixed quick-autonomous / consultative modes, pre-Chunk-1-6 tool behavior). Replace them with metrics from fresh thin-variant runs under the 1.a-locked prompt. Mothball today's fat-variant scoreboards as historical-only.

**Shape.** Small `scripts/update_baseline_from_run.py` helper that reads the archived scoreboard + topic state, writes `benchmarks/<slug>/baseline.json`. Archive old baselines in-place (rename to `baseline-archive-2026-04-23.json` so git history preserves them). After all 5 thin runs under locked-prompt are in, this becomes the new measurement floor.

**Why.** Today's gate compares against baselines we've already flagged as unreliable (see today's scoreboards). A thin-prompt baseline under the locked format = first real measurement under the "standard shape" that the ratchet is supposed to iterate from.

**Sequencing.** AFTER 1.a — baselines should be under the durable prompt, not the current one.

#### 1.c `[☑ shipped 2026-04-24]` `benchmark_score.py`: treat `api_calls=0` on baseline as unrecorded

**What.** When `baseline.total_api_calls == 0`, skip that axis in the cost-improvement gate (currently any ratchet run with non-zero api_calls is counted as "worse" even if genuinely efficient). Add a note to the scoreboard output. Parallel to the wall_time caveat shipped in `b6d1635`.

**Why.** AA-STEM and HL-STEM baselines predate the Stage 1.1 logging backfill — their api_calls=0 is missing-data, not actual-zero. Today's scoreboards show up as FAIL partly for this reason. Fix unblocks meaningful comparison during the 1.a→1.b transition. Will eventually be moot once 1.b lands (new baselines will have real api_calls), but ship it so interim comparisons aren't gated on phantom regressions.

**Shape.** One `if baseline_api_calls == 0: skip` branch in `compute_scoreboard`, plus a "(baseline data unavailable)" label in the table.

#### 1.d `[☑ shipped 2026-04-24]` Abstract shape-strategy wisdom into `server_instructions.md`

**What.** Move cross-topic-shape wisdom currently baked into the 2026-04-23 fat-variant kickoff prompts into the canonical instructions, so every thin-variant run benefits automatically without operator pre-hinting. Concrete edits:

- **Expand the existing `SHAPE → WIKIDATA PROPERTY` table** with `P138 (named after)` for named-event / award / institution shapes and `P171 (parent taxon)` for taxonomic shapes; add a "high-leverage first move" column. P171 evidence from the 2026-04-24 orchids thin-variant run: `wikidata_entities_by_property(property="P171", value="Q25308")` returned 66 enwiki sitelinks of which **27 were not already in the corpus** after a full category + list-page sweep — concrete lift data. **Frame these as ADDITIVE probes only** — they find candidates you'd otherwise miss; they do NOT have completeness properties. A taxon without P171 set still exists on Wikipedia; the probe won't find it. See `memory/feedback_wikidata_incomplete.md`.
- **Add an "additive vs subtractive tools" principle bullet** in the instructions (placement: near NOISE TAXONOMY or KNOWN SHARP EDGES): every tool is either **additive** (surfaces candidates; use freely) or **subtractive** (drops candidates; use carefully). Subtractive tools hide silent drops — `filter_articles` bug (2026-04-24), `auto_score_by_description(disqualifying=...)` proper-noun misses, any Wikidata-gated filter. When using a subtractive tool, prefer `preview_*` / `dry_run=True` variants; when reaching for a Wikidata property as an exclusion rule, reach for it as an annotation instead (see the revised type-hinted harvest item above).
- **Add a SOURCE-TRUST principle bullet**: when a source is topic-definitional (category named after the topic, list-page authored by topic specialists), trust source-provenance over shortdesc for inclusion. Evidence: orchids baseline's source-trust rule recovered ~5000 taxa whose Wikidata shortdesc said only "Species of plant".
- **Reinforce INTERSECTIONAL TOPICS** with a pointer to `fetch_article_leads` for ambiguous biography shortdescs — that's where the tool earns its keep (AA-STEM / HL-STEM wrap-up feedback this cycle).
- **Add "for parent-program shapes, `harvest_navbox` on the parent's template is your highest-leverage first move"** (Apollo 11's Kennedy-Space-Center-miss exemplar — recovered in the fat-variant run but only after a scope-wide dig).

**Topic-specific rulings that should NOT generalize** and stay in each topic's rubric (not in instructions): Brazilian-vs-peninsular-Spanish exclusions, medicine-blocklist cross-referencing, orchids-cultural-tail narrowness. Those are scope calls, not tool-strategy advice.

**Why.** Running thin-prompts without operator hand-holding only works if shape-general wisdom is in the substrate. The fat-variant prompts proved these strategies work; abstracting them lets thin runs benefit without operator pre-briefing.

**Sequencing.** MUST ship AFTER 1.b. Otherwise the abstraction gets baked into the new baselines and we can't measure whether it helped. The first ratchet cycle post-baseline IS this abstraction — that's what we're measuring.

#### 1.e `[☑ shipped 2026-04-24]` Informed-variant briefs for gold farming

**What.** Add `<slug>-informed.md` briefs under `dogfood/tasks/` with frontmatter `variant: informed`. Body = thin brief's content + "the gold set contains at least N articles; the prior thin baseline hit P precision, R recall." Reseed DB.

**Why.** Two-variant measurement split (per discussion 2026-04-23): **thin = product measurement** (what a realistic user gets); **informed = ceiling probe + gold-farming** (what the AI can do with target visibility). Gold farming is the specific value — an informed run is most likely to surface gold-growth candidates because the AI knows where the bar is. Orchids is the biggest current opportunity (2026-04-24 thin-variant run surfaced **456 reach candidates** at 100% precision; auditing + promoting would materially grow the orchids gold set).

**Shape.** Pure content / seed work. No code. Five new markdown files + a reseed. Can ship any time after 1.a (to use the locked template format); doesn't affect the thin-ratchet loop.

#### 1.f `[☑ shipped 2026-04-24]` Doc sweep for server-mediated dogfood task briefs

**What.** The `fetch_task_brief` / `list_tasks` entry-point system shipped 2026-04-23, but the surrounding docs still describe the old copy-paste-kickoff-file path as canonical. Five docs need updates:

1. **`docs/ratchet-plan.md`** — "Kick-off-and-leave-for-a-while mode" section. Point at `fetch_task_brief(task_id=...)` as the preferred kickoff.
2. **`dogfood/README.md`** — add a "Running a benchmark task" section with the one-line kickoff prompt.
3. **`benchmarks/README.md`** — "Fresh AI-driven builds" design note. Add the server-mediated path as a third option + mark as preferred for benchmarks.
4. **`CLAUDE.md`** — "~45 tools" is stale (now ~47); brief mention of dogfood task system under "Architecture at a glance".
5. **`dogfood/tasks/README.md`** — expand framing (why the system exists; when thin vs. informed vs. `task.md` freehand).

**Deliberately NOT updating:** `mcp_server/server_instructions.md`. Tool docstrings say "don't call in normal sessions"; adding to instructions would invite misuse.

**Open: what to do with the `dogfood/kickoffs/ratchet-2026-04-23-*.md` files?** Three options: (1) leave as historical, (2) add a README in `dogfood/kickoffs/` framing them as legacy-for-now, (3) migrate into DB as `<slug>-fat` tasks and delete the files. Leaning (2) for this sweep; (3) as follow-up if thin variants prove the right primary measurement and we want full DB consolidation.

**Shape.** Pure doc edits. Zero code change.

---

## Tier 2 — medium effort, multi-session-validated

### ☐ `cross_wiki_diff(source_wiki, target_wiki)` `[formerly 5.2]`

**What.** Take two topics on different wikis, return articles in A that have a sitelink to wiki B but aren't in topic B ("potential gap-fills"), and separately articles in A with no sitelink to B at all ("genuinely unique-to-A content"). Both directions useful.

**Why.** Direct evidence from the second orchids session: the AI walked the zh/ja/pt cultural clusters back to enwiki manually and **recovered 21 enwiki articles that 8 sessions of English-language discovery had missed** — including João Barbosa Rodrigues (father of Brazilian orchidology!) and Qu Yuan (whose Li Sao established orchid symbolism in the Chinese canon). The reverse walk found 14 zhwiki-only items, 3–4 jawiki-only, and 5 ptwiki-only items with no enwiki equivalent at all — distinct cultural content preserved only in that language's Wikipedia.

Without this tool, the methodology works but is tedious — N preview_search calls per non-en topic. With it, the whole reconciliation collapses to one call per direction.

**Shape.** For each article in topic A:
- Look up Wikidata QID (cheap now that `resolve_qids` has shipped).
- Check sitelink to wiki B.
- Classify into three partitions:
  - **`gap_fills`** — article has a B-wiki sitelink AND that B-title is *not* in topic B. Most valuable output: real articles on B that are missing from the user's B-topic. Candidates to add.
  - **`unique_to_a`** — article has no sitelink to B at all. No corresponding article exists on B. These are the culturally-unique-to-A items — great for cataloging what only lives in that wiki.
  - **`translation_candidates`** — articles that have no B sitelink AND whose title/description suggest they'd be valuable on B (e.g. species articles present on A with no B equivalent). Downstream handoff for a translation project. Not add candidates for B-topic (they don't exist yet on B), but worth surfacing as a distinct list.

The AI's Q4 walkthrough made this partitioning explicit: "partition by title pattern heuristically (cheap): species (~60% of results) → translation candidates; cultural concepts (~25%) and biographies (~15%) → gap-fill candidates after a preview_search confirms relevance."

**Open questions.**
- Standalone via MediaWiki langlinks API vs. via `wikidata_query` SPARQL. Langlinks is simpler and orchids needs it now; SPARQL version can come later. Ship standalone first.
- Separating `gap_fills` from `translation_candidates` needs a heuristic for "would this be valuable translated?" Probably: title looks like a species / formal name / institution → translation candidate if no B sitelink. Needs tuning with real data.
- How does the AI know which direction to run first? Instruction guidance: "if your primary wiki is en and you have non-en parallel topics, run `cross_wiki_diff(non_en, en)` to find gap-fills to add to your en topic; run the reverse to catalog unique content."
- Output size on big topics: 18K-article en topic diffed against 2K zh topic is 2K checks — manageable. En → pt with a full 18K sweep is bigger. Consider pagination / limit param.

### ☐ Spot-check support primitives cluster `[formerly 6.8]`

**What.** Three small read-only primitives that make the self-administered spot-check loop efficient instead of abusive:

1. **`check_article_presence(titles=[...])`** — takes a titles list, returns `{title: {in_corpus | not_in_corpus | near_match}}`. Replaces the current N-individual-`preview_search` pattern or the 40-name alternation-regex hack on `get_articles(title_regex=...)`. Pulitzer feedback: "a titles-list-in, {in_corpus, not_in_corpus, near_match} dictionary out would make the spot-check loop a 3-tool flow instead of N individual preview_search calls."
2. **`verify_claim(title, property, value)`** — structured check: does this Wikipedia article assert property=value? (e.g. "does the Walter V. Robinson article claim a Pulitzer Prize for Investigative Reporting?"). Replaces indirect `preview_search(query="\"Name\" \"Pulitzer Prize for Investigative\"")` quoted-phrase probes. Pulitzer feedback.
3. **`list_rejections(show_reasons=True)`** — audit view of rejected titles + reasons. Pulitzer feedback: "made the session feel slightly blind on that axis." (Note: a `list_rejections` tool already exists; this is about surfacing the reasons alongside titles, not the titles alone.)

**Why.** All three unblock the spot-check modality: hypothesize titles → check presence → classify misses → verify ambiguous cases → review rejection trail for consistency. With these, the loop is 3–5 calls instead of 20–30.

**Shape.** Read-only; no state mutation. `check_article_presence` + `verify_claim` wrap existing MediaWiki surface. `list_rejections` extension is a SQL read. Cluster them in one deploy — they share design context.

**Open questions.**
- `check_article_presence`: what's a `near_match`? Redirect-target match + case-insensitive title + diacritic-folded? Spell out.
- `verify_claim`: Wikidata-first (structured) with article-text fallback, or article-text-only? Probably Wikidata-first.
- Ship before or after the self-administered spot-check modality `server_instructions.md` update? Probably alongside.

**Sequencing note.** Single-session evidence (Pulitzer) but tightly tied to the self-administered spot-check modality item, which has multi-session evidence. Reference: `dogfood/sessions/2026-04-23/session-2026-04-23-run2-notes.md`.

### ☐ `harvest_navbox` preview mode / template discovery `[NEW]`

**What.** Post-ship extensions to the `harvest_navbox` tool that landed in the post-orchids chunk batch:
1. **Preview mode** — `preview_harvest_navbox(template)` returning candidate title count + sample without committing, matching the `preview_*` convention.
2. **Template discovery** — a helper that returns candidate navbox/infobox templates for a topic article, so the AI doesn't have to guess the template name.

**Why.** `harvest_navbox` is the right tool for award / franchise / program shapes (apollo-11, crispr-gene-editing peripheral, pop-culture shapes) — but the AI has to know the exact template name, and has no dry-run surface before committing. Same friction `preview_harvest_list_page` / `preview_category_pull` resolved for their commit variants.

**Shape.** Preview: small wrapper over existing `harvest_navbox` internals that returns count + sample. Discovery: given an article title, list templates used on that page (via `prop=templates`), filter to likely navboxes by name pattern.

**Open questions.** Is template discovery worth a separate tool, or should `harvest_navbox` itself accept an article title and auto-find the navbox template? The latter is fewer surfaces; the former is more predictable.

### ☐ `resolve_category(wikidata_qid)` — per-wiki category-name helper `[formerly 5.5]`

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
- Dependency: needs Wikidata API access (same infra as `wikidata_query`).

### ☐ `completeness_check(topic)` `[formerly 5.3]`

**What.** Compare a topic's contents against a Wikidata ground-truth count for its canonical class.

**Why.** Turns "is my list complete?" from vibe-check into an answerable question. Feedback: "Wikidata says ~28K orchid species exist; your topic has 13K species; here are the top 100 species by sitelink count that you're missing."

**Shape.** Needs a "canonical class" per topic — either explicitly configured by the AI (`completeness_check(topic, wikidata_class="Q25308")` for Orchidaceae) or inferred from topic sources.

**Open questions.** How does the tool know what "class" the topic is? Inference from dominant categories? Explicit AI-provided? Probably explicit, documented in instructions.

### ☐ Self-administered spot-check modality `[formerly 6.7]`

**What.** Promote the "ask the user to name 3–5 niche examples" spot-check into a structured self-evaluation loop the AI can run without human input. Pairs with the Tier 1 `coverage_estimate` field — this item is the instruction changes that direct the AI into the loop.

Recipe to encode in `server_instructions.md`: **hypothesize** a large, structured probe list (~50 candidate titles across ≥5 natural subdomains of the topic) → **verify** presence via `get_articles(title_regex=...)` or batched `preview_search` (or `check_article_presence` if the Tier 2 spot-check primitives have shipped) → **classify** each miss as variant-name-already-in-corpus / LLM-hallucination / real gap → **diagnose** miss-patterns into strategies ("five missed cultural-works → rerun preview_harvest_list_page on the cultural-tail list page, don't hunt each title") → **repair** → **estimate** remaining coverage → **iterate** until self-estimated coverage stabilizes or the user calls it. Explicitly authorize autonomous fabrication when no user is available.

Optional: a mid-build `report_coverage_estimate(confidence, rationale, remaining_strategies)` tool so the estimate can be logged before `submit_feedback` fires — useful if we want live telemetry or a UI surface.

**Why.** The 2026-04-23 Apollo 11 dogfood session stalled silently for 10 minutes waiting for user input the current spot-check instruction requires. Once unblocked, the AI executed essentially this loop in ~5 minutes — 13 `preview_search` probes, 3 spot-check gap-adds, `browse_edges(seeds=6)` yielding 10 more real gaps (notably Kennedy Space Center, which Category:Apollo program didn't tag). The workflow is good; the user-dependency is the break. Generalizing it gives us (a) an autonomous stopping criterion, (b) a per-topic completeness metric we can correlate against ratings and against benchmark audits, and (c) strategy-picker leverage — each *class* of miss is a lead into a whole class of misses, not one article.

The 2026-04-23 dogfood `task.md` has already been patched to authorize the loop for dogfood sessions specifically (see §3 of "While you build"). That was a one-harness band-aid; this item is the durable fix so every caller benefits.

**Shape.**
- Instruction surface: ~40–60 lines in `server_instructions.md`, with concrete recipe + subdomain-axis examples for 2–3 topic shapes. Authorize autonomous fabrication explicitly; don't leave it implicit.
- Helper tool (optional): `report_coverage_estimate(...)` mirrors `submit_feedback`'s shape for the mid-build case. Only ship if we want the mid-build telemetry; the end-of-session field alone covers the core need.

**Open questions.**
- **How many fabrication rounds?** Probably bound at 2–3 in the instructions. More than that is diminishing polish — LLM tails out.
- **Blind to the corpus while fabricating, or after seeing `describe_topic`?** Blind probably surfaces better gaps (avoids enumerating what's already visibly present); post-describe probably produces higher-precision probes but lower gap-discovery rate. May be worth two modes, or an explicit "fabricate first, then look" rule in the instructions.
- **How do we calibrate `confidence` over time?** Collect the self-reports; when we have gold-standard audits (`benchmarks/` directory), compare AI's confidence against ground-truth recall. Until then, capture and trust self-reports for relative comparison.

**Sequencing note.** Wait for `cross_wiki_diff` and the spot-check primitives cluster to land before writing the instructions — those expand the strategy surface the coverage estimate reasons about, and the subdomain-axis examples want to name them. Full session context and signal-origin in `dogfood/sessions/2026-04-23/session-2026-04-23-notes.md`.

---

## Tier 3 — deferred / speculative

Items worth keeping on the roadmap but not committing to pre-build. Revisit after Tier 1–2 land or as specific signals confirm.

### ☐ Cooperative async yielding in heavy tools `[NEW — 2026-04-24 deferred follow-up]`

**What.** Audit the longest-running tools (`get_category_articles` depth walks, `harvest_list_page` on large pages, `auto_score_by_description` on 10k+ corpora, `filter_articles` on large corpora, `resolve_redirects` / reconcile passes) and add periodic `await asyncio.sleep(0)` yield points — or switch synchronous HTTP (`urllib.request`) to `httpx` async — so one heavy call doesn't hold the event loop.

**Why.** The multi-worker fix (Tier 1, linked above) absorbs the visible symptom by running parallel event loops, but a single worker still freezes under any tool that doesn't yield. Real per-tool async-friendliness is the durable end state — especially if we ever scale workers back to 1 (e.g., on a resource-constrained deploy) or accept more than 2 concurrent heavy sessions.

**Sequencing.** Deferred until the multi-worker fix ships and we observe whether the symptom is fully absorbed or if we still see per-worker blocking under load. Surgical per-tool work; one afternoon per tool at most.

### ☐ `browse_edges(min_links="auto")` `[formerly 1.8]`

**What.** Auto-calibrated threshold that targets 20–50 candidates.

**Why.** Feedback: "I tried 10 seeds at `min_links=5` and got back only 2 candidates — both too general." Threshold semantics aren't intuitive.

**Shape.** Start at `min_links=3`, probe upward until candidate count falls into the 20–50 band. Or reverse-engineer: compute a threshold from the seed count.

**Open questions.** Low urgency — `browse_edges` wasn't central to orchids. Could be a docstring tweak rather than new logic.

### ☐ `topic_policy(include_desc, exclude_desc)` — sticky scope rules `[formerly 6.9]`

**What.** A new primitive that declares a topic's include/exclude policy as description patterns and has subsequent gather tools auto-apply it. Example: for Phenomenology, `include=/phenomenolog/i, exclude=/physics|particle|archaeolog|architectural/i`. After `topic_policy(...)`, future `get_category_articles` / `add_articles` / `harvest_list_page` calls skip candidates matching the exclude pattern automatically.

**Why.** Phenomenology feedback: "After deciding 'physics phenomenology out, architectural phenomenology in,' subsequent pulls still pull physics-phenomenology-tagged articles. The sticky rejection list catches *specific titles*, but not the *policy*. A `topic_policy(...)` would let me articulate the rule once and have it auto-apply on all future pulls." Structural addition — not topic-specific. The shipped two-axis model covers per-article inclusion + centrality; this adds a per-topic *policy* axis that determines which candidates are evaluated at all.

**Shape.** Per-topic table of `(pattern, include_or_exclude, mode)` rules; `topic_policy(include=[...], exclude=[...])` sets; `get_topic_policy(topic)` reads. Gather tools check candidates against the policy before commit. Storage alongside sticky rejections (similar precedent).

**Open questions.**
- Pattern language: substring? regex? key-value shortdesc axes (reuse `auto_score_by_description`'s rubric)?
- Apply at gather-time (skip candidates) or review-time (flag for AI review)? Probably configurable per rule.
- Stack with or replace sticky rejection list? Stack — rejection is "specific title"; policy is "class of title".

**Sequencing note.** Single-session evidence so far (Phenomenology) but the pattern ("scope is stable across iterations; re-judging is wasted") is structural. Revisit when (a) a second session demands it, or (b) the self-administered spot-check loop encounters repeat-miss-classes the policy would have caught.

### ☐ PetScan-style intersection `[formerly 5.4, backlog:#4]`

**What.** Compound category queries. "Articles in Category:Orchidaceae genera AND Category:Plants described in 1834."

**Shape.** Could wrap the existing `petscan.wmcloud.org` HTTP API, or build natively using `categorymembers` API with intersection logic.

**Sequencing note.** Arguably subsumed by SPARQL via `wikidata_query` (Wikidata supports category intersection queries). Decide after testing whether SPARQL covers the common intersection shapes — if so, drop this; if not, keep.

### ☐ `get_category_articles_bulk(categories=[...])` batch variant `[formerly 6.1]`

**What.** One tool call that pulls multiple categories in sequence, returning merged results.

**Why.** Second feedback: "Would let me pull 20 ptwiki genus categories in one call instead of 20 sequential calls. Most took under 10 seconds, but network overhead adds up." The per-genus fallback (when a root category is too broad to crawl at depth) becomes friction-free.

**Shape.** Internally a loop over existing `get_category_articles`; respects the shipped cost-budget + cooperative time-budget abstractions. Returns per-category sub-results + merged article list.

**Sequencing note.** Could slot up to Tier 2 if real demand confirms; parked here until then.

### ☐ `suggest_removals(source, max=50)` — LLM-assisted review `[formerly 6.2]`

**What.** A tool that uses an LLM on the server side to flag likely-noise articles in a source, surfacing a ranked list for the calling AI to review.

**Why.** Second feedback: "Given the source audit pattern I kept using manually (`get_articles_by_source(exclude_sources=[everything else])` then eyeball), there's probably a tool-level primitive."

**Shape.** Server-side LLM call per batch, with a rubric derived from the topic's scope + existing on-topic sources. Returns `{title, flag_reason, confidence}` list. AI decides what to actually remove.

**Open questions / caution.**
- Costs $. Server-side LLM calls add ongoing operating expense, not just build time. Worth it only if the human-speed review step is the real bottleneck.
- Could also be done client-side: give the AI enough context and it runs its own review via `get_articles_by_source`. May not need a server-side primitive at all.
- Model choice, prompt robustness, rubric construction — real engineering, not trivial.

Leaning: wait to see if the shipped regex filters + cost telemetry actually leave this as the cleanup bottleneck. If not, skip.

### ☐ Save-query presets / macros `[formerly 6.3]`

**What.** Let the AI save a parametrized search as a named macro. E.g. `probe_botanist("Barbosa Rodrigues")` runs the `<name> botanist <domain>` search templates the AI already constructs ad-hoc.

**Why.** Q5 answer: "I ran '<BotanistName> botanist orchid' templates many times across zh/ja/pt/nl probing for biographies. A saved parametrized query would let me `probe_botanist('Barbosa Rodrigues')` as a macro."

**Shape.** Tentative: a registry of named search templates scoped to a topic. `define_search_template(name, query_pattern)` then `run_template(name, args)`. Or simpler: a per-topic "search presets" table stored alongside rejections.

**Sequencing note.** Speculative. Revisit if we see the AI repeatedly constructing the same search shape across topics.

### ☐ Per-session watch / diff `[formerly 6.4]`

**What.** "What articles are in `category:Orchids` today that weren't last session?" — a delta operator over a topic's corpus across time.

**Why.** Q5 answer: "Topic maintenance over time." Useful when a topic is meant to be kept current (e.g., an initiative tracking Wikipedia's growing coverage of women in STEM over the course of a year).

**Shape.** Snapshot + diff. `snapshot_topic(topic, name)` captures current state; `diff_snapshots(topic, name_a, name_b)` returns added/removed/changed articles. Could also diff against an implicit "last snapshot."

**Sequencing note.** Useful when long-lived topics become a real use case — currently topics are largely one-off builds.

### ☐ Graph view of topic via internal links `[formerly 6.5]`

**What.** Visualize how articles in a topic are connected via Wikipedia's internal link structure. Expose islands (disconnected subsets = likely orphan additions or noise) and bridges (articles linking many clusters = likely on-topic hubs worth expanding around).

**Why.** Q5 answer: "The deepest one: I wanted a graph view of the topic showing how articles cluster via Wikipedia's internal links. Islands would flag orphan additions, bridges would flag on-topic content that wasn't pulled in. Very far from current tool scope but would be the right debugging primitive for completeness."

**Shape.** Fetch per-article outgoing links, build a subgraph restricted to the topic's article set, compute connected components + centrality. Output as JSON (cluster IDs, bridge candidates) or ultimately a visualization.

**Sequencing note.** Far future. Needs a lot of Wikimedia API traffic (links per article) and a visualization layer. Park here as a north-star primitive for completeness debugging.

### ☐ Empty-topic detection and nudge `[formerly 6.6]`

**What.** If a topic is created but has zero articles after N subsequent tool calls (or N minutes), surface a hint on the next tool call: "topic X is still empty — common starting points are `get_category_articles`, `harvest_list_page`, `search_articles`. What are you trying to do?"

**Why.** Kochutensilien dogfood pattern: 4 `start_topic` calls on 2026-04-21, only one reaching 43 articles — the other 3 remained empty. Looks like the user was struggling to find the right starting tool. An empty-topic nudge catches this specific friction.

**Shape.** On each tool call for a topic, check whether the topic is > 5 minutes old AND has zero articles AND had no add-shaped call attempted. If all true, include a suggestion in the response.

**Sequencing note.** Speculative until we see more of this pattern in the wild. Adjacent to the shipped resume-nudge (item 1.18) and COMMON TASK → TOOL mapping (item 2.7). Skip if those resolve the issue.

---

## Smaller items considered and deferred

One-liners that have been considered and deliberately deferred. Promote to a tier above if signal builds.

- **Source-label escaping for labels with colons/quotes.** Partially addressed by 1.14's slugification for `search_articles` labels, but `search:morelike:<seed>` labels with spaces/punctuation may still need attention.
- **`list_topics` per-user scoping.** Waits on auth. Flagged by orchids second feedback as a privacy concern ("I could see topics belonging to other users — Kochutensilien, Native American scientists, Seattle, educational psychology, upright bass"). `[backlog:#1]`
- **Lower `survey_categories` warning threshold.** Didn't come up in orchids. Keep on backlog.
- **Rate-limit backoff review.** Confirm that hitting a Wikimedia rate limit triggers actual exponential backoff in `wikipedia_api.py`, not just a counter increment. If the client is already doing the right thing, no work needed.
- **`harvest_list_page` behavior on dewiki.** Kochutensilien user feedback (2026-04-22) complained "no direct tool support for extracting link targets from a Wikipedia list page" — which is literally `harvest_list_page`'s job. Either (a) they didn't discover the tool (addressed by shipped COMMON TASK → TOOL mapping), (b) they mean "display text vs. link target" in a way that suggests a dewiki-specific parsing quirk, or (c) the tool silently underperformed on their target page. With logging backfill shipped, future dewiki sessions should show whether the tool gets reached for.
- **Hierarchical topic architecture (`start_topic(parent_topic=...)` + `reconcile_to_parent()`).** Considered and deferred 2026-04-22. The Q6 answer in the third feedback round suggested parallel topics should be first-class children of a parent topic, with reconciliation baked into the API. **Decided to take the light-touch path instead:** `cross_wiki_diff` (Tier 2) stays the only new primitive; parallel topics remain siblings; users / AI compose the workflow. Reasoning: the cost of adding parent/child concepts to the schema and API surface outweighs the benefit until we see the manual composition pattern prove too friction-heavy in real use. Revisit if (a) `cross_wiki_diff` ships and the AI still struggles to assemble the workflow, or (b) a user shape emerges where hierarchical topic relationships are central (e.g., long-running multi-wiki research projects).
- **Soft-redirect category hint on empty `survey_categories` result.** If `survey_categories` reports an existing category page with 0 articles (container/redirect category), emit a "try sibling X instead" hint. K-drama dogfood surfaced this on `Category:Korean television dramas` → should have pointed at `Category:South Korean television series`. Needs sibling-finding logic — probably scan for same-prefix categories via `prop=categories` on the empty category page. `[NEW — 2026-04-23 dogfood run 2]`
- **`auto_score_by_description` substring-matching edge on proper-noun words.** Pulitzer feedback: `disqualifying=["city", "county"]` would reject "The Kansas City Star" and "Orange County Register" because the geographic word is part of the institution's proper name. Word-boundary match alone doesn't fix it ("City" IS a word). Possible approaches: case-sensitive lowercase-only match, exclude matches where the word is part of a proper-noun phrase, or an "exclude-unless-preceded-by-lowercase" mode. No obvious right answer — more thought required. `[NEW — 2026-04-23 dogfood run 2]`

---
