# Topic Builder benchmark run — apollo-11 (2026-04-23 ratchet)

You are running the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`) against a single benchmark topic. Your goal this session is to build a fresh corpus for this topic under a new, non-colliding name, ending with an honest `submit_feedback`. Your work will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs on the "single historical event with cultural tail" shape.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today):
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it at session start.
  - New `fetch_article_leads(titles, sentences=3)` tool — the fix for misleading Wikidata shortdescs. Reach for it when a shortdesc looks too thin or wrong to judge centrality.
- **Don't call `export_csv`.** The scoring script pulls the corpus directly from the server.
- **Use the EXACT run-topic name below.** The scoring script looks up the topic by name. Using the baseline name would overwrite frozen ground truth.

## Run-topic name

- **Run-topic name (exact):** `apollo-11 ratchet-2026-04-23`
- **Baseline name (DO NOT use):** `Apollo 11`
- **Wiki:** `en`

## Step 0 — Setup check

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions (came in on session init via the MCP `instructions=` channel). Note especially the SCOPE RUBRIC, PIPELINE, COMMON TASK → TOOL, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, WRAP-UP sections.
3. If tools aren't loaded, stop and surface the blocker.

## Step 1 — Persist the rubric

Call `set_topic_rubric(rubric=<verbatim text below>)`. Don't paraphrase — the server stores it as-is.

```
# Centrality rubric — Apollo 11 benchmark
# Frozen 2026-04-23. A rubric change invalidates gold.csv and requires re-audit.

CENTRAL — the mission itself, its crew (Armstrong, Aldrin, Collins) and
  ground-support personnel, its spacecraft and launch/landing hardware,
  the landing site and immediate lunar geology studied during the mission,
  primary cultural works directly about the mission (films, books,
  documentaries whose main subject is Apollo 11), things officially named
  after the mission (lunar features, awards, vessels, schools), and
  mission-specific artifacts, experiments, and memorabilia.

PERIPHERAL — adjacent Apollo program missions (Apollo 8, 10, 12 — the
  ones whose trajectories or personnel directly bear on 11), lunar
  geology articles that provide essential context for the landing site,
  later re-creations / anniversaries / reunions, crew biographies'
  non-Apollo-11 aspects (pre-astronaut careers, post-mission life) when
  the article is primarily about the person rather than the mission,
  and general Apollo program infrastructure that 11 used but wasn't
  unique to it (Saturn V, Lunar Module as classes).

OUT — general spaceflight history not specific to Apollo 11 or its
  immediate program neighbors; non-Apollo Moon programs (Luna, Chang'e,
  Surveyor, Chandrayaan); generic Moon / astronomy / selenology articles;
  Apollo-adjacent figures without a meaningful 11 connection; conspiracy-
  theory articles whose main subject is conspiracy discourse rather than
  11 itself; broad "space exploration in popular culture" articles that
  only mention 11 in passing.

