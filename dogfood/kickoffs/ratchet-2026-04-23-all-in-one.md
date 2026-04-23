# Topic Builder — 2026-04-23 ratchet cycle (all 5 benchmarks, one session)

You are running a measured-improvement ratchet against the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`). Your goal this session is to build **fresh copies of all 5 benchmark topics** under new, non-colliding names, ending each with an honest `submit_feedback`. Each run will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs across five different topic shapes.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today — this session is the first real ratchet cycle against it):
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it at session start. Cirrus compound `intitle:A OR intitle:B` silently returns 0 (split and merge), `auto_score_by_description(disqualifying=[...])` substring-matches inside proper-noun phrases (Kansas City Star / Orange County Register), empty `survey_categories` on an existing category usually signals a container/redirect (look for a sibling), and Wikidata short-descriptions shouldn't be a sole signal when assigning centrality.
  - New `fetch_article_leads(titles, sentences=3)` tool — the fix for misleading Wikidata shortdescs. Reach for it when a shortdesc looks too thin or wrong to judge centrality; that's exactly what it was built for. Especially relevant on the intersectional biography topics (AA-STEM, HL-STEM).
- **Don't call `export_csv`** on any of the 5 runs. The scoring script pulls each corpus directly from the server. Export would trigger a triangulation warning on weak-overlap topics and isn't needed for the measurement.
- **Use the EXACT run-topic names below.** The scoring script looks up each topic by name. Using a baseline name would overwrite frozen ground truth — don't.

## Step 0 — Setup check (do this first)

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions — they come in on session init via the MCP `instructions=` channel. Note the SCOPE RUBRIC, PIPELINE, COMMON TASK → TOOL, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, and WRAP-UP sections.
3. If tools aren't loaded, stop and surface the blocker.

If any of those fail, halt and surface the blocker. Don't start a build on a broken toolset.

## The 5 benchmarks

Build each in order, one at a time. **Do not parallelize across topics in one session** — the MCP session tracks one current topic at a time.

| # | Slug | Run-topic name (exact — must match) | Baseline name (DO NOT use) | Wiki |
|---|---|---|---|---|
| 1 | apollo-11 | `apollo-11 ratchet-2026-04-23` | `Apollo 11` | en |
| 2 | crispr-gene-editing | `crispr-gene-editing ratchet-2026-04-23` | `CRISPR gene editing` | en |
| 3 | african-american-stem | `african-american-stem ratchet-2026-04-23` | `African American people in STEM` | en |
| 4 | hispanic-latino-stem-us | `hispanic-latino-stem-us ratchet-2026-04-23` | `hispanic-latino-stem-us` | en |
| 5 | orchids | `orchids ratchet-2026-04-23` | `orchids` | en |

## Per-benchmark protocol (apply to each of the 5)

For each slug, in order:

1. **Start the topic:** `start_topic(name="<exact run-topic name from the table>", wiki="en", fresh=False)`. The name must match the table exactly.
2. **Persist the rubric** (from the topic's section below): `set_topic_rubric(rubric=<verbatim rubric text>)`. Don't paraphrase — the server stores it as-is. The rubric is MANDATORY before any gather call.
3. **Internalize the scope** for that topic (section below). The IN / OUT rulings are binding; re-read when weighing borderline articles. The scope is the authority.
4. **Build the topic end-to-end** per the server's pipeline — reconnaissance (WikiProject probe, category survey, list-page discovery, Wikidata lookup as appropriate), gather (`get_category_articles`, `harvest_list_page`, `harvest_navbox`, `search_articles`, `search_similar`, `browse_edges`; prefer `preview_*` on risky pulls), descriptions (`fetch_descriptions`), review (`auto_score_by_description` for obvious noise; `fetch_article_leads` when a shortdesc looks thin or wrong), cleanup (`filter_articles`, `remove_by_pattern`, `remove_by_source`).
5. **SPOT CHECK + GAP CHECK** per server_instructions:
   - Fabricate ~15–25 niche titles you'd expect in the corpus based on the scope.
   - Check presence via `get_articles(title_regex="^(T1|T2|…)$")` or individual `preview_search` calls.
   - Classify each miss: variant-name (redirect target) / LLM hallucination / real gap.
   - Diagnose miss patterns — five missed cultural works → rerun a list-page harvest rather than adding by hand.
   - Repair the real gaps; seed `browse_edges` from the clusters that surface.
6. **Rubric review:** call `get_topic_rubric()`. If the build surfaced a scope wrinkle the rubric didn't anticipate, note it in feedback (but DO NOT change the rubric — it's frozen for this benchmark).
7. **Submit feedback:**
   ```
   submit_feedback(
       summary="<2-5 sentences on how the session went>",
       what_worked="<concrete tools / strategies that worked on this shape>",
       what_didnt="<concrete pain points, missing tools, sharp-edges hit>",
       missed_strategies="<tool shapes you wished existed — empty if none>",
       rating=<1–10 overall experience>,
       coverage_estimate={
           "confidence": <0.0–1.0>,
           "rationale": "<one sentence on why>",
           "remaining_strategies": ["<existing tool shapes you didn't apply>", ...]
       }
   )
   ```
   `confidence` = self-estimate of corpus completeness relative to the frozen scope (NOT confidence in individual classifications). `remaining_strategies` (inside `coverage_estimate`) = tools that exist but weren't applied this session. `missed_strategies` (top-level) = tool shapes you wished existed.
8. **Do NOT call `export_csv`.**
9. Move to the next slug.

## Budget + pacing

Target ~20–50 minutes per benchmark, 2–4 hours total. If one benchmark stalls past an hour without meaningful progress, wrap it up with an honest low confidence + diagnostic `what_didnt`, and move on. Don't let one stuck topic eat the whole session.

## Topic-specific guardrails

- **apollo-11** — smallest and cleanest shape. Single historical event + cultural tail. Kennedy Space Center is the canonical "missed on the first pass" article — the `harvest_navbox` tool on `Template:Apollo program` was never used in the baseline; it's a natural fit.
- **crispr-gene-editing** — search-native with distinctive vocabulary. Tight baseline (14 tool calls, 46 API calls). Noise class: lexical-search false positives (Cement, Plastic, Submarine, Umeå — literal examples from the baseline). `auto_score_by_description(disqualifying=[...])` with care (watch the KNOWN SHARP EDGE about proper-noun words) is the right cleanup lever.
- **african-american-stem** — intersectional biography. Category-heavy triangulation. Wikidata shortdescs are especially misleading on this shape (Gloria Chisum "American academic" → applied-STEM researcher; Meredith Gourdine "American long jumper" → also a plasma physicist and engineer). USE `fetch_article_leads` LIBERALLY on ambiguous biography hits.
- **hispanic-latino-stem-us** — same intersectional-biography shape as AA-STEM. The existing gold is BINARY (on_topic true/false, predates the three-tier framework); the scoring script handles the mapping. Same shortdesc-unreliability advice applies. Watch for Brazilian / peninsular-Spanish confusions (explicit OUT per scope).
- **orchids** — at 18k+ articles, this is the scale stress test. **For this ratchet: focus enwiki only.** Cross-wiki walks are expensive and the frozen gold is enwiki-only, so cross-wiki reach wouldn't affect the scoreboard for this run. (The `cross_wiki_diff` tool is on the backlog specifically for orchids-style topics — it's not shipped yet.) The scope's cultural-tail clauses matter — Chinese literary figures like Qu Yuan / Ma Shouzhen are currently OUT, not PERIPHERAL. Trust source-provenance for genus-level taxa: an article pulled from `category:Orchids` or a list-page in an orchid build is on-topic even if its Wikidata shortdesc says only "Species of plant".

---

## Benchmark 1 — apollo-11

**Run-topic name:** `apollo-11 ratchet-2026-04-23`
**Baseline name (DO NOT use):** `Apollo 11`
**Wiki:** en

### Rubric (paste verbatim to `set_topic_rubric`)

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

### Scope

**Short statement:** Wikipedia articles whose primary subject is, or is directly a part of, the Apollo 11 crewed lunar-landing mission of July 1969 — its crew, spacecraft, landing site, science program, cultural legacy, and things officially named after it.

**In scope:**
- The mission itself (launch, flight path, landing, EVA, return, splashdown).
- Crew: Neil Armstrong, Buzz Aldrin, Michael Collins — full biographies.
- Ground support and mission control: Gene Kranz, Christopher Kraft, Steve Bales, Charles Duke (CAPCOM), other named controllers and flight directors with a documented 11 role.
- Spacecraft and hardware used by 11 specifically: Columbia (CSM-107), Eagle (LM-5), Saturn V SA-506. Ancillary hardware and experiments deployed on 11 (EASEP components, Passive Seismic Experiment, Laser Ranging Retroreflector, Early Apollo Scientific Experiments Package).
- Landing site: Tranquility Base, Mare Tranquillitatis context directly relevant to the landing.
- Primary cultural works about 11: films (*First Man*, *Apollo 11* (2019 doc), *Moonwalk One*), books (*Of a Fire on the Moon*, *Carrying the Fire*, *First Man* (Hansen), *Chariots for Apollo* — the NASA SP-4205 history), plays, songs whose main subject is 11.
- Things named after Apollo 11: schools, streets, lunar craters (Armstrong, Aldrin, Collins craters), US vessels, institutions.
- Artifacts and memorabilia of 11: Goodwill messages, lunar samples from the mission, landed hardware, display artifacts.
- Adjacent Apollo missions whose content materially overlaps 11: Apollo 8, 10, 12 as PERIPHERAL (trajectory rehearsal, preparatory tests, immediate successor).

**Explicitly out of scope:**
- Non-Apollo Moon programs (Luna, Chang'e, Surveyor, Chandrayaan, Pioneer, Ranger) — OUT even though they share subject matter.
- General spaceflight history: "History of spaceflight", "Timeline of space exploration", "Space Race" as a whole — OUT when they mention 11 but aren't primarily about it.
- Generic Moon / astronomy articles: "Moon", "Selenology", "Lunar geology" general articles — OUT. Narrower geology articles specific to the 11 landing site are borderline — default PERIPHERAL.
- Conspiracy-theory articles (moon-landing conspiracy discourse) — OUT.
- Broad Apollo program articles ("Apollo program", "Project Apollo", "Apollo astronaut") — OUT because their subject is the program, not 11. Individual later Apollo missions (13–17) are OUT.
- People tangentially connected (astronauts who didn't fly 11 and had no specific 11 role) — OUT unless they're mission-control personnel with a documented 11 role.
- Apollo hardware shared across missions ("Saturn V", "Apollo Command/Service Module" as classes) — PERIPHERAL (contextualize 11's hardware).

**Ambiguity rulings:**
- Crew biographies are CENTRAL — the person IS the mission.
- Launch site articles (Kennedy Space Center Launch Complex 39A) — CENTRAL. KSC itself — PERIPHERAL (most of KSC isn't about 11 specifically).
- Lunar geology / craters named after 11 crew (Armstrong, Collins crater) — CENTRAL.
- Cultural works mentioning 11 among other subjects — OUT unless the coverage is primarily about the 11 element.
- "Apollo 11 in popular culture" article — IN as a topical index.
- Post-mission artifacts on display (Columbia at NASM) — CENTRAL.
- Goodwill messages microdisk — CENTRAL.

### Reach targets from the baseline run

- **Kennedy Space Center** was rescued only via `browse_edges`; direct `harvest_navbox(template="Template:Apollo program")` would catch it in one call.
- **Wikidata things-named-after probe** (P138=Q43653) was never done — would surface schools, streets, vessels, craters. Reach candidate.
- The baseline pre-dates the Chunk 1–6 tool improvements, so cost metrics should beat it readily.

---

## Benchmark 2 — crispr-gene-editing

**Run-topic name:** `crispr-gene-editing ratchet-2026-04-23`
**Baseline name (DO NOT use):** `CRISPR gene editing`
**Wiki:** en

### Rubric

```
# Centrality rubric — CRISPR gene editing benchmark
# Frozen 2026-04-23. A rubric change invalidates gold.csv.

