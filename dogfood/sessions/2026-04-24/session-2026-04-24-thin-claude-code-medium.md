# Dogfood session notes — 2026-04-24 (thin briefs, Claude Code, medium effort)

> **What this is.** First Claude-Code-driven thin-variant ratchet round
> against the 5 benchmark topics, run autonomously off
> `fetch_task_brief(task_id="<slug>-thin")` with no operator steering.
> Counterpart to the 2026-04-23 Codex fat-variant arc — same topics,
> same scope statements, but every operational detail (target counts,
> shape hints, reach targets) stripped from the brief. The substrate
> being measured is `server_instructions.md` (49.7k chars, including
> the recently-shipped SHAPE → WIKIDATA PROPERTY table + KNOWN SHARP
> EDGES + SOURCE-TRUST + intersectional-leads pointer).
>
> Runs landed 02:31–03:23 UTC; the post-run baseline rebuild
> (commit `f73157c`) lifted these exact metrics into
> `benchmarks/<slug>/baseline.json`, so this is the first cycle where
> "thin variant beats thin baseline" becomes the gate. The scoreboards
> still failed under the old fat-variant baselines (every topic
> "regressed" recall) — that's a measurement artifact, not a
> regression we should chase. The real artefacts to mine are *how*
> the AI built each topic and where the substrate let it down.

## Topline

| Topic | Corpus | Precision | Recall | Reach | API | Tools | Wall (s) | AI rating | AI conf |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| apollo-11 | 92 | 55.4% | 33.1% | 0 | 117 | 35 | 682 | 7 | 0.74 |
| crispr-gene-editing | 58 | 100.0% | 52.0% | 5 | 141 | 49 | 588 | 7 | 0.72 |
| african-american-stem | 863 | 99.3% | 85.4% | 114 | 453 | 96 | 1949 | 7 | 0.68 |
| hispanic-latino-stem-us | 199 | 95.4% | 58.9% | 5 | 480 | 59 | 1165 | 7 | 0.72 |
| orchids | 5044 | 100.0% | 50.1% | 0 | 2075 | 52 | 1313 | 7 | 0.72 |

(Recall is computed against the redirect-aware gold *after* the
2026-04-24 reach audit pulled 60 + 4 + 3 = 67 newly-classified `in`
rows into the AA-STEM / HL-STEM / CRISPR golds. Apollo and orchids
golds were unchanged that pass.)

## The single biggest signal: rating + confidence are pegged

Every one of the five topics self-rated **7/10** with
`coverage_estimate.confidence` between **0.68 and 0.74**. Actual recall
spans **33% → 85%** — a 52-point spread the AI compressed into a
6-point band of self-confidence. Calibration error per topic, in
absolute points:

| Topic | Stated conf | Actual recall | |Δ| |
|---|---:|---:|---:|
| AA-STEM | 0.68 | 0.85 | 17 (under) |
| Orchids | 0.72 | 0.50 | 22 (over) |
| HL-STEM | 0.72 | 0.59 | 13 (over) |
| CRISPR | 0.72 | 0.52 | 20 (over) |
| **Apollo 11** | **0.74** | **0.33** | **41 (over)** |

Apollo 11 — the lowest-recall, lowest-precision topic in the round —
got the *highest* stated confidence. The AI is anchoring at "I did the
pipeline, so 7/0.7" regardless of whether triangulation actually
landed. The brief explicitly tells it "an honest 0.6 is more useful
than an inflated 0.9" but the band collapsed to 0.7 anyway.

Sub-signal worth keeping: the rating is a *single number with no
standard*. The brief and instructions don't give the AI a rubric for
mapping signals → confidence band, and the structured
`coverage_estimate` schema doesn't surface anything the AI computed
itself (it just asks for prose rationale). When everyone gets a 7,
the rating column on the scoreboard is dead.

## The next-biggest signal: triangulation tracks recall

Source-overlap stats from the baselines, sorted by multi-sourced %:

| Topic | Multi-sourced % | Recall |
|---|---:|---:|
| AA-STEM | 47.2 | 85.4 |
| HL-STEM | 31.7 | 58.9 |
| Orchids | 20.7 | 50.1 |
| Apollo 11 | 0.0 | 33.1 |
| CRISPR | 0.0 | 52.0 |

Strict monotone except for the CRISPR vs. Apollo flip — and CRISPR's
"100% single-sourced" is misleading because its single source was
search-led against a small definable subject area, while Apollo 11's
single source was a category pull on a topic with rich structural
backbone the AI didn't reach for. Triangulation isn't *causing*
recall, but the same upstream choices produce both. **The server
already has source-count per article; surfacing it as a
"triangulation %" in `get_status` and at wrap-up would let the AI
see what we're seeing.**

