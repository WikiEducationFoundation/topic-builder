# Adding exemplars (and optionally, benchmark topics)

Exemplars are the highest-leverage thing to grow right now. They give
arbitrary future runs a shape-matched worked example to anchor on,
and they surface the strategy gaps that the existing five exemplars
don't cover. Benchmarks measure tool changes against frozen gold;
exemplars seed strategy for topics that don't have measurement
infrastructure. The two are coupled in practice (a topic with both
gives the cleanest signal) but separable in principle — you can
ship an exemplar without ever building a benchmark.

This doc covers both, with exemplar authoring as the lighter primary
path.

## TL;DR — three paths

| Goal | Path | What you write |
|---|---|---|
| Give future runs a worked example for a topic shape we don't have | **Exemplar only** | `dogfood/exemplars/<slug>.md` + DB seed |
| Above + a brief an AI can fetch and execute | **Exemplar + dogfood task** | + `dogfood/tasks/<slug>-thin.md` + DB seed |
| Above + audited measurement against frozen gold | **Full benchmark + brief + exemplar** | + `benchmarks/<slug>/{scope,rubric,README,baseline,audit.py,gold.csv,...}` |

The existing five suite members all picked path 3. Most future
additions probably belong on path 1 or 2 — committing to a frozen
audited gold is real maintenance overhead, and shape coverage is the
main thing we're short on.

## What shapes do we cover today

| Shape | Exemplar | Notable |
|---|---|---|
| Very large taxonomic + cultural tail | orchids | Source-trust on topic-named category; cross-wiki periphery sweep. |
| Named historical event with concentric reach | apollo-11 | Mission → program → agencies → people layers; navbox harvest is high-leverage. |
| Scientific discipline with distinctive vocabulary | crispr-gene-editing | Vocabulary-led search; named-tool extension chains. |
| Intersectional demographic × discipline (US) | african-american-stem, hispanic-latino-stem-us | Wikidata occupation + ethnicity intersection; biographies dominate. |
| Well-organized academic field + movement + policy | climate-change | WikiProject + dense category + named institutions; multi-strategy triangulation. |

That's effectively four distinct shapes (the two intersectional
exemplars share most strategy). The diversity isn't in the wrong
direction — these were picked to span the existing user-driven
benchmark portfolio — but it under-covers most of the topic-shape
space.

## Shapes we don't cover (illustrative gaps)

The point of authoring a new exemplar is usually to fill one of
these. Each entry pairs the shape with the failure mode the existing
exemplars don't anticipate:

- **Eponymous individual + their work / influence.** "Albert
  Einstein," "Marie Curie," "Frida Kahlo." Reach lives in the
  person's bibliography, named-after-them concepts (Einstein
  cross-section, Curie temperature), institutions named after them,
  cultural depictions. The orchids cross-wiki strategy partly
  applies; the named-after dimension is novel.
- **Cultural / artistic movement.** "Surrealism," "Bauhaus," "Hip
  hop," "New Hollywood." Reach is a stitched cluster: founding
  works, key practitioners, canonical institutions, derivative
  movements, regional offshoots. WikiProject coverage is uneven;
  named-practitioner identification is the lever.
- **Specific war / single conflict.** "World War II," "Vietnam
  War," "US Civil War." Reach is concentric like apollo-11 but
  vastly larger — battles, theaters, equipment, leaders, treaties,
  domestic-front articles, postwar reckonings. The apollo-11
  navbox-harvest lesson scales but the concentric depth is harder.
- **Specific disease / medical condition.** "Tuberculosis,"
  "HIV/AIDS," "Type 2 diabetes." Reach: pathogen / mechanism, named
  treatments, key researchers, epidemiology, public-health
  responses, cultural / historical impact. Vocabulary-led like
  CRISPR but with a strong historical / public-health periphery.
- **Specific language / language family.** "Spanish language,"
  "Tamil language," "Indo-European languages." Reach: dialects,
  literature, linguistics-of, named speakers, regional variants,
  geography of speakers. Heavy non-Anglosphere depth; cross-wiki
  is dominant.
- **Award / canonical honor.** "Nobel Prize in Physics," "Pulitzer
  Prize for Fiction," "Academy Award for Best Picture." Reach: each
  individual recipient, the awarding body, ceremony history,
  controversies, derivative awards. Strongly enumerative — every
  recipient article exists.
- **Industry / profession.** "Aviation industry," "Pharmaceutical
  industry," "Banking." Reach: companies, regulators, key figures,
  technology, history-by-decade, regional variants. Risks heavy
  drift into general business; needs tight mitigation-tech
  scope discipline like climate-change.
