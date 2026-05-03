# Server audit via mcp-builder skill

Plan for a focused audit pass against `mcp_server/server.py` using
Anthropic's `mcp-builder` skill (installed at
`~/.claude/skills/mcp-builder/`). To be run in a fresh `claude` session
where `/mcp-builder` is available — skills load at session start, so
this can't be done in the session that installed the skill.

## Why

The 2026-05-02 5-cell agent matrix surfaced concrete tool-friction
patterns (auth_token bug — fixed; large Wikidata response overflow;
`Climate change in [country]` redirect drift; cross-language sweep
gap; etc.). Those are *symptoms* the dogfood loop catches. The skill
brings a *systematic checklist* — naming, annotations, Pydantic, async,
pagination, response-format, resources — that lets us look for issues
that haven't surfaced in dogfood yet but would matter as the surface
grows. Goal: cross-reference the two so we land on a defensible Tier-1
backlog rather than reacting purely to whatever the last session
surfaced.

## Reference materials in the skill

- `~/.claude/skills/mcp-builder/SKILL.md` — top-level workflow (4 phases)
- `~/.claude/skills/mcp-builder/reference/python_mcp_server.md` —
  FastMCP-specific guide + Quality Checklist (load this first)
- `~/.claude/skills/mcp-builder/reference/mcp_best_practices.md` —
  universal MCP guidelines (naming, response format, transport)
- `~/.claude/skills/mcp-builder/reference/evaluation.md` — eval guide
- `~/.claude/skills/mcp-builder/scripts/evaluation.py` — automated
  eval harness; takes XML qa_pair file, drives an LLM through MCP, and
  collects per-question `<feedback>` on tool quality

## Tier 1 — Skill-driven audit (must-do)

### 1.1 Walk the Python checklist against server.py

**Shape:** open server.py side-by-side with `python_mcp_server.md`'s
Quality Checklist. For each line item, mark ✅ / ⚠ / ❌ with
rationale. Output: a table in this doc with verdicts.

**Why:** the matrix run already validated that some of our patterns
are good (docstrings, ctx injection) and some are gaps (`auth_token`
parameter coverage). We don't know which other checklist items have
hidden gaps until we look item-by-item.

**Expected gaps** (drafted ahead from a quick read of the checklist):

- ❌ Most tools use bare `@mcp.tool()` rather than `@mcp.tool(name=...,
  annotations={readOnlyHint, destructiveHint, idempotentHint,
  openWorldHint})`. Annotations help client UIs distinguish reads vs
  mutations and would have made the auth_token bug less surprising
  (clients could route writes through auth more deliberately).
- ❌ Server name is `topic-builder`, not the skill's recommended
  `wikipedia_topic_builder_mcp` (`{service}_mcp` convention). Renaming
  would break every existing MCP-client config — likely
  document-the-divergence rather than apply.
- ⚠ No Pydantic input models. Our docstrings carry the type
  information instead. The skill argues Pydantic catches bad input at
  the framework boundary, not via tool-body branching.
- ⚠ Sync tools throughout. Async migration is a known backlog item
  (cooperative-yielding fix referenced in dogfood/README.md re:
  parallel-runs-share-event-loop). Audit confirms it's a real gap;
  doesn't change the priority.
- ⚠ No `response_format` enum (markdown vs JSON). Our tools return
  json.dumps strings. The skill recommends supporting both.
- ❌ `@mcp.resource()` not used. Candidates: rubrics, exemplar
  bodies, scope statements (currently fetched via tools).

**Open questions:**

- Annotations: most useful flag for us is `readOnlyHint`. Does adding
  it retroactively to ~40 read tools have client-visible side effects
  (cached schemas, etc.) that would matter for ChatGPT?
- Tool prefix: skill recommends `topic_builder_start_topic` etc. for
  cross-server disambiguation. We don't share a workspace with other
  servers in production, so the value is low — but the skill flags
  this as a discoverability win for agents. Worth measuring? Probably
  no — the brief already names every tool.
- Pydantic: real benefit is input validation and auto-doc. Our manual
  validation is scattered (e.g., `wiki` codes, score ranges). Could
  pilot on one tool and decide.

### 1.2 Cross-reference matrix-run findings

**Shape:** a table mapping matrix-surfaced friction → skill checklist
items. Output goes in this doc.

| Matrix finding | Skill checklist coverage | Verdict |
|---|---|---|
| auth_token bug on 18 tools | "Parameter coverage" indirect | bundled with this audit's commit (server.py: 18 read tools gain `auth_token: str | None = None` so stateless clients can pass it on every call). Predates the audit; would have been a separate item anyway. |
| Wikidata P101/P106 response overflow | "Pagination is properly implemented" | v1 mitigation already shipped — `wikidata_entities_by_property` auto-trims `label`/`description` above 40kb soft limit (`_WIKIDATA_RESPONSE_SOFT_LIMIT`, server.py ~4239). **Refinement found during 2.1 eval-authoring 2026-05-03:** the soft limit checks compact-JSON byte count, but the response is returned indented (`json.dumps(..., indent=2)`) — for a 426-row Cattleya P171 query, compact-trimmed = 35kb but indented wire size = 61kb (76% larger), still overflowing client buffers. Either lower the soft limit (~22kb compact ≈ 40kb indented), or measure indented size for the threshold check. Small surgical fix; file as backlog item. True pagination/streaming remains the v2. |
| `Climate change in [country]` redirect → Geography | not skill-coverable (domain-level) | domain backlog, not server-audit |
| Cross-language sweep tool gap | not skill-coverable | domain backlog |
| Codex skips note= annotations | "Error messages are actionable" — adjacent | server_instructions.md tweak, not server.py |
| List_page:List of climate scientists noise | not skill-coverable | benchmarks audit.py rule (already added) |

