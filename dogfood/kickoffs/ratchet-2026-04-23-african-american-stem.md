# Topic Builder benchmark run — african-american-stem (2026-04-23 ratchet)

You are running the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`) against a single benchmark topic. Your goal this session is to build a fresh corpus for this topic under a new, non-colliding name, ending with an honest `submit_feedback`. Your work will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs on the "intersectional biography" shape — Wiki Education's priority shape.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today), and this shape is where two of those items matter most:
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it. **The Wikidata-shortdesc-unreliability bullet is especially relevant here.** Real examples observed during audit: Gloria Chisum ("American academic" → applied-STEM researcher on pilot-vision eyewear), William Hallett Greene (truncated shortdesc → first Black meteorologist), Meredith Gourdine ("American long jumper" → also a plasma physicist and engineer).
  - New `fetch_article_leads(titles, sentences=3)` tool — the fix for those misleading shortdescs. **USE IT LIBERALLY** on ambiguous biography hits. This is the topic shape it was built for.
- **Don't call `export_csv`.** The scoring script pulls the corpus directly from the server.
- **Use the EXACT run-topic name below.** The scoring script looks up the topic by name. Using the baseline name would overwrite frozen ground truth.

## Run-topic name

- **Run-topic name (exact):** `african-american-stem ratchet-2026-04-23`
- **Baseline name (DO NOT use):** `African American people in STEM`
- **Wiki:** `en`

## Step 0 — Setup check

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions (came in on session init via MCP `instructions=`). Note SCOPE RUBRIC, PIPELINE, INTERSECTIONAL TOPICS, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, WRAP-UP.
3. If tools aren't loaded, stop and surface the blocker.

## Step 1 — Persist the rubric

Call `set_topic_rubric(rubric=<verbatim text below>)`. Don't paraphrase.

```
# Centrality rubric — African American people in STEM benchmark
# Frozen 2026-04-23. A rubric change invalidates gold.csv.

CENTRAL — Wikipedia biographies of people of African American / Black
  American heritage, whose notability is research-primary STEM work,
  with a meaningful US affiliation (US-born, or significant research
  career at US institutions). Fields include natural sciences
  (physics, chemistry, biology, astronomy, geology, meteorology,
  oceanography, ecology, neuroscience, environmental science),
  mathematics, engineering disciplines (including biomedical and
  aerospace), computer science, astronautics, inventors /
  technologists, materials science, biochemistry, microbiology,
  genetics, physiology, nanotechnology, and related research-heavy
  professions.

PERIPHERAL — STEM-adjacent figures whose research contribution is
  secondary to another role (science communicators, curators, STEM
  administrators, program officers) but who retain a meaningful
  research or engineering qualification. Also: early-career
  researchers, STEM educators with a secondary research component
  (vs. pure teaching/administration). Score 3–5 on the centrality
  axis.

OUT — Articles about people whose notability is primarily clinical
  medicine without research component (practicing physicians noted
  for clinical work, medical administration, or medical education),
  pure social sciences (sociology, anthropology, economics, political
  science, psychology, history, philosophy), humanities (literature,
  poetry, journalism, law, religion), non-research business roles
  (tech executives, investors, entrepreneurs without STEM-primary
  notability), arts and entertainment (musicians, painters,
  actors/actresses, athletes), pure military careers, politicians,
  activists, and students. Articles in the AA STEM medicine
  blocklist (topic id 8) are prima facie OUT unless the description
  indicates research-primary physician-scientist status.

