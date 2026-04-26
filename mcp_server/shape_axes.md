# Shape axes

A small canonical vocabulary for characterizing a topic's shape. Used
across exemplars (`dogfood/exemplars/*.md`), the move catalog
(`mcp_server/strategy_moves.md`), the failure-mode catalog
(`mcp_server/failure_modes.md`), and the calibration band derivation.

Commit to an axis profile early — at scoping or rubric time — and
revise it mid-build when surprising signals come in. The profile
isn't a categorical judgment; it's a working model of the topic that
guides which strategy moves apply, which failure modes to watch for,
and what your honest recall ceiling forecast is.

The structural axes (scale through periphery type) are properties of
the topic. The final axis — perceived recall ceiling drivers — is
your strategic forecast given the topic, the tools, and your own
knowledge of the subject. It is multi-valued and explicitly
open-ended; the catalog of common drivers below is a starting set,
not a closed enum.

---

## Scale

How many on-topic articles you expect the working corpus to land at.

**Values.** `small` (<200) / `medium` (200–2k) / `large` (2k–10k) /
`huge` (>10k).

**Why it matters.** Sets cost expectations and determines whether
depth-3 sweeps are safe (`small`/`medium`) or need pre-survey + branch
exclusions (`large`/`huge`). Also constrains which review moves are
practical: a `huge` corpus can't be hand-reviewed, so per-source
trust + bulk filters carry the load.

**Detection.**
- Scoping: domain reasoning. "How many notable instances of this
  exist on Wikipedia?"
- Recon: `survey_categories(count_articles=True)` gives a usable
  estimate before commit.
- Mid-build: actual corpus size from `describe_topic` or
  `get_status`.

**Examples.**
- `small`: Studio Ghibli (132), CRISPR (~150), Apollo 11 (~250).
- `medium`: Esperanto (636), Bluegrass (1,292), Tour de France
  (1,453), London Underground (1,786), Type 2 diabetes (1,235),
  Chernobyl (464), African American STEM (~860), Hispanic/Latino
  STEM (~400).
- `large`: Sufism (2,788), Vietnam War (2,977), climate change
  (~6,500).
- `huge`: orchids (~13,000).

---

## Structural primitives present

Which Wikipedia structural artifacts exist for this topic. Multi-flag
boolean.

**Flags.**
- `canonical-category` — a category named after the topic exists and
  is topic-definitional (not a parent class, not a redirect /
  container).
- `dedicated-wp` — a WikiProject named after the topic actively tags
  articles (not registered-but-empty; not a broader-discipline WP).
- `curated-list-pages` — "List of X" / "Outline of X" pages exist
  and are authoritative.
- `canonical-navbox` — a `{{Template:X}}` navbox exists for the
  topic.
- `canonical-infobox` — an infobox uniquely identifies on-topic
  articles (e.g., `Infobox London station` tags every Tube
  station).

**Why it matters.** Each flag opens a strategy axis. No flags = the
topic is search-led; many flags = triangulation across multiple
high-precision sources is feasible.

**Detection.**
- `canonical-category`: `survey_categories(<topic name>)` returns a
  populated tree.
- `dedicated-wp`: `find_wikiprojects` + `check_wikiproject` confirms
  existence; `get_wikiproject_articles` returns >0 articles. Watch
  for `wp-registered-but-empty` (template registered, tags 0).
- `curated-list-pages`: `find_list_pages(<subject>)` returns
  topic-specific lists (not noise filtered out).
- `canonical-navbox`: domain reasoning + try `harvest_navbox` on the
  obvious template name. Future: a discovery primitive.
- `canonical-infobox`: domain reasoning. Future: transclusion-harvest
  primitive.

**Examples.**
- All five flags: orchids (Category:Orchidaceae, WP Plants/Orchids,
  many genus list pages, Template:Orchidaceae, Infobox taxon for
  every species).
- Strong category + navbox, no dedicated WP: Tour de France,
  Chernobyl, Vietnam War, Sufism.
- Dedicated WP + category: climate change, Esperanto.
- Strong category + infobox, no curated list pages: London
  Underground.
- Few flags (search-led): CRISPR, AA-STEM, HL-STEM, Type 2 diabetes.

---

## Biographical density

How heavily the topic's articles are biographies of people.

**Values.** `high` / `medium` / `low`.

