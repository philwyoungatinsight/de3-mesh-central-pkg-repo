---
name: doit-with-watchdog
description: Execute an ai-plan via /doit while the build watchdog monitors the process. Usage: /doit-with-watchdog <plan-name> [polling-minutes]
---

# /doit-with-watchdog <plan-name> [polling-minutes]

Executes an existing ai-plan (like `/doit <plan-name>`) while running the build watchdog
cron job for the duration. Registers the watchdog before execution, runs the full plan,
then stops the watchdog when done.

**Usage:**
```
/doit-with-watchdog add-ovs-wave        # 2-minute polling (default)
/doit-with-watchdog add-ovs-wave 5      # 5-minute polling
```

---

## Step 0 — Parse arguments

Split `$ARGUMENTS` on whitespace:

- `PLAN_NAME` = first token. If empty or missing: output
  `Error: Usage: /doit-with-watchdog <plan-name> [polling-minutes]` and stop.
- `POLL_MINUTES` = second token if present AND is a positive integer between 1 and 59;
  otherwise default to `2`.
- Derive: `CRON_EXPR="*/${POLL_MINUTES} * * * *"`

Confirm the plan file exists:
```bash
ls docs/ai-plans/${PLAN_NAME}.md
```
If it does not exist: output `Error: Plan not found: docs/ai-plans/${PLAN_NAME}.md` and stop.

---

## Step 1 — Resolve runtime paths

Run this bash command and capture the output:

```bash
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"
echo "GIT_ROOT=${GIT_ROOT}"
echo "DYNAMIC_DIR=${_DYNAMIC_DIR}"
```

Store these values:
- `GIT_ROOT` — repo root
- `WATCHDOG_SCRIPT="${GIT_ROOT}/scripts/ai-only-scripts/build-watchdog/check"`
- `WATCHDOG_LOG="${_DYNAMIC_DIR}/watchdog/build-watchdog.log"`
- `WATCHDOG_REPORT="${_DYNAMIC_DIR}/watchdog-report/watchdog_report.yaml"`

---

## Step 2 — Register watchdog

Call `CronList` to get all currently registered cron jobs.

Scan for any job whose prompt contains the string `build-watchdog`.

**If a matching job already exists:**

Note the existing job ID. Report:
```
Watchdog already running — job ID: <id>. Proceeding with plan execution.
```

**If no matching job exists:**

Before calling `CronCreate`, substitute the **literal resolved values** of `WATCHDOG_SCRIPT`,
`WATCHDOG_LOG`, and `WATCHDOG_REPORT` (from Step 1) into the prompt text below. The stored
prompt must contain literal resolved paths — shell variables will NOT expand at cron fire time.

Create the cron job with `CronCreate`:

- `cron`: the resolved value of `CRON_EXPR` (e.g. `*/2 * * * *`)
- `recurring`: `true`
- `durable`: `true`
- `prompt` (with `<WATCHDOG_SCRIPT>`, `<WATCHDOG_LOG>`, `<WATCHDOG_REPORT>` replaced by their
  resolved values):

```
Run the build watchdog check (this also writes the YAML report automatically):
  bash <WATCHDOG_SCRIPT>

Then read the report at:
  <WATCHDOG_REPORT>

If user_input_needed is false: show the last 5 lines of <WATCHDOG_LOG> and
  report current MaaS machine states. If something is wrong, fix it.
If user_input_needed is true: output the user_input_message as a direct question to
  the user and wait for their response before ending the session.
```

Then report:
```
Watchdog registered (every POLL_MINUTES min) — job ID: <new-id>
Script: <WATCHDOG_SCRIPT>
Log: <WATCHDOG_LOG>
Starting plan execution.
```

---

## Step 3 — Execute the plan

Read the plan file:
```
Read docs/ai-plans/${PLAN_NAME}.md
```

Execute each step in the "Files to Create / Modify" section in the order specified by
"Execution Order". For each file:

1. Read the current file (if modifying)
2. Make the exact change described in the plan
3. Verify the change looks correct before moving on

After all files are done, run the Verification steps from the plan.

---

## Step 4 — Archive the plan

Move the plan to the archive directory:

```bash
mkdir -p docs/ai-plans/archived
mv docs/ai-plans/${PLAN_NAME}.md docs/ai-plans/archived/$(date +%Y%m%d%H%M%S)-${PLAN_NAME}.md
```

Stage the archived plan as part of the ship commit (Step 5). Do NOT make a separate commit
just for the archive move.

---

## Step 5 — Ship

Write an ai-log entry to `docs/ai-log/$(date +%Y%m%d%H%M%S)-${PLAN_NAME}.md` documenting
what was done, then run `/ship` to commit and push. The ship commit must include the
archived plan file at its new path under `archived/`.

---

## Step 6 — Stop the watchdog

Call `CronList` to get all currently registered cron jobs.

Find all jobs whose prompt contains the string `build-watchdog`.

Call `CronDelete` for each matching job ID. Delete them one at a time.

Then report:
```
Watchdog stopped — plan complete.
Deleted <N> job(s): <id-list>
```

If no matching jobs are found (e.g. already stopped externally):
```
Watchdog not running — nothing to stop. Plan complete.
```
