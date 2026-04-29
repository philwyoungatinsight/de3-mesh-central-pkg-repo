---
name: ship
description: Review recent changes, update READMEs, write ai-log + ai-summary entry, commit, and push.
---

# /ship — Review, Document, Commit, Push

Ships a work session by documenting what changed, updating relevant READMEs, writing an ai-log entry, updating the ai-log summary, making a git commit, and pushing.

---

## Step 1 — Understand what changed

Run these in parallel:

```bash
git diff HEAD          # all staged + unstaged changes
git status             # untracked files and modified files
git log --oneline -10  # recent commits for context
```

Read the diff carefully. Identify:
- Which packages/directories were touched
- What the functional change was (fix, feature, refactor)
- What was broken before, what works now

---

## Step 2 — Update README files

Per CLAUDE.md: **update README.md when making code changes in a directory that has a Makefile.**

For each modified directory that contains a `Makefile`:
1. Read the current README.md
2. Update to reflect the current state of the code — describe how the code works, not what changed
3. Keep the main Steps section short; non-obvious details go in linked appendix sections
4. Use bullet lists for procedural steps
5. Do NOT narrate the changes ("I added X") — describe the current working state

Also check `infra/<pkg>/_docs/README.md` for any package whose units were modified.

Skip README updates if no Makefile-containing directories were touched.

---

## Step 3 — Write the ai-log entry

File: `docs/ai-log/$(date +%Y%m%d%H%M%S)-<short-kebab-description>.md`

Get the timestamp:
```bash
date +%Y%m%d%H%M%S
```

Format:
```markdown
# <Title: What Was Done>

## Summary

<2–4 sentence summary of what was accomplished and why.>

## Changes

- **`path/to/file`** — what changed and why
- **`path/to/other`** — what changed and why

## Root Cause (if a fix)

<What was broken and why.>

## Notes

<Anything surprising, non-obvious, or worth remembering for next time.>
```

Keep it factual and concise. Focus on the "why" not just the "what".

---

## Step 4 — Update the ai-log summary

File: `docs/ai-log-summary/ai-log-summary.md`

Add a new entry at the **top** (reverse-chronological), after the `---` separator line that follows the header. Format:

```markdown
## YYYY-MM-DD — <Title>

<3–6 bullet points summarizing the key changes, one line each. Focus on what is different now vs before.>

---
```

Read the existing summary first to match the style.

---

## Step 5 — Archive old ai-log files

Move any ai-log files older than 3 days from `docs/ai-log/` into `docs/ai-log/archived/`.
The timestamp in the filename is authoritative — parse it, do not rely on filesystem mtime.

```bash
mkdir -p docs/ai-log/archived
cutoff=$(date -d '3 days ago' +%Y%m%d%H%M%S 2>/dev/null || date -v-3d +%Y%m%d%H%M%S)
for f in docs/ai-log/*.md; do
  stem=$(basename "$f" .md)
  ts=${stem%%[-_]*}          # leading digits before first - or _
  [[ "$ts" =~ ^[0-9]{14}$ ]] && [[ "$ts" < "$cutoff" ]] && git mv "$f" docs/ai-log/archived/
done
```

Skip this step if there are no `.md` files in `docs/ai-log/` (only subdirectories present).
Stage the moves with `git mv` so they appear as renames in the commit, not delete+add.

---

## Step 6 — Stage and commit

Stage all relevant files:
```bash
git add <specific files — do NOT use git add -A blindly>
```

Include:
- All modified source files
- New/updated README files
- The new ai-log file
- The updated ai-log-summary
- Any archived ai-log files (already staged by `git mv` in Step 5)
- Any new skill or command files

Write the commit message following the repo's style (seen in `git log --oneline`). Use a HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <short description>

<Optional body — why, not what. One paragraph max.>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Step 7 — Push

```bash
~/bin/gpa
```

This pushes the current branch to all configured remotes. Confirm it completes without error.

---

## Done

Report:
- What was committed (file count, commit hash)
- Which READMEs were updated (or "none needed")
- The ai-log filename created
- Push result (success or error)