# Topic Builder benchmark run — crispr-gene-editing (2026-04-23 ratchet)

You are running the Topic Builder MCP server (`https://topic-builder.wikiedu.org/mcp`) against a single benchmark topic. Your goal this session is to build a fresh corpus for this topic under a new, non-colliding name, ending with an honest `submit_feedback`. Your work will be scored against a frozen baseline + audited gold set; the measurement is how well the current tool surface performs on the "scientific discipline with distinctive vocabulary" shape.

**Mode:** Deep consultative, completeness-seeking — not speed. An honest 0.65 coverage estimate is more useful than an inflated 0.9. No human user is here to steer you mid-session; you're running autonomously. Fabricate spot-check probes yourself when the protocol asks for them.

## Context you should know

- **Tier 1 bundle just shipped** (today):
  - `coverage_estimate` field on `submit_feedback`. Use it on every wrap-up.
  - New `KNOWN SHARP EDGES` section in `server_instructions.md` — read it at session start. **Especially relevant for this topic:** the `auto_score_by_description(disqualifying=[...])` proper-noun edge (e.g. `disqualifying=["city"]` matches "Kansas City Star"). When reaching for that tool, prefer multi-word phrases over single common words.
  - New `fetch_article_leads(titles, sentences=3)` tool — for misleading Wikidata shortdescs.
- **Don't call `export_csv`.** The scoring script pulls the corpus directly from the server.
- **Use the EXACT run-topic name below.** The scoring script looks up the topic by name. Using the baseline name would overwrite frozen ground truth.

## Run-topic name

- **Run-topic name (exact):** `crispr-gene-editing ratchet-2026-04-23`
- **Baseline name (DO NOT use):** `CRISPR gene editing`
- **Wiki:** `en`

## Step 0 — Setup check

1. Confirm the Topic Builder MCP tools are loaded. Quick probe: `list_topics()`.
2. Read the server's instructions (came in on session init via MCP `instructions=`). Note SCOPE RUBRIC, PIPELINE, NOISE TAXONOMY, KNOWN SHARP EDGES, SPOT CHECK, GAP CHECK, WRAP-UP.
3. If tools aren't loaded, stop and surface the blocker.

## Step 1 — Persist the rubric

Call `set_topic_rubric(rubric=<verbatim text below>)`. Don't paraphrase.

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

## Step 2 — Internalize the scope

**Short statement:** Wikipedia articles about CRISPR as a gene-editing system — its biology, mechanisms, associated techniques and tools, pioneering scientists, CRISPR-focused companies, applications (therapies and projects), and the central bioethical episode (He Jiankui affair).

**In scope:**
- CRISPR biology and mechanisms: the CRISPR main article, CRISPR RNA, Cas-family proteins (Cas9, Cas12a, Cas3), guide RNA, protospacer adjacent motif (PAM), tracrRNA / crRNA, anti-CRISPR proteins, CRISPR-associated transposons (CASTs).
- CRISPR editing techniques: Prime editing, base editing, CRISPR activation (CRISPRa), CRISPR interference (CRISPRi), CRISPR-Display, CRISPR/Cas tools, genome-wide CRISPR-Cas9 knockout screens, epigenome editing via CRISPR, LEAPER, TIGR-Tas, off-target editing, GUIDE-Seq.
- Foundational scientists: Jennifer Doudna, Emmanuelle Charpentier, Feng Zhang, Virginijus Šikšnys, Rodolphe Barrangou, Francisco Mojica, Yoshizumi Ishino, Luciano Marraffini, Erik J. Sontheimer, J. Keith Joung, Samuel H. Sternberg, Lei Stanley Qi, Patrick Hsu.
- CRISPR-focused companies: CRISPR Therapeutics, Editas Medicine, Intellia Therapeutics, Mammoth Biosciences, Innovative Genomics Institute.
- Approved / clinical-trial therapies: Exagamglogene autotemcel (Casgevy), Verve PCSK9-inhibitor gene therapy, Victoria Gray (first sickle-cell CRISPR patient), KJ Muldoon (early N=1 gene therapy).
- He Jiankui affair: He Jiankui, the He Jiankui affair article, Designer baby, Human germline engineering, closely-affiliated Chinese researchers when the article documents CRISPR-specific involvement.

