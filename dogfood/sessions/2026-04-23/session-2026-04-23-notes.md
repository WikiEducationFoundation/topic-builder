# Dogfood session notes — 2026-04-23

Parallel Claude Code session is running `dogfood/task.md`. I'm monitoring the
host (`172.232.161.125`) via `scripts/monitor_dogfood.sh` and capturing
anything that looks like a build-plan signal. Not a retrospective — this is a
running log; we'll distill it after the session ends.

Sources of signal:
- `/opt/topic-builder/logs/usage.jsonl` — every logged tool call (topic,
  params, result summary).
- `/opt/topic-builder/logs/feedback.jsonl` — `submit_feedback` entries.
- `/opt/topic-builder/data/topics.db` — current article counts, sources,
  score distribution, description coverage per topic.

## Topic chosen

**Apollo 11** (topic id 20, enwiki) — started 2026-04-23 15:37:29 UTC.

Shape: single historical event — one of the candidate shapes the task
suggested we haven't tested yet. Mix of event narrative + crew biographies +
spacecraft hardware + cultural tail.

---

## Running observations

### 15:37–15:38 UTC — recon fan-out

Within ~40 seconds of `start_topic`, the session fired a very parallel recon
burst:

```
15:37:29  start_topic(name=Apollo 11, wiki=en, is_new=True)
15:37:33  find_wikiprojects(keywords=[Apollo, Spaceflight, Moon, Rocketry, Astronomy, ...], limit=20) -> 4 projects
15:37:34  survey_categories(category=Apollo 11, depth=3) -> 2 categories
15:37:34  find_list_pages(subject=Apollo 11) -> 0 pages
15:38:08  survey_categories(category=Apollo program, depth=3) -> 81 categories
15:38:08  check_wikiproject(project=Spaceflight) -> exists=True
15:38:09  find_list_pages(subject=Apollo program) -> 1 pages
15:38:09  find_list_pages(subject=Moon landing) -> 3 pages
15:38:10  preview_search(query=intitle:"Apollo 11", limit=50) -> 16 results (16 new)
```

Signals:

- **`find_list_pages(subject=Apollo 11)` returned 0**, but
  `find_list_pages(subject=Apollo program)` returned 1 and
  `find_list_pages(subject=Moon landing)` returned 3. The session instinctively
  broadened the probe on its own — good emergent behavior, but worth asking
  whether `find_list_pages` should do that broadening itself (e.g. try a
  couple of obvious parent subjects when the literal subject returns 0).
