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

## The benchmarks

The size of the suite isn't fixed — benchmarks get added when a new
topic shape is worth measuring against, or when a Wiki-Education
priority topic merits per-cycle quality measurement. Five members
followed the standard layout below as of 2026-04-23; climate-change
joined 2026-04-25. See `docs/adding-exemplars.md` for the inclusion
rubric and `docs/ratchet-plan.md` for which benchmarks each ratchet
cycle measures.

Standard-layout members:

- `apollo-11` — single historical event + cultural tail
- `crispr-gene-editing` — scientific discipline with distinctive vocabulary
- `african-american-stem` — intersectional biography
- `orchids` — taxonomy at scale + cross-wiki (the marquee completeness test)
- `climate-change` — well-organized academic + movement + policy
  (origin topic of the project; bootstrapped 2026-04-25)

**`hispanic-latino-stem-us`** is slightly nonstandard: it was
bootstrapped from a 2026-04-17 dogfood session audit and integrated
into the suite later. It carries extra artifacts from that original
pass (`calls.jsonl`, `baseline.md`, review-queue state) that the
others don't have. See its per-topic README for the full map.

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

**Safety net for hand-classifications.** `audit.py` is the canonical
classifier, but operators sometimes hand-edit `gold.csv` directly
(e.g. one-off "Sage's call" rulings on edge cases). To prevent re-runs
from silently clobbering those decisions, every `audit.py`'s `main()`
loop preserves a row's prior `on_topic` whenever the classifier
returns `uncertain`. Rules win when they speak; the file wins when
rules are silent. The pattern (drop-in for any new benchmark's
`audit.py`):

```python
PRESERVE_FROM_FILE = {"in", "peripheral", "out", "redirect", "redlink"}
preserved = []
for row in body:
    title, prior, sources, score, desc, _notes = row
    cls, why = classify(title, desc, sources)
    if cls == "uncertain" and prior in PRESERVE_FROM_FILE:
        cls = prior
        why = f"Preserved prior verdict {prior!r} from gold.csv (no audit.py rule)"
        preserved.append((title, prior))
    # ... existing classification + counts ...
if preserved:
    print(f"Preserved {len(preserved)} hand-classifications from gold.csv (no audit.py rule).")
```

When the preserved-count is non-zero, codify durable verdicts as
`audit.py` rules so the safety net stays a backstop, not a load-
bearing surface. The 2026-04-26 apollo-11 incident is the
motivating case: re-running `audit.py` flattened 32 hand-classified
rows + 3 redirect markers back to `uncertain`, which precision then
read as false-positive churn. `audit.py` is gitignored (it pairs
names with judgments), so the safety net lives in each operator's
local copy — but the pattern is documented here so new benchmarks
inherit it.

**Validate against Wikipedia ground truth (redlinks + redirects).**
The keyword classifier in `audit.py` can label a title `in` /
`peripheral` / `out` based on its name and description, but it can't
tell whether the title actually has a Wikipedia article. Two facts
the classifier can't infer:

- The title might not exist on Wikipedia at all (`redlink`).
- The title might be a redirect to a canonical article (`redirect`)
  that's already in gold under its real name — counting both inflates
  `gold_in` and depresses recall measurements.

`benchmarks/audit_lib.py` provides `validate_gold_titles(gold_path,
wiki="en")` — a shared helper that batches all `in` / `peripheral` /
`redlink` / `redirect`-classified rows through the MediaWiki API
(`prop=info`, redirects=1, batches of 50, rate-aware backoff) and
updates the classification:

- `missing` on Wikipedia → `redlink`
- redirect → `redirect`, with target captured in the `notes` column
- previously `redlink` but article now exists → `pending_audit`
  (so the keyword classifier picks it up on next run)

Idempotent. Every `audit.py`'s `main()` should call it as the last
step (after the keyword classifier has written back), so existence
ground truth trumps pattern-derived verdicts:

```python
import sys
sys.path.insert(0, os.path.dirname(HERE))
from audit_lib import validate_gold_titles  # noqa: E402

# ... rest of audit.py ...

def main():
    # ... keyword classifier + safety net + write back ...
    print()
    validate_gold_titles(GOLD_PATH, wiki="en")
```

The helper itself lives in version control (`benchmarks/audit_lib.py`)
since it contains no name-judgment pairs — only generic existence-
checking logic. `audit.py` files remain gitignored.

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
  cycle starts a fresh AI-driven session for each of the benchmark
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