## Per-topic short reads

### Apollo 11 — only run that failed precision too

55.4% precision is the outlier of the round; everything else cleared
95%. The 41 false positives are dominated by the **"X lunar sample
displays"** family (Alaska / Hawaii / Cyprus / Honduras / etc.) plus
"Dark Side of the Moon (2002 film)" / "Fly Me to the Moon (2008/2024
films)" / "Footprints on the Moon (1969 film)". These look in-scope on
shortdesc — they reference Apollo 11 lunar samples / moon landing —
but the gold scope statement says "things officially named after
[Apollo 11]," and a *display of moon rocks* isn't named after the
mission; it's named after the state that hosts it. The rubric the AI
drafted from the scope statement evidently let these in.

The 103 missed gold are core-mission articles: **Apollo 8, Apollo 10,
Apollo 12, Apollo program, Apollo Telescope Mount, Apollo Lunar
Sample Return Container, Apollo Docking Mechanism**. These aren't
peripheral — they're the program around the mission. The AI's
feedback explicitly named what was missing:

> "Category membership was not exhaustive for the mission stack… I
> did not use navbox harvests or a Wikidata/property-based sweep."

The shape table has had a `harvest_navbox` first-move recommendation
for the "Single historical event (with cultural tail)" row since
1.d landed (2026-04-24), and Apollo 11 is exactly that shape. **The
recommendation didn't fire.** Tool counts confirm: zero `harvest_navbox`
calls, zero `wikidata_query` / `wikidata_entities_by_property` calls.
The pipeline ran but the *shape-typed first move* was skipped.

### CRISPR — the structurally-poor topic

CRISPR has effectively no structural backbone: empty Category:CRISPR,
no useful WikiProject, no canonical list page. The AI went search-led
(29 of 49 calls were `preview_search`) and built a tight, 100%-precise
58-article core. The 49 missed gold articles include **Beta
thalassemia, Broad Institute, Gene therapy, Gene knockout, Genetic
engineering, Genetically modified animal, Colossal Biosciences** —
topically-adjacent items that a `morelike:` sweep or a Wikidata
"used by CRISPR" probe would have caught.

CRISPR's `sharp_edges_hit` listed `intitle_or_silent_empty`. The
splitter (`_split_intitle_or_query` in `server.py:2434`) only fires
on queries that are **purely** `intitle:"A" OR intitle:"B"` —
anchored start to end. The AI hit polysemy with `SHERLOCK` / `DETECTR`
and probably tried a compound form mixed with another keyword, which
the regex won't match. So either (a) the CRISPR session genuinely
re-hit the bug on a query shape the splitter doesn't cover, or (b)
the AI saw a 0-result and reached for the suggested-tag vocabulary in
the `submit_feedback` docstring (`intitle_or_silent_empty` is listed
there). Both are worth investigating — the docstring vocabulary may
be priming false-positive sharp-edge reports, and the splitter regex
may be too narrow.

### African-American STEM — the success case

99.3% precision, 85.4% recall, 114 reach beyond gold (the largest
reach-growth signal in the round). Almost half the corpus is
multi-sourced — list pages and category pulls genuinely overlapped.
This was also by far the most cleanup-heavy session: **35 of the 96
tool calls were `remove_by_pattern`** (~36%), with 9 more on
`auto_score_by_description`. The AI built broadly, then cleaned
aggressively against an explicit STEM-profession gate. That recipe
worked.

Friction the AI reported and we should keep:

- **Sticky rejections blocked manual gap-add.** When the AI rejected
  an article via `auto_score_by_description` and later realized it
  needed adding back manually, the sticky-rejection table refused
  the add. Required a separate `unreject_articles` round-trip. AI
  noted this as friction.
- **`resolve_redirects` redirected biography titles to non-biographical
  targets** (e.g. "Death of X", "Family of X" articles). The hygiene
  step is currently lossy when redirect targets diverge in *meaning*,
  not just spelling/punctuation.
- **Transient 504s on large `remove_articles` calls** despite the
  300s nginx timeout bump. Concurrency-under-heavy-tool-load is still
  real; this round adds a third independent observation.

### Hispanic/Latino STEM — same shape, half the recall

Same intersectional-bio shape as AA-STEM, but recall stalled at 59%
where AA-STEM hit 85%. The structural delta:

