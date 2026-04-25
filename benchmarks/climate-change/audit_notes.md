# Climate-change gold audit — notes

First-pass automated audit by `audit.py`, run 2026-04-25. The
classifier is conservative: slam-dunk classifications only, with
ambiguous cases left in `uncertain` for human follow-up.

## First-pass result

| Bucket | Count | % |
|---|---|---|
| in (CENTRAL) | 1,770 | 27.0% |
| peripheral (PERIPHERAL) | 4,276 | 65.2% |
| out (remove from corpus) | 435 | 6.6% |
| uncertain (sample-audit pending) | 81 | 1.2% |
| **total** | **6,562** | |

`audit_summary.md` is the auto-generated bucket samples.

## Approach (in priority order)

1. **Hard-OUT title patterns.** Motor-vehicle prefixes (Toyota, Honda,
   Acura, Hyundai, Kia, BMW, Buick, etc.), `Geography of [X]`,
   `[Year] in popular culture`, `Economy of [X]`, `Ecology of [X]`,
   `Demographics of [X]`, `History of [X]`, `Culture of [X]`. These
   are slam-dunk noise from the by-country and outline-of-X harvests.

2. **Fluorocarbon individual-compound titles.** Numeric-prefixed
   refrigerant chemistry (`1,1,1,2-Tetrafluoroethane`) is OUT per
   rubric — the article is chemistry, not climate.

3. **Generic motor-vehicle descriptions** without EV/hybrid framing
   ("Motor vehicle", "Compact luxury MPV", etc.).

4. **Generic geography descriptions** (`Country in X`, `Capital city
   of`, `U.S. state`, `Region of`, `Continent`, etc.) — OUT *only when
   the article's single source is a known geographic-noise channel*
   (`list_page:List of countries by greenhouse gas emissions`,
   `search:intitle:climate-intitle:in`, `search:intitle:deforestation`).
   Articles ALSO tagged in `wikiproject:Climate change` survive the
   geography filter and get demoted to PERIPHERAL via the source-trust
   rule later. This is what saves Antarctica, Greenland, etc. from
   wrongful OUT.

5. **IN by title.** `Climate change in [X]`, `Effects of climate
   change in [X]`, `Impacts of climate change in [X]`, `[YYYY] in
   climate change`. All CENTRAL.

6. **IN by named institution / agreement** (in title or description).
   IPCC, UNFCCC, Paris Agreement, Kyoto Protocol, every COP-N,
   350.org, Fridays for Future, Extinction Rebellion, School Strike
   for Climate, Just Stop Oil, Sunrise Movement, Greenhouse effect,
   Carbon tax, Net zero, Cap and trade, etc.

7. **IN by climate-central phrase** in description or title (climate
   change / climate science / climate scientist / climate policy /
   climate movement / climate activist / climate justice / etc.).

8. **IN by Wikidata source** P31=Q7888355 (UN Climate Change
   Conferences — every match is a COP).

9. **PERIPHERAL by mitigation phrase** in description or title (solar
   power, wind power, photovoltaic, EV, carbon capture, decarboniz,
   geoengineering, biofuel, energy efficiency, paleoclim,
   ocean acidification, sea level, ice core, deforestation,
   reforestation, sustainable [X], etc.).

10. **PERIPHERAL by climate-impact event title** — year-prefix titles
    (`YYYY` or `YYYY-YYYY`) with drought / flood / wildfire / heat
    wave / El Niño / La Niña / cyclone / hurricane / typhoon / haze
    / coral bleaching keywords.

11. **PERIPHERAL by national-climate-adjacent title** — `Air
    pollution in [X]`, `Forestry in [X]`, `Environment of [X]`,
    `Water resources in [X]`, etc.

12. **PERIPHERAL by national biosphere title** — `Flora of [X]`,
    `Forests of [X]`, `Biodiversity of [X]`.