**Why it matters.** Biographies are subject to shortdesc ambiguity in
ways concept articles aren't ("American academic" hides applied-STEM
specialization). High-bio-density topics want `fetch_article_leads`
and `auto_score_by_description` (with profession-axis caution per
intersectional warnings) in the toolkit; low-bio-density topics
don't, and reaching for them wastes calls.

**Detection.**
- Scoping: domain reasoning before any pull.
- Mid-build: `describe_topic` top-first-words histogram dominated by
  given names / surnames; profession-axis keyword sweep matching a
  large fraction of the corpus.

**Examples.**
- `high`: Sufism (saints/poets/scholars), African American STEM
  (biographies-only), Hispanic/Latino STEM (biographies-only),
  Studio Ghibli (founder-anchored).
- `medium`: Apollo 11 (mission + crew + ground personnel), Vietnam
  War (commanders + units + politicians among broader corpus), Tour
  de France (cyclists + organizers), Bluegrass (musicians + songs +
  albums), CRISPR (researchers among technical articles).
- `low`: orchids (taxonomy dominates), Chernobyl, Type 2 diabetes,
  London Underground, Esperanto, climate change.

---

## Multilinguality depth

How much on-topic content lives natively on non-English Wikipedias.

**Values.** `deep` / `moderate` / `shallow` / `english-dominant`.

**Why it matters.** `deep` topics have a hard recall ceiling on
English-only discovery. The cross-wiki workflow (parallel topic on
the relevant native wiki, then walk back) is a primary strategy on
`deep` topics, not a fallback. `english-dominant` topics gain little
from cross-wiki work.

**Detection.**
- Scoping: domain reasoning. Where does this topic's primary
  community / scholarship / source material live linguistically?
- Refine: Wikidata sitelink count distributions on a sample of the
  corpus's QIDs. A topic where most articles have sitelinks across 5+
  language Wikipedias is `deep`.

**Examples.**
- `deep`: orchids (zh / ja / pt / de cultural depth), Sufism (ar /
  fa / tr / ur), Esperanto (eo — the topic IS the native-language
  wiki), Studio Ghibli (ja), Vietnam War (vi), Tour de France (fr),
  Chernobyl (uk / ru), Bluegrass (some).
- `moderate`: Apollo 11 (Cold War context, international reception),
  climate change (global policy, regional impact).
- `shallow`: AA-STEM (US-bounded), HL-STEM (some Spanish-language
  sources), CRISPR (recent + English-dominant in primary
  literature).
- `english-dominant`: Type 2 diabetes (medical literature), London
  Underground (UK-only).

---

## Topic-vs-parent relationship

How the topic relates to a parent / sibling / child class on
Wikipedia.

**Values.** `standalone` / `subtype-of-parent` / `superset-of-children`
/ `peer-of-siblings`.

**Why it matters.** `subtype-of-parent` is the trap shape: Wikipedia
categorizes the parent (e.g., Diabetes), the topic-as-subtype has no
clean structural narrowing to it (e.g., no Category:Type 2
diabetes), and a category sweep on the parent over-pulls. Specific
moves apply: Wikidata property joins, description filtering, or
accepting a broader corpus and post-filtering by hand.

**Values defined.**
- `standalone`: the topic itself is a category root; sibling /
  parent classes are out of scope. (orchids, Tour de France.)
- `subtype-of-parent`: the topic is one of several subtypes
  Wikipedia categorizes only at the parent level. (Type 2 diabetes
  inside Diabetes; Bluegrass arguably inside Country/Folk; AA-STEM
  inside Scientists.)
- `superset-of-children`: the topic includes child topics that
  themselves have full coverage. (Vietnam War includes First
  Indochina War as predecessor; climate change includes IPCC, COP
  conferences.)
- `peer-of-siblings`: topic peer to similar siblings. (Studio Ghibli
  peer to other anime studios; Tour de France peer to Giro / Vuelta.)

**Detection.**
- Does `survey_categories(<topic name>)` return a real category, or
  only a redirect / container / sparse stub?
- Does the topic have a Wikipedia article that's a section under a
  larger article, or its own article?
- Do shortdescs of articles consistently cite the parent rather than
  the topic ("American with diabetes" rather than "Type 2 diabetic")?