- AA-STEM's category tree had multiple usable parents
  ("African-American scientists", "African-American inventors",
  "African-American mathematicians", etc.) plus several curated list
  pages.
- HL-STEM's "Hispanic and Latino American scientists" category was
  overinclusive (economists, anthropologists, politicians,
  businesspeople) and the WikiProject template search returned zero.
  AI: *"I did not do a systematic pass over every nationality-specific
  American list page because the available search/list tools were too
  noisy for that shape."*

False positives include **Severo Ochoa** (Spanish, not US-affiliated)
and **Francisco J. Ayala** (similar) — exactly the scope-edge
"US-affiliation" condition the rubric was supposed to enforce. The
intersectional-bio row in the SHAPE table mentions cleanup time
explicitly but doesn't give the AI a probe pattern for the
US-affiliation gate.

### Orchids — taxonomy at scale, half-swept

5044 articles at 100% precision, 50% recall against a 7354-article
gold. Reach 0 — every corpus article was already in gold. This is
**a "stopped early" failure on a topic where the universe is
enumerable.** The AI harvested `Category:Orchids`, `List of
Orchidaceae genera`, and a couple of regional lists, then wrapped
up with "did not exhaust every regional list or Wikidata-based
descendant strategy" as a missed strategy. The shape table doesn't
have an explicit "did you sweep all regional / by-country lists?"
prompt for taxonomy.

The only Wikidata probe this whole session was a single
`wikidata_search_entity` call for "Orchidaceae" — no SPARQL. A
`P171` (parent taxon) recursive query rooted at Orchidaceae was the
AI-named missed strategy and would have surfaced thousands more
species directly.

## Cross-topic patterns

### 1. The Wikidata probes don't fire

| Topic | wikidata_query | wikidata_entities_by_property | wikidata_search_entity | harvest_navbox |
|---|---:|---:|---:|---:|
| Apollo 11 | 0 | 0 | 0 | 0 |
| CRISPR | 0 | 0 | 0 | 0 |
| AA-STEM | 0 | 0 | 0 | 0 |
| HL-STEM | 0 | 0 | 0 | 0 |
| Orchids | 0 | 0 | 1 | 0 |

Five topics, near-zero reaches for the two strategies the SHAPE
table explicitly recommends. Every single topic's
`missed_strategies` named Wikidata or SPARQL. The Codex fat-variant
arc (2026-04-23) reached for `wikidata_entities_by_property` /
`wikidata_query` on 4 of 6 topics. **The thin brief leaving the
shape-typed-first-move call out makes the difference**: Codex was
told "expect ~700 articles, here are the shape-specific properties,"
Claude was told only the scope paragraph. The substrate in
`server_instructions.md` is supposed to compensate; on this evidence,
it doesn't.

### 2. Pipeline-recipe vs. shape-recipe

Every session followed the same outer pipeline (start_topic →
set_topic_rubric → find_wikiprojects → survey_categories →
find_list_pages → wikidata_search_entity → category/list pull →
fetch_descriptions → cleanup → submit_feedback). What varied was
*how much weight each step carried*. Shape-typed strategies — the
"high-leverage first move" column added in 1.d — got skipped
universally except where they coincided with the default pipeline
(category pull was the first move for AA-STEM and orchids by
default, not because of shape-typing).

### 3. List-page contamination keeps eating cleanup budget

`main_content_only=True` is the default and it does strip navboxes,
but **list-page intros / running prose still link to non-list-member
articles** (concepts, places, organizations, missions). AA-STEM did
35 `remove_by_pattern` calls cleaning this up. Orchids reported the
same issue: regional orchid lists pulled in geography, ecology,
broad taxonomy. HL-STEM reported it. The harvester's body-link
extraction is still too greedy for prose-heavy list pages.

### 4. AI calibration is anchored, not measured

Five topics, five `7`s, five `0.7±0.04`s — across recall ranging
33% to 85%. Worth restating: **the AI is using the rating field as
"I followed the protocol" and the confidence as "I'm reasonably
sure I followed the protocol," not as measurements of the corpus
quality.** This isn't malice; the schema doesn't ask for anything
quantitative the AI can ground in.

### 5. The AI references SHARP EDGE tags it may not have hit

`shortdesc_misleading` was tagged on 5/5 topics, `intitle_or_silent_empty`
on CRISPR despite a deployed splitter, `container_category_empty` on
HL-STEM and orchids (legitimately — both saw it). The
`submit_feedback` docstring suggests vocabulary from this list, which
makes the field useful as a survey instrument but suspect as a
ground-truth bug-tracker. Worth distinguishing
"I-saw-this-symptom" from "I-applied-a-known-tag-because-it-fit."

