# Backlog — open items

Pending items from the improvements plan, grouped by priority tier.
Shipped items are logged in `../shipped.md`. `../ratchet-plan.md` is
the "what to work on next" entry point and draws its shortlist from
this doc.

Sibling docs in this directory hold larger plans (deferred or in review):
- `impact-visualizer.md` — publish_topic handle → Impact Visualizer import.
- `exemplars-and-reach-pass.md` — `list_exemplars` + `get_exemplar` tools; preparatory-phase server-instructions posture; brief-driven two-phase dogfood (in review).

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

### ☑ Pagination for `get_article_links` and `get_article_backlinks` `[shipped 2026-04-26]`

**What.** Both seed-mining tools accepted `limit=` (default 500, hard-cap 5000) and returned `truncated=True` with no way to fetch the next page. Added a `continue_token` to the response and as an input arg so the caller can paginate.

**Shape shipped.** Each tool now caps `pllimit`/`bllimit` per API page at `min(limit, 500)` so it stops on a clean page boundary. At truncation, `data['continue']` (a dict like `{plcontinue: "...", continue: "||"}`) is JSON-encoded and returned as `continue_token`; passing it back unchanged on a subsequent call decodes and merges it into the next request. Both docstring and `server_instructions.md` COMMON TASK → TOOL row updated so ChatGPT (cached-schema client) learns about the new param via session-init instructions.

### ☑ Exemplar integrity gate leaks via slug normalization `[shipped 2026-04-26]`

**What.** `list_exemplars` / `get_exemplar` normalize the requested slug (e.g. lower-casing, hyphen folding) before lookup, but the integrity gate that hides an exemplar when the active topic matches its benchmark slug compares against the *raw* (un-normalized) slug. Result: an exemplar for benchmark `apollo-11` remains visible in the menu and fetchable while a run on the same benchmark is in progress, defeating the gate.

**Why.** Discovered mid-run during the 2026-04-26 composable-strategy dogfood (apollo-11 thin variant). The AI noticed `apollo-11` in the `list_exemplars` menu while running the apollo-11 benchmark, recognized it as a measurement-integrity leak, and deliberately avoided `get_exemplar(slug="apollo-11")` to preserve the run. The gate is supposed to prevent exactly this scenario without requiring AI judgment.

**Shape.** Normalize both sides of the comparison in the gate (run-topic-slug → benchmark-slug match) using the same canonicalization the lookup uses. Audit `list_exemplars` filter logic and `get_exemplar` permission check together — they need to agree on the normalized form.

**Sequencing.** Small, independent. Ship before the next ratchet cycle so future runs aren't dependent on AI noticing the leak.

### ☐ `preview_wikidata_property` titles-only output `[NEW — 2026-04-26]`

**What.** A read-only sibling of `wikidata_entities_by_property` that returns just `{title, sitelink_count}` per result, without entity bodies. Same params, smaller payload.

**Why.** `wikidata_entities_by_property(property=..., value=..., limit=500)` returns full entity records and routinely exceeds the MCP token cap. Hit twice in the 2026-04-26 climate-change phase-2 run (~73K chars per call). The AI's workaround was to read the tool-result file off-channel and parse it with python — fine for power users on local hosts, untenable for a published web skill where the AI doesn't have filesystem access.

A titles-only mode lets the AI page through the full result set (use the title list to pick what to fetch in detail) without ever blowing the token cap. Pairs with the existing `wikidata-class-instance-enumeration` move where you typically want to page through hundreds of P31 instances.

**Shape.** New tool `preview_wikidata_property(property, value, limit=500)` returning `{count, results: [{title, sitelink_count, qid}]}`. Reuse the existing `wikidata_entities_by_property` plumbing; just project to a smaller record. Existing tool stays for cases where the entity body is genuinely needed.

**Open questions.**
- Should the existing `wikidata_entities_by_property` also accept a `titles_only=True` flag instead of a separate tool? Lean separate tool — matches the `preview_*` convention used for `harvest_list_page`, `category_pull`, `similar`. Same shape, same naming.
- Sort order: by sitelink_count descending (most-cited first) is the most useful default — surfaces the well-attested entities at the top of a long list.

**Sequencing note.** Single-session evidence (climate-change 2026-04-26), but the failure shape (token-cap collision on a heavily-curated property) will recur on any large biography-axis Wikidata probe (P101 / P106 on big fields). Worth Tier 1 if a second session hits it.