CENTRAL — articles whose primary subject is CRISPR biology, CRISPR
  editing mechanisms (Cas9, Cas12a, Cas3, guide RNA, PAM, anti-CRISPR,
  tracrRNA, prime editing, base editing, CRISPRi/CRISPRa, etc.),
  CRISPR-associated techniques and tools (GUIDE-Seq, genome-wide
  screens, LEAPER, TIGR-Tas), the foundational scientists and pioneers
  (Doudna, Charpentier, Zhang, Šikšnys, Barrangou, Mojica, Ishino,
  Marraffini, Sontheimer, etc.), CRISPR-focused companies (CRISPR
  Therapeutics, Editas, Intellia, Mammoth, Innovative Genomics
  Institute), the He Jiankui affair and its figures, and FDA-approved
  CRISPR gene therapies (Exagamglogene autotemcel, Verve's PCSK9
  therapy, etc.).

PERIPHERAL — diseases that CRISPR specifically targets (sickle cell
  disease, beta thalassemia, PCSK9-related conditions), adjacent
  genome-editing concepts (genome editing as a field, gene therapy,
  genetic engineering), related molecular techniques (gene knockout /
  knock-in / knockdown, gene targeting, recombinant DNA, RNA editing),
  CRISPR-application projects (Colossal Biosciences dire wolf, woolly
  mouse), organisms and biology from which CRISPR was derived
  (Streptococcus pyogenes), context biographies (Chinese stem cell
  researchers around He Jiankui), CRISPR-adjacent books and
  documentaries (The Code Breaker, Human Nature, Make People Better),
  and institutions/VCs meaningful for the CRISPR story (UC Berkeley,
  Flagship Pioneering). These score 3–5 on the centrality axis.

