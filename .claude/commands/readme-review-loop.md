---
name: readme-review-loop
description: Run /readme-review repeatedly until all pending rows in the README-tracker are processed.
---

# /readme-review-loop — Process All Pending READMEs

Runs `/readme-review` in a loop until every row in the tracker has a non-`pending` status.

---

## Step 1 — Check for pending rows

Read the tracker:

```
infra/default-pkg/_docs/readme-maintenance/README-tracker.md
```

Count the rows where Status = `pending`.

If **zero pending rows remain**, report:

> All READMEs reviewed — tracker complete.

and stop.

---

## Step 2 — Run `/readme-review`

Invoke the `/readme-review` skill. It will:
- Sync the tracker with the filesystem (Step 0)
- Find and review the next pending README
- Commit the result and run `/ship`

---

## Step 3 — Loop

After `/readme-review` completes, go back to **Step 1** and check again.

Repeat until no pending rows remain.

---

## Done

Report a summary:
- How many READMEs were processed this run
- How many are now `updated`, `ok`, or `skip`
- Confirm the tracker is complete