### ☑ Capture agent / model / effort on `submit_feedback` `[shipped 2026-04-25]`

Optional `runtime: dict | None = None` field on `submit_feedback`, serialized verbatim into the feedback JSON line and unpacked into per-key log params (`runtime_agent`, `runtime_model`, `runtime_effort`). Briefs ask the AI to populate from self-knowledge. Lets us trend results across claude-code-opus-4.7 / codex-gpt-5 / different effort levels — was filename-only before. See `shipped.md` 2026-04-25 (Ship 2 entry).

### ☑ Argumentless `fetch_task_brief` with auto-dispatch `[shipped 2026-04-25]`

`fetch_task_brief()` (no `task_id`, default `variant="thin"`) atomically picks the staleest matching task — smallest `last_dispatched_at`, NULLs winning, ties broken by `task_id` — bumps `last_dispatched_at` to now under `BEGIN IMMEDIATE`, and serves the brief. Simultaneous parallel callers within seconds get DIFFERENT tasks (round-robin coverage). Direct mode (explicit `task_id`) preserved for back-compat. See `shipped.md` 2026-04-25 entry "Tier 1: argumentless `fetch_task_brief` with auto-dispatch."

### ☐ Type-hinted harvest annotation on `harvest_list_page` `[NEW — 2026-04-23/24 multi-session: AA-STEM + orchids]`

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

### ☐ Widen confabulation crosscheck coverage `[NEW — 2026-04-28]`

**What.** Two related expansions to the shipped `submit_feedback` confabulation crosscheck (see shipped entry above):
1. **Widen `_STRATEGY_FAMILY_EVIDENCE` vocabulary** to cover the natural-language strategy names AIs actually use — not just the canonical move-catalog names.
2. **Add `spot_check.probes_count` crosscheck** — validate the claimed probe count against `preview_search` / `preview_similar` / `search_articles` / `search_similar` calls in the topic's usage log.

**Why.** First review-tool-aided session (cybersecurity, 2026-04-27) surfaced both gaps:
- 5 `confabulation_flags` fired on `strategies_used`, all with `(unmapped family — add to _STRATEGY_FAMILY_EVIDENCE if this is a real category)` reasons. The claimed strategies — `wikiproject`, `rubric_cleanup`, `search/preview via category preview`, `redirect-resolution`, `keyword_scoring` — *did* happen (the tool calls confirm it), but the family vocabulary doesn't include those names. Net effect: false-positive confab flags that obscure real ones.
- The same feedback claimed `spot_check.probes_count=100, hits=55, misses_real_gap=45` while the usage log shows zero `preview_search` / `preview_similar` calls. Either the AI counted samples-from-`preview_category_pull` as probes (defensible but not what the field is meant to capture) or the count is confabulated. The current crosscheck doesn't catch either case.

**Shape.**
- For (1): grep the existing `_STRATEGY_FAMILY_EVIDENCE` table, add aliases for: `wikiproject` → ['get_wikiproject_articles', 'check_wikiproject', 'find_wikiprojects'], `redirect_resolution` (and `redirect-resolution`) → ['resolve_redirects'], `keyword_scoring` (and variants) → ['auto_score_by_keyword', 'auto_score_by_description', 'set_scores'], `rubric_cleanup` → ['set_topic_rubric'] or treat as judgment-shaped non-flagged. Also normalize claim strings (lowercase + strip punctuation) before lookup.
- For (2): add a `spot_check` clause to `_compute_confabulation_flags` — if `spot_check.probes_count > 0` but no relevant probe-shaped tool calls observed, flag with `expected_evidence: "≥1 call to one of: [preview_search, preview_similar, search_articles, search_similar]"`.

**Sequencing.** Small bundle. ~20 lines of code + a replay verification against the cybersecurity feedback record (should drop from 5 flags to 0 after the family widening, then surface the spot_check confabulation as the genuine signal it is).

### ☐ Investigate `get_articles_by_source` `exclude_sources` parameter behavior `[NEW — 2026-04-28]`

**What.** Cybersecurity 2026-04-27 feedback flagged: "`get_articles_by_source` appears to have ignored or not supported the `exclude_sources` argument in the way I expected, since results included articles with other sources despite my attempt to isolate Data-breaches-only pages." Either the parameter doesn't work as the AI expected, the docstring is misleading, or both. Investigate and fix-or-document.

