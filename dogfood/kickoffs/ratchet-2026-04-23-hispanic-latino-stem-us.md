# Topic Builder benchmark run — hispanic-latino-stem-us (2026-04-23 ratchet)

You are running the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`) against a single benchmark topic. Your goal this session is to build a fresh corpus for this topic under a new, non-colliding name, ending with an honest `submit_feedback`. Your work will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs on the "intersectional biography" shape — Wiki Education's priority shape.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today), and this shape is where two of those items matter most:
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it. **The Wikidata-shortdesc-unreliability bullet is especially relevant here** for the same reasons as the sister AA-STEM benchmark.
  - New `fetch_article_leads(titles, sentences=3)` tool — the fix for misleading shortdescs. **USE IT LIBERALLY** on ambiguous biography hits. This is the topic shape it was built for.
- **Don't call `export_csv`.** The scoring script pulls the corpus directly from the server.
- **Use the EXACT run-topic name below.** The scoring script looks up the topic by name. Using the baseline name would overwrite frozen ground truth.
- **Gold format note.** This benchmark's gold set is BINARY (`on_topic=true/false`), predating the three-tier CENTRAL/PERIPHERAL/OUT framework. The scoring script handles the mapping (`true → in`, `false → out`). You still score centrality 1–10 if you're scoring at all — but the gate only cares about inclusion.

## Run-topic name

- **Run-topic name (exact):** `hispanic-latino-stem-us ratchet-2026-04-23`
- **Baseline name (DO NOT use):** `hispanic-latino-stem-us`
- **Wiki:** `en`

## Step 0 — Setup check

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions (came in on session init via MCP `instructions=`). Note SCOPE RUBRIC, PIPELINE, INTERSECTIONAL TOPICS, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, WRAP-UP.
3. If tools aren't loaded, stop and surface the blocker.

## Step 1 — Persist the rubric

Call `set_topic_rubric(rubric=<verbatim text below>)`. Don't paraphrase.

```
# Centrality rubric — hispanic-latino-stem-us benchmark
# Frozen 2026-04-23 (rubric); scope frozen 2026-04-17 (see scope.md).

CENTRAL — Wikipedia biographies of Hispanic / Latino American people
  (any Latin American Spanish-speaking heritage, Chicano/a self-
  identified, or US-born with Latino ancestry) whose notability is
  research-primary STEM work, with a meaningful US affiliation.
  Fields per scope.md: natural sciences (physics, chemistry, biology,
  astronomy, geology, meteorology, oceanography, ecology, neuroscience,
  environmental science), mathematics, engineering (including
  biomedical and aerospace), computer science, astronautics,
  inventors / technologists, materials science, biochemistry,
  microbiology, genetics, physiology. Physician-scientists (MD or
  MD/PhD research-primary) are CENTRAL per scope explicit ruling.

PERIPHERAL — STEM-trained Hispanic / Latino Americans whose primary
  notability is now in administration, policy, or leadership
  (university presidents, program officers, tech executives with
  engineering backgrounds), but who retain a meaningful research
  qualification. Also: early-career researchers still establishing
  notability. Score 3–5 on the centrality axis.

OUT — Per scope.md: Brazilian / Lusophone (not Latin American
  Spanish-speaking heritage), peninsular Spanish (not Latin American
  heritage), clinical-only medicine physicians without research
  primary notability, social sciences (economists, psychologists,
  sociologists, anthropologists, political scientists), STEM educators
  without research, non-US-affiliated scientists, and all non-STEM
  biographies (politicians, artists, writers, athletes, activists,
  businesspeople without STEM-primary work).

# Relationship to the existing gold.csv

