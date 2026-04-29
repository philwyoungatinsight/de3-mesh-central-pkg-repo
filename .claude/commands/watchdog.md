---
name: watchdog
description: Ensure the build watchdog cron job is registered and running. Idempotent — safe to run any number of times. Optional argument: session name to scope the watchdog to.
---

# /watchdog [session-name] — Ensure Build Watchdog Cron Is Running

Checks whether the build watchdog cron job is already registered. If it is, reports its
ID. If it is not, registers it. Never creates a duplicate.

Optional argument: `session-name` — the name of the Claude Code session this watchdog
is intended to run in.

---

## Step 0 — Resolve runtime paths

Run this bash command and capture the output:

```bash
GIT_ROOT="$(git rev-parse --show-toplevel)"
source "${GIT_ROOT}/set_env.sh"
echo "GIT_ROOT=${GIT_ROOT}"
echo "DYNAMIC_DIR=${_DYNAMIC_DIR}"
echo "WAVE_LOGS_DIR=${_WAVE_LOGS_DIR}"
```

Store these values for use in all subsequent steps:
- `GIT_ROOT` — repo root
- `WATCHDOG_SCRIPT="${GIT_ROOT}/scripts/ai-only-scripts/build-watchdog/check"`
- `WATCHDOG_LOG="${_DYNAMIC_DIR}/watchdog/build-watchdog.log"`
- `WATCHDOG_REPORT="${_DYNAMIC_DIR}/watchdog-report/watchdog_report.yaml"`

---

## Step 0.5 — Parse session argument

The user may have passed a session name as an argument (e.g. `/watchdog watchdog`).

- If a session name was provided: store it as `SESSION_NAME`. Note it in all output.
  **Important**: `CronCreate` fires in the current session only — it cannot target another
  session. If `SESSION_NAME` is provided and does not match the current session, output:
  ```
  WARNING: /watchdog was called with session="<SESSION_NAME>" but this session may differ.
  The cron job will fire in the CURRENT session.
  To ensure it runs in session "<SESSION_NAME>": open that session and run /watchdog <SESSION_NAME> there.
  Proceeding with registration in the current session.
  ```
  Then continue with Step 1.
- If no session name was provided: `SESSION_NAME` is empty. Proceed silently.

---

## Step 1 — Check for existing watchdog job

Call `CronList` to get all currently registered cron jobs.

Scan the results for any job whose prompt contains the string `build-watchdog`.

---

## Step 2 — Decide: already running or needs registration?

**If a job matching `build-watchdog` is found:**

Report (include `Session: <SESSION_NAME>` line only if SESSION_NAME is non-empty):
```
Watchdog already running — job ID: <id>
Schedule: every 2 minutes
Script: <WATCHDOG_SCRIPT>
Log: <WATCHDOG_LOG>
Session: <SESSION_NAME>          ← omit this line if no session name was given
Nothing to do.
```

Stop here. Do NOT create a second job.

---

**If no matching job is found:**

Before calling `CronCreate`, substitute the **literal resolved values** of `WATCHDOG_SCRIPT`,
`WATCHDOG_LOG`, and `WATCHDOG_REPORT` (from Step 0) into the prompt text below. The stored
prompt must contain the literal resolved paths — shell variables will not expand at cron
fire time.

Create the cron job with `CronCreate`:

- `cron`: `*/2 * * * *`
- `recurring`: `true`
- `durable`: `true`
- `prompt` (with `<WATCHDOG_SCRIPT>`, `<WATCHDOG_LOG>`, `<WATCHDOG_REPORT>` replaced by their resolved values):

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

Then report (include `Session:` line only if SESSION_NAME is non-empty):
```
Watchdog registered — job ID: <new-id>
Schedule: every 2 minutes
Script: <WATCHDOG_SCRIPT>
Log: <WATCHDOG_LOG>
Session: <SESSION_NAME>          ← omit this line if no session name was given
First check fires within 2 minutes.
```

---

## Step 3 — Run one immediate check

Regardless of whether the job was already running or just created, run one immediate
check now using the resolved path from Step 0:

```bash
bash "${WATCHDOG_SCRIPT}"
```

Then show the last 3 lines of `${WATCHDOG_LOG}`.

This confirms the script is working and gives the current build/MaaS state immediately.

---

## Step 4 — Read watchdog report

The check script (Step 3) writes the YAML report automatically. Read it now using
the resolved path from Step 0:

```bash
cat "${WATCHDOG_REPORT}"
```

- If `user_input_needed: false`: show the last 5 lines of `${WATCHDOG_LOG}` and
  report current MaaS machine states. If something is wrong, fix it.
- If `user_input_needed: true`: output the `user_input_message` as a direct question to
  the user and wait for their response before ending the session.
