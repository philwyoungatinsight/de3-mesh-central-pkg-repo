---
name: work-on-maas
description: Start or resume MaaS-focused work. Kills any full build, starts a MaaS-only build (--wave "*maas*"), runs the watchdog, and monitors until success or failure.
---

# /work-on-maas — Focus Build on MaaS Waves

Kills any running full build, then starts (or resumes) a MaaS-only build
with `./run -b -w "*maas*"`. Registers the watchdog and actively monitors
until all MaaS waves succeed or one fails.

---

## Step 1 — Kill any running full build

```bash
pkill -f "run -b" 2>/dev/null || pkill -f "run --build" 2>/dev/null || true
sleep 2
# confirm stopped
pgrep -fa "python3.*run" | grep -v "pgrep|claude|watchdog|dispatcher|reflex" || echo "no build running"
```

If a `*maas*`-only build is already running (check `pgrep` output), skip to Step 3 —
do not restart it.

---

## Step 2 — Start MaaS-only build

```bash
nohup bash -c 'source /home/pyoung/git/pwy-home-lab/set_env.sh && \
  cd /home/pyoung/git/pwy-home-lab && \
  ./run -b -w "*maas*" > ~/.run-waves-logs/run.log 2>&1' > /dev/null 2>&1 &
echo "MaaS build started PID $!"
```

---

## Step 3 — Register watchdog (idempotent)

Run `/watchdog` to ensure the build watchdog cron job is registered. This monitors
the build every minute and alerts if it stops unexpectedly.

---

## Step 4 — Monitor actively

Check build state every ~2 minutes until `maas.lifecycle.deployed` succeeds or a
wave fails. For each check:

```bash
# 1. Which waves have log files?
ls -lt ~/.run-waves-logs/latest/*.log | head -20

# 2. Tail the active log
tail -20 ~/.run-waves-logs/run.log

# 3. MaaS machine states
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ubuntu@10.0.10.11 \
  "sudo /usr/bin/snap run maas maas-admin machines read 2>/dev/null | python3 -c \"
import json,sys
for m in json.load(sys.stdin):
    print(m['hostname'],'=',m['status_name'],'power='+m.get('power_state','?'))
\""
```

**Gate checkpoints** — read the relevant log file when each wave starts:

| Wave | Log to watch | What to check |
|------|-------------|---------------|
| `maas.servers.all` | `wave-maas.servers.all-apply.log` | No TF errors; MaaS API up |
| `maas.lifecycle.new` | `wave-maas.lifecycle.new-precheck.log` | ms01-02 enrolled (MAC 38:05:25:31:81:10) |
| `maas.lifecycle.new` | `wave-maas.lifecycle.new-apply.log` | auto-import imports se7eyd→ms01-02 |
| `maas.lifecycle.commissioning` | `wave-maas.lifecycle.commissioning-precheck.log` | Plug bounce + AMT PXE boot |
| `maas.lifecycle.commissioning` | `wave-maas.lifecycle.commissioning-test-playbook.log` | All Commissioning/Ready |
| `maas.lifecycle.deploying` | `wave-maas.lifecycle.deploying-precheck.log` | Allocate + AMT deploy boot |
| `maas.lifecycle.deployed` | `wave-maas.lifecycle.deployed-test-playbook.log` | All Deployed |

---

## Step 5 — On failure

1. Read the failing wave's log in full
2. Diagnose root cause (do NOT retry the same action blindly)
3. Fix the automation code
4. Commit the fix
5. Restart this skill

**If ms01-02 is stuck**: check AMT standby first:
```bash
# Is AMT responding?
ssh ubuntu@10.0.10.11 "nc -zv 10.0.11.11 16993 2>&1"
# Bounce plug if AMT dead
curl -X POST 'http://10.0.10.11:7050/power/off?host=192.168.2.105&type=tapo'
sleep 10
curl -X POST 'http://10.0.10.11:7050/power/on?host=192.168.2.105&type=tapo'
# Poll AMT for 120s
```

---

## Step 6 — On success

When `maas.lifecycle.deployed` test-playbook passes:
1. Report final MaaS machine states (all should be Deployed)
2. Run `/ship` to commit any uncommitted changes and push
