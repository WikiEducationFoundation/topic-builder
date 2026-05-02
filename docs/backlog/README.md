# Backlog — open items

Pending items from the improvements plan, grouped by priority tier.
Shipped items are logged in `../shipped.md`. `../ratchet-plan.md` is
the "what to work on next" entry point and draws its shortlist from
this doc.

Sibling docs in this directory hold larger deferred plans:
- `impact-visualizer.md` — publish_topic handle → Impact Visualizer import.

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

### ☑ Validate `<slug>-exploratory` format on a second topic `[NEW — 2026-04-28; satisfied 2026-04-28 same-day by orchids exploratory id=72]`

**What.** Run `dogfood/kickoffs/exploratory-calibration.md` against one differently-shaped benchmark topic before promoting the brief to a seeded `<slug>-exploratory` task variant in `dogfood_tasks`. If the Phase-2 calibration report structure holds under a different shape, collapse the kickoff to "call fetch_task_brief and follow its instructions" and move the brief body into `dogfood/tasks/<slug>-exploratory.md`.

**Verdict.** Format validated. Climate-change exploratory (id=71, policy-movement-culture shape) and orchids exploratory (id=72, taxonomy-dominated shape) both produced rich Phase-2 calibration reports under the prescribed structure. Different shapes surfaced different findings (climate-change: harvest_navbox redundancy, llm-fabricate gap-detection, shortdesc false-positives; orchids: country-level-list-page-harvest, morelike-niche-vs-cultural-anchor split, browse_edges precondition). Both cleared ~45–55 metered calls — well under the 80 ceiling. Promote per the follow-up item below.

### ☐ Seed `<slug>-exploratory` task variants in `dogfood_tasks` `[NEW — 2026-04-28, follow-up to validation above]`

**What.** Move the exploratory-calibration brief body from `dogfood/kickoffs/exploratory-calibration.md` into per-slug task files at `dogfood/tasks/<slug>-exploratory.md`, seed them via `scripts/seed_dogfood_tasks.py`, and collapse the kickoff to `Call fetch_task_brief(task_id="<slug>-exploratory"), then follow its instructions.` Mirror the structure used for the `-thin` ratchet variants today.

**Why.** Format-validation prerequisite cleared (climate-change + orchids exploratory, 2026-04-28). Seeded variants enable round-robin dispatch via `fetch_task_brief()`, deduplicate the Hard-coverage list across slugs, and let per-topic refinements (e.g., orchids should pre-name the depth=4 vs depth=3 cap) live in the per-slug brief instead of the shared kickoff.

**Shape.** One markdown file per benchmark slug (`apollo-11`, `crispr-gene-editing`, `african-american-stem`, `hispanic-latino-stem-us`, `orchids`, `climate-change`) under `dogfood/tasks/<slug>-exploratory.md`, plus an updated `scripts/seed_dogfood_tasks.py` to register them. Per-slug files share the Hard coverage requirements + Phase-2 deliverable structure, but each one names its own (a) likely high-leverage moves on this shape, (b) likely refused/inapplicable moves with reasons (e.g., orchids: "no `harvest_navbox` — taxobox utilities only"), and (c) any topic-specific gotchas (e.g., orchids: "use Category:Orchids common name; Category:Orchidaceae Latin form is empty").

**Open questions.**
- Does the kickoff document stay around as a "how to author a new `<slug>-exploratory` brief" guide, or does it collapse to a one-liner? Probably stays as authoring guide since the substrate is still evolving.
- Same brief body for all 6 slugs (de-duplicating happens at fetch time), or per-slug variations baked in? Lean per-slug — that's why we're seeding rather than templating.

**Sequencing.** Tier 1 — small, mechanical follow-up. ~6 markdown files + seed-script update.

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

### ☐ `harvest_navbox` preview mode / template discovery `[NEW; multi-shape evidence on filter heuristic 2026-04-28]`

**What.** Post-ship extensions to the `harvest_navbox` tool that landed in the post-orchids chunk batch:
1. **Preview mode** — `preview_harvest_navbox(template)` returning candidate title count + sample without committing, matching the `preview_*` convention.
2. **Template discovery** — a helper that returns candidate navbox/infobox templates for a topic article, so the AI doesn't have to guess the template name.
3. **Tighten the navbox-name regex in `get_article_templates(filter='navbox')`.** Current heuristic returns false positives across multiple topic shapes — it's filtering on name pattern rather than actual template kind.

**Why.** `harvest_navbox` is the right tool for award / franchise / program shapes (apollo-11, crispr-gene-editing peripheral, pop-culture shapes) — but the AI has to know the exact template name, and has no dry-run surface before committing. Same friction `preview_harvest_list_page` / `preview_category_pull` resolved for their commit variants.