OUT — generic unrelated topics pulled in by lexical search noise
  (Cement, Plastic, Submarine, Vehicle, Transport, Technology,
  Integrated circuit, Incandescent light bulb, Non-fungible token,
  Umeå, Sputnik crisis, Ark Invest as a generic asset manager, etc.),
  broad biotech concepts that aren't CRISPR-specific (Genetically
  modified animal / crops as general umbrella articles — borderline
  with PERIPHERAL), and lists that merely mention CRISPR (List of
  inventions and discoveries by women, Fully Automated Luxury
  Communism as a political book).

# Notes for auditors:
# - "Pioneer" status: any scientist credited by major CRISPR histories
#   (including popular works like The Code Breaker) is CENTRAL. Mere
#   CRISPR-users without a foundational / methodology contribution
#   are PERIPHERAL.
# - Disease applications: the specific diseases CRISPR therapies are
#   approved or under trial for are PERIPHERAL. Unrelated diseases
#   that merely appear in gene-therapy discussion are OUT.
# - Companies: a company whose core platform is CRISPR is CENTRAL.
#   Ones adjacent (VC firms, asset managers) are PERIPHERAL at most,
#   often OUT.
# - Named books / films: if the work's subject is CRISPR or a CRISPR
#   figure, CENTRAL. Works that touch CRISPR among broader subjects
#   (history of biotech, future-of-humanity manifestos) → PERIPHERAL
#   or OUT depending on emphasis.
```

### Scope

**Short statement:** Wikipedia articles about CRISPR as a gene-editing system — its biology, mechanisms, associated techniques and tools, pioneering scientists, CRISPR-focused companies, applications (therapies and projects), and the central bioethical episode (He Jiankui affair).

**In scope:**
- CRISPR biology and mechanisms: the CRISPR main article, CRISPR RNA, Cas-family proteins (Cas9, Cas12a, Cas3), guide RNA, protospacer adjacent motif (PAM), tracrRNA / crRNA, anti-CRISPR proteins, CRISPR-associated transposons (CASTs).
- CRISPR editing techniques: Prime editing, base editing, CRISPR activation (CRISPRa), CRISPR interference (CRISPRi), CRISPR-Display, CRISPR/Cas tools, genome-wide CRISPR-Cas9 knockout screens, epigenome editing via CRISPR, LEAPER, TIGR-Tas, off-target editing, GUIDE-Seq.
- Foundational scientists: Jennifer Doudna, Emmanuelle Charpentier, Feng Zhang, Virginijus Šikšnys, Rodolphe Barrangou, Francisco Mojica, Yoshizumi Ishino, Luciano Marraffini, Erik J. Sontheimer, J. Keith Joung, Samuel H. Sternberg, Lei Stanley Qi, Patrick Hsu.
- CRISPR-focused companies: CRISPR Therapeutics, Editas Medicine, Intellia Therapeutics, Mammoth Biosciences, Innovative Genomics Institute.
- Approved / clinical-trial therapies: Exagamglogene autotemcel (Casgevy), Verve PCSK9-inhibitor gene therapy, Victoria Gray (first sickle-cell CRISPR patient), KJ Muldoon (early N=1 gene therapy).
- He Jiankui affair: He Jiankui, the He Jiankui affair article, Designer baby, Human germline engineering, closely-affiliated Chinese researchers when the article documents CRISPR-specific involvement.

**Explicitly out of scope:**
- Generic biotech / technology noise. The baseline observed: Cement, Plastic, Submarine, Vehicle, Transport, Technology, Integrated circuit, Incandescent light bulb, Non-fungible token, Umeå, Sputnik crisis. Lexical-search noise; should never have entered.
- Broad list articles ("List of inventions and discoveries by women") — mentions CRISPR but isn't about it.
- Tangential cultural works (*Fully Automated Luxury Communism* — touches CRISPR in one chapter) — OUT.
- Unrelated VC / finance firms (Ark Invest) — OUT. (Flagship Pioneering founded Editas and IS part of the CRISPR venture story — PERIPHERAL, not OUT.)
- Generic disease articles where CRISPR is one of many angles (Thalassemia as a broad umbrella → OUT; Beta thalassemia as the specific CRISPR therapy target is PERIPHERAL).

**Ambiguity rulings:**
- Pioneer vs. CRISPR-user biographies: CENTRAL if credited for a foundational contribution; PERIPHERAL at most if they merely use CRISPR. When in doubt, check whether *The Code Breaker* (Isaacson) would feature them.
- Chinese researchers associated with He Jiankui: He Jiankui himself and the affair article are CENTRAL. Figures whose articles mention He Jiankui context but whose notability is broader stem-cell work → PERIPHERAL or OUT. Default PERIPHERAL when unclear.
- Disease targets: sickle cell disease (primary CRISPR therapy target) → PERIPHERAL. Beta thalassemia → PERIPHERAL. Generic "Thalassemia" umbrella → OUT.
- "Genome editing" as a field article → CENTRAL.
- "Gene therapy" → PERIPHERAL (broader category).
- Science-popularization books: *The Code Breaker* → PERIPHERAL. *Fully Automated Luxury Communism* → OUT.
- Documentary films: *Human Nature* (2019) → PERIPHERAL. *Make People Better* → PERIPHERAL.
- Application projects: Colossal Biosciences' dire wolf, woolly mouse → PERIPHERAL.

### Reach targets from the baseline run

- **No Wikidata probe.** P101 (field of work) = Q42240 (CRISPR) would likely surface additional pioneer biographies.
- **No navbox harvest.** Check if there's a CRISPR navbox template.
- **Search noise** was cleaned manually — 13 articles via `remove_articles`. A stronger relevance filter (`auto_score_by_description` with care for the proper-noun KNOWN SHARP EDGE, description-match rejection) would cut the overhead.
- **No cross-wiki probe** for the He Jiankui figure, who has substantial zh/ja coverage.

---

## Benchmark 3 — african-american-stem

**Run-topic name:** `african-american-stem ratchet-2026-04-23`
**Baseline name (DO NOT use):** `African American people in STEM`
**Wiki:** en

### Rubric

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

### Scope

**Short statement:** Wikipedia biographies of people of African American / Black American heritage, working in STEM research fields, with meaningful US affiliation.

**In scope:**
- **Heritage:** African American / Black American. "Black American", African diaspora people whose notability includes US-affiliated work. Black immigrants who built a US research career (Nigerian-American, Ghanaian-American, Kenyan-American, Cuban-American of Afro-Latino heritage) are IN. Black British / Caribbean-born scientists with substantive US research work are IN.
- **STEM fields:** Natural sciences (physics, chemistry, biology, astronomy, geology, meteorology, oceanography, ecology, neuroscience, environmental science, paleontology, hydrogeology, soil science), mathematics and statistics, engineering (including biomedical and aerospace), computer science, astronautics, inventors / technologists, materials science, nanoscience, biochemistry, microbiology, genetics, physiology, pharmacology.
- **US affiliation:** US-born counts. Immigrants who pursued a STEM career at US institutions count. Foreign researchers with a substantive postdoc / research position in the US then returning home count. Bar is "some real US-based research activity," not "lifelong US resident."

**Explicitly out of scope:**
- **Clinical medicine.** Physicians whose notability is primarily clinical practice, medical administration, authorship of popular books, or medical education are OUT. **Physician-scientists whose notability is primarily research (lab work, clinical research programs, publication record) are IN,** including MDs and MD/PhDs. Biomedical engineers are IN.
- **Social sciences.** Economists, psychologists, sociologists, anthropologists, political scientists — OUT, even if quantitative.
- **STEM education (without research).** Educators whose notability is teaching / curriculum / advocacy / administration rather than research — OUT. STEM researchers who also teach — IN.
- **No US affiliation.** Black African / Caribbean scientists with no substantive US research ties — OUT.
- **Non-science roles.** Politicians, lawyers, athletes, musicians, artists, actors, journalists, poets, military officers (without STEM research), religious leaders, business executives (without STEM-primary notability), activists, fraternity founders.
- **Architecture.** Licensed architecture practitioners OUT. Civil / structural / environmental engineers IN.

**Ambiguity rulings:**
- Physician-scientists (MD or MD/PhDs doing primarily research) — IN.
- Astronauts — IN.
- STEM + secondary activism / politics / entrepreneurship — IN when STEM is the primary profession listed.
- Entrepreneurs with STEM credentials — IN if notability is engineering / invention / research; OUT if primarily a businessperson.
- Popular-science writers with PhDs — IN if they have an active research career; OUT if notability is as a writer.
- "Academic" (bare, no field) — PERIPHERAL default; case-by-case if more detail surfaces.
- Athletes who are also STEM researchers (Meredith Gourdine — long jumper + engineer) — IN via STEM qualifier. This exact case is the exemplar for why `fetch_article_leads` matters on this shape.

### Reach targets from the baseline run

- **Medicine-blocklist articles** still in the baseline corpus. The "AA STEM medicine blocklist" topic (id 8) identified clinical-physician bios as exclusion candidates but was never applied. A future run should ship tighter.
- **Wikidata P106 (occupation)** — `occupation = physicist` AND `ethnic group = African American` would surface additional bios.
- **Cross-wiki for African-diaspora researchers** — frwiki for Francophone African researchers with US postdocs. Non-zero reach.
- **Wikidata shortdescs mislead here** (see Gloria Chisum / Meredith Gourdine / William Hallett Greene cases). Use `fetch_article_leads` liberally on borderline biographies.

---

## Benchmark 4 — hispanic-latino-stem-us

**Run-topic name:** `hispanic-latino-stem-us ratchet-2026-04-23`
**Baseline name (DO NOT use):** `hispanic-latino-stem-us`
**Wiki:** en

### Rubric

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

### Scope

**Short statement:** Wikipedia biographies of people of Hispanic and Latino heritage, working in STEM fields, with a meaningful affiliation to the United States.

**In scope:**
- **Heritage:** Latin American ancestry from any Spanish-speaking Latin American country. Mexican, Puerto Rican, Cuban, Dominican, Colombian, Venezuelan, Peruvian, Argentine, Chilean, Guatemalan, Honduran, Nicaraguan, Salvadoran, Costa Rican, Panamanian, Ecuadorian, Bolivian, Paraguayan, Uruguayan. "Chicano/a" self-identified. US-born with Latino ancestry (Mexican-American, etc.) IN.
- **STEM fields:** Natural sciences (physics, chemistry, biology, astronomy, geology, meteorology, oceanography, ecology, neuroscience, environmental science), mathematics, engineering (including biomedical engineering), computer science, astronautics, inventors / technologists, materials science, biochemistry, microbiology, genetics, physiology.
- **US affiliation:** US-born counts. Immigrants who pursued a STEM career at US institutions count. Foreign scientists who did a substantive postdoc / research in the US and returned home: IN. Bar is "some real US-based research activity."

**Explicitly out of scope:**
- **Brazilian / Lusophone.** Brazilian-heritage people NOT in scope, regardless of US affiliation or STEM field.
- **Peninsular Spanish.** People from Spain (not Latin American heritage) NOT in scope.
- **Clinical medicine.** Physicians whose notability is primarily clinical practice / administration / popular books / medical education OUT. **Physician-scientists whose notability is primarily research (lab work, clinical research programs, publication record) ARE IN,** including MDs and MD/PhDs. Biomedical engineers IN.
- **Social sciences.** Economists, psychologists, sociologists, anthropologists, political scientists — OUT.
- **STEM education (without research).** Educators whose notability is teaching / curriculum / advocacy / administration — OUT.
- **No US affiliation.** Purely Latin America / Spain / Portugal-based scientists without US research ties — OUT.

**Ambiguity rulings:**
- Physician-scientists (MD or MD/PhDs research-primary) — IN.
- Entrepreneurs with STEM credentials — IN if notability is engineering / invention / research; OUT if primarily a businessperson.
- Popular-science writers with PhDs — IN if they have an active research career.
- Brief US visits (sabbatical, single conference) — OUT. US-affiliation bar is postdoc-level substantive.
- Dual-citizen scientists moving between US and home country — IN if US research activity was substantive.

### Reach targets from the baseline run

- **Reduce false positives.** 381 articles in the current server corpus are confirmed OUT per the binary gold; a scope-tightened run should ship without them.
- **Recover 5 missing gold positives** (per the 2026-04-17 baseline.md): Alba Colón, Annie Antón, Carmen Cid, Cecilia R. Aragon, Celso-Ramón García, Craig Henriquez.
- **1,246 unaudited articles** in the current server corpus need classification — they include both legitimate gold-candidate biographies and search noise.
- **Cross-wiki reach.** Spanish-language Wikipedia likely has Latino STEM biographies not sitelinked to enwiki. High-priority reach target; but for this ratchet cycle, enwiki focus is fine — the gold is enwiki-anchored.

---

## Benchmark 5 — orchids

**Run-topic name:** `orchids ratchet-2026-04-23`
**Baseline name (DO NOT use):** `orchids`
**Wiki:** en

### Rubric

```
# Centrality rubric — orchids benchmark
# Frozen 2026-04-23. A rubric change invalidates gold.csv.

