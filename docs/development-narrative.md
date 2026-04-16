# Wikipedia Topic Builder: Development Narrative

## Project Origins (April 16, 2026)

The Wikipedia Topic Builder was conceived and built in a single intensive session between Sage (Wiki Education Foundation) and Claude (Anthropic's Claude Opus, via Claude Code CLI). The goal: create an AI-driven system that can identify all Wikipedia articles belonging to an arbitrary topic, producing a CSV article list for input to Wiki Education's [Impact Visualizer](https://github.com/WikiEducationFoundation/impact-visualizer).

The core problem is that building comprehensive topic article lists has historically been manual and constrained by what's practical to compile by hand. Existing topic lists on Wikipedia reflect what was feasible, not what the topic actually encompasses. Sage wanted a system where the user — who doesn't need to know anything about how Wikipedia organizes content — can describe a topic in conversation with an AI that does the heavy lifting of exploring Wikipedia's content structures.

## Phase 1: Planning

Sage framed the initial vision: a chat-driven system where the user guides how narrowly or expansively to define a topic, while the AI executes exploration strategies. The end goal was identified early — not a CLI tool, but a **Claude skill** that anyone could load on claude.ai to do a guided topic-building session and download a CSV.

Claude drafted an architecture plan covering:
- Python scripts for structured Wikipedia API queries (category tree traversal, WikiProject article fetching, CirrusSearch, list page harvesting, navbox parsing)
- A CLAUDE.md encoding the workflow and domain knowledge
- A phased approach: build locally first to learn what works, then package as a skill

The plan identified the key Wikipedia content structures to leverage: categories, WikiProjects, navigation templates, "List of..." / "Index of..." pages, and CirrusSearch operators.

## Phase 2: Exploratory Build — Climate Change

Sage chose "climate change" as the test topic, requesting an expansive build. This became the primary learning vehicle for the entire project.

### Strategy Development

Claude built the foundational scripts (`config.py`, `category_tree.py`, `article_filter.py`) and began reconnaissance. The category tree survey at depth 2 revealed 45 subcategories, which Sage and Claude walked through together to establish scope. This conversation surfaced several key design principles that Sage articulated:

**Categories are a starting point, not the answer.** Sage emphasized that Wikipedia's categorization is uneven and incomplete. Categories help map the user's mental model of the topic against Wikipedia's structure, but they can't be trusted as a definitive inclusion/exclusion mechanism.

**The LLM is the quality gate.** Sage proposed that tools should generate candidates broadly, then the LLM should judge relevance — first by title (for obvious cases), then by reading article extracts (for ambiguous cases), then by browsing from edge articles (to find what was missed entirely).

**Scoring, not binary classification.** When Claude initially triaged Methane-branch articles into include/exclude/investigate buckets, Sage pushed for a more nuanced approach: a 1-10 relevance score that captures the LLM's confidence. This turned "how broadly to define the topic" into a threshold setting rather than a series of binary calls. An article scoring 7 would be included in an expansive build but excluded from a narrow one.

### The Methane Deep Dive

The Methane category branch became the project's first detailed case study. At depth 2, it contained 323 articles ranging from "Arctic methane emissions" (clearly in-scope) to "SpaceX Raptor" (a methane-fueled rocket engine, clearly not) to "Gas hydrate stability zone" (ambiguous — relevant if you know about methane clathrate climate feedbacks, but not obvious from the title).

Claude scored all 323 articles on the 1-10 scale, and Sage validated the scoring approach. This established the three-tier triage:
- **9-10**: Auto-include (article is directly about climate change)
- **7-8**: Include for expansive builds (strongly connected via mechanisms/policy/impacts)
- **4-6**: Investigate further (fetch article extract, read context)
- **1-3**: Auto-exclude

When Sage questioned why "Gas hydrate stability zone" was rated as clearly in-scope, Claude had been applying background knowledge about methane clathrate feedbacks rather than judging from the title alone. Sage's response: applying background knowledge is fine, but the scoring should reflect confidence level, not just a binary call. This became a core design principle.

### Multi-Strategy Comparison

Claude ran three strategies in parallel:
- **Category tree (depth 4)**: 6,806 articles
- **WikiProject Climate change**: 4,450 articles
- **List page harvesting** (17 curated pages): 4,329 articles

The overlap analysis:

| Overlap | Count |
|---------|-------|
| All 3 strategies | 498 |
| 2 strategies | 2,027 |
| 1 strategy only | 10,037 |

WikiProject was the highest-quality single source — human-curated, and it included articles no other strategy found (specific weather events, climate scientists, organizations). Category tree had the broadest coverage but drifted at depth 3-4 (petroleum geology, natural gas industry, Titan moon geography). List harvesting was the noisiest — even filtered to genuine index pages, it pulled in thousands of irrelevant links from context.

### Resolving 10,000 Unknowns

The 10,037 single-strategy articles needed individual assessment. Keyword-based heuristic scoring caught obvious matches but left 7,000+ articles as "unknown" (no keyword match in the title). The more effective approach turned out to be **extract-based scoring**: fetching the first 5 sentences of each article from Wikipedia and scoring based on actual content. This resolved 3,539 ambiguous category-only articles — a climate activist's article intro mentions "climate," a car article doesn't.

For the remaining borderline cases (score 5-6), Sage and Claude made batch decisions by grouping articles by type: mitigation technologies (include for an expansive build), soft drinks with "carbonated" in the extract (exclude — false positive from "carbon" matching), renewable energy articles (include).

### Edge Browsing

After establishing a base of ~5,000 high-confidence articles, Claude used **edge browsing** — fetching outgoing links from confirmed topic articles and finding articles linked by many of them but not yet in the list. This discovered articles like "School Strike for Climate" (linked by 95 seed articles but missed by all structured strategies), "Net zero emissions," "Instrumental temperature record," and the entire "deforestation by country" cluster.

Sage pointed out that edge browsing from **peripheral** articles (at the edges of the topic) is more productive than browsing from core articles, because core articles mostly link to things already in the list.

CirrusSearch's `morelike:` operator — which finds articles with similar content to a given article — turned up thematic clusters (deforestation by country, energy by country) that represented systematic gaps in category-based coverage.

### Final Result

The expansive climate change build produced **5,349 articles** after filtering (redirect resolution, disambiguation page removal, list page removal, missing page removal).

## Phase 3: Strategy Assessment

Based on the climate change build, Sage and Claude assessed each strategy:

**Most effective:**
1. WikiProject tagging — best quality, human-curated
2. Extract-based content scoring — the breakthrough for resolving ambiguous articles
3. Edge browsing from subtopic periphery — found important articles all structured strategies missed
4. `morelike:` CirrusSearch — small yield but uniquely valuable for finding thematic clusters

**Less effective:**
1. List page harvesting — very noisy signal-to-noise ratio
2. Title-only keyword heuristics — too many false negatives
3. Deep category tree crawling (depth 4+) — too much drift
4. Batch LLM scoring via sub-agents — failed due to tool permissions; local scripts were more reliable

## Phase 4: Skill Design and MCP Server

### Platform Research

Research into claude.ai's capabilities revealed hard constraints:
- ~10-20 tool calls per turn (user must click "Continue" for more)
- Each web fetch consumes ~10-15K tokens of context
- 50-100 API calls would overflow the context window

This ruled out having Claude on the web make Wikipedia API calls directly. The solution: an **MCP (Model Context Protocol) server** that wraps the Wikipedia exploration tools. Claude on the web connects to the MCP server as an integration, gets structured results back, and stays in its role as the intelligence/judgment layer.

### MCP Server Development

Claude built a Python MCP server using Anthropic's `mcp` SDK, packaging each exploration strategy as a tool:

- **Reconnaissance**: `survey_categories`, `check_wikiproject`, `find_list_pages`
- **Gathering**: `get_wikiproject_articles`, `get_category_articles`, `harvest_list_page`, `search_articles`, `search_similar`
- **Scoring**: `score_by_extract`, `set_scores`, `score_all_unscored`, `auto_score_by_title`
- **Review**: `get_status`, `get_articles`, `get_articles_by_source`
- **Cleanup**: `remove_articles`, `remove_by_pattern`, `filter_articles`
- **Export**: `export_csv` (returns a download URL)

The server maintains per-topic state in SQLite, so topics survive server restarts and users can resume across sessions.

### Deployment

Sage provisioned a minimal Debian VPS ($5/month Linode, 1GB RAM). Claude set up the full stack remotely via SSH:
- Python venv + MCP SDK
- nginx reverse proxy
- Let's Encrypt HTTPS certificate
- systemd service
- The server lives at `https://topic-builder.wikiedu.org/mcp`

A deploy script (`mcp_server/deploy.sh`) syncs code from the repo to the server, so the deployed version is always traceable to a git commit.

### Landing Page

A landing page at `https://topic-builder.wikiedu.org/` provides setup instructions for three account types (individual, org admin, org member).

## Phase 5: First Real User Test

Sage tested the MCP server from claude.ai with a "woodblock prints and woodblock print artists" topic — different from climate change in important ways: no WikiProject existed, the topic crosses cultural boundaries (Japanese, European, Chinese traditions), and the main Wikipedia list pages mix woodblock artists with all other printmaking techniques.

The session produced a 686-article CSV covering major woodblock traditions (ukiyo-e, shin-hanga, Northern Renaissance, Die Brücke, Chinese Modern Woodcut Movement, and others). The process involved gathering ~1,500 candidates, then pruning heavily — the "List of printmakers" harvest was the main noise source, pulling in hundreds of etchers, engravers, and lithographers who never worked in woodblock.

### Issues Discovered

The test revealed several server-side problems:

1. **Scoring was the biggest bottleneck.** After pruning to 688 on-topic articles, Claude needed to score them all to export — but had to page through 100 at a time, copy titles, call `set_scores`, repeat. This burned 3+ "Continue" rounds on pure bookkeeping.

2. **`export_csv` required scoring.** Claude pruned to 688 articles, tried to export, got 0 results because nothing was scored. The default should export everything.

3. **Token budget pressure.** Tool responses returning full article lists consumed too much of Claude's per-turn output budget. Claude mentioned "token budget is getting tight" multiple times.

4. **Cleanup was tedious.** Manually paging through articles and building removal lists was slow.

### Fixes Implemented

Based on the test:
- Added `score_all_unscored` — one call to mark everything as scored after pruning
- Changed `export_csv` default to export all articles (min_score=0)
- Added `get_articles_by_source` — review articles from a specific noisy source
- Added `remove_by_pattern` — bulk remove by substring match with dry-run preview
- Made gathering tools return only counts (data is in the DB, not the response)
- Added `titles_only` mode for `get_articles`
- Changed CSV export to return a download URL instead of the full content

## Roles

**Sage** provided:
- The product vision and use case (Impact Visualizer input)
- Deep domain knowledge of Wikipedia's content organization, tools, and community patterns
- Key design principles (LLM as quality gate, scoring not binary, categories as starting point)
- Scope decisions during the climate change build (include mitigation tech, geographic variants, etc.)
- The end-goal framing (Claude web skill, not CLI tool)
- Infrastructure (Linode server, DNS, Cloudflare configuration)
- Real-world testing with the woodblock prints topic
- Feedback that drove iterative improvements

**Claude** provided:
- Architecture design and planning
- All code implementation (Python scripts, MCP server, deployment automation)
- Wikipedia API integration (category traversal, WikiProject queries, CirrusSearch, extract fetching)
- The multi-strategy + overlap analysis approach
- Relevance scoring at scale (title heuristics, extract-based content scoring)
- Edge browsing implementation
- Server deployment and HTTPS setup
- Transcript analysis and server-side fixes

The division of labor was straightforward: Sage directed the product and design decisions, Claude wrote the code. Several of the system's design principles emerged from Sage correcting Claude's initial approaches — binary scoring became a 1-10 scale, category-centric collection became multi-strategy, and core-focused edge browsing was redirected to the periphery.

## What's Next

- Refine the skill prompt (system instructions for Claude on the web) based on continued testing
- Add Wikipedia OAuth for user authentication
- Test with more diverse topics to validate the workflow generalizes
- Consider whether PetScan integration would reduce the number of API calls needed
- Explore whether the tool descriptions alone are sufficient guidance, or whether a Project-level system prompt is needed to get the best conversational behavior