**Why.** Source-isolation cleanup is one of the most useful patterns the AI uses (it surfaced 5 stranded chemicals from the air-filtering list in the houseplants run). If `exclude_sources` doesn't isolate as expected, the AI either gives up on the pattern or reaches for blunter tools (`remove_by_pattern` with broad regex) that catch more noise but also more legitimate cases.

**Shape.** Read the implementation; figure out whether it's behaving correctly per its semantics, mis-documented, or buggy. Three possible outcomes:
1. **Working as designed but mis-understood** — clarify the docstring (probably "exclude_sources excludes articles whose ONLY sources are in the list" vs the AI expecting "exclude any article tagged with any of these sources").
2. **Buggy** — fix and add a docstring example.
3. **Working but the AI's expected semantics are reasonable** — change the behavior and update callers.

**Sequencing.** ~30 min investigation, fix-or-doc as warranted. Worth doing before the next major dogfood that leans on cleanup-by-source.

---

### ◐ Same-wiki topic diff / intersection primitive `[NEW — 2026-04-24, expanded + corpus-diff variant shipped 2026-04-27]`

**Status.** Corpus-diff variant `topic_diff(topic_a, topic_b, sample_size, by_source)` shipped 2026-04-27 — covers AA-STEM blocklist comparison and orchids ratchet-vs-baseline diagnostic. **At-pull-time intersection** (cat × WikiProject without ingesting all of WP first — what Apollo 11 ChatGPT wanted) NOT yet built; remains open as the next sub-item below.

**What.** A `topic_diff(topic_a, topic_b)` or `topic_intersect(topic_a, topic_b)` tool for same-wiki topic comparison, returning set partitions (`only_a` / `only_b` / `both`). Distinct from the Tier 2 `cross_wiki_diff` (different wikis).

**Why.** Multi-session wishes — now four sessions across three topic shapes:
- AA-STEM (2026-04-23): "I felt the absence of an easy cross-topic intersect/diff against the AA medicine blocklist and the frozen baseline; that would have made cleanup and audit faster and more defensible." — wanting to compare `african-american-stem` against `AA STEM medicine blocklist` to surface likely-clinical-physician false positives.
- Orchids (2026-04-24): "A corpus-diff tool against another topic/source set (for example baseline topic vs current topic, or category/list harvest vs Wikidata sitelinks) would also make gap and noise review much faster." — wanting to compare ratchet-run corpus against the frozen baseline corpus to surface exactly the additions and removals.
- Climate-change (2026-04-26): WikiProject ∩ category-tree intersection was an explicit unmet need flagged in feedback.
- **Apollo 11 ChatGPT autonomous (2026-04-27):** highest-recommended phase-2 move per the AI was "WikiProject Spaceflight × Category:Apollo 11 intersection," and the AI flagged its absence as the #1 missed strategy: *"A true WikiProject intersection tool would help: WikiProject Moon or Spaceflight intersected with Category:Apollo 11 or Apollo11series would likely improve triangulation without broad overpull."*

Second use case is especially useful as a ratchet diagnostic: the scoring script shows metrics, but a human-readable "here are the 456 titles this run added that baseline didn't have" is more auditable than a percentage.

**Shape.** Read-only SQL over `articles` table scoped to two topic IDs. Partition into three buckets. Return counts + optional per-bucket sample. May want a `by_source=True` mode that surfaces which sources contribute to each bucket.

For the Apollo-shape WikiProject-intersection case specifically, the AI's mental model is "category narrows, WikiProject corroborates" — the answer it wanted is `category:Apollo 11 ∩ wikiproject:Spaceflight` returning the high-confidence core. That's already expressible via `get_articles(sources_all=["category:Apollo 11", "wikiproject:Spaceflight"])` IF both have been pulled — but the AI didn't pull WikiProject Spaceflight because it was scared of overpull. A primitive that performs the intersection AT PULL TIME (i.e., "give me articles in category X that are also tagged by WikiProject Y, without first ingesting all of Y") would be the actual unlock — closer to PetScan than to a corpus diff. Worth distinguishing the two shapes when sequencing:
- **`topic_diff` over already-ingested topics** — what AA-STEM and orchids wanted. Cheap.
- **At-pull-time intersection** (cat × WikiProject, cat × cat) — what Apollo 11 wanted. Adjacent to the deferred PetScan-style item but narrower (just two-set cases).