- **Sport / league / specific team.** "Association football,"
  "National Basketball Association," "Manchester United F.C." Reach:
  rules, history, players, coaches, stadiums, derivative leagues,
  rivalries. Biography-heavy at scale; per-season-per-team
  combinatorics.
- **Religious tradition / sect.** "Buddhism," "Sufism,"
  "Reformation." Reach: doctrine, practices, key figures,
  historical periods, regional variants, sects, sacred texts.
  Strong cross-wiki / non-Anglosphere component.
- **Fictional universe / franchise.** "Marvel Cinematic Universe,"
  "Tolkien's legendarium," "Pokémon." Reach: each work, characters,
  creators, derivative media, fan culture. Risks "in popular
  culture" bloat.
- **Geographic region with deep multi-axis content.** "Antarctica,"
  "The Sahara," "Yellowstone." Reach: physical geography, ecology,
  specific features, history of exploration, governance, cultural
  representation. Easily confused with "Climate of [Region]" or
  "Geography of [Country]" generic articles.

This list is illustrative, not a backlog. Pick from it (or beyond
it) when you have a topic in mind that's underserved by the
existing five.

## Why exemplars are higher-leverage than benchmarks right now

- **Exemplars compound across topic builds.** A new exemplar makes
  every future build of a similar-shape topic better. A new
  benchmark only measures tool changes against that one topic.
- **Authoring is cheaper.** A solid exemplar is one Markdown file +
  a seed run. A benchmark is the same file plus scope + rubric +
  audited gold + classifier + per-cycle ratchet runs.
- **Strategy gaps get visible.** Authoring an exemplar for a shape
  we haven't done forces noticing what tool moves we'd want and
  don't have. That feeds the backlog more directly than another
  benchmark covering an already-explored shape.
- **No measurement-trend invalidation.** Exemplars don't have a
  frozen baseline; you can iterate on them without invalidating
  ratchet trend lines.

The ratchet's purpose is proving that tool changes ratchet quality
upward. The exemplar set's purpose is teaching the AI what good
moves look like for arbitrary topic shapes. Conflating the two has
been the historical pattern (every benchmark gets an exemplar) and
that's fine for the existing set; future additions don't need to
stay coupled.

## Path A: shape-only exemplar

The lightest contribution. Useful when:

- You have a topic shape that none of the five existing exemplars
  cover.
- You either built a sample topic recently OR have enough Wikipedia
  knowledge of that shape to write the case study honestly.
- You don't want to commit to maintaining audited gold or a frozen
  measurement reference.

### Steps