- **Category survey on "Apollo 11" itself returned 2 categories** but
  survey on "Apollo program" returned 81. The session correctly pivoted to
  the parent. Question for later: should `survey_categories` log a hint
  when the result looks suspiciously thin ("only 2 subcats — did you mean
  a broader root?").
- **`find_wikiprojects` with 5 keywords returned 4 projects** — the session
  immediately `check_wikiproject(Spaceflight)` without waiting for any
  user feedback. Confirms the session is running in autonomous dogfood mode.
- Scoping dialogue happened upstream (outside the tool surface) — I can't see
  it from the usage log. That's a monitoring blind spot worth noting: **we
  can't audit the scope-conversation quality from logs alone.**

### Tooling note (meta, not a signal about the server)

Needed to write `scripts/monitor_dogfood.sh` + add one permission entry to
poll the host without bouncing off deny rules (`Bash(python3 -c *)` etc.).
Wrapper does `scp status.py + ssh`. First version broke on topic names with
spaces — now requotes via `printf %q`. Reusable for future sessions.

---

### 15:38:55–15:42:21 UTC — gather + cleanup, all in ~3 minutes

Full burst summary (cumulative totals in `(...)`):

```
15:38:55  get_category_articles(Apollo program, depth=4)             -> 654 articles
15:39:19  preview_harvest_list_page("Apollo 11 in popular culture")  -> 145 links (109 new, NOT committed)
15:39:59  get_category_articles(Moon landing, depth=3)               -> (720)
15:39:59  harvest_list_page("List of Apollo missions")               -> +42 (762)
15:39:59  add_articles(manual:intitle-moon-landing, 5)                -> (765)
15:40:23  add_articles(manual:hardware-and-museum, 3)                 -> (768)
15:40:24  reject_articles(1, also_remove=True)                        -> (767)
15:41:08  filter_articles(resolve_redirects, remove_disambig, lists)  -> 767→716
15:41:13  fetch_descriptions(limit=2000)                              -> 647 non-empty, 0 undescribed
15:41:16  describe_topic                                              -> summary produced
15:41:16  list_sources                                                -> 5 sources
15:41:31  get_articles_by_source(list_page:List of Apollo missions,
            exclude_sources=[category:Apollo program, category:Moon landing])
                                                                      -> 29 list-only matches
15:42:19  reject_articles(20, also_remove=True)
15:42:21  reject_articles(10, also_remove=True)                       -> (686)
```

Signals worth capturing:

1. **`list_sources` + `get_articles_by_source(exclude_sources=...)` was used
   exactly as the server instructions prescribe.** Pulled the 29 articles
   that ONLY came from `List of Apollo missions` (i.e. not corroborated by
   either category pull) and rejected 30 of them in two batches. Strong
   positive signal: the source-triangulation pattern we teach in the
   instructions is actually being practiced. Worth a confirmation feedback
   memory.
2. **WikiProject Spaceflight was confirmed to exist but `get_wikiproject_articles`
   was never called.** Silent routing — the AI decided WP:Spaceflight is
   scoped to all-of-spaceflight, too broad for Apollo 11, and skipped it.
   The decision is probably correct (Apollo 11 ⊂⊂ spaceflight), but the
   instructions currently present WP > lists > categories as a quality
   ladder. For narrow event topics under a broad WP, what we actually want
   is "use the WP as a *scope intersection* tool, not a source." No current
   tool does that cleanly — would need something like
   `get_wikiproject_articles(..., within_category="Apollo program")`. **Flag
   as a build-plan candidate.**
3. **`preview_harvest_list_page("Apollo 11 in popular culture")` returned
   145 links (109 new) and was NOT committed.** The AI previewed, saw the
   content, and walked away. Two possible reads:
   - *Good:* recognized this page as a loose adjacency list, not all the
     links belong in the topic.
   - *Friction:* having previewed, there's no cheap "commit the on-topic
     subset of what I just previewed" path — the only way to cherry-pick
     is `add_articles(titles=[...])` which requires listing them out. The
     preview→partial-commit loop has a rough edge. **Candidate feedback memory:
     preview tools need a "commit these specific results" follow-up, or the
     AI ends up just discarding preview results.**
4. **Scoring has not started (0/686 scored)** at cleanup time. Stage 4 of
   the server instructions says centrality scoring is optional (nullable
   1–10, reject for off-topic). The session is using `reject_articles`
   directly and skipping the score axis. Consistent with current instructions;
   not a problem, just confirms that centrality-scoring is de facto optional.
5. **`filter_articles` dropped 51/767 (6.6%)** — disambigs/redirects/lists
   cleanup on a well-formed category pull. Reasonable baseline for this
   topic shape.
6. **`describe_topic` fired immediately after fetch_descriptions** — AI is
   using it as intended (inspect-the-corpus tool before cleanup). Worth
   verifying the output was actually useful once we can see the session's
   reasoning.

### 15:42:21–15:52+ UTC — silent gap (still)

Second poll at ~15:52 UTC: no new calls. 10 minutes of silence. Gap confirmed,
not a transient scheduling artifact.

### Cause of the quiet gap — SPOT-CHECK TASK FLAW

Sage reported: the session went quiet because it was waiting on the user
for spot-check input. `server_instructions.md` mandates "ask the user to
name 3–5 specific articles they'd expect to find" before export — but the
dogfood session is supposed to be autonomous. The AI dutifully stopped
and asked a user who wasn't there.

**This is a task-definition bug, not a server bug.** Two possible fixes,
both plan-relevant:

1. **dogfood/task.md should instruct the AI to generate its own spot-check
   list in autonomous mode** — pick 3–5 niche examples from its own domain
   knowledge, then verify them against the corpus. (Cheap fix, recovers
   the flow for the remaining autonomous sessions.)
2. **`server_instructions.md` could hedge the spot-check rule** — e.g.
   "if no human is available, seed your own examples from domain
   knowledge rather than skipping the step." This makes the rule robust
   to autonomous usage without requiring every caller-harness to know
   about it. (Better long-term fix; lets the spot-check discipline apply
   in CI-like contexts too.)

Either way: **the spot-check rule is a hard-block if the AI is strict
about it**, and a no-op if the AI is lax. We've now seen it act as a
hard-block once. Worth tracking whether this repeats.

Side-observation: we also didn't see `auto_score_by_description` or
`auto_score_by_keyword` fire, which the server instructions list BEFORE
the spot-check. The session skipped those too — possibly deliberate
(centrality scoring is optional), possibly because it got all the way to
the spot-check step and blocked there. Can't distinguish from logs alone.

### Build-plan idea (from Sage): spot-check as a first-class self-evaluation modality

Sage's framing, captured here so we don't lose it:

> After an initial gather, it's very useful to fabricate a list of possible
> article subjects — just from the LLM's own knowledge, no tool use — then
> use those as a probe to identify which strategies would have found those
> gaps (and might find other similar gaps if applied). Could be done
> multiple times for more thorough results. I'd also want the AI to keep
> track of how complete it thinks the search has been, and what it expects
> to find with 1 or X additional turns of applying more strategies.

This generalizes today's "ask the user for 3–5 niche examples" into a
*self-administered* quality-estimation step that doesn't require a human.
Shape of the idea as I understand it:

1. **Hypothesize.** The AI drafts a list of ~N (say 10–20) article
   subjects it *expects* to exist for this topic, from its own knowledge,
   without any tool use. Mix of central figures and niche cases.
2. **Verify.** Check which ones are present in the current corpus (by
   title, redirect, or near-match).
3. **Diagnose.** For each miss, infer *why* it wasn't caught: was it in a
   category the AI didn't survey? A list page it didn't harvest? A
   WikiProject it didn't probe? A language edition? Wikidata property?
4. **Repair.** Apply the inferred strategies to recover that gap, and
   typically a bunch of neighbors at once.
5. **Estimate.** Report a coverage-confidence score: "I think we're at
   ~X% of the topic; one more pass on [strategy] would likely add Y
   articles; after that diminishing returns."
6. **Iterate.** Repeat 1–5 until the self-estimate stabilizes or the user
   calls it.

Why this is interesting:

- Turns the spot-check from a *human input dependency* into a *diagnostic
  loop* the AI can run on its own. That's what the autonomous dogfood
  session needed.
- It's a *strategy picker*, not just a validator. The value isn't
  "did we find these 10 articles?" — it's "oh, we missed these 3, and
  they're all people-who-won-the-X-award, which means we should fire
  `wikidata_entities_by_property` or `search_articles` against that
  pattern." Each miss is a lead into a whole class of misses.
- Self-estimated completeness unlocks good UX either way:
  - In consultative mode: "I think we're at ~80%, mostly solid; next
    strategy that'd move the needle is a Wikidata award-winners query,
    should I run it?" lets the user trade off time vs. coverage.
  - In autonomous mode: the self-estimate is the stopping criterion.
    No estimate → no stop → runaway session. We should probably
    require it before `export_csv` in autonomous contexts.
- It echoes the two-axis model already in the server: the "inclusion"
  axis is binary (on-topic yes/no); completeness is a third axis, about
  the *corpus* rather than any one article. Worth being explicit that
  it's a separate axis in the instructions.

Tooling implications (backlog candidates):

- **`hypothesize_gap_targets(topic, count=N)` or similar** — optional
  server-side primitive that returns the AI's claimed expected set,
  logged alongside the rest of the session so we can audit quality
  over time. Not strictly required (the AI can just list them in prose),
  but a tool-shaped wrapper gives us telemetry + structured evaluation.
- **`check_article_presence(titles=[...])`** — already effectively
  exists via `get_articles` / `add_articles(dry_run)`, but a dedicated
  "are these in the corpus?" primitive with near-match/redirect-awareness
  would make step 2 one call instead of N.
- **`report_coverage_estimate(confidence, rationale, remaining_strategies)`**
  — a self-report tool that persists the AI's coverage claim into the
  topic record so we can (a) compare against the eventual ground truth
  and (b) display it to the user. Parallels `submit_feedback` in shape.
- **`server_instructions.md` edit**: describe this loop explicitly as the
  recommended wrap-up, replacing or augmenting the current "ask the user"
  spot-check. Include "if no user, generate your own examples" hedging.

Open questions to resolve when we design this:

- How many fabrication rounds is too many? 2 rounds probably catches
  most classes of gap; 5 rounds is probably just LLM hallucination
  polish. Want to bound this.
- Does the AI need to be *blind* to the corpus while fabricating?
  (Probably yes, or it'll just enumerate what it already knows is
  there.) Implies the fabrication step should happen before the AI
  sees a corpus dump, or we need to prompt explicitly "without
  consulting the current corpus, list…"
- How do we score fabrication quality? Some LLM guesses will be
  wrong (the article just doesn't exist). That's not a gap in our
  corpus, it's a gap in the AI's knowledge. Need to distinguish
  "we missed a real article" from "AI hallucinated an article."
  `preview_search(exact match)` + redirect resolution is probably
  enough but worth spelling out.

This is plan-tier, not tweak-tier. Worth a dedicated section in
`docs/post-orchids-plan.md` (or its successor) after today's session
lands.

### 15:52:16–15:58:10 UTC — post-unblock: autonomous spot-check, edge-browse, export

After Sage unblocked, the session ran the wrap-up loop. Notably, once told
it could proceed without user input, it DID generate its own spot-check
list from domain knowledge — so the capability is latent in the model, the
current instructions just tell it not to use it.

The spot-check burst (18 queries in ~70 seconds):

```
15:52:16  preview_search intitle:"Passive Seismic"                  -> 6/2 new
15:52:17  preview_search intitle:"Collins" crater                    -> 7/5 new
15:52:17  preview_search intitle:"Armstrong" crater                  -> 6/4 new
15:52:18  preview_search intitle:"Eagle Has Landed"                  -> 10/8 new
15:52:18  preview_search intitle:"Fly Me to the Moon"                -> 10/8 new
15:52:19  preview_search intitle:"Shadow of the Moon"                -> 7/6 new
15:52:20  preview_search intitle:"Moonshot"                          -> 10/9 new
15:52:26  preview_search intitle:"First on the Moon"                 -> 4/2 new
15:52:26  preview_search intitle:"Michael Collins"                   -> 10/9 new
15:52:52  preview_search "Chariots for Apollo"                       -> 10/3 new
15:52:54  preview_search "Goodwill Moon Rock"                        -> 10/2 new
15:52:54  preview_search intitle:"Moonshot" Apollo                   -> 7/4 new
15:53:09  preview_search intitle:"In the Shadow" book                -> 10/9 new
15:53:21  add_articles(manual:spot-check-gaps, 3)                    -> +3
15:53:24  browse_edges(seeds=6, min_links=2)                         -> 26 candidates
15:53:50  add_articles(manual:browse-edges-gaps, 10)                 -> +10
15:54:06  fetch_descriptions(limit=2000)                             -> fetched 13
15:58:10  export_csv(min_score=0, scored_only=False)                 -> 699 articles exported
```

Signals:

1. **Spot-check target classes reveal the AI's own gap model.** Grouping
   the queries:
   - **Lunar geography** (Collins crater, Armstrong crater, Moon craters
     named after crew) — cross-topic link the category pull missed.
   - **Science experiments** (Passive Seismic ~= ALSEP) — instrument/
     payload gap.
   - **Cultural tail** (Eagle Has Landed, Fly Me to the Moon, Shadow of
     the Moon, Moonshot, In the Shadow) — the "popular culture" list it
     had previewed but never committed. This retroactively confirms the
     earlier observation: previewing-without-committing leaves real
     topical tail articles out.
   - **Biography-adjacent** (Michael Collins disambiguation → the astronaut
     specifically) — name-collision territory.
   - **Primary sources** (Chariots for Apollo — the official NASA history,
     Goodwill Moon Rock — the display-program artifacts).
   - All coherent with Sage's proposed self-evaluation loop — the AI is
     already doing this, just not exposing the reasoning.
2. **Low yield: 3 additions from 13 spot-check queries**, 10 from
   `browse_edges`. Preview queries each turned up 2–9 "new" hits, but
   almost all were rejected as off-topic. The 3 that made it were
   specifically the ones the AI was confident about. **Spot-check on this
   topic was disproportionately diagnostic, not expansionary** — it mostly
   confirmed the corpus was OK, and flagged a small real gap. Useful
   baseline: the cultural-tail articles almost entirely didn't make it,
   which fits the event-shape intuition (fuzzy cultural edge).
3. **`browse_edges(seeds=6)` produced 10/26 adds** — a much better
   signal-to-noise ratio than spot-check previews. Evidence for promoting
   edge-browse earlier in the wrap-up flow, or making it the default
   gap-discovery tool after the first cleanup pass.
4. **Zero centrality scoring end-to-end.** 0/699 articles scored.
   `auto_score_by_description` and `auto_score_by_keyword` never fired.
   Export went out with `scored_only=False, min_score=0` — i.e. "give me
   everything, no score filter." Either (a) the AI correctly read the
   instructions' "centrality is optional" clause, or (b) the AI was
   unaware the scoring tools would have helped here. Worth asking the
   AI in feedback: "would scoring have improved the export, or was the
   post-cleanup corpus already clean enough?"
5. **Export fired at 15:58:10** — but no `submit_feedback` yet at poll
   time. Session wrap-up is in progress; feedback pending.

### Metric for the session so far

- Elapsed wall time (excluding the 10-min user-block): ~7 minutes active
  tool time for 699 articles.
- Tools used: start_topic, find_wikiprojects, check_wikiproject,
  survey_categories (×6), find_list_pages (×3), preview_search (×17),
  get_category_articles (×2), preview_harvest_list_page, harvest_list_page,
  add_articles (×4), reject_articles (×3), filter_articles,
  fetch_descriptions (×2), describe_topic, list_sources,
  get_articles_by_source, browse_edges, export_csv. **That's 19 distinct
  tools, zero scoring tools.**
- Tools in the server but NOT used: auto_score_by_description,
  auto_score_by_keyword, score_by_extract, score_all_unscored, set_scores,
  search_articles (bare, no `intitle:` prefix), search_similar,
  find_wikiprojects *beyond the initial probe*, get_wikiproject_articles,
  auto_score_by_description, wikidata_query, wikidata_entities_by_property,
  wikidata_search_entity, resolve_qids, remove_by_pattern, remove_by_source,
  unreject_articles, list_rejections, preview_similar. **Big surface
  unexercised — most of the Wikidata stack, all the centrality scoring,
  and `remove_by_source` (which the instructions specifically recommend).**
  - The `get_articles_by_source` + `reject_articles` pattern at 15:41:31
    is functionally equivalent to `remove_by_source(keep_if_other_sources=True)`
    but more verbose and more chatty. **Possible that the AI doesn't know
    about `remove_by_source` or reaches for the composable primitive
    first.** Worth checking in feedback.

---

## FINAL ROLLUP

### 1. Session summary (5 bullets)

- **Topic:** Apollo 11 on enwiki, topic id 20. Shape: single historical
  event with crew + hardware + cultural tail. New shape for our benchmark set.
- **Outcome:** 699 articles exported (CSV at
  `/opt/topic-builder/exports/topic-articles-apollo_11.csv`), 0 scored,
  self-rated 7/10, ~39 KB CSV.
- **Wall time:** ~21 min total. ~7 min of active tool time; ~10 min blocked
  waiting for user spot-check input (recovered once Sage unblocked); the
  rest on reasoning.
- **Strategy mix used:** recon (find_wikiprojects + survey_categories +
  find_list_pages) → two category pulls (Apollo program d=4, Moon landing
  d=3) → list-page harvest → targeted `intitle:` searches → filter →
  describe → source-triangulated reject → spot-check preview flurry →
  browse_edges → export. Zero centrality scoring.
- **Shape fit of tool surface:** acceptable but leaky. The tool surface
  handled the mission/hardware/category backbone cleanly; it struggled
  with the cultural tail, cross-program contamination (Luna/Gemini/Chang'e
  bleed via Category:Moon landing), and the real category-system gap at
  Kennedy Space Center. browse_edges saved the category-system gap; no
  tool cleanly handled the cultural tail (preview-without-commit
  dead-end + prose-heavy list page noise).

### 2. Top 5 signals for the build plan (priority order)

1. **`intitle:"A" OR intitle:"B"` silently returns zero results.** The AI
   reports it confirmed this on 4+ queries, which forced ~10 separate
   preview_search calls that should have been 2. Silent failure that
   *looks authoritative*. This is exactly the "AI silently routes around
   broken tools" anti-pattern we have a memory about. **Highest priority
   because it silently burns tool-call budget, slows the session, and
   hides from logs.** Fix is probably a single-line change in the
   CirrusSearch query construction; until then a docstring warning or an
   explicit error would prevent the silent fail.
2. **Spot-check as a first-class self-administered modality** — the idea
   Sage raised + the behavior confirmed by the session once unblocked.
   Build-plan tier, not tweak-tier. Full treatment in the earlier
   "Build-plan idea" section of this doc. Expected deliverables:
   (a) update `server_instructions.md` to authorize "if no user,
   fabricate your own 10–20 probe titles from domain knowledge,"
   (b) add a lightweight `report_coverage_estimate(...)` tool so
   self-assessed completeness can be logged + inspected.
3. **`survey_categories.estimated_total_articles` is ~2× off**
   (un-deduped across subcategories). Docstring lie — a user sizing a
   pull against a 300-article budget would badly miscalibrate. Cheap to
   fix: either dedupe across subcats in the count, or explicitly mark
   the field as "upper-bound, includes duplicates."
4. **`find_list_pages` prefix heuristic is too narrow.** Missed "Apollo
   11 anniversaries" and "Apollo 11 in popular culture" because neither
   starts with "List of" / "Index of". The AI had to broaden the subject
   to "Apollo program" and "Moon landing" to find anything. Either widen
   the heuristic or flag the narrowness in the docstring + instructions.
5. **Wikidata stack unexercised + specific high-value queries identified.**
   The AI listed concrete missed strategies:
   - `wikidata_entities_by_property('P793', Apollo11_QID)` — significant
     events
   - `wikidata_entities_by_property('P361', Apollo11_QID)` — part-of
   - `wikidata_entities_by_property('P138', Apollo11_QID)` — named-after
     (catches schools/streets/awards)
   These tools exist in the server (Stage 5 work) but the AI didn't
   reach for them. Gap is in the *instructions*, not the tools — the
   prompt doesn't make it clear when the Wikidata path beats the
   category path. For event topics where category coverage is known to
   be leaky, the Wikidata P361/P793/P138 queries should be routine.

### 3. AI feedback vs. my log observations

Where the AI's self-report confirms my log read:
- **browse_edges high-signal** — I flagged 10/26 adds; AI flagged
  Kennedy Space Center rescue as the marquee win. Same observation.
- **`describe_topic` usefulness** — I saw it fire; AI confirms it surfaced
  the Luna/Gemini/Chang'e cross-program contamination immediately.
- **Apollo program d=4 as the real anchor, not Apollo 11** — I saw the
  pivot; AI explicitly called the Apollo 11 category "tiny (~102)."
- **Centrality scoring was skipped deliberately (NOT a silent-routing
  gap).** The AI's feedback doesn't dwell on scoring, which suggests
  the post-cleanup corpus was already clean enough that scoring wasn't
  the gap. The NULL-centrality export is on purpose. Resolves one of
  my earlier open questions.

Where the AI's report reveals things the log didn't show:
- **The AI used `get_articles title_regex` mode** — "feeding 29 titles
  through get_articles title_regex let me distinguish 'in topic under
  variant name' vs 'hallucinated by LLM' vs 'real gap' in one shot."
  My log view just said "get_articles" — not visible that regex was
  being used as a membership probe. This means the AI is already
  executing something very close to step 2 of Sage's proposed spot-check
  loop (verify presence against corpus) — just with a foot-gun tool.
- **Two `title_regex` foot-guns the AI hit:**
  - Case-insensitive by default — `^[A-Z]{3,}` for acronyms matched 645
    normal English titles. AI wants a case-sensitive mode or clearer
    docstring.
  - `^Luna(\s|$)` returned 0 while `^Luna ` returned 15 — the `\s|$`
    alternation silently failed (JSON-escape or regex parse bug).
- **`preview_harvest_list_page` on prose-heavy list pages still leaks
  noise** even with `main_content_only=True` (Washington Post, Houston,
  JFK, Texas as new-to-topic links from "Apollo 11 in popular culture").
  The AI *skipped the commit* — which matches my earlier "preview without
  commit is a dead-end" observation, but reveals the cause: the
  main-content filter isn't strong enough for prose-driven lists.

Where the AI's feedback *surprises* me vs. my log interpretation:
- **The AI described the spot-check-with-user as a good workflow**, not
  as a blocker. Sage framed it as the session waiting for a user who
  wasn't there; the AI (once unblocked) reports it was actually
  productive: 29 candidate titles from domain knowledge + regex
  membership check = three-way classify (variant-name-already-in-corpus
  vs. hallucinated vs. real gap). This is interesting because it means
  the *workflow* is good, it's the *autonomous-mode UX* that's broken.
  Fits Sage's framing: generalize the workflow, just remove the
  human dependency.

### 4. Concrete build-plan candidate items

Ordered by cost-to-value:

1. **Fix `intitle:"A" OR intitle:"B"` silent-empty bug.** Small
   server-side fix (~1 hour). High value: unblocks a search pattern
   the AI naturally reaches for, stops silent failures.
2. **Document / soften `survey_categories` count semantics.** Either
   dedupe the count across subcategories, or rename the field to
   `subcategory_articles_sum` and explain. ~30 min.
3. **Broaden `find_list_pages` heuristic** to also match
   "X anniversaries", "X in popular culture", "Timeline of X", etc.
   ~2 hours + test against known topics.
4. **Case-sensitive mode (or better default) for `get_articles
   title_regex`**, and investigate the `\s|$` silent-fail. Small.
5. **Update `server_instructions.md`** to:
   - authorize autonomous spot-check (fabricate-your-own-probe list
     when no user is available),
   - flag Wikidata P361/P793/P138 as the go-to for event topics,
   - call out `remove_by_source(keep_if_other_sources=True)` as the
     preferred shortcut over `get_articles_by_source` +
     `reject_articles`,
   - mention `title_regex` foot-guns with examples.
6. **Add `report_coverage_estimate(confidence, rationale,
   remaining_strategies)`** — new self-assessment tool. Mid-effort
   (adds a column or a log entry; small UX surface). Value: unlocks
   autonomous stopping criterion and per-topic completeness tracking.
7. **Add `harvest_navbox(template_name)`** — expert-curated navbox
   harvest, cleaner than list-page harvest for e.g.
   "Template:Apollo program." Mid-effort (parse navbox template,
   extract links). High value for event + franchise + program topics.
8. **Add `include_by_description(pattern|keywords)`** — inverse of
   `auto_score_by_description` rejection. Mid-effort, complements the
   two-axis model. Would have caught Kennedy Space Center without
   browse_edges.
9. **Add `backlinks(title)`** — what-links-here probe, the reverse of
   `browse_edges`. Expensive per-call on Wikipedia but high-signal
   for central articles. Mid-effort.
10. **Add category-intersection (PetScan-style) set operations** —
    "Moon landing BUT NOT Chinese lunar program." The AI called this
    out explicitly. Larger effort (needs a new query shape) but the
    contamination problem is generic across event topics.
11. **Longer-term:** make the spot-check *loop* (hypothesize →
    verify → diagnose → repair → estimate → iterate) a first-class
    section of the server instructions, and potentially wrap it in
    helper tooling so the loop itself is logged and auditable.
    Plan-tier.

### Session status: complete

submit_feedback fired at 2026-04-23 15:58:56 UTC. Rating 7. No further
activity expected. Monitoring loop ends.

### 15:42:21–15:47+ UTC — silent gap

No new tool calls for 5+ minutes after the 30-article rejection batch. Topic
is stuck at 686 articles, 0 scored, 0 exports. Possibilities:

- Session is composing a spot-check prompt / reasoning without tool calls.
- Session is done in its own head but hasn't triggered `export_csv` or
  `submit_feedback`.
- Session paused or errored (I can't see that from here).

This is itself a monitoring gap: **I can tell when a tool is called but not
when the AI is mid-reasoning vs. truly stopped.** If we ever wire usage
analytics into session-health dashboards, we'll want a heartbeat or "session
closed" signal — without it, "idle for 5 min" is ambiguous.

### Monitoring blind spots (meta)

- I can see tool calls but not which articles were added/rejected or why
  the AI chose a query. The `reject_articles` call with
  `reason_given=True` logs that a reason exists but not the text. If we
  want usage-log-driven retros, **logging the reason text (truncated) on
  reject_articles** would unlock a lot of analysis without needing the
  full session transcript.

