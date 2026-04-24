# Benchmarks

Regression tests for the Topic Builder tools. Each subdirectory is one
benchmark topic, thoroughly audited against a frozen scope. The goal: when
we change a tool or prompt, we can re-run a scripted session against the
benchmark topic and measure precision / recall / noise against a gold set,
so we know whether changes help or hurt.

## Why benchmarks

As the tool set grows and the AI-facing instructions evolve, small changes
can have uneven effects across topic classes. Benchmarks let us answer "did
this change improve things?" quantitatively instead of relying on
ad-hoc impressions from dogfood sessions.

## The five benchmarks

Four of the five follow the standard layout below:

- `apollo-11` — single historical event + cultural tail
- `crispr-gene-editing` — scientific discipline with distinctive vocabulary
- `african-american-stem` — intersectional biography
- `orchids` — taxonomy at scale + cross-wiki (the marquee completeness test)

The fifth, **`hispanic-latino-stem-us`**, is slightly nonstandard: it
was bootstrapped from a 2026-04-17 dogfood session audit and integrated
into the 5-benchmark suite later. It carries extra artifacts from that
original pass (`calls.jsonl`, `baseline.md`, review-queue state) that
the other four don't have. See its per-topic README for the full map.

## Per-topic layout (as of 2026-04-23)

```
benchmarks/<topic-slug>/
├── scope.md            — Plain-language scope, ambiguities resolved. Frozen.
├── rubric.txt          — Three-tier CENTRAL / PERIPHERAL / OUT rubric.
│                         Used by audit.py for classification.
├── gold.csv            — Authoritative article list with on_topic ∈
│                         {in, peripheral, out}. Rebuilt by audit.py;
│                         WebFetch / manual overlays applied via
│                         per-topic helper scripts.
├── baseline.json       — Arc-run metrics: tool_call_count, total_api_calls,
│                         wall_time_s, final_article_count, single_sourced
│                         %, ai_self_rating, precision/recall/reach vs.
│                         gold. A future run compares against this.
├── audit.py            — Frozen classifier that produces gold.csv's
│                         on_topic column. Reproducibly re-runnable if
│                         scope / rubric change.
├── audit_summary.md    — Classifier's auto-generated output. Regenerated
│                         whenever audit.py runs; don't hand-edit.
├── audit_notes.md      — Human-written commentary — judgment calls,
│                         edge cases, reach targets. Curated; NOT
│                         overwritten by audit.py.
├── README.md           — Per-topic notes: origin, status, ratchet targets.
└── (optional)
    ├── medicine_blocklist.txt            — AA STEM only: cross-referenced.
    ├── apply_webfetch_resolutions.py     — AA STEM only: overlays 20
    │                                       hand-verified classifications
    │                                       after audit.py runs.
    └── baseline.md, review_queue.json,   — hispanic-latino-stem-us only:
        gold-readable.csv, …                preserved from 2026-04-17 audit.
```

## Workflow

**Bootstrap a new benchmark topic:**

```
bash scripts/smoke.sh scripts/bootstrap_benchmark.py "<Topic Name>"
scp <from /tmp/benchmark-<slug>/> benchmarks/<slug>/
```

This produces `baseline.json` (arc-run metrics from usage.jsonl +
feedback.jsonl + live DB) and `gold.csv` (corpus snapshot with
`on_topic=pending_audit` on every row).

**Write scope.md + rubric.txt** by hand using the existing benchmarks
as templates. These are the frozen human decisions that the classifier
depends on.

**Write audit.py** — per-topic classifier. Five existing examples
(apollo-11, crispr-gene-editing, african-american-stem, orchids,
hispanic-latino-stem-us) demonstrate the range: enumerative, keyword-
rules, source-trust, blocklist cross-reference. Keep the classifier
rules aligned with scope.md.

**Run the audit:**

```
python3 benchmarks/<slug>/audit.py
```