1. **Pick a slug.** Convention: `lowercase-with-hyphens`. The slug
   doesn't have to match an existing benchmark — `slug:
   surrealism` or `slug: nobel-prize-in-physics` is fine for
   shape-only exemplars.

2. **Write `dogfood/exemplars/<slug>.md`.** Format:

   ```markdown
   ---
   slug: <slug>
   title: <Topic Title>
   shape: <one-line shape descriptor>
   last_validated_against: <YYYY-MM-DD>
   ---

   # Menu card

   **Shape axes**
   - structural: ...
   - scale: <order-of-magnitude bucket>
   - layered_shape: ...
   - non-Anglosphere depth: ...
   - biography density: ...
   - canonical category coverage: ...
   - recall_ceiling_driver: ...

   **Doesn't apply when:** ...

   **Shape (prose).** ...

   **Summary.** ...

   **High-leverage moves**: ...

   # Full case study

   [tool sequence + lessons; can be deferred to a stub initially]
   ```

   `dogfood/exemplars/orchids.md` is the longest, most worked-
   through template. The other four are stubs (menu card only).

3. **Seed it:**

   ```
   bash scripts/scp_exemplars.sh
   bash scripts/smoke.sh scripts/seed_dogfood_exemplars.py
   ```

4. **Verify** by calling `list_exemplars` from any MCP client — the
   new entry should appear in the menu.

### Honest grounding

If the exemplar is grounded in a specific run, name the run in the
case study and pull real metrics. If it's authored without a real
run, mark it explicitly:

```markdown
> **Stub status (YYYY-MM-DD):** drafted from prior knowledge for
> schema pressure-testing. Numbers and specific moves need
> verification against a real build before this exemplar is
> treated as authoritative.
```

The four current stub exemplars use this convention. Stub
exemplars are still useful — the menu card teaches shape-matching
even when the case study isn't fleshed out yet. A future build can
upgrade the stub by replacing it with a real-run-grounded version.

## Path B: exemplar + dogfood task brief

If you want an AI to be able to fetch and execute the topic via
`fetch_task_brief`, add the brief.

### Additional steps (on top of path A)

5. **Write `dogfood/tasks/<slug>-thin.md`.** Format:

   ```markdown
   ---
   task_id: <slug>-thin
   variant: thin
   benchmark_slug: <slug>          # set even if no benchmark exists; the AI uses this for the own-slug exclusion gate
   run_topic_name_template: <slug>-thin {ts}
   ---

   # Benchmark run: <topic title>

   [scope statement + two-phase protocol]
   ```

   Don't invent a different protocol — copy `dogfood/tasks/orchids-thin.md`
   verbatim and edit the scope paragraph + run-topic name + the
   `get_exemplar(slug=...)` reference. The two-phase protocol is the
   measurement contract; consistency is what makes metrics
   comparable when a benchmark is later added.

6. **Seed:**

   ```
   bash scripts/scp_tasks.sh
   bash scripts/smoke.sh scripts/seed_dogfood_tasks.py
   ```

### What you don't get without a benchmark

- `benchmark_score.py` won't have a `gold.csv` to score against —
  precision / recall / reach metrics are unavailable.
- The brief's "submit_feedback → land in usage log" still works;
  the AI can run the task and reflect, you just can't measure
  corpus quality automatically.
- No ratchet eligibility.

If/when you later add a benchmark for this slug (path C), the brief
and exemplar already exist; you just author the benchmark scaffold.

## Path C: full benchmark scaffold + brief + exemplar

The full path. Necessary when:

- The topic is a Wiki-Education priority where measuring tool quality
  *on this specific topic* matters (e.g. a topic Wiki Education
  consistently builds for partners).
- The shape is well-represented enough by an existing exemplar that
  the additional value is in measurement, not in strategy seeding.

### Decision: does this benchmark join the regular ratchet runs?

The number of benchmarks the ratchet runs on isn't sacred. The 5
historical members were picked to span shapes AND to represent
Wiki-Education priorities; future additions follow the same
criteria. Adding a benchmark mid-cycle re-baselines the gate (the
new topic's first cycle becomes its own baseline); existing topics'
trend continuity is preserved.

The relevant question is: **do we want each ratchet cycle to spend
its API + tool-call budget measuring this topic?** Two factors:

- **Wiki-Education priority.** If this topic is one we ship to
  partners, measuring quality on it per cycle is worthwhile.
- **Shape-coverage value.** If the topic exposes a shape the
  existing benchmarks don't (e.g. cross-wiki-heavy, or
  enumerative-award-style), adding it grows the gate's coverage.

Either factor is sufficient. Neither factor and you have a path-A
or path-B contribution, not a benchmark.

### Additional steps (on top of paths A + B)

7. **Bootstrap baseline + gold:**

   ```
   bash scripts/smoke.sh scripts/bootstrap_benchmark.py "<exact topic name>"
   ```

   Pulls usage log + feedback log + DB state from the live topic.
   Output lands at `/tmp/benchmark-<slug>/{baseline.json,gold.csv}` on
   the host; retrieve to local.

8. **Lay out the scaffold:**

   ```
   mkdir -p benchmarks/<slug>/runs
   ```

   - **`benchmarks/<slug>/scope.md`** (committed) — frozen plain-language
     scope. Frozen-date stamp at top. Templates: `benchmarks/orchids/scope.md`
     for large topics, `benchmarks/apollo-11/scope.md` for concentric
     ones, `benchmarks/climate-change/scope.md` for well-organized
     academic ones.
   - **`benchmarks/<slug>/rubric.txt`** (committed) — three-tier
     CENTRAL / PERIPHERAL / OUT.
   - **`benchmarks/<slug>/README.md`** (committed) — origin, status
     table, ratchet-target gaps.
   - **`benchmarks/<slug>/baseline.json`** (committed) — the
     bootstrap output. For a fresh benchmark with no audited gold
     yet, null the gold-derived fields and set
     `gold_pending_audit_count` to the corpus size.
   - **`benchmarks/<slug>/gold.csv`** (gitignored) — the bootstrap
     output. Stays local; never committed.
   - **`benchmarks/<slug>/audit.py`** (gitignored — encodes named
     blocklists / allowlists) — keyword-rule classifier. Templates:
     `benchmarks/climate-change/audit.py` is the most heavily-
     commented; `benchmarks/orchids/audit.py` is the source-trust
     pattern; `benchmarks/apollo-11/audit.py` is the small-concentric
     pattern.
   - **`benchmarks/<slug>/audit_summary.md`** (gitignored — bucket
     samples include named individuals) — `audit.py` regenerates this
     every run.
   - **`benchmarks/<slug>/audit_notes.md`** (committed) — human
     commentary on classifier approach + edge cases. Curated, not
     overwritten by `audit.py`. Author at the class level (don't pair
     specific named individuals with classifier verdicts) — see the
     orchids exemplar for the right tone.
   - **`benchmarks/<slug>/runs/`** (gitignored — per-run scoreboards
     contain named reach / missed / OUT samples). The directory
     itself isn't tracked.

   File-status matrix:

   | File | Tracked? | Authored by |
   |---|---|---|
   | `scope.md` | ✓ | human |
   | `rubric.txt` | ✓ | human |
   | `README.md` | ✓ | human |
   | `baseline.json` | ✓ | bootstrap script |
   | `audit_notes.md` | ✓ (class-level; no named verdicts) | human |
   | `audit.py` | ✗ (named blocklists / allowlists) | human |
   | `audit_summary.md` | ✗ (named bucket samples) | `audit.py` regenerates |
   | `gold.csv` | ✗ (names + judgments) | bootstrap then `audit.py` |
   | `runs/` | ✗ (per-run named samples) | per-run scoring lands here |

9. **Run the audit:** `python3 benchmarks/<slug>/audit.py`. Iterate
   until the `uncertain` bucket is small (climate-change first pass
   landed at ~1.2%). Then write `audit_notes.md` with classifier
   approach + judgment calls + known limitations.

10. **Update the doc references** if the topic joins ratchet runs:
    `benchmarks/README.md` (member list), `docs/ratchet-plan.md`
    (named list near line 81 + the budget references), and
    `docs/shipped.md` (log the addition).

## Gotchas

- **Slug naming.** `lowercase-with-hyphens`. The brief's
  `benchmark_slug` frontmatter is what links a brief to its
  benchmark and drives the own-slug exclusion gate in
  `list_exemplars`. Slugs MUST match across exemplar / task /
  benchmark dir.
- **Frontmatter is YAML-lite.** Seed scripts parse `key: value`
  lines naively. No quoting / multi-line / lists unless the script
  handles them — copy from existing files.
- **`{ts}` is the only template placeholder.** Server's
  `fetch_task_brief` substitutes it once at call time on both the
  `run_topic_name_template` and the brief body. Other Python-style
  placeholders silently pass through unrendered.
- **Editing requires re-seeding.** `scp_*.sh` + the seed script.
  The MCP client may cache schemas — restart the session if a
  previously-fetched brief or exemplar looks stale.
- **`bootstrap_benchmark.py` requires the topic to already exist.**
  Build the topic via the MCP server first, then bootstrap. The
  script keys on the topic name in usage log / DB.
- **Ratchet runs use NEW topic names.** Never overwrite the
  canonical baseline topic. The brief's
  `run_topic_name_template: <slug>-thin {ts}` enforces this — the
  rendered name is always different from the canonical name.
- **`gold.csv`, `audit_summary.md`, `audit.py`, `runs/` are
  gitignored.** All four pair real names with on/off-topic judgments
  (audit.py via named blocklists / allowlists in classifier rules).
  `audit_notes.md` IS tracked but should be authored at the class
  level — describe patterns, not specific people.
- **Stub exemplars are fine but mark them.** A menu-card-only
  exemplar without a real-run case study can ship — orchids is the
  exception, not the rule. Use the `> **Stub status**` blockquote
  convention so a future contributor knows to upgrade it.

## Worked example: climate-change (2026-04-25)

Path C (full): exemplar pending, brief seeded, benchmark scaffolded.

```
benchmarks/climate-change/
├── scope.md            (committed)
├── rubric.txt          (committed)
├── README.md           (committed)
├── baseline.json       (committed; gold-derived fields null)
├── audit_notes.md      (committed; class-level commentary)
├── audit.py            (gitignored — named classifier rules)
├── audit_summary.md    (gitignored — bucket samples)
├── gold.csv            (gitignored — 6,562 rows)
└── runs/               (gitignored)

dogfood/tasks/climate-change-thin.md     (committed; seeded)
dogfood/exemplars/climate-change.md      (committed; seeded)
```

First-pass classifier: 1,770 IN / 4,276 PERIPHERAL / 435 OUT / 81
uncertain. Sample-precision audit pending. Decision on ratchet
inclusion deferred — climate-change adds a "well-organized academic
+ movement" shape we don't otherwise cover, but the per-cycle cost
is meaningful (~2,500 API calls at this corpus size).

## Pointers

- `benchmarks/README.md` — per-file purpose + the audit / scoring workflow.
- `dogfood/tasks/README.md` — task-brief authoring + format.
- `dogfood/README.md` — operator recipe for running a dogfood task.
- `docs/ratchet-plan.md` — gate semantics + cycle workflow (when a benchmark joins ratchet runs).
- `mcp_server/server_instructions.md` — what the AI reads at session start. The exemplar-consultation prep checklist lives here.
- `docs/backlog/exemplars-and-reach-pass.md` — the design doc behind
  Ship 1 + Ship 2; explains why the menu-card schema looks the way
  it does and what the own-slug exclusion gate is for.
