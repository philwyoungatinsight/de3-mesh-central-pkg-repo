# install-mesh-central

Installs and configures MeshCentral on the dedicated `mesh-central` VM.

**Once `mesh-central` is running, everything is `./run --build`.**

---

## What gets deployed

- MeshCentral (Node.js-based self-hosted remote device management server)
- Runs as a systemd service (`meshcentral`) under a dedicated system user
- Web UI available at `https://<mesh-central-ip>:443`
- Intel AMT server on port 4433 (for out-of-band management)
- Source patches applied for Intel AMT ACM mode compatibility

---

## How it works

```
make (stage: install-mesh-central)
  ↓
scripts/install-mesh-central/run --build
  ↓
Play 1 (localhost): load YAML + SOPS → extract MeshCentral admin credentials
  ↓
Play 2 (mesh_central group): install-mesh-central.yaml
  Node.js 20 LTS (NodeSource apt repo)
  npm install meshcentral → /opt/meshcentral/
  apply-patches.py → source patches for Intel AMT ACM compatibility
  systemd service with OPENSSL_CONF for legacy TLS renegotiation (AMT)
  node cap_net_bind_service → allows binding to port 443
  Admin account creation via MeshCentral CLI (first run only)
```

---

## Configuration

Config is read from `pwy-home-lab-pkg.yaml` and SOPS secrets under:
```
providers.null.config_params["mesh-central-pkg/_stack/null/examples/example-lab/mesh-central/configure-server"]
```

Required secrets (in SOPS):
- `admin_username` — MeshCentral admin account name (default: `admin`)
- `admin_email` — admin account email
- `admin_password` — admin account password

The `mesh-central` VM is tagged `role_mesh_central` in Proxmox YAML; the
inventory generator uses this tag to populate the `mesh_central` Ansible group.

---

## Source patches

`apply-patches.py` is written to `/opt/meshcentral/apply-patches.py` and run after
each MeshCentral npm install. It patches three files in-place:

| File | Patch | Reason |
|---|---|---|
| `amtmanager.js` | Fix BatchEnum status check | AMT 16.x returns HTTP 400 on `IPS_HostBasedSetupService` in ACM mode; the meaningful check is `AMT_GeneralSettings` |
| `amtmanager.js` | Default `controlMode` to ACM when IPS inaccessible | Prevents CCM fallback on ACM-provisioned devices |
| `meshagent.js` | Preserve `node.host` when AMT credentials configured | Prevents agent reconnect from overwriting the AMT NIC IP with the jump-host IP |
| `commander*.htm` | Use TLS port (16993) when `intelamt.tls==1` | Connect button hardcodes port 16992; TLS-only AMT devices need 16993 |

The script is idempotent: re-running reports `ALREADY_PATCHED` and exits 0.

---

## Commands

```bash
./run --build    # Generate inventory + install/configure MeshCentral
./run --test     # Check web UI reachable at https://<host>:443
./run --deps     # Install Python/Ansible dependencies only
./run --clean    # Remove tmp files
```

---

## Appendix A — Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `mesh_central group not found` | mesh-central VM not yet in inventory | Wait for VM to boot; re-run `scripts/generate_ansible_inventory/run --build` |
| Service not starting | Port 443 bind permission missing | Verify `cap_net_bind_service` is set: `getcap /usr/bin/node` should include `cap_net_bind_service=ep` |
| AMT scanner can't connect | OpenSSL legacy TLS not enabled | Check `OPENSSL_CONF=/opt/meshcentral/openssl-legacy.cnf` in `systemctl cat meshcentral` |
| Intel AMT shows CCM instead of ACM | amtmanager.js patch not applied | Run `sudo python3 /opt/meshcentral/apply-patches.py` on mesh-central; check for CHANGED output |
| node.host overwritten on agent reconnect | meshagent.js patch not applied | Same as above |
