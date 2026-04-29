---
name: watchdog-off
description: Stop the build watchdog cron job. Removes all registered watchdog jobs so no further periodic checks fire. Run /watchdog to re-enable.
---

# /watchdog-off — Stop the Build Watchdog

Finds and deletes all registered build watchdog cron jobs so no further periodic checks
fire in this session. Safe to run when no watchdog is active — it will report that and
stop cleanly.

Run `/watchdog` (optionally with a session name) to re-enable.

---

## Step 1 — List all cron jobs

Call `CronList` to get all currently registered cron jobs.

---

## Step 2 — Find watchdog jobs

Scan the results for any job whose prompt contains the string `build-watchdog`.

Collect all matching job IDs.

---

## Step 3 — Delete or report

**If no matching jobs are found:**

Report:
```
Watchdog is not running — nothing to stop.
Run /watchdog to start it.
```

Stop here.

---

**If one or more matching jobs are found:**

Call `CronDelete` for each job ID found. Delete them one at a time.

Then report:
```
Watchdog stopped — deleted <N> job(s):
  - <job-id-1>
  - <job-id-2>  ← if more than one
No further watchdog checks will fire in this session.
Run /watchdog to re-enable.
```