The matrix-run already points at which items are server-audit-shaped
vs domain-layer. The skill checklist can validate the server-audit
items but doesn't help with domain.

### 1.3 Findings

| Item | Verdict | Notes |
|---|---|---|
| 1.1.a — Tool annotations | Applied | 71 tools bucketed via 4 module-level `ToolAnnotations` constants (`READ_ONLY` 37, `WRITE_ADDITIVE` 25, `WRITE_IDEMPOTENT` 3, `WRITE_DESTRUCTIVE` 6). Borderline calls reviewed with Sage: `reject_articles`/`resolve_redirects`/`export_csv`/`publish_topic` → ADDITIVE, `filter_articles` → DESTRUCTIVE. |
| 1.1.b — Server name (`_mcp` suffix) | Documented divergence — won't change | Skill recommends `{service}_mcp`. Current registered name is `"Wikipedia Topic Builder"` (display only). Renaming wouldn't break clients (URL, not name, is the wire identifier) but the convention is for cross-server disambiguation in agent workspaces — we don't share a workspace with peer MCP servers in production. The substantive part of this convention (per-tool `topic_builder_` prefix) is already deferred under "Out of scope." |
| 1.1.c — Pydantic input models | Pilot, then decide | 71-tool en-masse rollout rejected. Pilot 2–3 tools where input shape is underspecified today: `petscan` (free-form `params: dict`), `set_topic_rubric` (`topic_profile: dict` has a documented schema but no enforcement), `set_scores` (dict-of-dicts shape). Pilot proves the win on richer client-side errors / removed tool-body validation. If clean, expand selectively (not en masse). If churn outweighs, document divergence. Tracked as a separate backlog item; pilot itself is not part of this audit's acceptance criteria. |
| 1.1.d — Sync vs async | No new item — existing backlog covers it | `docs/backlog/README.md` line 230 ("Cooperative async yielding in heavy tools") already has the dogfood evidence (multi-worker shipped 2026-04-25 absorbs cross-IP concurrency; same-IP still serializes). Skill flag confirms the gap but doesn't change priority — the existing item's sequencing note ("promote when we see this limit hurt a real workflow") still holds. No audit action. |
| 1.1.e — `response_format` enum (markdown vs JSON) | Documented divergence — won't change | Skill recommends supporting both markdown and JSON per call. Our 71 tools all return JSON-as-string by deliberate design (codified in CLAUDE.md "Required patterns"). The skill's recommendation suits agents whose primary output is user-facing prose; ours is whose primary output feeds the next tool call. JSON is what Claude consumes natively, and the four tools whose output the AI synthesizes for users (`audit_progress`, `topic_diff`, `describe_topic`, `get_status`) get markdown formatting at the AI's response layer anyway. Per-tool dual rendering would be 71 ongoing template-maintenance items for unclear payoff. |
| 1.1.f — `@mcp.resource()` not used | Defer — exemplars are a clean fit but cost-vs-payoff doesn't justify now | Three candidates considered: (1) **Exemplars** — `list_exemplars` / `get_exemplar` serve static markdown from `dogfood/exemplars/`, perfect resource shape (`exemplar://{slug}`); deferred because tool surface works and migration means deprecation churn. Filed to backlog. (2) **Rubrics / scope statements** — topic-state, not static reference; stay as tools. (3) **Strategy substrate** (`server_instructions.md` + `shape_axes.md` + `strategy_moves.md` + `failure_modes.md`) — interesting because of upfront-token cost, but the substrate is *push-shaped* by design (AI internalizes at session start, doesn't pull on demand); switching to resources is an architectural regression for our AI ergonomics. |
| 2.1 — Author eval qa_pairs | Authored 7 questions | `benchmarks/topic-builder-evals.xml`: 4 Wikidata-stable (Greta Thunberg P569, Paris Agreement QID disambiguation, IPCC P571 inception year, Cattleya P171 SPARQL count), 3 Wikipedia-drift-acceptable (WP Climate change vs WP Environment comparison, get_article_templates wikiproject filter on "Climate change", get_article_see_also on "Carbon footprint"). Each answer verified via live MCP tools 2026-05-03. Drift questions noted in inline XML comment — drift over months is acceptable per plan's "±5% over a year is fine" stance. |
| 2.2 — Run eval harness | Run via 7 parallel `Agent` subagents (no API key needed) | Skill's `evaluation.py` requires `ANTHROPIC_API_KEY` because it uses the SDK directly. Routed around by spawning 7 fresh general-purpose Sonnet subagents in parallel, each given the harness's `EVALUATION_PROMPT` + one qa_pair — same shape as `agent_matrix.sh` uses with `claude -p`, no per-API-call billing. **Result: 7/7 (100%) pass; 17 total tool calls; ~24s avg per question.** Report at `benchmarks/topic-builder-evals-report-2026-05-03.md`. 100% pass means our questions are within the recon cluster's competence — first pass, expected. Cross-cutting feedback themes (≥2-agent evidence): (1) `wikidata_get_entity` returns full sitelinks blob even for narrow `properties` filter, (2) Wikidata time literals returned raw (precision not surfaced), (3) `auth_token` parameter visible in schema but undocumented in tool docstrings. All three filed below. |