The filter-heuristic noise is now multi-shape:
- Climate-change exploratory (2026-04-28): `get_article_templates(title="Climate change", filter="navbox")` returned 30 templates of which 27 were utility templates; the 3 actual content navboxes had to be inferred from article body.
- Orchids exploratory (2026-04-28): `get_article_templates(title="Orchid", filter="navbox")` returned 32 templates, ALL 32 were taxobox utility infrastructure (`Automatic taxobox`, `Edit taxonomy`, `Period color`, etc.). Zero real content navboxes; AI confirmed via the templates list that no thematic family navbox exists for Orchidaceae.

The pattern: name-regex matching catches utility templates whose names happen to match navbox naming conventions. A more reliable filter would inspect template content (look for `class="navbox"` / `wikitable navbox` markers) or check the template's own categories (`Category:Navigational boxes`).

**Shape.** Preview: small wrapper over existing `harvest_navbox` internals that returns count + sample. Discovery: given an article title, list templates used on that page (via `prop=templates`), filter to likely navboxes by inspecting the template's own page (categories / class markers) rather than name pattern alone.

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
- **Soft-redirect category hint on empty `survey_categories` result.** If `survey_categories` reports an existing category page with 0 articles (container/redirect category), emit a "try sibling X instead" hint. K-drama dogfood surfaced this on `Category:Korean television dramas` → should have pointed at `Category:South Korean television series`. Orchids exploratory (2026-04-28) added a same-shape case: `Category:Orchidaceae` (Latin form) is structurally empty on enwiki; canonical content lives at `Category:Orchids` (common name). One wasted survey call before the AI re-tried. Now multi-session — the Latin-vs-common-name failure is structural for biology topics. Needs sibling-finding logic — probably scan for same-prefix categories via `prop=categories` on the empty category page, or check Wikidata sitelinks for the topic QID and surface alternative category names. `[NEW — 2026-04-23 dogfood run 2; +2026-04-28 orchids exploratory]`
- **`auto_score_by_description` substring-matching edge on proper-noun words.** Pulitzer feedback: `disqualifying=["city", "county"]` would reject "The Kansas City Star" and "Orange County Register" because the geographic word is part of the institution's proper name. Word-boundary match alone doesn't fix it ("City" IS a word). Possible approaches: case-sensitive lowercase-only match, exclude matches where the word is part of a proper-noun phrase, or an "exclude-unless-preceded-by-lowercase" mode. **2026-04-28 climate-change exploratory adds two more cases**: `"video game"` rejects the canonical "Climate change video game" (substring matches title prefix), and `"manufacturer"` hits legit-periphery industrial actors (Solectrac electric tractor mfr, Skeleton Tech battery). Now multi-session evidence; promote to a tier above. No obvious right answer — more thought required. Adjacent item in Tier 1 ("Catalog refinements from exploratory calibrations") adds a documentation-side warning to `auto-reject-by-disqualifying-shortdesc` in parallel. `[NEW — 2026-04-23 dogfood run 2; +2026-04-28 climate-change exploratory]`
- **`remove_by_pattern` description-match misfires on geographic descriptors that overlap biome / place names.** Orchids exploratory (2026-04-28): a dry-run `remove_by_pattern(pattern="province", match_description=True)` would have dropped *Satyrium coriifolium*, a real Cape Province orchid whose description contains "Cape Provinces". The substring match doesn't distinguish "geographic descriptor in a real taxon's range" from "off-topic place article". Same family as the `auto_score_by_description` proper-noun edge case above. Possible approaches: paired markers, surface-as-suggestion-not-rejection, or constrain to "description contains pattern AND title doesn't contain a topic-vocabulary token". The dry-run-first habit caught it this time, but worth surfacing in the docstring or the catalog warning. `[NEW — 2026-04-28 orchids exploratory]`
- **Refuse first gather call without `set_topic_rubric`.** server_instructions says rubric is mandatory before any gather call, but the houseplants 2026-04-27 run skipped it entirely (gathered + cleaned + submitted feedback with `centrality_rubric=''`). Could harden by having the topic-touching tools refuse with an actionable error until `set_topic_rubric` has fired. Behavior change with real friction implications — easy to imagine cases where the operator legitimately wants to gather-then-decide-scope. Single-session evidence; revisit if a second run skips the rubric. `[NEW — 2026-04-27]`
- **Identify a group of core editors for a topic, exported as a `topic-users-<slug>.csv` for IV `import_users`.** TB currently produces only the article CSV; the IV pipeline also accepts a parallel users CSV (one Wikipedia username per row) that drives the editor-activity side of the visualization. A TB-side tool that surfaces likely "core editors" for a topic — e.g. top contributors across the topic's articles by edit count, weighted by centrality, optionally filtered by editor-namespace activity — would close the second half of the TB → IV handoff. Output shape mirrors the article CSV: one column, no header, slug-based filename. Open: do we lean on an existing tool (XTools, Wikidashboards) for the per-article contributor data, or compute it natively via revisions API? Speculative until a real session asks for it; flag as a natural follow-up to the article-side handoff. `[NEW — 2026-04-30, surfaced during TB → IV CSV ingestion testing]`

---