**Examples.**
- `standalone`: orchids, Apollo 11, Esperanto, London Underground,
  Sufism, Studio Ghibli.
- `subtype-of-parent`: Type 2 diabetes (within Diabetes), Bluegrass
  (within Country music), AA-STEM (within Scientists), HL-STEM
  (within Scientists), CRISPR (within Genetic engineering).
- `superset-of-children`: Vietnam War (predecessor + spillover
  conflicts), climate change (institutions, regional policy).
- `peer-of-siblings`: Tour de France, Studio Ghibli, Chernobyl
  (peer to Three Mile Island, Fukushima).

---

## Time profile

How the topic sits in time.

**Values.** `recent` / `historical-bounded` / `ongoing` /
`multi-period`.

**Why it matters.** `historical-bounded` topics have a finite
universe of articles and benefit from completeness probes
(navbox, parent-program). `ongoing` topics need year-by-year coverage
and grow continuously. `recent` topics often have weak Wikipedia
structural backbone (no curated lists yet, sparse categories);
search-led + Wikidata is the substrate. `multi-period` topics need
both deep history and current coverage strategies.

**Detection.** Domain reasoning at scoping.

**Examples.**
- `recent`: CRISPR (post-2012), Studio Ghibli (1985–present, but
  the company-arc is bounded enough that this also reads as
  ongoing).
- `historical-bounded`: Apollo 11 (single 1969 mission), Chernobyl
  (1986 incident + aftermath), Vietnam War (1955–1975).
- `ongoing`: Tour de France (annual, 1903–present), Bluegrass
  (genre, 1940s–present), London Underground (operational network),
  Type 2 diabetes (continuous medical understanding), Esperanto
  (movement, 1887–present), Studio Ghibli (operational).
- `multi-period`: Sufism (medieval through present), orchids
  (taxonomic discovery 18th c. through present), climate change
  (paleoclimate through current policy).

---

## Periphery type

What kind of articles the topic's edges are made of, beyond the core.

**Values.** `cultural` / `technical` / `political` / `minimal`.

**Why it matters.** Different peripheries get pulled in by different
strategies. `cultural` periphery (works, depictions, art) often lives
in cross-wiki traditions and "X in popular culture" subcategories.
`technical` periphery is dense in sub-discipline categories and
Wikidata properties. `political` periphery lives in named
institutions, treaties, and biographies of decision-makers. `minimal`
periphery topics have a hard center and little to gather around it.

**Values defined.**
- `cultural`: works, depictions, traditions, festivals, art.
- `technical`: variants, sub-disciplines, methods, instruments.
- `political`: institutions, treaties, decision-maker biographies,
  controversies.
- `minimal`: tight center with little outer ring.

**Detection.** Domain reasoning at scoping; refined by what
`survey_categories` shows at depth 1.

**Examples.**
- `cultural`: orchids (cultural symbolism), Sufism (poetry, music,
  shrines), Bluegrass (festivals, regional scenes), Studio Ghibli
  (cultural reception). Often the periphery is the
  highest-value reach axis.
- `technical`: CRISPR (variants, applications), Type 2 diabetes
  (drug classes, complications), London Underground (rolling stock,
  signaling). Periphery dense in sub-discipline categories.
- `political`: Vietnam War (treaties, domestic politics, units),
  Chernobyl (Soviet response, IAEA), climate change (UNFCCC, COPs,
  national policy), Esperanto (organizations, congresses).
- `minimal`: Tour de France (very contained — winners + stages +
  jerseys + scandals; little tail beyond). Apollo 11 (small core +
  bounded program tail).

---

## Perceived recall ceiling drivers

Multi-valued list. What you (the AI building this topic) expect will
cap completeness on this topic, expressed in your own terms — informed
by the topic, the available tools, AND your domain knowledge of the
subject.

**Why it matters.** This is your strategic forecast, not a
system-derived classification. Naming a ceiling driver commits you
to either reach for the relevant move or document the gap.
Aggregating across runs is also how we discover where our toolset is
systematically short — including limits the AI sees that we haven't
named.

**Open-ended.** A topic can have multiple drivers. The anchors below
are starting points, not a closed enum. If your perceived ceiling
doesn't match any of them, name it in your own words on
`submit_feedback` — that's useful signal, not a vocabulary error.
Out-of-tool strategies (canonical monograph reading, domain-specific
external databases, expert consultation) are legitimate ceiling
namings even though our system can't act on them; they reveal where
the wiki-API toolkit falls short.