This rewrites `gold.csv`'s `on_topic` column and regenerates
`audit_summary.md`. It does NOT touch `audit_notes.md` (human-written)
or `apply_webfetch_resolutions.py`-style overlay scripts.

**Apply overlays** (if any — e.g. AA STEM has 20 WebFetch-resolved
cases):

```
python3 benchmarks/african-american-stem/apply_webfetch_resolutions.py
```

## Running a ratchet comparison

```
python3 scripts/benchmark_score.py <slug> "<run-topic-name>"
```

Pulls the run topic's current corpus + usage-log entries from the
deployed server, reads `gold.csv` + `baseline.json` locally, emits a
scoreboard markdown report:

- Precision / recall / reach vs. gold
- Δ tool_call_count, Δ total_api_calls, Δ wall_time_s
- Pass/fail gate per the ratchet rules (precision + recall non-
  regressing + ≥1 cost metric improvement)

See `docs/ratchet-plan.md` for the full one-loop workflow.

## What does NOT go in version control

**Gold sets and audit artifacts contain real people's names paired with our
on/off-topic judgments and free-text justifications.** Both are
error-prone. Committing them to a public repo could mean publishing
defamatory or inaccurate claims about real people.

The repo's `.gitignore` excludes:

- `benchmarks/*/gold.csv`
- `benchmarks/*/audit*.csv`, `benchmarks/*/audit*.md`, `benchmarks/*/*.audit.*`
- `benchmarks/*/petscan_results*` (raw PetScan snapshots with names)

What DOES get committed for each topic:

- `scope.md` — scope rules, no names
- `README.md` — workflow, no names
- `calls.jsonl` — scripted tool calls (may reference category / WikiProject
  names, which are public; avoid including individual-person titles)
- `petscan.md` — the query URL + parameters + result count (but not the
  raw list of names)

Gold sets live on individual contributors' machines. If we ever need
shared storage, do it through a private mechanism — not this repo.

## Design notes

- **Fresh AI-driven builds, scored against frozen gold.** Each ratchet
  cycle starts a fresh AI-driven session for each of the 5 benchmark
  topics under a new topic name — the baseline topic is left
  untouched. The scoreboard measures the new run against the audited
  `gold.csv`. AI behaviour variance shows up in the results alongside
  tool changes; we accept that tradeoff for now because the AI-driven
  workflow is what we actually ship. A purely scripted replay harness
  is out of scope.

  Three kickoff paths exist; prefer (1) for ratchet runs:
    1. **`fetch_task_brief(task_id="<slug>-thin")`** — preferred. Each
       benchmark has a pre-seeded task brief in the server's
       `dogfood_tasks` table. The tool renders a fresh `{ts}`-stamped
       run-topic name at call time, so runs never collide. Score with
       `benchmark_score.py --task <task_id>`. See `dogfood/README.md`
       for the operator recipe; `dogfood/tasks/README.md` for the
       authoring format.
    2. **`dogfood/task.md`** — freeform exploratory sessions where the
       AI picks a topic from a candidate list. Used for surfacing tool
       friction on new topic shapes, not for the frozen benchmarks.
    3. **Standalone fat-variant `.md` kickoffs** under
       `dogfood/kickoffs/` — legacy from the 2026-04-23 cycle. Kept
       for historical reference; don't use for new ratchet runs.
- **`hispanic-latino-stem-us/calls.jsonl`** is a vestige of an earlier
  scripted-replay experiment. It's preserved for historical reference
  but the current ratchet does not consume it.
- **Live API, real rate limits.** Wikipedia's live API is hit for real
  (that's what we're measuring). Production topic state is untouched
  — runs go under distinct topic names.
- **Gold ages.** Wikipedia adds/removes/renames articles. Each gold set
  has a "last audited" date at the top of its scope.md; budget a quarterly
  refresh pass.
- **Scope is a frozen human decision.** `scope.md` is the authority. Gold
  evaluates "does the tool hit articles that match THIS scope?" not "is
  this scope right?" — those are separate questions.