## Friction this round added that wasn't in the backlog

Items the AI surfaced specifically in `tool_friction` /
`what_didnt`, deduped:

1. **Sticky rejections block legitimate manual re-add.** AA-STEM hit
   it after the STEM-profession gate over-rejected canonical
   biographies. Workflow gap: gather tools should warn-and-allow on
   "you previously rejected this title — override?" instead of
   silent skip.
2. **`resolve_redirects` is destructive on biography → non-bio
   redirects.** AA-STEM. Suggests a "lossy-redirect" warning when
   the canonical title's Wikidata QID differs from the source title's
   QID, or when title shape changes meaningfully (anything beyond
   case / punctuation / minor spelling).
3. **Transient 504s persist on heavy `remove_articles` and
   `harvest_list_page` calls.** AA-STEM (504 on remove), HL-STEM
   (504 on harvest + add), orchids (transport timeout on
   fetch_descriptions + survey_categories). The 60→300s nginx bump
   isn't sufficient; concurrency Tier-1 item now has 4-of-5 sessions
   of evidence.
4. **List-page intro/body prose contamination** despite
   `main_content_only=True`. Three sessions named it; the harvester
   needs a tighter "links inside the enumerated section only" mode
   or explicit section selection.
5. **`auto_score_by_description` STEM-profession gate over-rejects
   on thin shortdescs** — AA-STEM (Patricia Bath / Dorothy Vaughan
   bucket). The SOURCE-TRUST guidance landed in 1.d but the auto-
   reject doesn't honor it: an article from a topic-definitional
   list page should not be evictable by shortdesc-pattern alone.
6. **`fetch_descriptions` transport timeout when server keeps
   working.** Orchids reported this: client times out, server
   continues filling, AI doesn't know whether to retry or wait.
   Suggests an "idempotent resume" / "what's still pending?" check
   that doesn't itself trigger a long-running call.

## What this round points to (candidate changes, not yet ranked)

These are the directions the evidence suggests. Pick-and-rank for
backlog promotion in a follow-up; the multi-topic-evidence ones are
the strongest candidates.

### Substrate-side (server_instructions.md / brief)

