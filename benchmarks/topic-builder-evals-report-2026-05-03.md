# Topic Builder MCP Evals — Report 2026-05-03

Run via 7 parallel `Agent` subagents (general-purpose, Sonnet) each given
the harness's `EVALUATION_PROMPT` + a single qa_pair. No API key used —
local subagent invocation routed through the same auth path as
`agent_matrix.sh`. See `docs/backlog/server-audit.md` Tier 2 for context.

## Summary

| Metric | Value |
|---|---|
| Accuracy | 7 / 7 (100%) |
| Avg tool calls per question | 2.43 |
| Total tool calls | 17 |
| Avg duration per question | ~24s |
| Avg tokens per question | ~28.5k |

100% pass means our questions are within the recon-cluster's competence
zone. That's expected for a first pass — the questions probe whether the
tool surface *works*, not whether it has hard edges. Hard-edge probing
needs different question shapes (multi-tool ambiguity, large-response
overflow, error recovery). Note for future eval rounds.

The richer signal is the per-question `<feedback>` blocks below — every
agent independently surfaced 1–3 concrete tool refinements.

## Cross-cutting feedback themes

Same observation surfaced by ≥2 independent agents:

1. **`wikidata_get_entity` returns full sitelinks (~80 languages) even
   for narrow `properties=[...]` lookups** — Q1, Q3. Sitelinks dominated
   the response when the agent only needed one claim. Suggested fix:
   `include_sitelinks: bool = True` parameter, or auto-suppress when
   `properties` is a short filter.

2. **Wikidata time literals returned in raw form
   (`+1988-00-00T00:00:00Z`, `+2003-01-03T00:00:00Z`)** — Q1, Q3.
   Precision (year-only vs day-level) isn't surfaced — caller infers
   from `00-00` pattern. Suggested fix: include a `precision` field
   alongside the value, or a parsed `year` / `date` convenience.

3. **`auth_token` parameter visible in schema but undocumented in
   docstrings** — Q6, Q7. Agents wonder whether it's required for
   read-only calls. Suggested fix: one-line docstring addition
   "`auth_token`: not required for read-only calls."

Single-agent observations also worth noting:

- **`wikidata_query` aggregates return strings** (`"55"` not `55`).
  Q4 flagged this; harmless but worth a docstring line.
- **Generic response `note` mixes contexts.** Q6 noted that
  `get_article_templates(filter='wikiproject')` returned a `note`
  with leading navbox-heuristic guidance — irrelevant under that
  filter. Suggested: filter-specific note.
- **Double-wrapped JSON.** Q5 noted responses are a JSON object
  whose `result` field is a JSON-encoded string. Minor for LLMs.
