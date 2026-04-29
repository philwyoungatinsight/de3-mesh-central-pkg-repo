---
name: annihilate-maas-machine
description: Deterministically wipe a MaaS machine — delete from MaaS + remove all TF state — so waves rebuild it from scratch. The correct answer to any stuck/broken machine.
---

# /annihilate-maas-machine — Delete MaaS Machine + Wipe TF State

Usage: `/annihilate-maas-machine <machine-name>`

Example: `/annihilate-maas-machine ms01-02`

The machine name is the leaf directory name under `machines/` in the stack — same as
the hostname in MaaS after enrollment.

---

## Step 1 — Confirm argument

Parse `$ARGUMENTS`. If empty, ask the user which machine to annihilate before continuing.
Machine name = `$ARGUMENTS` (e.g. `ms01-02`).

---

## Step 2 — Read current state

Run these in parallel:

```bash
# MaaS system_id and current status
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machines read 2>/dev/null | python3 -c \"
import json,sys
for m in json.load(sys.stdin):
    if m.get('hostname') == '$MACHINE':
        print('system_id=' + m['system_id'])
        print('status=' + m['status_name'])
        print('power_state=' + m.get('power_state','?'))
\""

# GCS TF state files under this machine
gsutil ls -r "gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/$MACHINE/" 2>/dev/null
```

Report what was found. If machine is not in MaaS at all, skip to Step 4 (still wipe TF state).

---

## Step 3 — Pre-delete state transitions (if machine exists in MaaS)

Based on current MaaS status:

**If Deployed or Allocated:**
```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machine release $SYSTEM_ID 2>&1"
# Wait up to 60s for Released/Ready
```

**If Commissioning, Deploying, or Testing:**
```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machine abort $SYSTEM_ID 2>&1"
# Wait up to 30s for abort to complete
```

**If New, Ready, Failed*, Broken:** — no pre-step needed, delete directly.

---

## Step 4 — Delete from MaaS

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machine delete $SYSTEM_ID 2>&1"
```

Confirm deletion by checking machine no longer appears in `maas machines read`.

If machine was not in MaaS: skip this step and note it.

---

## Step 5 — Wipe all GCS TF state under this machine

```bash
GCS_PREFIX="gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/$MACHINE"

# List what will be deleted
gsutil ls -r "$GCS_PREFIX/" 2>/dev/null

# Delete all state files and locks
gsutil -m rm -r "$GCS_PREFIX/" 2>/dev/null || echo "No GCS state found — already clean"
```

Confirm with `gsutil ls "$GCS_PREFIX/"` returning nothing.

---

## Step 6 — Report and next steps

Print a summary:

```
=== Annihilation complete: $MACHINE ===
MaaS: deleted (was $STATUS, system_id=$SYSTEM_ID)
  — OR —
MaaS: not found (already absent)

TF state wiped:
  $GCS_PREFIX/default.tfstate
  $GCS_PREFIX/commission/default.tfstate
  ... (all found paths)
  — OR —
TF state: none found (already clean)

Next steps:
  Re-run waves: maas.lifecycle.new → maas.lifecycle.commissioning → ...
  Or run: make   (if full build is appropriate)
```

---

## Notes

- This skill calls `maas machine release/abort/delete` — these are the ONLY permitted
  direct MaaS API calls (lifecycle transitions, not config overrides). They are safe here
  because annihilation is the explicit goal.
- YAML config is not touched — the machine will be recreated with the same config on the
  next wave run.
- The `auto-import` before_hook in `machines/$MACHINE/terragrunt.hcl` handles re-enrollment
  from scratch when the machine unit is re-applied.