CENTRAL — Wikipedia articles about orchids (Orchidaceae family) and
  their immediate biology: species, genera, natural hybrids, cultivars,
  and notable individual plants; orchid-focused taxonomy; named
  orchid-related institutions (botanical gardens specializing in
  orchids, orchid societies); orchid-focused cultural works (books,
  documentaries, paintings centered on orchids); orchid phytochemistry
  (compounds identified in or isolated from orchids); orchid pests,
  pathogens, and symbionts where the article's subject is the
  interaction with orchids; and people whose primary notability is
  orchid-specific work (orchidologists, orchid breeders, orchid
  hunters, orchid growers, orchid hybridizers).

PERIPHERAL — General botanists, naturalists, biologists, explorers,
  or botanical illustrators whose work includes orchid taxonomy but
  whose primary notability isn't orchid-specific. Also: related
  botanical gardens without orchid specialization; cultural works
  that include orchids among many subjects (East Asian Four
  Gentlemen art tradition if the broader work is the article's
  subject); plant-collector biographies where some species are
  orchids.

OUT — Non-orchid plants, generic flowering plants not in Orchidaceae,
  non-botanical topics pulled in by name collision or lexical noise
  (semiconductor companies sharing a species epithet, actors sharing
  a botanist's name, anthologies that mention orchids only in
  passing), and bios of non-botanical figures swept up by cross-wiki
  reconciliation without orchid-specific work.

