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

## Per-topic layout

```
benchmarks/<topic-slug>/
├── scope.md        — Plain-language scope, every ambiguity explicitly
│                     resolved. Frozen; revisit deliberately with a version
│                     bump.
├── gold.csv        — Authoritative on-topic article list. Columns:
│                     title, on_topic, best_source_strategy, justification,
│                     notes. Validated-negative articles are also recorded
│                     so tools that cut noise can be tested too.
├── petscan.md      — If applicable: the PetScan (or SPARQL) query the
│                     org uses as its non-AI baseline for this topic, plus
│                     when last run and a raw-result snapshot.
├── calls.jsonl     — Scripted "exemplar" tool-call sequence that a good
│                     AI run would make. One JSON object per line:
│                     {"tool": "...", "args": {...}}
└── README.md       — Per-topic notes: origin, pending work, known limits.
```

## Running the benchmark

```
python3 scripts/benchmark.py <topic-slug>
```

Reads gold.csv + calls.jsonl from the topic's directory, replays the call
sequence against a disposable temporary SQLite DB (so the production DB is
untouched), and emits a markdown report comparing the resulting working
list to the gold set — precision, recall, noise count, per-strategy
contribution, session cost in tool calls.

If a baseline report exists at `benchmarks/<slug>/baseline.md`, the runner
emits a delta against it (did this change help?).

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

- **Scripted, not AI-driven.** Replays a fixed sequence of tool calls. This
  isolates tool/prompt changes from AI behaviour changes — the latter is
  a separate, harder problem not in scope here.
- **Disposable DB.** The runner uses a tempdir DB; production data is not
  touched. Wikipedia's live API is hit for real (that's what we're
  measuring).
- **Gold ages.** Wikipedia adds/removes/renames articles. Each gold set
  has a "last audited" date at the top of its scope.md; budget a quarterly
  refresh pass.
- **Scope is a frozen human decision.** `scope.md` is the authority. Gold
  evaluates "does the tool hit articles that match THIS scope?" not "is
  this scope right?" — those are separate questions.
