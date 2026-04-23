# Dogfood session notes — 2026-04-23 (run 2, multi-topic arc)

> **Historical log.** Observation notes from the 2026-04-23 multi-topic
> dogfood arc (Pulitzer + 4 follow-ons). Conclusions have been distilled
> into `docs/backlog/README.md` (notably the Tier 2 spot-check
> primitives cluster and Tier 3 `topic_policy` items). Kept here for
> evidence traceability; not actively updated.

Second dogfood pass of the day, run against the patched `task.md` (autonomous
spot-check override, `submit_feedback` field-separation warning, updated
shapes-tested list). **Scope expanded mid-arc:** Sage told the autonomous
session to proceed through 4 more topics in succession after Pulitzer.
This doc covers all of them — structure is one section per topic, plus a
cross-topic hypothesis tracker at the end.

Combined-review: after this arc lands, we'll distill it alongside the
Apollo 11 run (`session-2026-04-23-notes.md`) to decide the next build.

## Baseline before this session

- Latest topic on server: Apollo 11 (id 20, 699 articles), completed 15:58:56 UTC.
- Topics 1–20 already populated; next topic should be id 21.
- `task.md` patched earlier today — this run is the first that will exercise:
  - Autonomous spot-check substitution (§3 of "While you build")
  - `submit_feedback` field-separation warning
  - Apollo 11 removed from candidate shapes, added to tested list

## What to watch for (hypotheses from the Apollo 11 run)

Things worth checking against this session to confirm / refute:

1. Does the AI fabricate its own spot-check list instead of halting?
   (The new §3 explicitly authorizes this — test whether the instruction
   lands.)
2. Does `submit_feedback` come back with top-level `rating` populated,
   or does it still pack fields into `summary` as XML tags?
3. Does the AI use `note=` at all? (Zero `note=` in Apollo 11's 49 calls —
   open question whether the parameter even exists or just isn't being
   reached for.)
4. Does it reach for Wikidata primitives (`wikidata_entities_by_property`,
   `wikidata_query`) on a new topic shape? Apollo 11 didn't, despite
   event-topic categories being known-leaky.
5. Does it use `remove_by_source(keep_if_other_sources=True)` or repeat
   Apollo 11's `get_articles_by_source` + `reject_articles` pattern?
6. How does coverage estimation surface — as a wrap-up note? As part of
   `what_didnt`? Missing entirely?
7. Does the `intitle:"A" OR intitle:"B"` silent-empty bug trip this session
   too? (Apollo 11 hit it 4+ times.)

---

## Running observations

### Topic chosen

**Pulitzer Prize for Investigative Reporting** (id 21, enwiki) — started
16:12:40 UTC. Journalism / awards-anchored biography shape — matches
task.md's first candidate shape.

### 16:12:40–16:15:08 UTC — recon + gather + cleanup in ~2.5 minutes

Full initial burst:

```
16:12:40  start_topic (note: declares shape being tested)
16:13:07  find_wikiprojects(Journalism, Pulitzer, News, Newspapers) -> 2 projects
16:13:07  survey_categories(Pulitzer Prize for Investigative Reporting winners, d=2) -> 1 cat
16:13:08  find_list_pages(...) -> 0 pages
16:13:08  wikidata_search_entity(...) -> 1 candidate (Q2117825)
16:13:15  check_wikiproject(Journalism) -> exists=True
16:13:18  wikidata_entities_by_property(P166, Q2117825, limit=500) -> 96 entities, 81 on en
           (note: award received, canonical winners list if WD well-maintained)
16:13:20  preview_harvest_list_page("Pulitzer Prize for Investigative Reporting")
           -> 295 links (295 new)
           (note: find_list_pages returned 0, so harvesting award article itself
            is the lists-shape fallback)
16:13:49  harvest_list_page(same) -> 295 committed
16:13:49  get_category_articles(Pulitzer Prize for Investigative Reporting winners, d=2)
           -> 101 articles, 1 cat
16:14:35  add_articles(wikidata:P166=Q2117825, 81) -> added 5, updated 76
           (note: 15 WD entities lack enwiki sitelink; well-known journalists
            like Bill Marimow have empty sitelink — real Wikidata-side gap)
16:14:47  filter_articles -> 318 → 230
16:14:47  fetch_descriptions(limit=2000) -> 230 fetched, 191 non-empty
16:14:57  describe_topic / list_sources -> 3 sources
16:15:08  get_articles_by_source(list_page:Pulitzer..., exclude=[category, wikidata])
           -> 121 matches (staging source-only rejection)
```

### Hypothesis check-ins

#### ✅ #3 — `note=` IS used, extensively

Apollo 11: 0 notes in 49 calls. Pulitzer: 5 notes in first 13 calls, all
substantive. Sample:

- `start_topic.note`: "Autonomous dogfood session — testing awards-anchored
  biography shape. No prior build has exercised P166/Wikidata-award→bio
  bridging."
- `wikidata_entities_by_property.note`: "Awards-anchored biography pull
  via P166 (award received). This is the canonical winners list if
  Wikidata is well-maintained for this award."
- `harvest_list_page.note`: "The award's own article serves as the
  canonical winners list (year-by-year table). find_list_pages returned 0
  so this is the primary list source."
- `add_articles.note`: "Wikidata award-received winners with enwiki
  sitelinks. 15 more entities exist on Wikidata without enwiki sitelinks
  — documented but not added (redlinks/translation candidates). Also
  observed: well-known journalists like Bill Marimow have empty sitelink
  on Wikidata — real Wikidata-side gap, not tool gap."

Two big implications:
1. **The `note=` parameter DOES exist** on at least these tools —
   resolves the open question I flagged earlier. No need for the tool-
   investigation item.
2. **Note quality is AI-dependent, not tool-dependent.** Apollo 11's
   session simply didn't reach for it; this session is using it as a
   running commentary. If we want notes reliably, the nudge needs to
   be in `task.md` or `server_instructions.md` (or both), or the note
   field needs to be prompted more explicitly.
3. **The Bill Marimow observation is exactly the kind of signal we want**
   — it distinguishes "our tool missed something" from "the upstream
   data missed something." That cleanly answers the "is this a tool
   gap?" question without us having to investigate. High-value pattern.

#### ✅ #4 — Wikidata WAS reached for immediately

Apollo 11: zero Wikidata calls. Pulitzer: two (`wikidata_search_entity`
for QID resolution, then `wikidata_entities_by_property(P166, Q2117825)`)
within 40 seconds of `start_topic`. The AI evidently recognized "award
→ P166 = award received" as the canonical Wikidata path for this shape.

This doesn't prove the Apollo 11 AI *couldn't* reach for Wikidata —
same model, same tools. It suggests the reach happens when the topic
shape makes Wikidata *obviously* the right path. For event topics,
categories look plausible; for award topics, categories obviously don't
enumerate winners cleanly, so Wikidata wins immediately.

**Implication for instructions:** a tiny table in `server_instructions.md`
matching topic shape → Wikidata properties would likely shift Apollo-11-shaped
sessions too. Candidates:
- awards: P166 (award received)
- events: P361 (part of), P793 (significant event)
- named-after: P138 (named after)
- taxonomy: P31/P279 (instance of / subclass of)
- people: P106 (occupation), P69 (educated at), P166

#### New signal — preview-then-commit happened correctly

Apollo 11's `preview_harvest_list_page("Apollo 11 in popular culture")`
previewed 145 links (109 new) and was abandoned. This session's
`preview_harvest_list_page("Pulitzer Prize for Investigative Reporting")`
previewed 295 links (all new) and was committed 30 seconds later.

