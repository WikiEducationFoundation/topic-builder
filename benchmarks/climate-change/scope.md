# Scope: climate change

Frozen: 2026-04-25. Revisit deliberately — a scope change invalidates the
gold audit and requires a re-run.

## Short statement

Wikipedia articles whose primary subject is, or is directly tied to,
human-caused climate change / global warming — its science and
attribution, its impacts, its mitigation, its policy, and its movement.
Includes the field's people and institutions, named events and named
agreements, "Climate change in [country]" geographic variants, and
cultural works whose explicit subject is climate. Excludes articles
that touch climate-relevant chemistry / energy / weather subjects but
whose framing is not climate-centered.

## Origin and aspirational reference

Climate change was the original exploratory topic for the Topic Builder
project (Phase 2 of the 2026-04-16 development narrative). That early
build, executed via standalone Python scripts before the MCP server
existed, produced a 5,349-article expansive corpus by combining
WikiProject + depth-4 category sweep + 17 list pages + extract-based
scoring + edge browsing. Several of the project's load-bearing design
principles — "categories are a starting point, not the answer", "the LLM
is the quality gate", "centrality not binary", "edge-browse from the
periphery, not the core" — were articulated during that build.

This benchmark exists to:

1. Make that original exploration **reproducible** through the current
   MCP tool surface.
2. Provide a "well-organized academic" topic shape (the inverse of
   intersectional shapes like AA-STEM and Hispanic/Latino-STEM) for
   the ratchet to measure against.
3. Test the tools at scale on a topic with a strong WikiProject AND a
   dense category tree AND mature curated indexes — all three primary
   gather paths firing.

## In scope

- **Climate science.** Climate-change attribution, modeling,
  projection, paleoclimate evidence, atmospheric and oceanographic
  mechanisms framed in climate terms (CO₂ in Earth's atmosphere,
  ocean acidification, ice-sheet loss, AMOC shutdown).
- **The IPCC and its reports.** All assessment cycles and special
  reports.
- **International agreements and conferences.** UNFCCC, Kyoto,
  Paris Agreement, every annual UN Climate Change Conference (COP-N,
  ~33 entries via Wikidata P31=Q7888355).
- **Climate movement and protests.** Fridays for Future, School
  Strike for Climate, Just Stop Oil, Extinction Rebellion, Sunrise
  Movement, named protest events, climate-justice campaigns.
- **Climate impacts.** Sea level rise, climate-attributed extreme
  weather events (drought, wildfire, flood, heatwave events
  documented as climate-attributed), species range shifts, climate-
  driven migration, named coral bleaching events, mass mortality
  events.
- **"Climate change in [country/region]"** articles — geographic
  variants are CENTRAL, not peripheral.
- **Mitigation technologies and energy systems** when the article's
  framing is climate-response: renewable energy (solar / wind /
  hydro / geothermal), EVs, carbon capture and storage, nuclear
  power as low-carbon, energy efficiency, green building, carbon
  markets, ESG, decarbonization, just transition.
- **Climate scientists, activists, and policy figures** whose
  primary notability is climate work.
- **Major climate NGOs / advocacy orgs / governmental bodies**
  whose mission is climate (350.org, Greenpeace's climate work,
  ministries of climate change in various countries).
- **Cultural works about climate** when climate is the explicit
  subject of the work (films, novels, video games, art).
- **Annual climate-year summaries** (2019 in climate change → 2026
  in climate change).
- **Greenhouse gases as atmospheric agents** — articles whose
  subject is the gas's climate role.
- **Deforestation and land-use change** including "Deforestation
  in [country]" variants and reforestation / afforestation /
  REDD+ / Amazon Fund.

## Explicitly out of scope

- **Petroleum geology and oil/gas industry processes** that aren't
  climate-framed: drilling, refining, well-completion, pipeline
  operations, oil reserves quantification, gas-field articles.