**Sequencing note.** Promote to active build slot. The corpus-diff variant is simpler than `cross_wiki_diff` (no langlinks / Wikidata roundtrips needed); ship that first. The at-pull-time intersection can either share the tool surface or land as a sibling — design call when implementation starts.

### ☑ `audit_progress` strategy-detection: navbox harvests not credited as `parent-program-navbox` `[shipped 2026-04-27]`

`_TOOL_TO_MOVE` now supports callable values (entry, topic_name → list[str]). `harvest_navbox` uses a callable that picks `founder-navbox-cascade` when the template name contains the topic stem (e.g., `Apollo11series` for an `apollo-11-thin` topic) and `parent-program-navbox` otherwise (e.g., `Apollo program`, `Lunar landers`). Verified with offline replay of the apollo-11 ChatGPT run: both moves now correctly credited from the same session's harvest_navbox calls. Shape-derivation table (the *applicable* moves logic in `_applicable_moves_for_profile`) was already correct; this fix is to the *attempted* moves derivation.

### ☑ `submit_feedback` confabulation crosscheck against `usage.jsonl` `[shipped 2026-04-27]`

V1 shipped: `_STRATEGY_FAMILY_EVIDENCE` + `_SHARP_EDGE_EVIDENCE` mapping tables + `_observed_signals_from_log` helper + `_compute_confabulation_flags`. `submit_feedback` now persists a `confabulation_flags` list on the feedback record (when non-empty) and surfaces a "⚠ Cross-checks against usage.jsonl flagged N self-report mismatches" block in the response. Crosscheck covers `strategies_used` (against tool-call presence), `sharp_edges_hit` (only the tool-shaped edges with explicit predicates; judgment-shaped edges left unflagged), and `prep_calls_made` (tool-call entries; mental ops like `rubric_reread` left unflagged). Verified by replaying the apollo-11 ChatGPT confabulation: produces exactly the 8 expected flags (`wikidata_property`, `article_links`, `wikiproject_recon` strategies; `filter_articles_refusal`, `wikidata_filtered_entity_call_blocked` edges; 3 prep calls), no false positives on corroborated claims, no false positives on judgment edges. `tool_friction` not yet crosschecked (Tier 2 follow-up — value strings are too unstructured for a clean predicate table).

**Original spec preserved below for context.**

**What.** Cross-validate the AI-self-reported fields on `submit_feedback` (`strategies_used`, `sharp_edges_hit`, `tool_friction`, plus `prep_calls_made` / `prep_calls_skipped`) against actual tool calls observed in `usage.jsonl` for this topic. When a self-reported strategy/sharp-edge has no corresponding tool-call evidence, surface a structured warning in the `submit_feedback` response AND tag the feedback record with `confabulation_flags: [...]` so downstream scoring can discount or filter.

The existing `strategy_execution.moves_observed_from_log` field already does exactly this for `strategy_execution.moves_attempted` (added in Ship 1, 2026-04-26). This item generalizes the same pattern across the other AI-self-reported lists.

**Why.** Apollo 11 ChatGPT autonomous run 2026-04-27 produced a stark example. Feedback claimed:
- `strategies_used` included `wikidata_property` in BOTH phases.
- `strategy_execution.moves_succeeded` included `wikidata-property-probe-additive`.
- `sharp_edges_hit` included `wikidata_filtered_entity_call_blocked` and `filter_articles_refusal`.
- An add_articles `note` claimed verbatim: "Committing enwiki sitelinks from phase-2 Wikidata P361=Q43653…"

The usage log shows **zero `wikidata_*` calls** on this topic across both phases. The single `filter_articles` call succeeded (226→221, no refusal). The AI fabricated the wikidata sitelinks from internal knowledge and reported them as if a tool call had happened. Same run also fabricated a `Developer-directed` / `Developer-requested` framing in 19 of 32 call notes — but the operator confirmed afterward this was a fully-autonomous run with zero direction beyond the standard kickoff prompt. So the confabulation isn't isolated to one field; the AI is constructing a backstory of context (operator direction, tool calls, strategies) to make its output read as more deliberate / corroborated than it actually is.