## Tier 2 — Evaluation harness (yes-do, after Tier 1)

### 2.1 Author 5–10 evaluation questions

**Shape:** create
`benchmarks/topic-builder-evals.xml` with `<qa_pair>` elements per the
skill's evaluation.md. Each question should require multiple
read-only tool calls and have a verifiable answer.

**Why:** the matrix-run scoring tests a *full topic build*. The
skill's eval tests *short focused questions* — different signal.
Per-question `<feedback>` block from the LLM is concentrated tool
critique that's hard to extract from a long benchmark run.

**Candidate questions** (read-only, verifiable):

- "How many distinct WikiProjects claim the article 'Greta
  Thunberg'?" (uses `get_article_templates(filter='wikiproject')`)
- "What's the Wikidata QID for the Paris Agreement, and how many
  parties (P710) does it list?" (uses `wikidata_search_entity` →
  `wikidata_get_entity`)
- "Find the canonical title for the article currently at 'Climate
  change in Slovenia' on en.wikipedia." (uses `resolve_redirects` —
  expected answer "Geography of Slovenia", testing whether agent notices
  the drift)
- "How many articles are in `Category:Climate fiction novels` at
  depth 0?" (uses `get_category_articles` and length check)
- "What's the article count for WikiProject Climate change versus
  WikiProject Environment?" (uses `preview_wikiproject` × 2)

**Open questions:**

- These all hit the same 6–8 tools. Should we deliberately spread
  questions across the full ~66-tool surface, or is "depth on the
  most-used tools" more useful? Probably the latter — friction on
  high-traffic tools matters more.
- Stable-answer constraint: the article-count answers will drift over
  time as Wikipedia changes. Acceptable? Skill says "Stable: Answer
  won't change over time" — strict reading would exclude these.
  Practical reading: ±5% drift over a year is fine for a tool-quality
  benchmark.

### 2.2 Run the eval harness

**Shape:** run `evaluation.py` against the deployed server.

```bash
export ANTHROPIC_API_KEY=...
export TB_AUTH_TOKEN=tb_...
python ~/.claude/skills/mcp-builder/scripts/evaluation.py \
    -t http \
    -u https://topic-builder.wikiedu.org/mcp \
    -H "Authorization: Bearer $TB_AUTH_TOKEN" \
    -m claude-sonnet-4-6 \
    -o /tmp/tb_eval_report.md \
    benchmarks/topic-builder-evals.xml
```

**Why:** captures whether the right tool surface exists, in
agent-judgment terms.

**Open questions:**

- Default model in `evaluation.py` is `claude-3-7-sonnet-20250219` —
  override to `claude-sonnet-4-6` (or 4-7) so we're testing against
  current-gen.
- The harness expects an `ANTHROPIC_API_KEY` env var. Setup-only
  cost, but worth flagging.

## Tier 3 (deferred) — apply findings

Standard build-workflow.md flow: things the skill audit and matrix
run BOTH flag → Tier 1; skill flags but matrix didn't surface →
Tier 2 (worth measuring before applying); skill flags but conflicts
with documented design choice (sync, no Pydantic) → document the
divergence in CLAUDE.md and don't change. Don't refactor en masse —
land changes incrementally with a benchmark gate verdict for each.

## Out of scope for this audit

- Async migration (separate backlog item, evidence already established
  via dogfood/README.md "parallel runs share one worker")
- Tool renaming with `topic_builder_` prefix (every client would need
  to update; the discoverability win is small for our deployment)
- Wholesale Pydantic adoption (large refactor; pilot one tool first)
- Anything about the AI-facing strategy substrate
  (`server_instructions.md`, `shape_axes.md`, etc.) — the skill is
  about server quality, not agent guidance

## Acceptance criteria

This audit is "done" when:

1. The Tier-1 checklist table is filled out in this doc with
   verdicts.
2. The matrix → skill cross-reference table is filled out.
3. At least 5 evaluation questions are authored and run; the report
   is saved to `benchmarks/topic-builder-evals-report-<date>.md`.
4. New backlog entries (or amendments to existing ones) are filed in
   `docs/backlog/README.md`, each citing the audit finding and the
   matrix evidence (where applicable).
5. This file gets a "shipped: <date>" header at the top and the
   audit findings are summarized into `docs/shipped.md`.