This benchmark was bootstrapped on 2026-04-17 and uses a BINARY
classification (`on_topic=true` / `false`) — predating the 3-tier
CENTRAL/PERIPHERAL/OUT framework adopted across the 5-benchmark
suite in 2026-04-23. Mapping for cross-benchmark comparison:

  on_topic=true  → in (CENTRAL) — all 314 positive entries are
                   research-primary STEM biographies per scope.md;
                   the audit didn't distinguish STEM-active-researcher
                   from STEM-admin at the time. If a future audit
                   pass wants PERIPHERAL granularity, the handful of
                   STEM-admin cases can be downgraded individually.
  on_topic=false → out (OUT)

Future audit: the current corpus has 1,246 articles not yet in the
binary gold. Those are candidates for both reach-audit (growing gold)
and classification via the 3-tier rubric.

# Notes for future auditors

- Physician-scientists are explicit IN per scope's ambiguity rulings.
- Brazilian / peninsular Spanish are explicit OUT.
- STEM educators without research are OUT.
- Edge cases: see `scope.md` "Ambiguity rulings" section.
```

## Step 2 — Internalize the scope

**Short statement:** Wikipedia biographies of people of Hispanic and Latino heritage, working in STEM fields, with a meaningful affiliation to the United States.

**In scope:**
- **Heritage.** Latin American ancestry / heritage, from any Spanish-speaking Latin American country. Mexican, Puerto Rican, Cuban, Dominican, Colombian, Venezuelan, Peruvian, Argentine, Chilean, Guatemalan, Honduran, Nicaraguan, Salvadoran, Costa Rican, Panamanian, Ecuadorian, Bolivian, Paraguayan, Uruguayan. "Chicano/a" self-identified. US-born with Latino ancestry (Mexican-American, etc.) are IN.
- **STEM fields.** Natural sciences (physics, chemistry, biology, astronomy, geology, meteorology, oceanography, ecology, neuroscience, environmental science), mathematics, engineering (including biomedical engineering), computer science, astronautics, inventors / technologists, materials science, biochemistry, microbiology, genetics, physiology.
- **US affiliation.** US-born counts. Immigrants who pursued a STEM career at US institutions count. Foreign scientists who did a substantive postdoc / research in the US and returned home: IN. Bar is "some real US-based research activity."

**Explicitly out of scope:**
- **Brazilian / Lusophone.** Brazilian-heritage people NOT in scope, regardless of US affiliation or STEM field.
- **Peninsular Spanish.** People from Spain (not Latin American heritage) NOT in scope.
- **Clinical medicine.** Physicians whose notability is primarily clinical practice, medical administration, popular-book authorship, or medical education — OUT. **Physician-scientists whose notability is primarily research (lab work, clinical research programs, publication record) are IN,** including MDs and MD/PhDs. Biomedical engineers IN.
- **Social sciences.** Economists, psychologists, sociologists, anthropologists, political scientists — OUT, even if quantitative.
- **STEM education (without research).** Educators whose notability is teaching / curriculum / advocacy / administration rather than research — OUT. STEM researchers who also teach — IN.
- **No US affiliation.** Scientists purely based in Latin America, Spain, or Portugal with no substantive US research ties — OUT.

**Ambiguity rulings:**
- Physician-scientists (MD or MD/PhDs research-primary) — IN.
- Entrepreneurs with STEM credentials — IN if notability is engineering / invention / research. OUT if primarily a businessperson.
- Popular-science writers with PhDs — IN if active research career; OUT if notability is as a writer.
- Brief US visits (sabbatical, single conference) — OUT. US-affiliation bar is postdoc-level substantive.
- Dual-citizen scientists moving between US and home country — IN if US research activity was substantive.

### Topic-specific guardrails

- **INTERSECTIONAL shape** (demographic × discipline). Same playbook as the sister AA-STEM benchmark: category + WikiProject coverage tends to be SPARSE. Pivot fast from category/WP probes to search-based strategies (`search_articles` with boolean queries intersecting heritage/nationality with discipline terms, `search_similar` from canonical figures).
- **Wikidata shortdescs are the bottleneck.** Use `fetch_article_leads` liberally. The reason two of today's Tier 1 items target this exact shape.
- **Brazilian / peninsular-Spanish confusions.** The scope explicitly excludes Brazilian-heritage and Spain-peninsular people. Watch for names that look Hispanic but whose heritage traces back to Brazil / Spain — these need a lead-check to disambiguate.
- **Morelike: danger.** Per server_instructions: `morelike:<Hispanic_scientist>` returns mostly non-Hispanic scientists (profession weight > demographic weight). For this shape, morelike: results are noisy — treat as candidates needing review.
- **PetScan baseline.** The org's non-AI baseline is a PetScan query on `Category:Hispanic_and_Latino_American_scientists` deep-crawl. It pulls ~284 articles, with the known scope mismatch that the category tree nests medical specialties under "scientists" — PetScan's result has clinical-physician false positives per our scope. You're not beating PetScan specifically; you're competing against the audited gold. But PetScan is a useful sanity-check set.

## Step 3 — Build to completeness

Standard pipeline:
- Reconnaissance — WikiProject probe (`find_wikiprojects` for "Hispanic and Latino American scientists" or similar); category survey on `Category:Hispanic and Latino American scientists`, `Category:Hispanic and Latino American engineers`, etc.; list-page discovery ("List of Hispanic and Latino American scientists" / "List of Mexican American scientists" / etc.); Wikidata search for ethnic-group + occupation intersections.
- Gather — `get_category_articles`, `search_articles` with boolean intersections (heritage keywords × STEM field terms), `search_similar` seeded from canonical figures (with morelike: caution). `harvest_list_page` on list pages found.
- Descriptions — `fetch_descriptions`.
- Review — `fetch_article_leads` on ambiguous bios (especially where heritage is unclear from shortdesc). `auto_score_by_description` with multi-word disqualifying phrases (per KNOWN SHARP EDGES).
- Cleanup — `filter_articles`, `remove_by_pattern`, `remove_by_source`. Likely removal classes: Brazilian-heritage bios pulled in by broad search, Spain-peninsular bios, clinical-only physicians, STEM educators without research.

### Reach targets from the baseline run

- **Reduce false positives.** 381 articles in the current server corpus are confirmed OUT per the binary gold; a scope-tightened run should ship without them.
- **Recover 5 missing gold positives** (per the 2026-04-17 baseline.md): Alba Colón, Annie Antón, Carmen Cid, Cecilia R. Aragon, Celso-Ramón García, Craig Henriquez.
- **1,246 unaudited articles** in the current server corpus — candidates for both reach-audit and classification.
- **Cross-wiki reach.** Spanish-language Wikipedia likely has Latino STEM biographies not sitelinked to enwiki. High-priority *long-term* reach target — but for this ratchet cycle, enwiki focus is fine (the gold is enwiki-anchored; cross-wiki adds wouldn't affect the scoreboard).

## Step 4 — SPOT CHECK + GAP CHECK

1. Fabricate ~15–25 niche Hispanic / Latino STEM biographies you'd expect in the corpus (specific named scientists across fields, specific astronauts, specific inventors, specific Nobel laureates / Guggenheim fellows). Authorized to fabricate autonomously.
2. Check presence via `get_articles(title_regex="^(T1|T2|…)$")` or `preview_search`.
3. Classify misses: variant-name (redirect) / LLM hallucination / real gap.
4. Diagnose patterns: if several missed biographies share a field, rerun a list-page / category probe for that field rather than adding by hand.
5. Repair; seed `browse_edges` from clusters.

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

`confidence` = self-estimate of corpus completeness relative to the frozen scope. Honest low beats inflated high. Given this topic's known-sparse-category coverage, 0.5–0.7 is a reasonable honest range.

## Step 7 — Do NOT call `export_csv`

The scoring script pulls the corpus directly from the server.

## Done

Reply with a brief summary: final article count, coverage_estimate.confidence, and any notable friction. Also useful: how many `fetch_article_leads` calls you made + how often the lead changed your inclusion or centrality decision (ratchet signal for this shape).