# Notes for auditors:
# - At 18,122 articles, this benchmark uses a keyword-rule classifier
#   with source-trust (articles pulled from category:Orchids or
#   orchid-list-pages are trusted as on-topic taxa, since orchid
#   builds only harvest orchid-relevant lists by construction).
# - Sample-audit via WebFetch is the recommended validation path:
#   pull 30–100 random articles from each bucket, verify against
#   their Wikipedia articles, and refine classifier rules if
#   precision on the sample drops below a threshold.
# - Orchid phytochemistry is CENTRAL (orchid-specific compounds); the
#   classifier marks "Chemical compound" + category:Orchids as IN.
# - Cultural-tail coverage: East Asian Four Gentlemen tradition
#   (Chinese poetry / painting featuring orchids) is IN via the
#   orchid-cultural-tail criterion when the article's primary subject
#   is the orchid cultural role. The specific authors/artists (Qu Yuan,
#   Guan Daosheng) are tangential and currently OUT; a future audit
#   could lift them to PERIPHERAL if we want broader cultural-tail
#   coverage.
```

### Scope

**Short statement:** Wikipedia articles about members of the Orchidaceae family (orchids) and their immediate biology, taxonomy, cultivation, pollination, phytochemistry, and cultural role. Includes orchid-focused people and institutions; includes orchid cultural works; excludes non-Orchidaceae plants and general botany unless orchid-specific.

**In scope:**
- **Orchid taxonomy.** Species, genera, subtribes, hybrids (natural and cultivated), cultivars, and named individual plants of the Orchidaceae family. Notable example genera: Phalaenopsis, Cattleya, Dendrobium, Vanda, Cymbidium, Oncidium, Vanilla, Bulbophyllum, Paphiopedilum, Epidendrum, Masdevallia, Laelia, Caladenia, Acianthera, Pleurothallis, Stelis, Lepanthes, Ornithocephalus.
- **Orchid-specific people.** Orchidologists, orchid hunters, orchid growers, orchid hybridizers, orchid breeders, orchid collectors, orchid nursery operators. Scientists whose primary published work is orchid taxonomy or orchid biology.
- **Orchid-specific institutions.** Botanical gardens specializing in orchids, orchid societies, orchid research centers.
- **Orchid cultural works.** Books, documentaries, films whose primary subject is orchids (e.g. *The Orchid Thief* — but not necessarily its film adaptation unless that article is primarily about the orchid subject matter).
- **Orchid phytochemistry.** Chemical compounds identified in or isolated from orchids, including fragrance components and medicinal compounds.
- **Orchid pollination biology.** Articles about pollination mechanisms specific to orchids, orchid-symbiont mycorrhizae, orchid-pollinator coevolution.
- **Orchid pests, diseases, and conservation.** Pests and pathogens where the article's subject is the interaction with orchids; conservation status articles for orchid species.

**Explicitly out of scope:**
- **Non-Orchidaceae plants.** Roses, lilies, irises, any flowering plant family other than Orchidaceae. Even if the plant shares an orchid-species epithet, OUT.
- **General botany.** Pollination biology in general, plant taxonomy in general, flowering-plant evolution in general — OUT unless orchid-focused.
- **Name collisions.** Articles unrelated to orchids pulled in by fuzzy search or list-page inclusion (semiconductor companies, actors, politicians whose names match orchid-species epithets or list entries).
- **Non-orchid figures from cross-wiki reconciliation.** Chinese artists/poets (Qu Yuan, Ma Shouzhen, Guan Daosheng) tangentially connected to orchid cultural tradition but whose primary notability is unrelated — default OUT.

**Ambiguity rulings:**
- **General botanists.** PERIPHERAL default. A botanist who described orchid taxa but is also known for other families is peripheral (Carl Ludwig Blume, Alfred Cogniaux, Achille Richard).
- **Orchid phytochemicals.** IN. Chemical compounds from orchids whose articles are in category:Orchids count.
- **Four Gentlemen art tradition** ("Four plants in East Asian art"). The overarching cultural article is IN. Specific artists who painted the Four Gentlemen are OUT by default unless the article emphasizes orchid-specific work.
- **Empty Wikidata shortdesc + orchid source.** IN — trust the source (build context guarantees orchid relevance).
- **Cross-wiki-reconciliation manual sources.** Mostly IN (articles walked back to enwiki from other-language orchid builds). Non-botanical biographies from cross-wiki are OUT.

### Reach targets from the baseline run

- **Cross-wiki reach** was the biggest unexploited strategy on the baseline (21 gap-fills on the first walk; many more likely reachable). **For this ratchet cycle: stay enwiki.** The `cross_wiki_diff` tool isn't shipped yet, and the frozen gold is enwiki-only, so cross-wiki reach wouldn't affect the scoreboard. Lean hard on enwiki completeness instead.
- **Wikidata P171 (parent taxon) against Q25308 (Orchidaceae).** Not exercised in the baseline; likely captures a handful of orchid species missing from the enwiki corpus.
- **Reduce false positives.** The 9 known OUT entries in gold (Besi semiconductor, Bruce Gray the actor) came from name collisions — a ratcheting run with relevance filtering or title-type verification should drop these pre-commit.
- **Cultural-tail scope.** Keep Chinese literary figures (Qu Yuan, Ma Shouzhen) OUT per current rubric.

---

## When all 5 are done

Reply with a single summary table:

| slug | run-topic name | final article count | coverage_estimate.confidence | rating | notable friction |
|---|---|---|---|---|---|
| apollo-11 | apollo-11 ratchet-2026-04-23 | … | … | … | … |
| crispr-gene-editing | crispr-gene-editing ratchet-2026-04-23 | … | … | … | … |
| african-american-stem | african-american-stem ratchet-2026-04-23 | … | … | … | … |
| hispanic-latino-stem-us | hispanic-latino-stem-us ratchet-2026-04-23 | … | … | … | … |
| orchids | orchids ratchet-2026-04-23 | … | … | … | … |

That's enough for the operator to run the scoring script. Don't push further unless asked.