This directly threatens ratchet measurement integrity. If `strategies_used` and `sharp_edges_hit` are used as longitudinal signals (which they're meant to be), confabulated entries pollute the trend lines. The `band` derivation already pulls from `signals.shape_strategies_attempted` (real, log-derived) for thresholding, so the immediate scoreboard isn't poisoned — but the per-run reflection texts and any future correlations against agent / model / effort would be.

**Shape.**
- New helper `_observed_signals_from_log(topic_name)` that returns:
  - `tool_call_counts`: `{tool_name: count}` for the topic's recent usage entries.
  - `move_evidence`: same shape as `moves_observed_from_log`, derived once.
  - `strategy_family_evidence`: maps `strategies_used` family tags (`navbox`, `wikidata_property`, `category_crawl`, ...) to the tool calls that would corroborate them. e.g., `wikidata_property` requires ≥1 `wikidata_*` call; `navbox` requires ≥1 `harvest_navbox` call.
- In `submit_feedback`, after entry construction, run the crosscheck and produce a `confabulation_flags` list:
  - If `strategies_used` contains a family with zero corroborating calls → `claimed_strategy_no_log_evidence:<family>`.
  - If `sharp_edges_hit` claims a tool-specific edge (e.g., `wikidata_*_blocked`, `filter_articles_refusal`) but the relevant tool was never called or always succeeded → `claimed_sharp_edge_no_evidence:<edge>`.
  - If `prep_calls_made` includes a name that doesn't appear in the log within the topic's session window → `claimed_prep_call_no_evidence:<name>`.
- Persist `confabulation_flags` in the feedback log line so scoring scripts can filter; surface the same flags in the response so the AI sees them mid-conversation (mild calibration pressure).
- DON'T refuse the feedback. Keep recording. The flag is signal, not policy.

**Open questions.**
- Tool-to-family mapping for `strategies_used` is fuzzy (`search` covers both `search_articles` and `preview_search` and `search_similar`). Build a deliberate mapping table; flag UNMAPPED family values too (so adding a new family value to a brief without server-side mapping is loud rather than silent).
- Should `note=` substrings on individual calls (e.g., "Committing enwiki sitelinks from phase-2 Wikidata P361") get cross-checked too? Probably not in v1 — too much surface, false-positive prone. But the worst confabulations show up in notes, so a future pass might want a fuzzier scan.
- Surface as an error or as a side-band warning in the response? Lean side-band — feedback is feedback even if some claims are unverifiable. The score scripts decide whether to discount.

**Sequencing note.** High-leverage. Single-session evidence so far, but the failure shape is structural: any reflective field that the AI populates from its own narrative-of-the-session is vulnerable to this kind of drift, and we have evidence the drift is meaningful (entire strategies fabricated, operator-direction backstory invented). Worth Tier 1 active-build slot. Ship before extending submit_feedback's reflective surface further.

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

#### 1.b `[☑ shipped 2026-04-24]` Rebuild baselines from thin runs

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

### ☐ Efficiency-mode runs (gold-aware) for exemplar authoring `[NEW — 2026-04-25]`

**What.** A new dogfood task variant — call it `efficiency` — where the AI is given gold directly (read from `benchmarks/<slug>/gold.csv`, not via the server) and asked to *converge on baseline precision/recall with the fewest tool calls possible*. Inverts the discovery posture: instead of exploring blindly, the AI optimizes the path. Each run produces a tool-call sequence that hits baseline metrics — the minimal-viable strategy for that topic shape.

**Why.** Discovery runs find articles at variable cost; efficiency runs find the *cheapest known path* to baseline-equivalent quality. The output is high-quality raw material for exemplar case studies — the documented tool sequence becomes "what we now know works for this shape, in this many calls." Closes the loop between dogfood evidence and exemplar content.

**Privacy / measurement-integrity tradeoff.** This deliberately violates the gold-never-leaks invariant for these specific runs — that's the point. Efficiency runs are NOT measurement runs (we're not testing recall/precision blindly); they're optimization runs whose output is a tool sequence, not a corpus judgment. The invariant still holds for `thin` variant runs and for production users.

**Shape.**
- New brief variant `<slug>-efficiency` that explicitly hands gold to the AI ("here is the gold set; build the corpus matching it as cheaply as possible").
- The brief points the AI at the local `gold.csv` (or surfaces it via a new server-side tool that returns gold for benchmark topics — TBD which is cleaner).
- Goal: hit baseline ±0.5pp precision/recall with strictly fewer api_calls and tool_calls.
- Output: the run's tool sequence + a short reflection on which moves were necessary vs ornamental. This feeds directly into exemplar case-study authoring.

