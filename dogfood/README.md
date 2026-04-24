# Topic Builder dogfood sessions

A single-file scaffold for running autonomous Claude Code sessions against
the Topic Builder MCP server. The AI drives a topic build end-to-end and
reports pain points via `submit_feedback` + `note=` on tool calls.

- **AI-facing prompt:** `task.md` — paste this as the first user message.
- **Operator doc:** this README.

## One-time setup

Register the Topic Builder MCP server at user scope so it's available
from any working directory:

```bash
claude mcp add --transport http topic-builder https://topic-builder.wikiedu.org/mcp --scope user
```

Verify:

```bash
claude mcp list
```

You should see `topic-builder` listed. That's it — no auth, no per-session
flag. The tools show up automatically in any `claude` session.

To remove later:

```bash
claude mcp remove topic-builder
```

## Running a benchmark task (preferred for ratchet runs)

Each benchmark has a pre-seeded task brief in the server. The kickoff
is a single line. Use this path for all benchmark / ratchet runs.

1. **Open a fresh terminal** in any empty directory (a scratch dir like
   `~/tmp/codex-run/` is fine).
2. **Start your MCP client** (Codex, Claude Code, etc.) with the
   Topic Builder MCP available.
3. **Paste this as the first message** (swap the task_id for the
   benchmark you want):
   ```
   Call fetch_task_brief(task_id="apollo-11-thin"), then follow its instructions.
   ```
4. **Walk away.** The session starts its own topic with a fresh
   timestamped name, drafts a rubric, runs the pipeline, does spot/gap
   check, and ends with `submit_feedback`. Expect 20–60 minutes.

**Task IDs currently seeded (all `thin` variant):**

- `apollo-11-thin`
- `crispr-gene-editing-thin`
- `african-american-stem-thin`
- `hispanic-latino-stem-us-thin`
- `orchids-thin`

**Scoring when the run wraps:**

```bash
python3 scripts/benchmark_score.py --task apollo-11-thin
```

`--task` mode auto-resolves the most recent run of that task by matching
the `{ts}` template against server topic names. Pass `--nth 1` to score
the second-most-recent run, etc.

To list available tasks from the server at any time:

```
Call list_tasks() from any MCP client.
```

## Running a freeform dogfood session (exploratory, bring-your-own-topic)

Distinct from benchmark runs. Use this when you want to surface tool
friction on a topic *shape* we haven't tested yet — the AI picks the
topic from a prompt-provided candidate list.

1. **Open a fresh terminal.** Any working directory — the session doesn't
   touch the local filesystem, so a scratch dir like `~/tmp/dogfood-run/`
   works, or just wherever you happen to be.
2. **Start `claude`.** The Topic Builder tools are already loaded (from
   the user-scope registration above).
3. **Paste the contents of `task.md`** as the first user message. The AI
   will start by listing existing topics and proposing 2–3 candidates in
   shapes we haven't tested.
4. **Converge on a topic with the AI.** Confirm scope; then step back.
5. **Let it run.** The session will scope, gather, review, and either
   export or stop on a blocker — ending with a `submit_feedback` call.

## Collecting the results

The signal lives in two places on the server:

- `/opt/topic-builder/logs/feedback.jsonl` — one JSON line per
  `submit_feedback` call. This is the primary output.
- `/opt/topic-builder/logs/usage.jsonl` — one line per interesting tool
  call, including any `note=` observations the AI dropped mid-flow.

Quick pull:

```bash
ssh -i deploy_key root@172.232.161.125 \
  "tail -n 5 /opt/topic-builder/logs/feedback.jsonl"

ssh -i deploy_key root@172.232.161.125 \
  "grep '\"note\"' /opt/topic-builder/logs/usage.jsonl | tail -n 20"
```

The most recent `feedback.jsonl` line for a session should have a
`what_didnt` field with specific complaints and a `missed_strategies`
field naming tool shapes we don't have. If those are thin or generic,
the task prompt needs sharpening.

## Tuning the prompt

After a few runs, expect to edit `task.md` based on what the AI did
vs. what we wanted:

- Candidate-shape list too narrow / too broad — add or drop shapes.
- Rating came back politely high despite real friction — sharpen the
  rating-calibration sentence.
- AI stopped too early or pushed through dead ends — tune the stopping
  rules.
- AI skipped the "brainstorm the workaround, don't execute it" pattern
  — rephrase or add an example.

Edits are normal. `task.md` is meant to evolve as we learn what kind of
session we want.

## Why this shape

Earlier sessions (orchids, ed-psych, Hispanic/Latino STEM, Kochutensilien,
Native American scientists, Seattle) surfaced that feedback captured via
`submit_feedback` — when the AI is primed with "this is for tool
development" — contains most of what we'd extract from the transcript
anyway, in a concentrated form. So the scaffold is deliberately minimal:
one prompt file, no transcript capture, no scripted replay, no parallel
harness. The AI runs autonomously and hands us a structured retrospective.
If that breaks down in practice we'll add more; for now, less is more.
