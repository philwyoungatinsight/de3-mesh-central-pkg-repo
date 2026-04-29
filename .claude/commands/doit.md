---
name: doit
description: Analyse a task, write a detailed plan to docs/ai-plans/, surface decisions for the user, then clear context and execute. Avoids mid-coding compaction by separating the research/planning phase from the coding phase.
---

# /doit — Analyse, Plan, Confirm, Execute

**Usage**:
- `/doit <task description>` — plan a new task, write a plan file, then execute
- `/doit <plan-name>` — resume an existing plan (skips straight to execution)

**Examples**:
```
/doit add OVS wave after maas.lifecycle.deployed   # new task
/doit add-ovs-wave                                  # resume existing plan
```

---

## Step 1 — Read the screwups log

Read `docs/ai-screw-ups/README.md` in full. Required at every session start per CLAUDE.md.

---

## Step 2 — Detect mode: resume vs. new task

Parse `$ARGUMENTS`. If empty, ask the user what they want to accomplish before continuing.

**Resume detection**: check whether `docs/ai-plans/$ARGUMENTS.md` exists (treat `$ARGUMENTS`
as a plan name if it is a single token or hyphen-joined words with no spaces — i.e. looks
like a kebab-case filename stem rather than a sentence).

- If the file **exists**: print `Resuming plan: docs/ai-plans/$ARGUMENTS.md` and **jump
  directly to Step 8** (skip Steps 3–7).
- If the file **does not exist**: treat `$ARGUMENTS` as a task description and continue
  with Step 3.

---

## Step 3 — Understand the task *(new tasks only)*

Confirm understanding of `$ARGUMENTS` as the task description before exploring the codebase.

---

## Step 4 — Explore the codebase *(new tasks only)*

Read all files relevant to the task. This is the research phase — be thorough. For each area of the codebase the task will touch:

- Read the current code/config
- Read related docs in `infra/<pkg>/_docs/`
- Identify what exists vs. what needs to be added/changed
- Understand dependencies, naming conventions, and patterns used elsewhere

Do NOT skip this step. A plan written without reading the code will be wrong.

---

## Step 5 — Write the plan file *(new tasks only)*

Derive a short kebab-case name from the task (e.g. `add-ovs-wave`, `fix-rocky-preseed`).

Create `docs/ai-plans/<kebab-name>.md` with this structure:

```markdown
# Plan: <Task Title>

## Objective
<One paragraph: what this plan achieves and why.>

## Context
<Key findings from code exploration — what exists, what's missing, relevant constraints.>

## Open Questions
<List any decisions that need user input BEFORE executing. If none, write "None — ready to proceed.">

## Files to Create / Modify

### `path/to/file` — <create|modify>
<Exact description of what to write or change. Include code snippets where the change is non-trivial.
Be specific enough that a fresh Claude instance with no prior context can execute this correctly.>

### `path/to/other` — <create|modify>
...

## Execution Order
<Numbered list of which files to touch in what order, and why (dependencies between steps).>

## Verification
<How to confirm the plan was executed correctly — commands to run, outputs to check.>
```

Write the plan to disk using the Write tool. Commit it:

```bash
git add docs/ai-plans/<kebab-name>.md
git commit -m "doit(<kebab-name>): write implementation plan

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Step 6 — Review the plan for correctness *(new tasks only)*

Re-read the plan against the actual code. Check:

- Every file path in the plan actually exists (for modifications) or has a valid parent directory
- Naming conventions match the rest of the codebase (wave names, YAML keys, HCL patterns)
- Dependencies are correct (e.g. Terraform deps, wave ordering)
- No hardcoded values that should come from config
- No steps that violate CLAUDE.md rules (no DB edits, no skipping tests, etc.)

Fix any issues in the plan file before proceeding.

---

## Step 7 — Surface open questions *(new tasks only)*

Check the "Open Questions" section of the plan. Present them to the user clearly:

> **Questions before I proceed:**
> 1. ...
> 2. ...

If there are questions: **STOP HERE**. Wait for the user to answer before continuing to Step 8.

If there are no questions, say:

> **No open questions. Plan is complete. Ready to clear context and execute.**
>
> The plan is at `docs/ai-plans/<kebab-name>.md`.  
> Run `/clear` when ready, then `/doit <kebab-name>` to execute.

---

## Step 8 — Execute the plan

Read the plan file:

```
Read docs/ai-plans/<kebab-name>.md
```

Then execute each step in the "Files to Create / Modify" section in the order specified by "Execution Order". For each file:

1. Read the current file (if modifying)
2. Make the exact change described in the plan
3. Verify the change looks correct before moving on

After all files are done, run the verification steps from the plan.

---

## Step 9 — Archive the plan

Once execution is complete and verified, move the plan file to `docs/ai-plans/archived/`
with a timestamp prefix matching the ai-log convention:

```bash
mkdir -p docs/ai-plans/archived
mv docs/ai-plans/<kebab-name>.md docs/ai-plans/archived/$(date +%Y%m%d%H%M%S)-<kebab-name>.md
```

Stage the archived plan as part of the `/ship` commit so the move is captured atomically
with the work it describes. Do NOT make a separate commit just for the archive move.

---

## Step 10 — Ship

Write an ai-log entry documenting what was done, then run `/ship` to commit and push.
The `/ship` commit should include the archived plan file (at its new path under `archived/`).
