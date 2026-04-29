---
name: run-wave
description: Run a specific wave by number or name, verify ALL phases passed (precheck + apply + inventory + test-playbook), fix automation on failure, and rerun until the wave succeeds.
---

# /run-wave — Run, Verify, Fix, and Retry a Wave

**Usage**: `/run-wave <wave-number-or-name>`  
**Example**: `/run-wave 10` or `/run-wave maas.test.proxmox-vms`

---

## Step 1 — Clear context

Run `/clear` NOW, before doing anything else. This prevents stale summaries or prior session context from affecting your analysis of this wave run.

## Step 2 — Read the screwups log

Read `docs/ai-screwups/README.md` in full. Required at every session start per CLAUDE.md.

## Step 3 — Identify the wave

If given a number N, run:
```
./run --list-waves
```
to confirm the wave name for number N.

## Step 4 — Run the wave

```
source set_env.sh && ./run -n <N>
```

Stream the output. Do not proceed until the run completes.

## Step 5 — Verify ALL phase logs

List all log files produced:
```
ls ~/.run-waves-logs/latest/
```

For the wave that just ran, read the final 50 lines of every phase log that exists:
- `wave-<name>-precheck.log` — pre-wave Ansible playbook
- `wave-<name>-apply.log` — Terraform/OpenTofu apply
- `wave-<name>-inventory.log` — inventory update
- `wave-<name>-test-playbook.log` — post-wave Ansible test

Check each log for failure indicators:
- `ERROR:` anywhere
- `FAILED!` anywhere
- `failed=[^0]` in any PLAY RECAP (e.g. `failed=1`)
- `fatal:` anywhere
- `command failed` anywhere
- `exit 2` / `rc=1` / `RC:1`

## Step 6 — Produce a verdict table

```
Phase           | Log present | Result
----------------|-------------|--------
precheck        | YES / NO    | PASS / FAIL / N/A
apply           | YES / NO    | PASS / FAIL
inventory       | YES / NO    | PASS / FAIL / N/A
test-playbook   | YES / NO    | PASS / FAIL / N/A
```

**A wave PASSES only when every present phase log shows no failures.**

---

## If the wave PASSES

> **WAVE VERDICT: PASS — safe to advance to wave N+1.**

Stop here.

---

## If the wave FAILS — fix the automation, then rerun

> **WAVE VERDICT: FAIL — phase [X] failed. Fixing automation before retry.**

Then follow this loop until the wave passes:

### Diagnose

Read the full failing log — not just the last 50 lines. Identify the root cause.

### Fix rules — NO EXCEPTIONS

**Fix the automation. Never monkey-patch state.**

| Forbidden | Correct alternative |
|-----------|-------------------|
| Edit a database directly (`psql`, `UPDATE maasserver_*`) | Use MaaS CLI API (`maas machine release`, `maas machine delete`) |
| Force MaaS machine status by writing to DB | Delete machine + `tofu state rm` + re-run wave |
| Monkey-patch Terraform state | `tofu state rm` the broken resource, let automation recreate |
| Change `test_ansible_playbook` to `test_action: reapply` to silence a failing test | Fix the infrastructure the test is checking |
| Remove or weaken an Ansible test assertion | Fix the root cause; only change the test with explicit user confirmation |
| Run one-off scripts to push config that automation manages | Fix the playbook/Terraform module so it does it correctly |
| Hardcode values in scripts or playbooks | Read from YAML config via `config_base` |

**If the test-playbook is failing**: the infrastructure is in the wrong state — not the test. Investigate why the infrastructure didn't reach the expected state. The test is the signal; don't shoot the messenger.

**If you believe the test is checking the wrong condition** (e.g. wrong phase for that assertion): stop, explain to the user exactly what the test checks vs. what is appropriate for this wave, and wait for explicit confirmation before touching the test.

### Fix, then rerun

After fixing the automation code:
1. Re-read the fix to confirm it addresses the root cause
2. Rerun: `source set_env.sh && ./run -n <N>`
3. Go back to Step 5 — verify all phase logs again
4. Repeat until verdict is PASS

**Never advance to the next wave until this wave's verdict is PASS.**
