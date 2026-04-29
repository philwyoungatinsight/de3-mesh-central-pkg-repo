---
name: readme-review
description: Process the next pending README in the tracker, update it if stale, mark it done, and commit. Run repeatedly until all READMEs are reviewed.
---

# /readme-review — Process the Next Pending README

Works through `infra/default-pkg/_docs/readme-maintenance/README-tracker.md` one README at a time.
Each invocation handles exactly one `pending` row, then commits and reports what's next.

---

## Step 0 — Sync tracker with filesystem

Before finding the next pending row, synchronize the tracker with the filesystem.

**Scan** for all `.md` files under `infra/default-pkg/_docs/`.

**Exclude** the following (not meaningful review targets):
- Files whose basename starts with 14 digits (dated ai-log entries, e.g. `20260418000000-*.md`)
- Anything under an `archived/` subdirectory
- `infra/default-pkg/_docs/ai-log-summary/ai-log-summary.md` (living summary, not a README)
- `infra/default-pkg/_docs/readme-maintenance/README-tracker.md` (the tracker itself)
- Any file under `infra/default-pkg/_docs/ai-plans/` that is NOT named `README.md`

**For each remaining file not already in the tracker:**
- Add it as a new `pending` row in the appropriate priority section
- Get the last commit date with: `git log -1 --format="%as" -- <file>`
- Place `framework/` files in the **Priority 5** section; all other `_docs/` files in **Priority 7**

**For each tracker row whose file no longer exists on disk:**
- Change its status to `skip`

If any rows were added or removed, commit the tracker update before proceeding:

```bash
git add infra/default-pkg/_docs/readme-maintenance/README-tracker.md
git commit -m "$(cat <<'EOF'
docs: sync readme-maintenance tracker with _docs filesystem

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If no changes were needed, proceed directly to Step 1 without committing.

---

## Step 1 — Find the next pending README

Read the tracker:

```
infra/default-pkg/_docs/readme-maintenance/README-tracker.md
```

Scan the tables top-to-bottom (Priority 1 first). Find the **first row where Status = `pending`**.

Note its:
- Row number (`#`)
- File path
- Description (to understand what it should cover)

If **no pending rows remain**, report "All READMEs reviewed — tracker complete." and stop.

---

## Step 2 — Understand the README's context

Read the README file at the path from Step 1.

Then read the surrounding directory to understand what it actually does now:
- List the directory containing the README (`ls` or Glob)
- Read relevant source files (scripts named `run`, `playbook.yaml`, `main.tf`, key `.hcl` files, etc.)
- If a `Makefile` exists nearby, read it
- For tg-scripts: read the `run` script
- For Ansible playbooks: read `playbook.yaml`
- For package `_docs/README.md`: skim the package's `_config/config.yaml` for current structure

The goal is to understand the **current state** well enough to judge whether the README is accurate.

---

## Step 3 — Assess and update

Compare what the README says against what the code actually does.

**Update the README if any of these are true:**
- It describes scripts, flags, or steps that no longer exist or have been renamed
- It omits important scripts, flags, or behaviour that exist in the code
- It references hardcoded values, paths, or names that conflict with the current YAML/HCL config
- It is so brief it would not help someone unfamiliar with the directory

**Leave the README as-is (`ok`) if:**
- It accurately describes the current code
- No material information is missing

**README writing rules (from CLAUDE.md):**
- Bullet lists for procedural steps
- Non-obvious details in linked appendix sections; keep the main Steps section short
- Describe how the code works — do NOT narrate what changed
- No comments, no emojis, no multi-paragraph preambles
- No hardcoded IPs/names — reference config keys instead

---

## Step 4 — Update the tracker

Edit the tracker row for this README:
- Set **Status** to `updated` (if the README was changed) or `ok` (if it was already accurate)
- Set **Last Reviewed** to today's date in `YYYY-MM-DD` format

Do **not** change any other rows.

---

## Step 5 — Commit

Stage only the files touched in this session:

```bash
git add infra/default-pkg/_docs/readme-maintenance/README-tracker.md
# plus the README file itself if it was changed
git add <readme-path>
```

Commit with a concise message:

```bash
git commit -m "$(cat <<'EOF'
docs: review README for <short directory name>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Step 5.5 — Ship

Run `/ship` to write an ai-log entry and push the commit.

---

## Step 6 — Report

Output a brief summary:

- **Reviewed:** `<file path>`
- **Status:** `updated` or `ok` — one sentence on what was wrong / why it was fine
- **Next pending:** the file path of the next `pending` row in the tracker (or "none — all done")
- **To continue:** run `/readme-review` again