**Explicitly out of scope:**
- Generic biotech / technology noise. Baseline observed: Cement, Plastic, Submarine, Vehicle, Transport, Technology, Integrated circuit, Incandescent light bulb, Non-fungible token, Umeå, Sputnik crisis. Lexical-search noise; should never have entered the corpus.
- Broad list articles ("List of inventions and discoveries by women") — mentions CRISPR but isn't about it.
- Tangential cultural works (*Fully Automated Luxury Communism* — touches CRISPR in one chapter) — OUT.
- Unrelated VC / finance firms (Ark Invest) — OUT. (Flagship Pioneering founded Editas and IS part of the CRISPR venture story — PERIPHERAL.)
- Generic disease articles where CRISPR is one of many angles (Thalassemia as umbrella → OUT; Beta thalassemia as specific CRISPR therapy target → PERIPHERAL).

**Ambiguity rulings:**
- Pioneer vs. CRISPR-user biographies: CENTRAL if credited for a foundational contribution; PERIPHERAL at most if they merely use CRISPR. When in doubt, check whether *The Code Breaker* (Isaacson) would feature them.
- Chinese researchers around He Jiankui: He Jiankui himself and the affair article are CENTRAL. Figures whose articles mention He Jiankui context but whose notability is broader stem-cell work → PERIPHERAL or OUT. Default PERIPHERAL.
- Disease targets: sickle cell disease → PERIPHERAL. Beta thalassemia → PERIPHERAL. Generic "Thalassemia" umbrella → OUT.
- "Genome editing" as a field article → CENTRAL.
- "Gene therapy" → PERIPHERAL (broader category).
- Science-popularization books: *The Code Breaker* → PERIPHERAL. *Fully Automated Luxury Communism* → OUT.
- Documentary films: *Human Nature* → PERIPHERAL. *Make People Better* → PERIPHERAL.
- Application projects: Colossal Biosciences' dire wolf, woolly mouse → PERIPHERAL.

### Topic-specific guardrails

- **Shape:** search-native (distinctive lexical stem "CRISPR" / "Cas"), weak category / list structure, single-source-heavy. The baseline reached rating 8 with only 14 tool calls / 46 API calls — a tight bar.
- **Noise class:** lexical-search brought in ~15 obvious unrelated articles (Cement, Plastic, Submarine, Umeå, etc.) in the baseline. A stronger relevance filter should cut this pre-commit.
- **`auto_score_by_description` with care:** per the KNOWN SHARP EDGES section, `disqualifying=["city"]` would match "Kansas City Star" / "Orange County Register". For CRISPR-adjacent descriptions, prefer multi-word phrases or more specific terms.

## Step 3 — Build to completeness

Standard pipeline:
- Reconnaissance — WikiProject probe, category survey, list-page discovery, Wikidata lookup (likely relevant for CRISPR: Q42240 on Wikidata; P101=Q42240 could surface field-of-work matches).
- Gather — `get_category_articles`, `harvest_list_page`, `harvest_navbox` (check for a CRISPR navbox), `search_articles`, `search_similar`, `browse_edges`. Prefer `preview_*` on risky pulls.
- Descriptions — `fetch_descriptions`.
- Review — `auto_score_by_description` (with the caveat above); `fetch_article_leads` when a shortdesc looks thin or wrong on borderline pioneer bios.
- Cleanup — `filter_articles`, `remove_by_pattern`, `remove_by_source`.

### Reach targets from the baseline run

- **No Wikidata probe.** P101 (field of work) = Q42240 (CRISPR) would likely surface additional pioneer biographies.
- **No navbox harvest.** Check for a CRISPR navbox/template (e.g. `Template:Genome editing`) — if one exists, `harvest_navbox` would surface adjacent articles.
- **Search noise cleaned manually.** 13 articles via `remove_articles` in baseline. A stronger relevance filter (centrality scoring, description-match rejection) should cut this overhead.
- **No cross-wiki probe** for He Jiankui (substantial zh/ja coverage). Low-priority reach for this ratchet.

## Step 4 — SPOT CHECK + GAP CHECK

1. Fabricate ~15–25 niche CRISPR titles you'd expect (specific Cas proteins, specific editing techniques, specific pioneers, specific therapies, specific clinical patients, specific bioethics articles). Authorized to fabricate autonomously.
2. Check presence via `get_articles(title_regex=...)` or `preview_search`.
3. Classify misses: variant-name (redirect) / LLM hallucination / real gap.
4. Diagnose patterns.
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

`confidence` = self-estimate of corpus completeness relative to the frozen scope. Honest low beats inflated high.

## Step 7 — Do NOT call `export_csv`

The scoring script pulls the corpus directly from the server.

## Done

Reply with a brief summary: final article count, coverage_estimate.confidence, and any notable friction.