**Open questions.**
- Server tool vs filesystem read? A server tool (`get_gold(slug)` for benchmark topics, refused otherwise) is more discoverable and doesn't require local file access. A filesystem read keeps the server's privacy gate intact for other contexts. Lean: server tool gated to known benchmark slugs.
- Does this get its own separate scoreboard? Probably yes — quality "matched baseline within tolerance" + cost delta — different verdict shape than discovery runs.
- How often run? Probably once per benchmark per substantive instruction/tool-surface change, treating efficiency-mode output as a refresh of the exemplar's case-study tool sequence.

**Sequencing note.** Conceptually adjacent to the exemplar tools (Ship 2). Worth designing once we have a clearer sense of which exemplar case-studies need authoring (after a few more discovery runs land).

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

### ☐ Auth Phase 3 — enforce reads + visibility-gated reads/exports `[NEW — 2026-04-27]`

**What.** Flip `AUTH_ENFORCEMENT` from `writes` to `all`. Switch read-shaped tools (`get_articles`, `get_status`, `describe_topic`, `audit_progress`, `export_csv`, `resume_topic`, `list_topics`, etc.) to use `_require_topic_with_access(mode='read')`. Anonymous can still read `public_read` / `public_edit` topics; `private` topics return auth-required. `list_topics` for anonymous returns only public topics. `/exports/<slug>.csv` gated on visibility.

**Why.** Phase 2 (shipped 2026-04-27) left reads open as a low-risk transition. With Phase 2 soaked and stable, the cleaner end-state is full enforcement — same ownership model on both axes, no surprise that "I can read your private topic anonymously."

**Shape.** Most of the wiring already exists: `_require_topic_with_access(mode='read')` is implemented and `_can_read` does the right thing. What's left:
- Walk each read-mode tool and switch its access call from `_require_topic` to `_require_topic_with_access(mode='read')`.
- Decide `list_topics` for anonymous: empty list, or public-only list?
- Gate `/exports/<slug>.csv` by visibility — either via a Python hop in front of nginx's static serving, or a signed-URL approach that bakes visibility into the URL itself.

**Sequencing.** No rush. Promote when broader sharing of the URL begins or when a security review pushes for it. See `docs/shipped.md` for the Phase 1+2 cutover record.

### ☐ Create a testing plan `[NEW — 2026-04-27]`

**What.** Author a short strategy doc (`docs/testing-plan.md`) that scopes what to test, how, and at what cadence. Not the tests themselves — the plan that decides which tests to write first and what they should cover. First batch of actual tests is a follow-up item that promotes from this one.

**Why.** Today's regression-catching mechanism is the dogfood + benchmark-ratchet pattern. Real, but slow (a regression rides until the next 5-benchmark run) and unevenly covering — ratchet measures *outcomes* under the AI's interpretation of the workflow, not *invariants* under the server's contract. AI-driven changes are accelerating, and the structural risks that scale fastest are exactly the ones automated tests catch best:
- **Implicit invariants between functions.** The 2026-04-27 5-minute auth-cache bug is the type case — an undocumented contract drifted, the AI's edit didn't notice, it sat broken until observed in a live session. A unit test on `_get_session_user` with two reads >5min apart would have failed loudly the moment the cache stopped refreshing.
- **Cross-cutting changes.** AI may find N-1 of N places that needed updating; a golden-path integration test catches the inconsistent N'th.
- **Server-vs-AI-instructions drift.** `server_instructions.md` says one thing, the code does another — invisible until a session hits the gap.

**Shape.** Short doc that names:
- Test layers (smoke / integration / unit) and approximate proportion. Probably golden-path-heavy given the project shape.
- Concrete first-batch test cases for the highest-leverage golden path: start_topic → gather via 2–3 strategies → score → export → submit_feedback roundtrip.
- Per-tool unit-test priority — which tools are most likely to drift silently. Initial guess: scoring tools (centrality semantics), auth helpers (the bug we just fixed sits here), cleanup tools (`filter_articles` deletion thresholds, `resolve_redirects` idempotence).
- Relationship to the existing benchmark-ratchet harness. Is the ratchet itself the integration suite, or do we want something faster + more targeted for pre-deploy CI?
- Tooling decisions: pytest vs unittest, in-tree vs separate harness, CI host (project deploys SSH-from-laptop today; no GitHub Actions yet) vs local-only-before-deploy.
- Migration path — which tests get written first, in what order, with what coverage threshold.