**Common anchors.**

- `cross-wiki-gap` — articles exist on a non-en wiki without enwiki
  sitelink, or vice versa. The cross-wiki workflow recovers them.
- `shortdesc-ambiguity` — biographies whose shortdesc hides
  scope-relevant identity (intersectional shapes especially).
  `fetch_article_leads` is the rescue.
- `subtype-narrow-from-parent` — Wikipedia categorizes the parent
  class; no clean structural narrowing to this subtype. Wikidata
  property joins or post-filtering by description.
- `wp-broader-than-topic` — a relevant WikiProject covers a superset.
  Without intersection logic the working list bloats.
- `wp-registered-but-empty` — the WikiProject template exists but
  tags zero articles. No rescue from that source; rely on
  category + lists + search.
- `consolidation-into-list-pages` — per-instance articles fold into
  list-of-X-characters / discography pages, ceiling-ing
  instance-level recall.
- `adversarial-categories` — semantically antithetical subcats sit
  under the topic root (e.g., Salafi/Wahhabi inside Sufism). Branch
  exclusion at survey time.
- `heritage-redirect-mass` — a large fraction of historical /
  abandoned-project / renamed-entity titles redirect to canonicals,
  inflating gross corpus counts.
- `main-article-context-link-noise` — harvesting the topic's main
  article body brings heavy context-link noise on event topics.
- `out-of-tool-strategy-needed` — closing the gap would need a
  strategy outside the wiki-API toolkit (canonical monograph, domain
  database, expert curation, non-Wikipedia citation indices). Worth
  naming explicitly: it's a tool-surface gap to log, not a topic
  defect.

**Detection.** Forecast at scoping time, refined mid-build. Not
fully derivable from the other axes — your domain knowledge of the
subject is part of the input.

**Examples.**
- Sufism: `cross-wiki-gap` (ar / fa / tr / ur native sources),
  `adversarial-categories` (Salafi/Wahhabi inside).
- Tour de France: minimal — `out-of-tool-strategy-needed` only if
  pushing for non-English domestique biographies via fr-wiki.
- Type 2 diabetes: `subtype-narrow-from-parent`,
  `out-of-tool-strategy-needed` (clinical-trial /
  medical-database joins).
- London Underground: `wp-broader-than-topic` (London Transport),
  `heritage-redirect-mass`.
- Studio Ghibli: `consolidation-into-list-pages`,
  `cross-wiki-gap` (jawiki).
- Esperanto: `cross-wiki-gap` (eo — the topic-native wiki),
  `wp-registered-but-empty`.
- AA-STEM: `shortdesc-ambiguity` on demographic axis.
- HL-STEM: `shortdesc-ambiguity` on demographic axis,
  `cross-wiki-gap` (es).
- Apollo 11: `out-of-tool-strategy-needed` arguably (mission
  documents, NASA archives) for the deepest reach.
- Chernobyl: `cross-wiki-gap` (uk / ru), `main-article-context-link-noise`.
- Vietnam War: `cross-wiki-gap` (vi), `wp-broader-than-topic`
  (WP Military History).
- Bluegrass: `consolidation-into-list-pages` (album/song
  consolidation), `wp-registered-but-empty`.
- orchids: `cross-wiki-gap` (zh / ja / pt / de),
  `consolidation-into-list-pages` (genus species lists).
- climate change: `cross-wiki-gap` (regional policy),
  `wp-broader-than-topic` (mitigation tech bleeds).
- CRISPR: `out-of-tool-strategy-needed` (closely-cited recent
  literature), `subtype-narrow-from-parent` (gene editing
  generally).

---

## Pointers

- Move catalog (`mcp_server/strategy_moves.md`) — atomic strategy
  primitives keyed off these axes via preconditions.
- Failure-mode catalog (`mcp_server/failure_modes.md`) — anti-patterns
  with axis-keyed detection cues.
- Exemplars (`dogfood/exemplars/*.md`) — worked case studies. Each
  exemplar's menu card axis-profile uses this vocabulary.
- `set_topic_rubric` (when Ship 2 lands) — accepts an axis profile
  and returns axis-applicable moves and relevant failure modes.