13. **PERIPHERAL by climate-impact event description** ("natural
    disaster", "severe weather", "weather event", "warming of the
    eastern Pacific", etc.).

14. **PERIPHERAL by environmental role** — descriptions like
    "environmental activist / advocate / journalist / lawyer / NGO",
    "conservation movement", "ecological economist".

15. **PERIPHERAL by energy/industrial periphery** — coal-fired
    power, gas-fired power, ministry/department-of-energy /
    environment / climate, heat pump, battery storage.

16. **PERIPHERAL by climatologist/meteorologist/oceanographer
    description** — generic scientist who *may* have done climate
    work (rubric says PERIPHERAL when climate work isn't primary).

17. **`Climate of [Region]` titles** → PERIPHERAL (regional climate
    article, not climate change itself).

18. **Multi-sourced from primary climate sources** (both
    `wikiproject:Climate change` and `category:Climate change`) →
    IN. Both primary sources agreeing is high-confidence.

19. **Source-trust PERIPHERAL** — at least one source label is
    climate-named (WikiProject / category / climate-named list page /
    intitle:climate-change / intitle:global-warming /
    intitle:greenhouse-gas / morelike-climate / Wikidata P101=Q7942).
    Demoted to `uncertain` when only-source is one of the noisy
    Outline-of-X list pages.

20. **Source-trust PERIPHERAL: manual edge-browse** — articles added
    by hand in the edge-browse step were deliberate climate-adjacent
    additions. Default PERIPHERAL.

21. **Source-trust PERIPHERAL: Outline-of-solar-energy bios + tech**
    (when only-source is a noisy outline). Solar pioneers / engineers
    / journalists / politicians / mitigation-tech device articles all
    land peripheral via SOLAR_ROLE_PATTERNS.

22. **Source-trust PERIPHERAL: Wikidata-only role-described bios**
    — articles single-sourced from `wikidata:P106=` (climate activist
    or climatologist tag) whose description identifies a single
    occupation (politician, writer, actor, businessman, etc.) get
    PERIPHERAL. The Wikidata tag captures climate-relevance even when
    the shortdesc doesn't.

23. **Source-trust PERIPHERAL: morelike paleo/atmospheric** — articles
    sourced from `morelike:Carbon dioxide in Earth's atmosphere`
    whose description identifies a paleoclimate / atmospheric topic
    (Eocene, mass extinction, geological epoch, hydrogen ion,
    mesopause, etc.).

24. **HARD OUT: emissions-search noise** — when the only source is
    `search:intitle:emissions` AND the description has no climate
    keyword (climate / greenhouse / carbon / atmospheric / CO2 /
    emission factor). Catches atomic emission spectroscopy, flue-gas
    stacks, the heavy-metal festival "Emissions from the Monolith",
    diesel-exhaust generic articles.

## What's in the 81 uncertain rows

Patterns the classifier deliberately doesn't auto-classify:

- **Generic-energy / mitigation-tech articles** with non-climate
  shortdescs (Algae fuel, Desalination, Energy storage, Pipeline,
  Polycrystalline silicon, Solar cell, Solar thermal energy,
  Photovoltaic effect, Photoelectric effect). These are PERIPHERAL
  per rubric but the descriptions don't fire the existing periphery
  rules. Manually elevate to PERIPHERAL on follow-up.
- **Bare geographic articles** that snuck in via
  `search:intitle:climate-intitle:in` despite description rules
  (Punjab India, Sahara, San Francisco, Vostok Station, Washington
  DC, etc.). These are mostly OUT.
- **Wikidata-only bios** with descriptions the classifier doesn't
  recognize (occupation roles outside the climate-activist /
  climatologist / environmentalist vocabulary the classifier matches —
  e.g. cultural critic, religious-studies scholar, zoologist).
- **Politically scoped agreements / events** that aren't climate
  (Dayton Agreement 1995 Bosnian War, Paris Peace Accords 1973
  Vietnam, Na Chornykh Lyadakh 1995 Belarusian film). All OUT —
  these came from the compound `intitle:Kyoto OR Paris` search,
  which matched on "Paris" or "Dayton" without climate context.
- **Energy-policy / org articles** (Energy Policy Act of 2005,
  OPEC, United States Department of Energy, United States Atomic
  Energy Commission). PERIPHERAL — fossil-fuel-industry context for
  US Atomic Energy Commission and OPEC; energy-decarbonization for
  Energy Policy Act and DoE.

## Known limitations / future work

- **`audit.py` doesn't drop OUT articles from the topic.** It only
  classifies in `gold.csv`. To remove OUT from the live corpus,
  use `mcp__topic-builder__reject_articles` or `remove_articles`
  with the OUT title list.
- **Sample-audit precision not yet computed.** A 30–100 article
  random sample of the IN bucket should be WebFetch-verified to
  estimate precision. The orchids audit ran a 30-article sample that
  came back 30/30 in-scope → ~99% precision; a similar pass should
  be run here once the uncertain bucket is resolved.
- **Cultural-tail articles** ("12 Characters in Search of an
  Apocalypse: On the Road" — Performance, "A Children's Bible" —
  novel) are landing PERIPHERAL via source-trust. The rubric says
  cultural works ARE in scope when climate is the explicit subject;
  some of these may deserve IN. A future pass with `fetch_article_leads`
  on the cultural cluster would clarify.
- **`Climate of [Region]`** articles (Climate of Australia, Climate
  of Brazil, etc.) are landing PERIPHERAL. Per rubric they're
  borderline OUT (regional climate ≠ climate change). If a future
  scope tightening wants them OUT, the rule lives at line ~340 of
  `audit.py`.