# Notes for auditors:
# - "Primary cultural works" means the work's main subject is Apollo 11
#   (e.g. "First Man" biopic). Works that feature 11 as one scene among
#   many are OUT.
# - Crew biographies are CENTRAL (the person IS Apollo 11's crew). The
#   PERIPHERAL carve-out is for content WITHIN a crew biography that's
#   about the person separate from the mission — this doesn't typically
#   affect inclusion, just scoring.
# - The "things officially named after" clause is meant to be generous —
#   schools, streets, craters, awards all count even if the article about
#   them only mentions Apollo 11 once as the namesake.
```

## Step 2 — Internalize the scope

**Short statement:** Wikipedia articles whose primary subject is, or is directly a part of, the Apollo 11 crewed lunar-landing mission of July 1969 — its crew, spacecraft, landing site, science program, cultural legacy, and things officially named after it.

**In scope:**
- The mission itself (launch, flight path, landing, EVA, return, splashdown).
- Crew: Neil Armstrong, Buzz Aldrin, Michael Collins — full biographies.
- Ground support and mission control: Gene Kranz, Christopher Kraft, Steve Bales, Charles Duke (CAPCOM), other named controllers and flight directors with a documented 11 role.
- Spacecraft and hardware used by 11 specifically: Columbia (CSM-107), Eagle (LM-5), Saturn V SA-506. Ancillary hardware and experiments deployed on 11 (EASEP components, Passive Seismic Experiment, Laser Ranging Retroreflector, Early Apollo Scientific Experiments Package).
- Landing site: Tranquility Base, Mare Tranquillitatis context directly relevant to the landing.
- Primary cultural works about 11: films (*First Man*, *Apollo 11* (2019 doc), *Moonwalk One*), books (*Of a Fire on the Moon*, *Carrying the Fire*, *First Man* (Hansen), *Chariots for Apollo*), plays, songs whose main subject is 11.
- Things named after Apollo 11: schools, streets, lunar craters (Armstrong, Aldrin, Collins craters), US vessels, institutions.
- Artifacts and memorabilia of 11: Goodwill messages, lunar samples from the mission, landed hardware, display artifacts.
- Adjacent Apollo missions whose content materially overlaps 11: Apollo 8, 10, 12 as PERIPHERAL (trajectory rehearsal, preparatory tests, immediate successor).

**Explicitly out of scope:**
- Non-Apollo Moon programs (Luna, Chang'e, Surveyor, Chandrayaan, Pioneer, Ranger) — OUT.
- General spaceflight history ("History of spaceflight", "Timeline of space exploration", "Space Race") — OUT when they mention 11 but aren't primarily about it.
- Generic Moon / astronomy ("Moon", "Selenology", "Lunar geology" general) — OUT. Narrower geology articles specific to the 11 landing site — borderline, default PERIPHERAL.
- Conspiracy-theory articles (moon-landing conspiracy discourse) — OUT.
- Broad Apollo program articles ("Apollo program", "Project Apollo", "Apollo astronaut") — OUT. Individual later Apollo missions (13–17) — OUT.
- People tangentially connected (astronauts who didn't fly 11 and had no specific 11 role) — OUT.
- Apollo hardware shared across missions ("Saturn V", "Apollo Command/Service Module" as classes) — PERIPHERAL.

**Ambiguity rulings:**
- Crew biographies → CENTRAL.
- Kennedy Space Center Launch Complex 39A → CENTRAL. KSC itself → PERIPHERAL.
- Craters named after 11 crew (Armstrong, Collins crater) → CENTRAL.
- Cultural works mentioning 11 among other subjects → OUT unless coverage is primarily about the 11 element.
- "Apollo 11 in popular culture" → IN as topical index.
- Post-mission artifacts on display (Columbia at NASM) → CENTRAL.
- Goodwill messages microdisk → CENTRAL.

### Topic-specific guardrails

- **Kennedy Space Center** was the canonical "missed" article in the baseline — recovered only via `browse_edges`. Direct `harvest_navbox(template="Template:Apollo program")` would catch it in one call. Reach for `harvest_navbox` early.
- **Wikidata things-named-after probe** (P138 → Q43653) was never done in the baseline — would surface schools, streets, vessels, craters. Try `wikidata_entities_by_property(property="P138", value="Q43653")` or equivalent via `wikidata_query`.
- The baseline pre-dates the Chunk 1–6 tool improvements, so cost metrics should beat it readily.

## Step 3 — Build to completeness

Work through the standard pipeline:
- Reconnaissance — WikiProject probe (`find_wikiprojects`, `check_wikiproject`), category survey (`survey_categories`), list-page discovery (`find_list_pages`), Wikidata (`wikidata_search_entity`).
- Gather — `get_category_articles`, `harvest_list_page`, `harvest_navbox`, `search_articles`, `search_similar`, `browse_edges`. Prefer `preview_*` on risky pulls.
- Descriptions — `fetch_descriptions` to drain the backlog.
- Review — `auto_score_by_description` for obvious noise rejection; `fetch_article_leads` when a shortdesc looks thin or wrong.
- Cleanup — `filter_articles`, `remove_by_pattern`, `remove_by_source` as needed.

## Step 4 — SPOT CHECK + GAP CHECK

1. Fabricate ~15–25 niche Apollo-11 titles you'd expect in the corpus (crew's specific publications / honors, specific mission-control personnel, specific artifacts, specific commemorations, specific cultural works). You're authorized to fabricate autonomously.
2. Check presence via `get_articles(title_regex="^(T1|T2|…)$")` or `preview_search`.
3. Classify misses: variant-name (redirect) / LLM hallucination / real gap.
4. Diagnose patterns: if five missed cultural works, rerun `preview_harvest_list_page` on the cultural list rather than adding by hand.
5. Repair real gaps; seed `browse_edges` from clusters that surfaced.

## Step 5 — Rubric review

Call `get_topic_rubric()`. If the build surfaced a scope wrinkle, note it in feedback. DO NOT change the rubric — it's frozen for this benchmark.

## Step 6 — Submit feedback

```
submit_feedback(
    summary="<2-5 sentences>",
    what_worked="<concrete tools / strategies that worked>",
    what_didnt="<concrete pain points, sharp-edges hit>",
    missed_strategies="<tool shapes you wished existed — empty if none>",
    rating=<1–10>,
    coverage_estimate={
        "confidence": <0.0–1.0>,
        "rationale": "<one sentence>",
        "remaining_strategies": ["<existing tool shapes you didn't apply>", ...]
    }
)
```

`confidence` = self-estimate of corpus completeness relative to the frozen scope (not confidence in individual classifications). Honest low beats inflated high. `remaining_strategies` inside `coverage_estimate` = existing tools you didn't apply; `missed_strategies` (top-level) = tool shapes you wished existed.

## Step 7 — Do NOT call `export_csv`

The scoring script pulls the corpus directly from the server.

## Done

Reply with a brief summary: final article count, coverage_estimate.confidence, and any notable friction.