- **Chemistry of methane / CO₂ / fluorocarbons** unrelated to
  atmospheric or climate context: industrial processes, food
  chemistry, "carbonated" beverages, semiconductor uses, individual
  fluorocarbon refrigerant articles whose subject is the chemistry,
  not the warming role.
- **Generic meteorology and weather** not framed as climate:
  everyday forecasting, generic storm taxonomy, individual
  non-attributed weather events.
- **Generic engineering articles** about renewable-tech components
  when the article isn't climate-framed: specific turbine bearings,
  panel-manufacturing techniques, battery-cell chemistry articles
  that happen to be in solar-energy outline pages.
- **"Geography of [country]"** articles — climate is a sub-section
  of these, not their subject. OUT.
- **Generic motor-vehicle articles** even if low-emission: "Toyota
  Prius" is climate-relevant context, "Toyota Camry (XV70)" is not.
  Borderline; defaults to OUT.
- **Biographies of energy-industry figures** whose work is not
  climate-centric.
- **Works of fiction with only incidental climate themes.**
- **"X in popular culture"** pages that mostly enumerate fiction.
- **Cities, capitals, generic country articles** even when they
  appear in climate-tagged categories or "by country" list-page
  harvests — the country is context for "Climate change in
  [country]", not the topic itself.

## Ambiguity rulings (default decisions)

- **Sustainable / circular economy articles.** PERIPHERAL by default.
  The article often touches climate as one of many environmental
  motivations; admitted to the corpus but not central.
- **Greenhouse-gas chemistry compounds.** OUT by default at
  individual-compound resolution (e.g. 1,1,1,2-Tetrafluoroethane).
  The aggregate "Greenhouse gas" article and "Methane / Carbon
  dioxide / Nitrous oxide" main articles are PERIPHERAL — they
  carry climate framing.
- **Climate scientists with non-climate primary work.** PERIPHERAL.
  A meteorologist who also did climate work but is primarily
  notable for general meteorology (or even unrelated work) lands
  peripheral. Catch-all for "climatologist" / "meteorologist" /
  "atmospheric scientist" descriptions.
- **Climate activists who are also celebrities / writers / artists.**
  PERIPHERAL when climate is one cause among many. Reserved CENTRAL
  for figures whose public identity is the climate work.
- **Annual COP conferences.** CENTRAL — every COP-N article counts,
  via the Wikidata P31=Q7888355 join.
- **"Energy in [country]"** when the article's framing is
  decarbonization / energy transition. PERIPHERAL.
- **Outline-of-X pages** (Outline of solar energy, Outline of energy
  development). These are tools, not topic articles — they get
  filtered out by `filter_articles` along with other list pages.
  The articles they LINK to remain in the corpus subject to per-
  article rubric review.

## Cross-wiki relevance

The original exploratory build was enwiki-only. This benchmark is
also primary-enwiki, but the topic is genuinely cross-wiki: climate-
change articles exist on dozens of major wikis. Cross-wiki sitelink
walks against Wikidata for non-Anglosphere climate scientists,
regional climate-impact articles, and country-scale climate
movements are an aspirational reach target — not exercised in the
2026-04-25 baseline run.

## Known scope revisits / open questions

- **Sustainability / circular-economy depth.** The 2026-04-25
  baseline includes ~30 sustainability-economy articles surfaced
  via edge-browse. If a future run shows that path leaks heavily
  into general business / development articles, narrow the rubric
  to require explicit climate framing.
- **"In popular culture" handling.** Currently OUT. If users want
  cultural-impact coverage, separate scope question.
- **Geographic granularity.** "Climate change in [country]" is
  in scope; "Climate change in [city]" / "Climate change in
  [state]" — currently in via category sweep. A future audit
  could draw a city/state vs. country line if the corpus turns
  out to over-include sub-national geographic articles.
- **Motor-vehicle adjacency.** The 2026-04-25 build pruned 42
  Toyota-vehicle articles from the Outline of solar energy harvest.
  If future runs accidentally re-introduce them, the keyword
  classifier will need a vehicle-block rule.