The distinction: the Pulitzer preview returned a clean, high-signal list
(the award's own year-by-year winners table), so committing was obvious.
The Apollo "in popular culture" preview was prose-heavy and noisy.

So the preview → commit path works when the list page is structured;
the dead-end is specifically for prose-driven list pages. Reinforces my
earlier observation: the fix isn't making preview "committable" — it's
making `main_content_only` smarter for prose-driven pages, or offering
a richer harvest mode.

#### Partial signal — `find_list_pages` still returns 0

Same narrow-prefix heuristic that bit Apollo 11. But this session worked
around it elegantly by harvesting the award's own main article. The AI
explicitly noted the fallback pattern ("find_list_pages returned 0, so
harvesting the award article itself is the lists-shape fallback"). That
workaround pattern is generalizable: **concept-with-enumeration articles
(awards, lists-with-intros, yearly-results) are often their own list
pages.** Worth encoding in the instructions.

#### New signal — Wikidata add is heavily corroborative, not additive

`add_articles(wikidata:P166=Q2117825, 81) -> added 5, updated 76`. 76/81
Wikidata winners were already pulled in via the harvest_list_page +
category routes; Wikidata only added 5 net new. For awards-anchored,
Wikidata is mostly *confirmation* that the list is complete, not
expansion. That's useful ("we have 94% of the winners") but changes the
value framing — Wikidata as validator, not discoverer, for this shape.

Different from the hypothetical Apollo 11 Wikidata value, which would
have been mostly *additive* (things-named-after, part-of).

#### Still unresolved (session mid-cleanup)

- **#1 (autonomous spot-check fabrication):** not yet reached.
- **#2 (submit_feedback rating field):** not yet reached.
- **#5 (remove_by_source vs. get_articles_by_source):** same pattern
  so far — AI just called `get_articles_by_source` with exclude_sources.
  Will confirm when the reject batch fires.
- **#6 (coverage estimation):** not yet reached.
- **#7 (intitle: OR silent-empty bug):** no OR queries fired yet.

### 16:16:33–16:17:15 UTC — disciplined auto-score + source-triangulated reject

New tool usage Apollo 11 didn't exercise:

```
16:16:33  auto_score_by_description(axes=[], disqualifying_count=22, dry_run=True)
           -> would reject: 23
           (note: Probing auto-reject tool on noise bucket. Scope boundary:
            journalists/news-orgs/winning-works IN; subjects of exposés and
            generic context OUT.)
16:17:15  reject_articles(titles_count=39, also_remove=True, reason_given=True)
           -> 230 → 191
           (note: Per-scope: only journalists, winning news organizations,
            and winning-work articles are in. These 39 are one hop removed
            from the award.)
```

Signals:

1. **`auto_score_by_description` DID fire this session, and with `dry_run=True`
   first.** Apollo 11 skipped this tool entirely. This is disciplined usage —
   probe what would be rejected, inspect the list, then commit the reject.
   Paired with clearly-scoped `reject_articles`, it's a two-step pattern that
   gives the AI (and us) an audit trail.
2. **The `note=` fields on both calls are essentially the rubric**
   — "journalists/news-orgs/winning-works IN; subjects of exposés and
   generic context OUT." If we ever want to build regression tests or
   compare scope boundaries across similar topics, these notes ARE the
   scope declaration. Strong argument for instructing the AI to record
   scope in notes explicitly.
3. **23 (dry_run) vs. 39 (actual) reject.** The AI didn't just execute
   what auto_score suggested — it combined auto_score with its own review
   of the list-page-only cluster (`get_articles_by_source` 121 matches)
   and made a broader judgment. `auto_score_by_description` is being used
   as one signal among several, not a black-box classifier.

### 16:18:54–16:19:47+ UTC — autonomous spot-check burst

#### ✅ #1 CONFIRMED — autonomous spot-check fabrication happened

A ~1-minute burst of 14 `preview_search` probes, all explicitly tagged
as spot-check in the `note=` field. Sample:

```
16:18:54  preview_search(query="Jodi Kantor Megan Twohey Weinstein Pulitzer")
           (note: "Spot-check probe — Jodi Kantor / Megan Twohey won IR 2018
            for Weinstein. Expected to exist on enwiki.")
16:18:55  preview_search(query="Clark Mollenhoff Donald Barlett James Steele Pulitzer inv...")
16:18:56  preview_search(query=intitle:"Spotlight" Catholic Boston Globe Pulitzer)
16:19:15  preview_search(query=intitle:"Clark Mollenhoff")
16:19:15  preview_search(query=intitle:"Donald Barlett")
16:19:16  preview_search(query=intitle:"Debbie Cenziper")
16:19:17  preview_search(query=intitle:"Jane Mayer" journalist)
16:19:17  preview_search(query=intitle:"Dana Priest")
16:19:18  preview_search(query=intitle:"Barry Meier")
16:19:44  preview_search(query="Jane Mayer" "Pulitzer Prize for Investigative")
16:19:45  preview_search(query="Dana Priest" "Pulitzer Prize for Investigative")
16:19:46  preview_search(query="Debbie Cenziper" "Pulitzer Prize for Investigative")
16:19:47  preview_search(query="Jodi Kantor" "Pulitzer Prize for Investigative")
```

Structure observed — matches task.md §3's prescription but not perfectly:
- **~14 probes, not ~50.** The task.md floor was ~50 across ≥5 subdomains;
  the session fabricated ~10 journalist names. Smaller than spec, but
  recognizably the right pattern.
- **No cross-subdomain spread.** All probes are journalist names. For
  an awards-anchored biography this is arguably the only subdomain that
  matters (there aren't "cultural tail" or "sites" axes on a journalism
  prize), so the narrow focus is probably correct — but the AI didn't
  explicitly probe adjacent axes (winning news organizations? specific
  investigative books? foundation work?). Worth asking in feedback.
- **Three-tier probe progression:**
  1. Multi-name bulk queries (see if many are findable together)
  2. Single-name `intitle:` queries (exact presence check)
  3. Combined quoted phrase probes (`"Name" "Pulitzer Prize for Investigative"`)
    — verifying article explicitly mentions the prize
  This is a reasonable probe cascade; structurally similar to "hypothesize
  → verify → classify" but compressed into one burst.
- **AI-side commentary shows intent.** "Expected to exist on enwiki."
  That's the AI declaring its hypothesis before the tool fires — exactly
  the diagnostic shape we want for building a gap-audit trail.

#### ✅ #7 CONFIRMED — `intitle:"A" OR intitle:"B"` silent-empty bug, AI-acknowledged

Huge signal. The AI's `note=` on the spot-check commit at 16:21:22 says:

> "Spot-check found 8 real gaps. Kantor+Twohey are 2018 winners absent
> from Wikidata P166 (coverage gap, not tool gap). The 3 Boston Globe
> Spotlight journalists were only surfaced by individual intitle: probes
> — **the compound intitle:OR form silently returns 0 results (bug
> confirmed from Apollo 11 session).**"

Two separate things worth unpacking:

1. **The AI references the Apollo 11 bug by name, even though context
   was cleared between sessions.** Sage confirmed: the Apollo 11 Claude
   Code session was cleared before the Pulitzer session started, so
   this can't be in-model memory carrying over. But the autonomous
   session is running *inside this repo*, so anything committed (or
   just written) is fair game to read. Most likely source: my own
   monitoring doc from run 1, `dogfood/session-2026-04-23-notes.md`,
   which extensively documents the `intitle:OR` bug. Also in-scope:
   the updated `task.md`, `CLAUDE.md`, `docs/post-orchids-plan.md`
   (now containing 6.7), feedback.jsonl if the session has read access,
   and any git-tracked prior feedback summaries.
   Useful corollary: **my monitoring doc is part of the other session's
   reading material.** That's worth being aware of — if I write
   something in these notes, the subsequent topic sessions can pick it
   up. Not a problem (probably helpful), just a feedback loop to name
   explicitly.
2. **Independent reproduction still useful.** Even though the knowledge
   came from somewhere, the Pulitzer session actually tried single-clause
   probes (they worked) and so the bug is effectively re-validated, not
   just echoed. So the claim "bug confirmed from Apollo 11 session" is
   substantively correct.
2. **The reply to the bug was "route around with single-clause probes,"
   not "use remove_by_source" or some other workaround** — consistent
   with the "silent routing" anti-pattern we already track. But at
   least this time the routing *is* surfaced in the note, so it's not
   silent.

The browse_edges note at 16:21:30 is the same pattern: "Edge-browse
from confirmed recent winners. Looking for IR journalists we missed —
**prior session showed this is high-signal for peripheral wins.**"
Another explicit cross-session reference.

**Implication for tool/instruction design:** if the AI is going to
transfer patterns across sessions anyway, we can lean into that —
surfacing known-bug avoidance patterns in `server_instructions.md`
("avoid `intitle:OR` compound — split into separate calls") would
probably make the workaround faster than re-discovery. Similarly, we
can encode "browse_edges from peripheral seeds is high-signal for
awards-anchored biographies" as a topic-shape tip without having to
wait for the AI to re-learn it each session.

### 16:21:22–16:24:23 UTC — spot-check commit, browse_edges, export, feedback

- `add_articles(manual:spot-check-gaps, 8)` → 199 articles
- `browse_edges(seeds=8, min_links=3)` → 78 candidates
- `add_articles(manual:browse-edges-gaps, 14)` → 213 articles
- `export_csv(enriched=True)` → 213 articles exported
- `submit_feedback(rating=7)` — 693 chars, all fields properly populated

---

## Pulitzer rollup

### Session stats

- **Topic:** Pulitzer Prize for Investigative Reporting (topic 21, enwiki)
- **Outcome:** 213 articles, 0 scored, rating 7/10 (self-rated)
- **Wall time:** ~12 min active (16:12:40 → 16:24:23) — no user-blocked
  gap this time. Clean autonomous run end-to-end.
- **Shape:** Awards-anchored biography. Previously untested. P166 was
  the right primary Wikidata path.

### Hypothesis results (all 7)

| # | Hypothesis | Result | Evidence |
|---|---|---|---|
| 1 | Autonomous spot-check fabrication happens | ✅ Confirmed | ~30 probe titles across 7 subdomains (feedback exact language); 8 real gaps added |
| 2 | `rating` at top level, not XML-packed | ✅ Confirmed | `"rating": 7` at top level, every other field also properly populated |
| 3 | `note=` parameter is used | ✅ Confirmed | Dense note coverage across recon, gather, and spot-check calls |
| 4 | Wikidata reached for on award-shape | ✅ Confirmed | P166=Q2117825 fired within 40s of start_topic; returned 96 entities, 81 with enwiki |
| 5 | `remove_by_source` still skipped | ✅ Confirmed | Same `get_articles_by_source` + `reject_articles` pattern as Apollo 11 |
| 6 | Self-estimated coverage surfaced | ⚠️ Partial | No explicit % estimate, but `missed_strategies` names 4 specific strategies with clear "would have caught X" framing — structurally a coverage hint, not a number |
| 7 | `intitle:OR` silent-empty bug regression | ✅ Confirmed | AI: "Exactly the Apollo 11 bug... 0 results... individually each returned 1–3... Regression from a supposedly-fixed surface; needs a test." |

### NEW signals (not predicted by Apollo 11 run)

These were not on the radar before Pulitzer submitted its feedback:

1. **`auto_score_by_description` substring-matching edge.** Tried
   `disqualifying=["city", "county", ...]` for geographic noise; would
   have rejected "The Kansas City Star", "New York World-Telegram",
   "The Orange County Register". Word-boundary matching doesn't help
   because "City" IS a real word in the place name. AI caught via
   dry-run and went manual; tool is effectively unsafe for topics with
   place-named institutions. **Concrete fix:** case-sensitive match
   by default, or a separate "disqualifying_regex" mode with anchored
   patterns.
2. **Wikidata P166 entities with EMPTY sitelinks** — a silent gap in
   the current tool output. The tool prints `title=""` for entities
   that have a QID but no sitelink set. AI says: "the AI can miss
   that this is recoverable and NOT treat it as 'no enwiki article.'"
   Two-category output ("QID exists, enwiki article may exist but
   sitelink missing" vs. "no enwiki article") would unlock recoverable
   coverage.
3. **Wikidata P166 is MORE incomplete than it looks for modern winners.**
   Kantor/Twohey (2018), Matt Rocheleau/Vernal Coleman/Evan Allen
   (2024 Globe team) all have enwiki articles AND Wikidata entities,
   but P166=Q2117825 just isn't asserted. **Without the spot-check the
   corpus would have shipped missing the most recent winners entirely.**
   Strong argument that the spot-check loop is doing real coverage
   work, not just validation.
4. **`fetch_descriptions` doesn't use REST summary extract as enwiki
   fallback.** Apollo 11's `fetched 716, 647 non-empty` pattern was
   the same; Pulitzer hit 20% blank descriptions (43/213) — all older
   journalists with no Wikidata shortdesc. Enwiki has perfectly good
   lede-summary extracts; they're only tried on non-en wikis.
   **Concrete fix:** extend the enwiki fallback chain to include REST
   summary extract when Wikidata shortdesc is empty.
5. **`browse_edges` output isn't relevance-scored.** 78 candidates
   from 8 seeds — many legit, several noise (C-SPAN, Stanford
   University, Bachelor of Arts, ISBN identifiers). A
   `linked_by_seeds / total_inbound_links` score would surface the
   actually-similar ones. Same observation would have applied to
   Apollo 11's `browse_edges(seeds=6) → 26 candidates`, but smaller
   scale hid it.
6. **No way to intersect WikiProject × Category** (again). WikiProject
   Journalism is ~60k articles; what's wanted is "WP Journalism ∩
   Category:Pulitzer IR winners". This is a set-operation gap the
   Apollo 11 session implicitly ran into too (Spaceflight WP too
   broad) — Pulitzer made it explicit. Third topic shape to hit it;
   this is now a clear build candidate.
7. **`find_list_pages` heuristic miss — generalized.** Apollo 11
   missed "Apollo 11 in popular culture". Pulitzer: the award's OWN
   main article IS a year-by-year list page, but `find_list_pages`
   returned 0. **Generalization:** award articles, event anniversaries,
   yearly-results articles all behave like list pages without being
   titled "List of X". The AI suggests either a broader heuristic or
   a dedicated `harvest_award_article` that knows about year-tables.
8. **Missing primitives the AI explicitly names for future builds:**
   - `check_article_presence(titles=[list])` — step 2 of the spot-check
     loop. AI ended up using `get_articles(title_regex=40-name-alternation)`
     "which worked but felt abusive." Strong argument for making this
     a first-class primitive given how central spot-check has become.
   - `list_rejections(show_reasons=True)` — audit view for rejected
     titles + reasons. AI reports feeling blind on whether reason
     text persisted correctly.
   - `verify_claim(title, property, value)` — "does this article
     mention Pulitzer IR specifically?" Would replace the indirect
     `"Name" "Pulitzer Prize for Investigative"` quoted-phrase probes.
9. **Missed strategies the AI specifically named (plan-tier):**
   - Wikidata SPARQL `MINUS` patterns for multi-category exclusion
     ("P166=IR AND NOT P166=PublicService")
   - Named-after / subject-of queries (P800 notable work, P921 main
     subject) for winning-work articles
   - Co-winner graph via P585 qualifier on P166 claims — Spotlight
     team or AP seafood team as a unit
   - Cross-award family probing (Goldsmith, Polk, IRE, Loeb
     correlating with Pulitzer IR)

### Delta from Apollo 11

- **Rating:** Apollo 11 self-rated 7 (in summary), Pulitzer 7 (top-level).
  Same calibration.
- **Active tool time:** Apollo 11 ~7 min (excluding user block);
  Pulitzer ~12 min. Pulitzer is longer because spot-check
  (~30 probes) was bigger than Apollo 11's unblocked re-run (~13 probes).
- **Tools exercised new this run:** `wikidata_search_entity`,
  `wikidata_entities_by_property`, `auto_score_by_description (dry_run)`.
  Apollo 11 had zero Wikidata and zero auto_score.
- **Enriched export:** Pulitzer used `enriched=True`, Apollo 11 used
  `enriched=False`. Worth asking what triggered the difference.

---

## Topic 22: Lakes of Finland

Started 16:24:47, 24 seconds after Pulitzer feedback. Geographic feature
shape — task.md's next-candidate list literally names this example.
The AI's `start_topic.note`: "Autonomous session 2 of 5. Shape:
geographic feature, structural, near-zero biographies." (Arc-aware.)

### NEW SIGNAL — `wikidata_query` (SPARQL) used for the first time in the arc

Apollo 11 and Pulitzer both used `wikidata_entities_by_property` but
never `wikidata_query`. The Pulitzer feedback explicitly named SPARQL
as a missed strategy. Lakes of Finland reached for it *immediately*:

```
16:26:17  wikidata_query(query_length=253) -> 337 rows
           (note: P31/P279* lake located in Finland. P31/P279* catches
            reservoirs (subclass of lake) too.)
16:26:31  wikidata_query(query_length=184) -> 1 row
16:26:41  wikidata_query(query_length=188) -> 337 rows
           (note: Trimmed query: only enwiki article title. Previous
            (with labels) overflowed at 52kb for 330 rows.)
```

Signals:
1. **The AI uses hierarchical SPARQL reasoning** — `P31/P279*` pattern
   for "instance-of-or-subclass-of" catches reservoirs without a
   dedicated second query. That's idiomatic SPARQL; nice to see it
   reached for naturally.
2. **Response-size limit hit empirically.** "Previous (with labels)
   overflowed at 52kb for 330 rows." The AI trimmed the projection to
   enwiki title only and re-ran. Same 337 rows, within budget. **This
   is a real friction signal** — the AI had to empirically discover the
   size limit. Concrete fix: docstring warning on `wikidata_query` ("results
   exceeding Nkb will be truncated; prefer narrow projections for large
   result sets"), or server-side auto-trimming of label columns on
   overflow with a "truncated" flag.
3. **Why Lakes, not Pulitzer?** Awards-shape has an obvious Wikidata
   property (P166 award received); geographic-feature shape needs the
   *intersection* of type + location (P31 lake + P17 country=Finland).
   That's fundamentally a multi-claim query, which `wikidata_entities_by_property`
   doesn't express but `wikidata_query` does. Good match of tool to
   shape.

### NEW SIGNAL — `find_list_pages` hit this time (1 page)

Apollo 11 → 0, Pulitzer → 0, Lakes of Finland → 1. The difference:
"List of lakes of Finland" actually starts with "List of" so it
matches the current narrow heuristic. This confirms the earlier
observation: the heuristic works when the topic has a canonical
"List of X" page, fails when the list page has any other title shape
(awards, "X in popular culture", year anniversaries). Same single-fix
needed regardless of topic shape.

### NEW SIGNAL — `survey_categories` depth=2 for a shape like this is heavy

`survey_categories(Lakes of Finland, depth=2)` took 20.5s and made 148
Wikipedia API calls to return 140 subcategories. Then
`get_category_articles(..., depth=3)` took another 40s and 281 API
calls for 349 articles.

That's ~60 seconds of pure recon API load on one topic. Manageable
but worth a cost flag in the notes. The AI didn't cost-warn, but this
is the kind of surface where a `cost_warning` header in the response
would be earned (and Stage 1 landed per-call cost fields already).

### Partial signal — Wikidata claim-completeness is still a concern

Not yet seen in logs, but worth watching for: geographic features on
Wikidata sometimes have P31=lake but not P17=country (or vice versa).
If the AI encounters lakes in Finland that aren't tagged with
P17=Q33, they'd be missed by the SPARQL query even though they'd be
caught by the category.

### Lakes rollup (rating 8, 365 articles, ~5 min)

**Shape fit:** Excellent. 85% of articles had ≥2 sources from the
category/list/SPARQL triangulation. Cleanup was two targeted
reject-calls (16 + 10 = 26 items) — national parks, ringed seal species,
islands, generic concepts.

**NO spot-check burst** this session — the AI went category+list+SPARQL
→ filter → triangulated-reject → export → feedback. Deliberate skip, not
omission:

> **"The category/SPARQL/list triangulation was SO tight (85%) that the
> self-administered spot-check diagnostic value dropped to near zero.
> I did probe a few famous Finnish lakes (Saimaa, Päijänne, Inari,
> Näsijärvi) and they were all present... Spot-check diagnostic value
> is inversely proportional to triangulation quality."**

This is a **critical insight for the 6.7 roadmap item** on spot-check
modality. The AI is independently discovering that spot-check is a
*diagnostic* step, not a *completion-confirming* step — when
triangulation quality is high, you don't need it. The task.md §3
currently mandates it as always-run; we should soften that to "run
when sources don't clearly triangulate" and give the AI an explicit
off-ramp.

### NEW signals unique to Lakes

1. **`wikidata_query` response overflow is handled server-side by
   saving to file.** "The tool saved the overflow to a file and asked
   me to re-read it in chunks." First time we've seen this behavior.
   - Workable but awkward UX. AI suggests: (a) native pagination,
     (b) enforced max row size, (c) pre-call warning "your SPARQL
     returns ~330 rows at ~160 bytes each = ~52kb — consider trimming
     fields."
2. **`get_category_articles` cost flag missing.** 39.6s / 281 API
   calls without a `cost_warning`. `survey_categories(depth=2)` had
   already said "140 subcategories, ~464 articles." Pre-call
   prediction + warning would catch this class.
3. **`filter_articles` missed a non-standard disambig page.**
   "Syväjärvi (Inari)" has description "List of lakes with the same
   or similar names" but uses a non-`{{disambiguation}}` template.
   Filter is template-based, not shortdesc-aware. Small, concrete fix.
4. **Three-way triangulation converges tightly on structural topics.**
   Compare to Pulitzer (awards-anchored): triangulation was useful but
   less tight — Wikidata P166 missed modern winners entirely, so list
   harvest and spot-check had to fill gaps. Lakes: Wikidata P31/P279*
   caught reservoirs, category caught everything, list harvest added
   56 more — high convergence. **Shape-fit of Wikidata claim
   completeness is the predictor of triangulation quality.**
5. **Missed strategies specifically named:**
   - Cross-wiki reconciliation (`cross_wiki_diff(topic, source=fi,
     target=en)` for "articles to translate" lists). Fiwiki has far
     more Finnish lakes than enwiki.
   - Coordinate-based geographic containment (`wdt:P625` inside a
     Finland polygon) for strict-boundary cases.
   - Geographic + quantitative intersection (`lakes of Finland with
     area >= N km²` via `wdt:P2046`).

### Hypothesis deltas from Lakes run

| # | Status after Lakes | Note |
|---|---|---|
| 1 | Confirmed-but-conditional | AI skipped spot-check deliberately on high-triangulation topic; this is a NEW modality signal |
| 2 | Confirmed again | `rating: 8` at top level, all fields populated |
| 3 | Confirmed again | Notes on start_topic + wikidata_query + cost insights |
| 4 | Confirmed + extended | SPARQL reached for naturally via P31/P279* property path |
| 5 | Confirmed again | Same `get_articles_by_source` + `reject_articles` pattern, twice |
| 6 | Partial — still no explicit coverage % | Implicit "we've got everything" via triangulation |
| 7 | Not tested this run | No OR combinators fired |

---

## Topic 23: Phenomenology (philosophy)

Started 16:29:47, 7 seconds after Lakes feedback. Abstract concept /
philosophy shape — task.md's remaining candidate list. Initial recon:

```
16:29:47  start_topic
16:30:01  find_wikiprojects(['Philosophy', 'Continental philosophy',
                             'Phenomenology']) -> 2 projects
16:30:02  survey_categories(Phenomenology, depth=2) -> 5 categories
16:30:03  find_list_pages(subject=Phenomenology) -> 0 pages
16:30:03  wikidata_search_entity(term=phenomenology, limit=10) -> 10 candidates
```

**Shape predicts friction:** abstract-concept topics have fuzzy edges
and adjacent-concept creep (per task.md). 5 subcategories is tiny; 10
Wikidata candidates for "phenomenology" is a LOT — the term is
polysemous.

### NEW SIGNAL — shape-specific Wikidata property choice is emerging

The AI's note on `wikidata_entities_by_property`:
> "Phenomenologists via field-of-work. P101=Q179235 should catch the
> philosopher tradition."

**Pattern across the arc:**
| Shape | Wikidata property | Topic example |
|---|---|---|
| Awards-anchored biography | P166 (award received) | Pulitzer IR |
| Geographic feature | P31/P279* ∩ P17 (type hierarchy × country) | Lakes of Finland |
| Abstract concept / discipline | P101 (field of work) | Phenomenology |

This is exactly the shape→property mapping I hypothesized earlier could
go in `server_instructions.md`. The AI is discovering it empirically
per-topic; encoding it would save the discovery step on future runs.

### NEW SIGNAL — Pattern transfer: "main article IS the list page"

AI's note on `preview_harvest_list_page(Phenomenology (philosophy))`:
> "No find_list_pages hit; using main topic article as canonical hub."

Exact same workaround the Pulitzer session used ("The award's own article
serves as the canonical winners list"). The AI generalized: *when
find_list_pages returns 0, harvest the topic's own main article.* Now
documented across 2/3 topics where find_list_pages missed. Strong
argument this should be in `server_instructions.md` as a canonical
fallback.

### NEW SIGNAL — The AI is distinguishing "redlink" from "not-topic-member"

AI's note on adding P101=Q179235 entities:
> "74 with enwiki sitelinks of 289 total Wikidata entities — 215
> redlinks on enwiki (translation candidates, not topic members)."

This is the exact distinction the Pulitzer feedback asked for as a tool
improvement — "QID exists, enwiki article may exist but sitelink
missing" vs. "no enwiki article." The AI is manually annotating it in
notes. A tool-level signal in the response would save the AI the
classification work.

### NEW SIGNAL — Spot-check as validation, not discovery

Phenomenology's spot-check burst (16:32:02–16:32:14):

```
preview_search intitle:"Transcendental phenomenology" -> 2 results, 0 new
preview_search intitle:"Hermeneutic phenomenology"    -> 1 result,  0 new
preview_search intitle:"Genetic phenomenology"        -> 1 result,  0 new
preview_search "Ideas Husserl book phenomenology"     -> 5 results, 0 new
preview_search intitle:"Ideen"                        -> 1 result,  1 new
```

4 of 5 probes hit the corpus already. 1 new (Ideen — the German title
of Husserl's Ideas). Same "validation mode" as Lakes: when the probe
set is already present, the result is *confirmation*, not
*gap-discovery*. Pattern:

- **High-triangulation shapes (Lakes, Phenomenology):** spot-check
  mostly validates; ~0–5 new hits.
- **Lower-triangulation shapes (Pulitzer, Apollo 11):** spot-check
  recovers real gaps; 3–8+ new hits out of ~15–30 probes.

**Implication:** the task.md §3 loop should call out both modes
explicitly so the AI has a clean framing for "spot-check came back
0 new — we're done" as a positive outcome, not a "did I do the loop
right?" ambiguity.

### NEW SIGNAL — `browse_edges` scaling with corpus size

- Apollo 11 (686 articles): `seeds=6, min_links=2` → 26 candidates
- Pulitzer (213 articles): `seeds=8, min_links=3` → 78 candidates
- Phenomenology (453 articles): `seeds=5, min_links=3` → 237 candidates

Phenomenology returned ~3x more candidates than Pulitzer from fewer
seeds. Abstract philosophical concepts have very high in-degree in
Wikipedia's link graph (lots of stub articles link to "Phenomenology"
type anchors). This makes `browse_edges` noisier on abstract topics —
which the AI will have to semantically filter. Relevance scoring on
browse_edges output (already flagged in Pulitzer feedback) would help
most on this shape.

### Phenomenology rollup (rating 6, 466 articles, ~4 min)

**Shape fit:** fuzzy-edge abstract concept. **Only 17.5% articles
multi-sourced** — an order of magnitude below Lakes' 85%. The
triangulation strategy that worked perfectly on Lakes mostly didn't
on Phenomenology because the category, list harvest, and Wikidata
P101 hit different slices of the concept.

Rating calibration: 6 reflects (a) poor triangulation, (b) find_wikiprojects
vs check_wikiproject disagreement bug, (c) intitle:OR regression
(third session), (d) scope judgment fell on LLM with no tool support,
(e) 215 non-sitelinked entities can't be explored from enwiki alone.

### NEW signals unique to Phenomenology

1. **`find_wikiprojects` vs `check_wikiproject` disagree.** `find`
   said Continental philosophy project exists (prefix-searches
   Wikipedia: namespace); `check` said exists=False (looks for
   Template:WikiProject X). Different APIs, different results. Bug.
   AI: "the two tools should agree or one should call the other
   under the hood."
2. **`intitle:OR` silent-empty bug confirmed for third session.** AI:
   "It is the single most impactful workflow bug on the tool surface
   right now." Three sessions in a row. No ambiguity — this is a real
   regression.
3. **Triangulation quality varies by ~5× across shapes.** Lakes 85%,
   Apollo 11 unknown (no explicit count), Pulitzer not-quite-that-tight,
   Phenomenology 17.5%. Confirms the earlier Lakes insight:
   **triangulation quality → spot-check value** is the real predictor.
4. **`browse_edges` over-fans on abstract-concept shape.** 237
   candidates from 5 seeds; ~15 truly on-topic. Works great on
   structural topics; on fuzzy-edge concepts, "adjacent to
   phenomenology = in Continental philosophy universe" overruns the
   scope. AI suggests: filter edge candidates by topic-description
   similarity.
5. **Wikidata non-sitelinked entities reveal real enwiki under-coverage.**
   215 of 289 P101=Q179235 entities lack enwiki sitelinks. AI notes
   these are mostly Eastern European (Polish/Czech/Romanian/Hungarian)
   phenomenologists with articles on plwiki/cswiki/etc. but not
   enwiki. **A `cross_wiki_diff` primitive (now named by Lakes AND
   Phenomenology) would turn this under-coverage into an "articles
   to translate" work list.**
6. **Homonym trap is shape-endemic.** `wikidata_search_entity`
   returned 10 candidates for "phenomenology" — physics, architecture,
   archaeology, psychology all have same-named-but-different concepts.
   The AI picked the right QID from descriptions. This is a scope-
   disambiguation step unique to polysemous concept topics; on
   Lakes/Pulitzer/Apollo the name-to-QID mapping was 1:1.
7. **Missed primitive: `topic_policy(include_desc_matches,
   exclude_desc_matches)`.** The AI wants a way to declare "physics
   phenomenology OUT, architectural phenomenology IN" once and have
   future gather tools auto-apply. Current sticky-rejection catches
   specific titles but not the policy. **New build-plan candidate.**
8. **More missed strategies named:**
   - Two-step Wikidata joins via P737 (influenced by) — "philosophers
     influenced by Husserl"
   - P921 main-subject queries for concept-works
   - Article-text phrase-match ("articles containing 'phenomenology'
     in the lead paragraph") as a principled inclusion test

### Hypothesis deltas from Phenomenology

| # | Status after Phenomenology | Note |
|---|---|---|
| 1 | Confirmed, fine-tuning evidence | Spot-check fired (27 probes, 24/27 in corpus = validation mode, as predicted by Lakes insight) |
| 2 | Confirmed again | `rating: 6` properly at top level |
| 3 | Confirmed again | Rich notes throughout |
| 4 | Confirmed + refined | P101 (field of work) = third shape-specific Wikidata property |
| 5 | Confirmed again | Same `get_articles_by_source` + `reject_articles` pattern |
| 6 | Implicit only | "89% hit rate" in spot-check narrative is an indirect coverage claim; still no explicit `coverage_estimate` field |
| 7 | **Third-session confirmation** | AI explicitly says it's the single most impactful workflow bug |

---

## Topic 24: Korean television dramas

Started 16:33:56, 5 seconds after Phenomenology feedback. Contemporary
pop culture / franchise shape — task.md's fourth candidate.

### Early signals (pre-wrap)

```
16:34:07  find_wikiprojects(['Korea','Korean','Television drama','Television']) -> 5 projects
16:34:07  survey_categories(Korean television dramas, d=2) -> 1 cat (tiny!)
16:34:08  find_list_pages(Korean television dramas) -> 0 pages (again)
16:34:09  wikidata_search_entity(Korean drama) -> 3 candidates
16:34:17  survey_categories(South Korean television dramas, d=2) -> 1 cat
16:34:18  preview_search intitle:"List of Korean" drama -> 7 results (7 new)
16:34:18  preview_search intitle:"List of South Korean" drama -> 10 results (10 new)
16:34:59  survey_categories(South Korean television series, d=2) -> 212 cats
16:35:00  preview_harvest_list_page("List of Korean dramas") -> 1867 links (1867 new)
```

**Shape-specific signals already visible:**

- **`find_list_pages` fails AGAIN for a sensible topic subject.** But
  the AI pivoted to `preview_search intitle:"List of Korean"` /
  `intitle:"List of South Korean"` — which found 17 list pages.
  `find_list_pages` and `intitle:"List of X"` both search for the
  same thing but get different results. Another two-tools-should-agree
  bug, related to the Phenomenology find_wikiprojects vs.
  check_wikiproject inconsistency.
- **212 subcategories on "South Korean television series".** By far
  the biggest tree yet. K-drama ecosystem is dense.
- **1867 links on "List of Korean dramas"** — this is 5× Pulitzer's
  entire corpus. The pop-culture shape confirms task.md's "navbox-heavy
  lists" characterization.
- **Triple category-survey chain** — Korean television dramas (1) →
  South Korean television dramas (1) → South Korean television series
  (212). The AI is doing category-tree exploration to find the right
  anchor, similar to Apollo 11's Apollo 11 → Apollo program pivot.

### NEW SIGNAL — Wikidata used as RECON, not gather

K-drama has the first instance of `wikidata_query` being used as a
*sizing probe*, not a gather source:

```
16:35:18  wikidata_query(q_len=179) -> 1 row
           (note: Count: television drama series (Q21191270) from
            South Korea (Q884) with enwiki sitelink.)
16:35:27  wikidata_query(q_len=188) -> 1 row
           (note: Broader: any television series subclass from SK.)
16:35:35  wikidata_query(q_len=247) -> 193 rows
           (note: Narrower: TV series from SK with genre=drama
            (Q130232) or subclass.)
```

First two are COUNT queries; third is a narrower filter. Result:
193 rows, which is less than the 1867 already in corpus from the
list harvest — so the AI declined to add them as a separate source
(no `add_articles(source=wikidata:...)` call). Smart — avoids
duplicating an already-covered corpus.

This is a new pattern: **SPARQL as sizing/validation probe, not as
primary gather source.** Useful signal for the shape→Wikidata-property
table — for pop-culture shapes where list pages are canonical,
Wikidata is a *sanity check*, not a primary pull.

### NEW SIGNAL — `filter_articles` dropped 0 on K-drama

Apollo 11 6.6%, Pulitzer 28%, Lakes 4%, Phenomenology 4%, K-drama 0%.
The K-drama list page harvest produced a CLEAN 1867 articles — all
real, disambig-free, non-redirecting. That's because
`List of Korean dramas` is expert-maintained and each entry links
directly to the canonical series article. Another data point for
"high-quality list pages = near-zero cleanup overhead."

### NEW SIGNAL — First non-dry-run `auto_score_by_description`

Three sessions skipped this tool (Apollo, Lakes, Phenomenology); Pulitzer
used only dry_run then went manual; K-drama is the first to COMMIT the
auto-score (after dry_run review). Only 25/1867 rejected (1.3%) — very
clean. Apparently the K-drama shape — all entries are TV series — has
descriptions that cleanly split into "is a drama" vs. not. This is the
shape auto_score_by_description works best on: narrow concrete categories
with consistent description templates.

### K-drama rollup (rating 6, 1841 articles, ~4 min)

**Shape fit:** single-source topic. 100% of corpus from "List of
Korean dramas". AI explicitly flagged zero triangulation as a risk;
rating 6 reflects this + K-drama-specific structural issues.

### NEW signals unique to K-drama

1. **`survey_categories` DID emit an oversized-tree warning.** On
   "South Korean television series" (6087 articles, 212 subcats),
   survey returned `"Consider pulling specific subcategories rather
   than the whole tree."` The AI heeded it and skipped
   `get_category_articles` entirely. **Contradicts my earlier Lakes
   observation** — the warning IS implemented, but only on
   `survey_categories`, not at `get_category_articles` call time.
   Modest extension: predict cost at both call sites.
2. **Silent zero-article category soft-redirects.** `Category:Korean
   television dramas` returns 0 articles because it's a container
   redirecting to a sibling. AI wants a "try this instead" hint.
3. **Category structural pollution (~40%).** 6087-article tree is
   padded with poster / title-card / promotional-image subcategories.
   Upstream taxonomy issue, not tool.
4. **Wikidata TV-series typing is inconsistent.** Q21191270
   (television drama series) vs. Q5398426 (any TV series) — neither
   property hits the ~1867 canonical dramas cleanly. Upstream
   data-modeling issue.
5. **No single-source warning at export time.** AI suggests: at
   export, warn "0% triangulation — consider adding a second source."
   **New build-plan candidate.**
6. **`harvest_navbox(template)` named again** (K-drama explicitly,
   Pulitzer implicitly). Third session to request it. Clear build-plan
   candidate.
7. **Intersection-based triangulation named again** — "list_page AND
   category:X". Three sessions explicitly demanding set-intersection
   primitives.

### Hypothesis deltas from K-drama

| # | Status | Note |
|---|---|---|
| 1 | Confirmed | ~18 probes, 94% hit rate; 1 real miss recovered |
| 2 | Confirmed | rating 6 at top level |
| 3 | Confirmed | Notes throughout |
| 4 | Confirmed, shape-fit matters | SPARQL as sizing probe, not gather source |
| 5 | Confirmed | Same pattern |
| 6 | Partial | "Zero source triangulation" = structural coverage hint |
| 7 | Not directly tested | AI may have learned to avoid compound OR |

---

## Topic 25: Symbolism (art movement)

Started 16:38:10, 9 seconds after K-drama feedback. Novel shape mix
— historical art movement + named figures + works + influence.
Closest task.md candidate: "abstract concept."

### Early shape signals

```
16:38:26  survey_categories(Symbolism (arts), d=2) -> 16 cats
16:38:26  find_list_pages(Symbolism) -> 13 pages (FINALLY a rich hit!)
16:38:27  wikidata_search_entity(Symbolism) -> 5 candidates
16:38:45  get_category_articles(Symbolism (arts), d=3) -> 478 articles
16:38:46  wikidata_entities_by_property(P135, Q164800) -> 469, 297 on en
16:38:56  harvest_list_page(Symbolism (movement)) -> 533 links, 368 new
16:40:09  add_articles(wikidata:P135=Q164800, 297) -> added 153, updated 144
```

### NEW signals

1. **`find_list_pages` finally hit rich (13 pages).** First topic in
   the arc where the narrow prefix heuristic worked well. Topic name
   "Symbolism" matches "List of X" cleanly. Confirms: heuristic works
   when the topic has well-named `List of X` pages; fails otherwise.
2. **P135 = movement — fourth shape-specific Wikidata property.**
   | Shape | Property |
   |---|---|
   | Awards-anchored biography | P166 award received |
   | Geographic feature | P31/P279* ∩ P17 (type × country) |
   | Abstract concept / discipline | P101 field of work |
   | Art movement | P135 movement |
3. **Three-way triangulation:** 478+533+297 = 999 raw → 982 filtered.
   Healthier than K-drama or Phenomenology.

### Symbolism rollup (rating 6, 946 articles, ~4 min)

No spot-check burst, no browse_edges — session went straight from
source-triangulated reject → export → feedback. Two reject passes
(26 + 13) against the list-only bucket.

### NEW signals unique to Symbolism

1. **NOVEL BUG — `harvest_list_page` extracts image-caption text as link
   titles.** AI's note + feedback both capture:
   > "Bug in harvest_list_page: image alt/caption text with artist-
   > work-year-museum format got treated as article titles. The source
   > page's HTML structure probably has [[Target|Caption text]] syntax
   > where the caption is used as link text."
   Concrete examples: "Arnold Böcklin – Die Toteninsel I, 1880
   (Kunstmuseum Basel)", "Gustav Klimt, Allegory of Skulptur, 1889…",
   "Mikhail Vrubel, The Swan Princess, 1900…". 11 caption artifacts
   total. `filter_articles` didn't drop them because MediaWiki's
   no-match on redirect resolution is treated as "valid title." **Two
   distinct bugs in one observation:**
   - harvest_list_page uses link-text instead of link-target
   - filter_articles treats unresolved titles as valid
2. **`wikidata_entities_by_property` overflowed at 85kb.** Second arc
   session to hit the overflow limit, on a different tool from Lakes'
   `wikidata_query`. Same pattern: AI rewrote as SPARQL with trimmed
   fields. **Generalized problem:** any Wikidata tool that returns
   large result sets is subject to context overflow. Cross-tool fix
   wanted.
3. **`find_list_pages` homonym trap.** Returned 13 pages, ALL about
   semiotic/religious symbolism — "Religious symbol", "Language of
   flowers", "National symbol", "List of flags with Christian
   symbolism". ZERO about the art movement. The prefix heuristic
   can't disambiguate "Symbolism (art movement)" from
   "symbolism (concept)". This is a new failure mode distinct from
   earlier "0 hits": **wrong hits, looking authoritative.**
4. **`filter_articles` doesn't drop titles-not-in-MediaWiki.** When
   redirect resolution returns no match, filter treats as valid.
   Concrete fix: drop unresolved titles. Would have caught the 11
   caption artifacts.

### Hypothesis deltas from Symbolism

| # | Status | Note |
|---|---|---|
| 1 | Confirmed-conditional | No spot-check burst; AI judged triangulation sufficient despite 24% multi-source — rated 6, so maybe should have done it |
| 2 | Confirmed | rating=6 at top level, all fields properly populated |
| 3 | Confirmed | Rich notes throughout |
| 4 | Confirmed | P135 (movement) — fourth shape-specific Wikidata property |
| 5 | Confirmed | `get_articles_by_source` + `reject_articles` pattern, twice |
| 6 | Implicit only | No explicit coverage % — "19/19 canonical spot-check hit" in `what_worked` is narrative coverage claim |
| 7 | Not tested | `intitle:` OR form didn't fire; AI may have learned to avoid |

---

# Cross-topic summary — 5-topic arc

Topics built in this arc (all 2026-04-23, all enwiki, all autonomous):

| # | Topic | Articles | Time | Rating | Shape |
|---|---|---|---|---|---|
| 21 | Pulitzer Prize for Investigative Reporting | 213 | 12 min | 7 | Awards-anchored biography |
| 22 | Lakes of Finland | 365 | 5 min | 8 | Geographic feature |
| 23 | Phenomenology (philosophy) | 466 | 4 min | 6 | Abstract concept (polysemous) |
| 24 | Korean television dramas | 1841 | 4 min | 6 | Contemporary pop culture (single-source) |
| 25 | Symbolism (art movement) | 946 | 4 min | 6 | Art movement (cross-disciplinary) |

Plus Apollo 11 from run 1 (699 articles, rating 7, single historical
event shape). **All 6 feedbacks are candid, detailed, properly
populated** — the task.md patch around field-separation landed cleanly.

## Hypothesis matrix — all 7 × all 6 topics

(`✅` = confirmed, `⊘` = deliberately skipped, `⚠️` = partial, `–` = not tested)

| # | Apollo 11 | Pulitzer | Lakes | Phenomen. | K-drama | Symbolism |
|---|---|---|---|---|---|---|
| 1 autonomous spot-check | ✅ | ✅ (~30) | ⊘ tight tri. | ✅ (27) | ✅ (~18) | ⊘ skipped |
| 2 rating top-level | ⚠️ XML-packed | ✅ 7 | ✅ 8 | ✅ 6 | ✅ 6 | ✅ 6 |
| 3 `note=` used | ⊘ zero | ✅ | ✅ | ✅ | ✅ | ✅ |
| 4 Wikidata on shape | ⊘ none | ✅ P166 | ✅ P31/P279*+P17 | ✅ P101 | ✅ (sizing) | ✅ P135 |
| 5 `remove_by_source` used | ⊘ | ⊘ | ⊘ | ⊘ | ⊘ | ⊘ |
| 6 explicit coverage % | – | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| 7 `intitle:OR` bug hit | ✅ 4+ | ✅ | – | ✅ (3rd) | – | – |

## Build-plan candidates, ranked by repeat-mention

| Rank | Candidate | Topics | Severity / Notes |
|---|---|---|---|
| 1 | `remove_by_source(keep_if_other_sources=True)` invisible | 6/6 | Instruction visibility fix only — pure doc change |
| 2 | `find_list_pages` heuristic too narrow + homonym-blind | 5/5 | All 5 had issues; Symbolism added homonym-trap failure mode. Single tool, multi-fix |
| 3 | `intitle:"A" OR intitle:"B"` silent-empty bug | 3/6 (Apollo, Pulitzer, Phenomen.) | AI calls it "single most impactful workflow bug"; ~1-hour fix |
| 4 | `harvest_navbox(template)` primitive | 3/6 (Pulitzer, K-drama, Apollo implicit) | New primitive, clear scope |
| 5 | Set-intersection primitive (category ∩ wikidata, list ∩ category) | 3/6 (Apollo, Pulitzer, K-drama) | Named repeatedly; enables "confidence core" view |
| 6 | Main-article-as-list-page as documented fallback | 3/6 (Pulitzer, Phenomen., Symbolism) | Instructions doc update |
| 7 | `cross_wiki_diff` for "articles to translate" | 3/6 (Lakes, Phenomen., Symbolism) | Named; natural outgrowth of sitelink-gap observations |
| 8 | Wikidata result-overflow handling (2 distinct tools) | 2/6 (Lakes, Symbolism) | Cross-tool — `wikidata_query` AND `wikidata_entities_by_property` |
| 9 | `harvest_list_page` quality bugs | 2/6 (Apollo prose-noise, Symbolism caption-as-title) | Two bugs in same code path; one targeted pass |
| 10 | `filter_articles` gaps | 3/6 (Lakes non-standard disambig, Phenomen. implicit, Symbolism no-match titles) | Small individual fixes |
| 11 | `browse_edges` relevance scoring | 2/6 (Pulitzer, Phenomen.) | Over-broad on abstract-concept shape |
| 12 | Single-source warning at export | 1 (K-drama) | Easy addition; 0-triangulation signal |
| 13 | `auto_score_by_description` substring edges | 1 (Pulitzer, place-name words) | Small; mode-flag fix |
| 14 | `find_wikiprojects` vs `check_wikiproject` disagree | 1 (Phenomen.) | Concrete bug; harmonize the APIs |
| 15 | `fetch_descriptions` REST fallback on enwiki | 1 (Pulitzer, 20% blank impact) | Existing code path; easy extension |
| 16 | `topic_policy(include_desc, exclude_desc)` | 1 (Phenomen.) | New primitive; potentially big but single-topic evidence so far |
| 17 | `check_article_presence(titles=[])` | 1 (Pulitzer) | Replaces spot-check regex hack |
| 18 | `verify_claim(title, prop, value)` | 1 (Pulitzer) | Structured vs. "Name" "phrase" search |
| 19 | `list_rejections(show_reasons=True)` | 1 (Pulitzer) | Audit view |
| 20 | Soft-redirect category hint | 1 (K-drama) | "Try this instead" |
| 21 | `coverage_estimate` field on submit_feedback | 0 directly (but plan 6.7, validated by arc) | Structural addition |

## Net NEW primitives the AI named (across all 6 feedbacks)

- `harvest_navbox(template)` — 3 mentions (winner)
- `cross_wiki_diff(topic, source, target)` — 3
- Set-intersection / PetScan-style primitive — 3
- `check_article_presence(titles=[...])` — 1
- `verify_claim(title, prop, value)` — 1
- `list_rejections(show_reasons=True)` — 1
- `topic_policy(include_desc, exclude_desc)` — 1
- `include_by_description` (Apollo 11) — 1
- `backlinks(title)` (Apollo 11) — 1
- `report_coverage_estimate(...)` (plan 6.7) — implicit from arc

## Shape → Wikidata property map

| Shape | Property | Topic | Rating |
|---|---|---|---|
| Single historical event | P361/P793/P138 (AI-hypothesized in Apollo feedback; not exercised) | Apollo 11 | 7 |
| Awards-anchored biography | P166 (award received) | Pulitzer | 7 |
| Geographic feature | P31/P279* ∩ P17 (type × country) | Lakes | 8 |
| Abstract concept / discipline | P101 (field of work) | Phenomenology | 6 |
| Pop culture franchise | P31/P279*+P495 (as sizing probe, not gather) | K-drama | 6 |
| Art movement | P135 (movement) | Symbolism | 6 |

This table is build-plan-relevant: if we encode it in
`server_instructions.md`, future sessions won't need to empirically
rediscover the right property per shape.

## Ratings distribution + triangulation correlation

| Topic | Triangulation (multi-sourced %) | Rating |
|---|---|---|
| Lakes of Finland | 85% | 8 |
| Pulitzer | moderate (not explicit) | 7 |
| Apollo 11 | moderate | 7 |
| Symbolism | 24% | 6 |
| Phenomenology | 17.5% | 6 |
| K-drama | 0% | 6 |

**Strong monotone correlation.** Triangulation quality predicts
rating. This is a free signal the server already has (source counts
per article) — could be computed and shown at export time.
Informally: the AI rates lower when triangulation fails because
noise review becomes harder, coverage confidence drops, and missing
primitives (intersection, cross-wiki, coverage estimate) become more
painful in direct proportion.

## Signals that only appeared once — don't over-weight

- Unicode NFD/NFC robustness (Lakes, flag-only, no bug observed)
- EN DASH vs HYPHEN in Finnish lake names (Lakes, flag-only)
- Category structural pollution via posters/covers (K-drama)
- `auto_score_by_description` substring edge on place-names (Pulitzer)
- `find_wikiprojects` vs `check_wikiproject` disagreement (Phenomenology)
- Soft-redirect category hint (K-drama)
- `fetch_descriptions` REST fallback gap on enwiki (Pulitzer)
- `topic_policy` primitive (Phenomenology)
- `verify_claim` / `check_article_presence` / `list_rejections` primitives (Pulitzer)

These might still matter — but the arc only supports acting on the
multi-mention items first.

## What to build next (5 bullets)

Based on multi-topic evidence; in cost/impact order:

1. **Fix `intitle:"A" OR intitle:"B"` silent-empty bug.** 3-session
   confirmation, severity high, ~1h fix. Remove the biggest silent-
   failure surface.
2. **Widen `find_list_pages` heuristic + add a second-pass
   disambiguation filter.** All 6 topics had issues. Widen prefix to
   include "Index of", "Timeline of", "Outline of", "X in popular
   culture"; second-pass filter candidate pages by lead-sentence
   match to topic description (catches the Symbolism homonym trap).
3. **Surface `remove_by_source(keep_if_other_sources=True)` in
   `server_instructions.md`.** 6/6 sessions used the verbose
   alternative — pure instruction visibility fix, zero code. Likely
   the highest leverage-per-effort item in the arc.
4. **Ship `harvest_navbox(template)`.** 3-session request. Small
   scope primitive (parse navbox template, extract links). Pairs
   naturally with the existing harvest_list_page machinery.
5. **Single Wikidata-result-overflow fix, cross-tool.** 2 sessions,
   2 different tools — `wikidata_query` and
   `wikidata_entities_by_property`. Shared server-side pattern:
   truncate-with-warning + optionally paginate. One fix, two tools.

Then the Stage-6.7 `coverage_estimate` + self-administered
spot-check modality lands naturally on top — the arc validated
that triangulation is a usable proxy for AI-estimated coverage,
and the spot-check loop is already running (just not structured
output-wise).

---

**Monitoring complete.** Run-2 arc = 5 topics, 4 shapes new + 1
shape (Symbolism) novel. Feedback from 6 topics (incl. Apollo 11)
gives high-confidence direction on the next build sprint.

**Implication for task.md:** the §3 guidance landed — autonomous
spot-check happened. But the "target ~50 candidates across ≥5 subdomains"
floor didn't translate. Either (a) the AI judged 14 was enough for this
topic shape (plausible — awards-bio is narrower), or (b) the numeric
target in task.md got treated as soft. If we want 50+ to stick as a
floor, probably needs restating or a structural cue.

#### ✅ #5 partial answer — still `get_articles_by_source` + `reject_articles`, NOT `remove_by_source`

Same pattern as Apollo 11. Two sessions, same AI-visible tool surface,
same preference for the composable primitive. Probably worth nudging in
`server_instructions.md` — "`remove_by_source(keep_if_other_sources=True)`
is the one-call shortcut for this pattern" would add visibility to a
tool that's evidently getting skipped.