# Notes for auditors:
# - Research-primary physicians (lab work, clinical research programs,
#   publication record as primary notability) ARE IN, consistent with
#   the sister hispanic-latino-stem-us scope.
# - The category sources (category:African-American scientists,
#   category:African-American engineers) are strong IN signals;
#   combine with a STEM profession in the description to classify IN.
# - Mixed STEM + secondary activist/politician/entrepreneur roles are
#   IN if the STEM profession is listed. Mixed STEM + primary-humanities
#   roles (author+poet first, biologist listed secondary) should be
#   audited individually.
```

## Step 2 — Internalize the scope

**Short statement:** Wikipedia biographies of people of African American / Black American heritage, working in STEM research fields, with meaningful US affiliation.

**In scope:**
- **Heritage.** African American / Black American. "Black American", African diaspora people whose notability includes US-affiliated work. Black immigrants who built a US research career (Nigerian-American, Ghanaian-American, Kenyan-American, Cuban-American of Afro-Latino heritage, etc.) are IN. Black British / Caribbean-born scientists with substantive US research work are IN.
- **STEM fields.** Natural sciences (physics, chemistry, biology, astronomy, geology, meteorology, oceanography, ecology, neuroscience, environmental science, paleontology, hydrogeology, soil science), mathematics and statistics, engineering (including biomedical and aerospace), computer science, astronautics (astronauts included), inventors / technologists, materials science, nanoscience, biochemistry, microbiology, genetics, physiology, pharmacology.
- **US affiliation.** US-born counts. Immigrants who pursued a STEM career at US institutions count. Foreign researchers with a substantive postdoc or research position in the US then returning home count. Bar is "some real US-based research activity," not "lifelong US resident."

**Explicitly out of scope:**
- **Clinical medicine.** Physicians whose notability is primarily clinical practice, medical administration, authorship of popular books, or medical education are OUT. **Physician-scientists whose notability is primarily research (lab work, clinical research programs, publication record) are IN,** including MDs and MD/PhDs. Biomedical engineers are IN.
- **Social sciences.** Economists, psychologists, sociologists, anthropologists, political scientists — OUT, even if they use quantitative / statistical methods.
- **STEM education (without research).** Educators whose notability is teaching / curriculum / advocacy / administration rather than research — OUT. STEM researchers who also teach — IN.
- **No US affiliation.** Black African / Caribbean scientists with no substantive US research ties — OUT.
- **Non-science roles.** Politicians, lawyers, athletes, musicians, artists, actors, journalists, poets, military officers (without STEM research), religious leaders, business executives (without STEM-primary notability), activists, fraternity founders.
- **Architecture.** Licensed architecture practitioners OUT. Civil / structural / environmental engineers IN.

**Ambiguity rulings:**
- **Physician-scientists** (MD or MD/PhDs doing primarily research) — IN.
- **Astronauts** — IN.
- **STEM + secondary activism / politics / entrepreneurship** — IN when STEM is the primary profession listed.
- **Entrepreneurs with STEM credentials** — IN if notability is engineering / invention / research. OUT if primarily a businessperson.
- **Popular-science writers with PhDs** — IN if they have an active research career; OUT if notability is as a writer.
- **"Academic" (bare, no field)** — PERIPHERAL default.
- **Athletes who are also STEM researchers** (Meredith Gourdine — long jumper + engineer) — IN via STEM qualifier. This is the canonical exemplar for why `fetch_article_leads` matters here.

### Topic-specific guardrails

- **INTERSECTIONAL shape** (demographic × discipline). Per server_instructions: category + WikiProject coverage tends to be SPARSE on this shape. Wikipedia tags people by nationality-descent and by profession separately but rarely at the intersection. Expect to pivot fast from category/WP probes to search-based strategies (`search_articles` with boolean queries intersecting ethnicity/nationality keywords with discipline terms, `search_similar` from canonical figures).
- **Wikidata shortdescs are the bottleneck.** Use `fetch_article_leads` liberally. The cost is ~1 HTTP round-trip per 20-title batch; the benefit is distinguishing "American academic" → applied-STEM researcher from "American academic" → sociologist.
- **Medicine blocklist.** The "AA STEM medicine blocklist" topic (id 8) was built separately to flag clinical-physician bios. If you decide to pull from it as a negative filter, cross-reference carefully — a research-primary physician-scientist will be in the blocklist too but belongs IN this corpus.
- **Morelike: danger.** Per server_instructions: `morelike:<Black_scientist_seed>` weights profession over demographic. For this shape, morelike: results are noisy — treat as candidates needing review. Prefer non-polymath seeds (specific topic-node articles like "African Americans in mathematics") over biographical hub seeds.

## Step 3 — Build to completeness

Standard pipeline:
- Reconnaissance — WikiProject probe (`find_wikiprojects` for "African American scientists", etc.); category survey on `Category:African-American scientists`, `Category:African-American engineers`, `Category:African-American astronauts`, etc.; list-page discovery; Wikidata search for relevant property shapes.
- Gather — `get_category_articles` (core strategy on this shape), `search_articles` with boolean intersections, `search_similar` seeded from canonical figures (with morelike: caution). `harvest_list_page` on "List of African-American scientists" / "List of African-American inventors" / etc.
- Descriptions — `fetch_descriptions`.
- Review — `fetch_article_leads` on any biography whose shortdesc is ambiguous or looks thin. `auto_score_by_description` with multi-word disqualifying phrases (per the KNOWN SHARP EDGES section about `["city"]` matching proper-noun phrases).
- Cleanup — `filter_articles`, `remove_by_pattern`, `remove_by_source`.

### Reach targets from the baseline run

- **Medicine-blocklist articles still in corpus.** The blocklist topic (id 8) identified clinical-physician bios for exclusion but was never applied to the baseline. A future run should ship tighter by default.
- **Wikidata P106 (occupation)** — `occupation = physicist` AND `ethnic group = African American` would surface bios the category-based sweep missed. Try `wikidata_query` with SPARQL.
- **Cross-wiki for African-diaspora researchers** — frwiki for Francophone African researchers with US postdocs. Non-zero reach; lower priority for this ratchet since the gold is enwiki-only.
- **Wikidata shortdesc unreliability** — canonical exemplars (Chisum, Gourdine, Greene) suggest that the baseline corpus has misclassified biographies where shortdesc was misleading. Use `fetch_article_leads` on borderline bios to catch these.

## Step 4 — SPOT CHECK + GAP CHECK

1. Fabricate ~15–25 niche African American STEM biographies you'd expect in the corpus (specific named inventors, specific NASA scientists, specific astronauts, specific mathematicians, specific engineers). Authorized to fabricate autonomously.
2. Check presence via `get_articles(title_regex="^(T1|T2|…)$")` or `preview_search`.
3. Classify misses: variant-name (redirect) / LLM hallucination / real gap.
4. Diagnose patterns: if several missed biographies share a field (e.g. "five missed computer scientists"), rerun a list-page / category probe for that field rather than adding by hand.
5. Repair; seed `browse_edges` from clusters. Remember: on this shape, category+WP coverage is sparse, so gap-discovery via focused search is higher-leverage than it is elsewhere.

## Step 5 — Rubric review

Call `get_topic_rubric()`. Note scope wrinkles in feedback. DO NOT change the rubric.

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

`confidence` = self-estimate of corpus completeness relative to the frozen scope. Honest low beats inflated high. Given this topic's known-sparse-category coverage, 0.5–0.7 is a reasonable honest range; >0.85 would need strong justification.

## Step 7 — Do NOT call `export_csv`

The scoring script pulls the corpus directly from the server.

## Done

Reply with a brief summary: final article count, coverage_estimate.confidence, and any notable friction. Special call-outs useful: how many `fetch_article_leads` calls you made + how often the lead changed your classification (this is the ratchet signal for whether the tool is earning its keep on this shape).