- **`wikidata_search_entity` docstring leans heavily on the
  topic-building workflow** ("for downstream
  wikidata_entities_by_property"). Q2 noted it works fine for ad-hoc
  lookup but the framing reads as off-target. One-liner generalization
  would help.

---

## Per-question results

### Q1 — Greta Thunberg DOB (Wikidata) — ✅ PASS

- **Question:** On Wikidata, find the entity for the Swedish climate
  activist Greta Thunberg, then look up her date of birth (property
  P569). Answer in YYYY-MM-DD format and nothing else.
- **Expected:** `2003-01-03`
- **Actual:** `2003-01-03` ✅
- **Tools used (3):** ToolSearch → `wikidata_search_entity` →
  `wikidata_get_entity` (filtered to `properties=["P569"]`)
- **Duration:** 24.4s | **Tokens:** 30,904

**Feedback:** Search-then-get pairing pattern intuitive.
`properties` filter is "a great affordance" but sitelinks blob came
along regardless and dominated output — `include_sitelinks=False`
escape hatch suggested. P569 returned as raw Wikidata time literal;
precision field would make general date lookups more robust.

### Q2 — Paris Agreement QID disambiguation — ✅ PASS

- **Question:** What is the Wikidata QID for the international
  agreement signed on 12 December 2015 within the United Nations
  Framework Convention on Climate Change, commonly called the "Paris
  Agreement"? Distinguish it from the 1954 post-conference Paris
  Agreements and the 1864 treaty. Answer with the QID string only
  (e.g., "Q12345").
- **Expected:** `Q21707860`
- **Actual:** `Q21707860` ✅
- **Tools used (2):** ToolSearch → `wikidata_search_entity`
  (single call resolved the ambiguity via descriptions)
- **Duration:** 22.8s | **Tokens:** 28,686

**Feedback:** Returned `description` + `aliases` made disambiguation
trivial. Inline `note` ("Pick the QID whose description best matches
your concept...") is "lightweight inline guidance for what to do
next, which helps stateless clients." Docstring "leans heavily on
topic-building workflow" — slight off-target framing for ad-hoc
lookup.

### Q3 — IPCC inception year (Wikidata) — ✅ PASS

- **Question:** Locate the Wikidata entity for the United Nations
  body responsible for assessing climate-change science (commonly
  abbreviated IPCC), then read its inception date (P571). In what
  year was it founded? Answer with the four-digit year and nothing
  else.
- **Expected:** `1988`
- **Actual:** `1988` ✅
- **Tools used (3):** ToolSearch → `wikidata_search_entity` →
  `wikidata_get_entity(properties=["P571"])`
- **Duration:** 27.0s | **Tokens:** 31,365

**Feedback:** Same sitelinks-dominate-payload concern as Q1.
P571 value `+1988-00-00T00:00:00Z` is raw — precision encoding
not exposed; caller must know `00-00` means year-only.

### Q4 — Cattleya species count via SPARQL — ✅ PASS

- **Question:** Using SPARQL on Wikidata, count the distinct items
  whose "parent taxon" (P171) is the orchid genus Cattleya (Q133733)
  AND that have an en.wikipedia article. Answer with a single integer.
- **Expected:** `55`
- **Actual:** `55` ✅
- **Tools used (2):** ToolSearch → `wikidata_query` (single SPARQL
  joining P171 with `schema:isPartOf <https://en.wikipedia.org/>`)
- **Duration:** 25.6s | **Tokens:** 26,432

**Feedback:** Docstring is "excellent" — operational guidance
(60s cap, rate limits, in-process cache, hygiene tips) saved
guesswork. One nit: aggregate query results return as strings
(`"55"` not `55`); worth a docstring line.

### Q5 — WikiProject size comparison — ✅ PASS

- **Question:** On en.wikipedia, two WikiProjects worth comparing
  for breadth are WikiProject Climate change and WikiProject
  Environment. Using a read-only WikiProject preview tool, determine
  which has the larger total article count. Answer with the project
  name, omitting the "WikiProject " prefix.
- **Expected:** `Environment`
- **Actual:** `Environment` ✅ (4,840 vs 21,951)
- **Tools used (3):** ToolSearch → `preview_wikiproject` × 2
  (issued in parallel)
- **Duration:** 24.7s | **Tokens:** 28,572

**Feedback:** Docstring's pipeline ordering hint ("call this BEFORE
`get_wikiproject_articles`") is exactly the kind of guidance that
prevents wasted calls. `size_band` + `recommendation` fields
"telegraph follow-up cost" usefully. Minor: response is double-
wrapped (object whose `result` is a JSON-encoded string). Suggestion:
when `found_in_bot_index=false`, auto-include a hint pointing at
`find_wikiprojects` / `check_wikiproject`.

### Q6 — WikiProject banners on "Climate change" — ✅ PASS

- **Question:** The talk page of an en.wikipedia article reveals
  which WikiProjects claim it. For the article "Climate change" on
  en.wikipedia, how many WikiProject-shaped templates does the
  appropriate read-only tool return when filtered to wikiprojects?
  Answer with a single integer (count exactly what the tool returns,
  including any utility wrappers it surfaces).
- **Expected:** `14`
- **Actual:** `14` ✅
- **Tools used (2):** ToolSearch →
  `get_article_templates(title="Climate change", filter="wikiproject")`
- **Duration:** 20.1s | **Tokens:** 27,080

**Feedback:** Docstring "explicitly calls out that
`filter='wikiproject'` queries the Talk page (an easy pitfall
otherwise)." Returning both `count` (post-filter) and `raw_count`
(pre-filter) "is helpful for sanity checking." Two refinement
suggestions: (a) generic `note` field mixes navbox + wikiproject
guidance — make it filter-specific. (b) Docstring should mention
that `filter='wikiproject'` includes utility wrappers like
`WikiProject banner shell`, since callers iterating to call
`check_wikiproject` would want to skip those.

### Q7 — Carbon footprint See also count — ✅ PASS

- **Question:** The "See also" section of an en.wikipedia article
  lists editor-curated related articles. For the article "Carbon
  footprint" on en.wikipedia, how many entries does its "See also"
  section contain? Use a read-only tool that fetches see-also
  content without modifying topic state. Answer with a single
  integer.
- **Expected:** `10`
- **Actual:** `10` ✅
- **Tools used (2):** ToolSearch →
  `get_article_see_also(title="Carbon footprint")`
- **Duration:** 23.7s | **Tokens:** 26,797

**Feedback:** Comparative framing in docstring ("contrasted with
`get_article_links`, `morelike:`") "is genuinely helpful for an
agent picking among similar tools." Dedicated `count` field +
`section_present` distinguishing "no section" from "empty section"
is "a thoughtfully designed return shape." Same `auth_token`-not-
in-docstring concern as Q6.

---

## Backlog candidates from this run

Tier-1-eligible (cross-cutting, ≥2-agent evidence):

1. **`wikidata_get_entity` should optionally suppress sitelinks.**
   Add `include_sitelinks: bool = True` parameter (or auto-suppress
   when `properties` is a non-empty short filter). Q1 and Q3 evidence;
   sitelinks blob dominated payload for narrow lookups.

2. **Surface Wikidata time precision.** When returning P569/P571/etc.
   values, include a `precision` field (year/month/day) so callers
   don't have to infer from `00-00` substrings. Q1 and Q3 evidence.

3. **`auth_token` docstring note.** One-liner per tool: "not required
   for read-only calls." Q6 and Q7 evidence; cheapest possible fix.

Tier-2-or-deferred (single-agent, lower-impact):

4. `wikidata_query` aggregate-returns-strings docstring note.
5. `get_article_templates` filter-specific `note` field.
6. `wikidata_search_entity` docstring generalization for ad-hoc
   (non-topic-building) use cases.
7. `preview_wikiproject` auto-suggests `find_wikiprojects` on
   `found_in_bot_index=false`.