A. **Force the shape-typed first move.** The SHAPE table is in
   instructions but the AI walks past it. Possible shapes:
   - A pipeline-step insertion ("Step N+: name your topic shape and
     name the high-leverage first move; if it's not in your tool
     plan, justify why").
   - A `suggest_shape_strategy(topic_summary)` tool that returns the
     applicable row(s) — turns a passive table into an active
     prompt.
   - Embed the shape-table guidance into the rubric-set step (the AI
     already calls `set_topic_rubric` once at start; that's the
     natural spot to also commit to a shape + first-move plan).
   Multi-topic evidence: **5/5**.

B. **Calibrate confidence against signals, not vibes.** Replace the
   single `confidence` float with banded inputs the AI must compute:
   triangulation %, # of shape-typed strategies attempted, # of gap
   probes that came back hit. Map those to a band recommendation
   server-side. Or expose `triangulation_pct` in `describe_topic` and
   require the AI to cite it in the rationale. Multi-topic evidence:
   **5/5** (rating 7 / conf ~0.7 across the board).

C. **Shape-typed gap-check checklist at wrap-up.** WRAP-UP guidance
   should ask, by shape: "Have you swept all regional / by-country
   lists?" (taxonomy), "Have you checked the parent-program navbox?"
   (event), "Have you tried `morelike:` from your top 3 seeds?"
   (search-led on structurally-poor topics like CRISPR). Five-of-
   five sessions named at least one shape-typical missed strategy
   in `missed_strategies`.

### Tool-side (server.py)

D. **Surface triangulation % in `get_status` and gather responses.**
   Already computed (single_sourced / multi_sourced exist on the
   baseline export). Show it on `describe_topic` so the AI can see
   whether its sources actually overlap. Multi-topic evidence:
   **5/5**.

E. **Soften sticky rejections on explicit manual add.** Don't
   silently skip — return `{ added: 0, blocked_by_rejection:
   [{title, reason}], hint: "call unreject_articles({titles}) then
   retry" }`. AA-STEM evidence; pattern likely to recur on any
   STEM-profession-gate-style topic.

F. **`resolve_redirects` lossy-target detection.** When the canonical
   title and the source title have meaningfully different Wikidata
   QIDs (or no QID match), flag rather than silently rewrite.
   Specifically: do not auto-merge a biography into a non-biography
   target. AA-STEM evidence.

G. **Widen `_split_intitle_or_query` to handle compound queries
   that include an extra free-text term** (`intitle:"A" OR
   intitle:"B" subject`). Verify against CRISPR's session log if we
   can pull it; otherwise leave as a regex audit candidate. Single
   session of evidence (CRISPR), with calibration caveat about the
   suggested-vocab priming.

H. **`harvest_list_page` "enumerated section only" mode.** Three
   sessions reported intro/body prose contamination. A
   `enumerated_only=True` flag (extract only links inside `<ul>` /
   `<ol>` / table rows that look like list-entries, ignore links in
   `<p>`) would catch most of it. Multi-topic evidence: **3/5**.

I. **Source-trust gate on `auto_score_by_description`.** When an
   article's source includes a topic-definitional list-page or
   category, the auto-reject should require a second signal before
   firing. AA-STEM evidence + matches the 1.d SOURCE-TRUST guidance
   not yet enforced in code.

J. **`fetch_descriptions` resumability indicator.** A read-only
   `descriptions_pending(topic)` that returns "N titles still need
   descriptions" without triggering a fetch — so AI can decide
   whether the prior timeout actually completed. Orchids evidence.

### Concurrency

K. **Multi-worker Tier 1 item is overdue.** Four of five sessions
   reported transient 504s under heavy single-tool load despite the
   nginx-300s bump. The cooperative-yielding work is already in
   `_walk_category_tree` / `filter_articles` (Stage 3 shipped) but
   evidently doesn't help when the heavy tool is a long
   `harvest_list_page` or `remove_articles` chunk. Promote.

### Process / measurement

L. **Strip suggested vocabulary from `submit_feedback` docstring or
   re-frame it.** The vocabulary list serves as a survey instrument
   (good for tracking) but it primes the AI to apply tags it may
   not have empirically encountered (CRISPR `intitle_or_silent_empty`
   may be priming, may be real). Either separate "tags I observed"
   from "tags consistent with what I saw" or move the vocabulary
   into a separate enum-like field.

M. **Add a baseline-rebuild hygiene step to the ratchet protocol.**
   This round's scoreboards compared thin runs against fat baselines
   and showed dramatic "regressions" that were really
   measurement-substrate changes. The post-run rebuild
   (commit `f73157c`) handled it correctly, but the scoreboards
   themselves are now stale. Worth either deleting them or adding
   a `--baseline=archive-20260424` flag so they can be regenerated
   honestly when comparing thin-vs-thin.

## Cross-reference to existing backlog

Items here that already have a backlog entry (don't double-count):

- **K (multi-worker / concurrency)** — already Tier 1 in
  `docs/backlog/README.md`. This round adds 4-session evidence.
- **B / D (calibration + triangulation surfacing)** — partially
  covered by the Tier 1 1.b work that already lifted source-count
  fields into baseline.json. The remaining work is exposure to the
  AI at runtime, not capture.
- **G (intitle:OR widen)** — was shipped as Chunk 1 of the
  post-orchids dogfood arc; this is potentially a regression or a
  scope-of-fix question, not a new item.

Items that look new on this evidence:

- **A (force-shape-first-move)** — strong multi-topic case.
- **C (shape-typed wrap-up gap-check)** — same.
- **E (sticky-rejection block on manual add)** — single topic but
  clear UX gap.
- **F (resolve_redirects lossy-target detection)** — single topic,
  worth verifying on the actual redirect map before promoting.
- **H (harvest_list_page enumerated-only mode)** — three sessions.
- **I (source-trust gate on auto_score)** — directly extends 1.d.
- **J (fetch_descriptions pending-only check)** — single session.
- **L (strip / re-frame suggested vocabulary)** — process item.

## What we *didn't* learn

- **No reach-quality signal yet.** The 114 AA-STEM reach candidates
  haven't been audited (the prior reach audit covered the *previous*
  cycle's 114 AA-STEM reach). We won't know how much of this round's
  reach is genuine gold growth vs. noise until the next audit pass.
- **No second-cycle ratchet read.** Until we re-run thin variants
  against the now-thin baselines, we can't tell which of the changes
  above will actually move the gate. Promote the substrate-side
  items first (A / B / C / I) — they're cheap and have multi-topic
  evidence — then re-run before doing the bigger tool-side work.
- **Whether the suggested-vocab effect on `intitle_or_silent_empty`
  is real or priming.** Resolution: log the actual `srsearch` body
  on `preview_search` / `search_articles` calls and re-grep
  `usage.jsonl` for compound `intitle:` patterns post-fact.