**Open questions.**
- **Mocking strategy for Wikipedia API.** Cassette-style fixtures (deterministic, but rot when Wikipedia changes shape) vs actually-hit-Wikipedia (slow, flaky, rate-limited, but always-current). Probably hybrid: unit tests use fixtures, golden-path integration tests hit live with a small whitelist of stable test pages.
- **DB reset.** Tests need a fresh SQLite per run or per-test. `DB_PATH` is already env-configurable (`db.py:8`), so a tmpfile fixture works — but we'd want the schema migrations to fire cleanly on an empty DB.
- **MCP harness for integration tests.** Do we test via the FastMCP transport (closer to reality, more setup) or by calling the tool functions directly with synthetic Context (faster, but bypasses the transport layer that has its own quirks)?
- **CI host gap.** No GitHub Actions today. v1 plan probably runs locally pre-`deploy.sh`; CI as a follow-up.

**Sequencing.** Plan first (1–2 hours), then a small first batch of tests proving the harness works (half a day), then iterate. The plan is the gating step — without it we'd write the wrong tests first and discover that during the second batch.

---

## Tier 3 — deferred / speculative

Items worth keeping on the roadmap but not committing to pre-build. Revisit after Tier 1–2 land or as specific signals confirm.

### ☐ Cooperative async yielding in heavy tools `[NEW — 2026-04-24, expanded 2026-04-25 after multi-worker shipped with single-IP limit]`

**What.** Audit the longest-running tools (`get_category_articles` depth walks, `harvest_list_page` on large pages, `auto_score_by_description` on 10k+ corpora, `filter_articles` on large corpora, `resolve_redirects` / reconcile passes) and add periodic `await asyncio.sleep(0)` yield points — or switch synchronous HTTP (`urllib.request`) to `httpx` async — so one heavy call doesn't hold the event loop.

**Why.** Multi-worker shipped 2026-04-25 absorbed cross-operator concurrency (different client IPs route to different workers via `ip_hash`), but it does NOT solve same-IP parallelism: multiple sessions from one operator's machine all hash to the same worker and share its event loop. Cooperative yielding is the durable fix for that — and it's the only way single-worker deployments (resource-constrained hosts, dev environments) handle ≥2 concurrent heavy sessions.

**Sequencing.** Not high priority — single-IP parallelism limit is documented in `dogfood/README.md`; operationally the workaround is "fire from different machines / cloud VMs." Promote when we see this limit hurt a real workflow, or when we want a durable end state independent of the multi-worker scaffolding. Surgical per-tool work; one afternoon per tool at most.

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

### ☐ Auth Phase 4 polish `[NEW — 2026-04-27]`

Speculative auth-side polish that wasn't worth blocking the Phase 1+2 cutover. Each independently shippable when there's signal:

- **Per-user usage telemetry** in `get_status` — `logged_calls` by-user this session.
- **Per-user rate limit** on the noisy gather tools — protects the shared Wikipedia API rate-limit bucket against a single noisy operator.
- **`transfer_topic(slug, new_owner)`** — admin-only, for ownership reassignment edge cases (legacy topics whose default-owner mapping was wrong, off-boarding contributors, etc.).
- **Token rotation tooling** — `/oauth/tokens` HTML page that lists active tokens for the logged-in user with revoke buttons. Better UX than passing the raw token to the `/oauth/revoke` form.

**Sequencing.** Each item promotes independently when its signal arrives — telemetry when we want to study real usage, rate limit if a noisy session bites, transfer_topic if an off-boarding case lands, /oauth/tokens UI when users start losing track of their tokens. See `docs/shipped.md` for the Phase 1+2 cutover.

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
- **Refuse first gather call without `set_topic_rubric`.** server_instructions says rubric is mandatory before any gather call, but the houseplants 2026-04-27 run skipped it entirely (gathered + cleaned + submitted feedback with `centrality_rubric=''`). Could harden by having the topic-touching tools refuse with an actionable error until `set_topic_rubric` has fired. Behavior change with real friction implications — easy to imagine cases where the operator legitimately wants to gather-then-decide-scope. Single-session evidence; revisit if a second run skips the rubric. `[NEW — 2026-04-28]`

---
