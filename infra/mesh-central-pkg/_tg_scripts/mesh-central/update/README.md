# update-mesh-central

Enrolls all hosts tagged `role_mgmt_group_FOO` into MeshCentral as managed
remote devices, and configures Intel AMT credentials for machines that support
out-of-band management.

## How it works

1. **Generates the Ansible inventory** from Terraform GCS state and YAML config
   so that all managed hosts (MaaS machines and Proxmox VMs) and their IPs are
   current.

2. **Creates or reuses MeshCentral device groups** — one per `mgmt_group_*`
   Ansible group found in the inventory (e.g. `mgmt_group_ms01`,
   `mgmt_group_vms`).

3. **Cleans up stale nodes** — if a host moved to a different group or was
   removed from the inventory, its old MeshCentral node entry is deleted.

4. **Installs the MeshCentral agent** on every host in every `mgmt_group_*`
   group via SSH (routed through the MaaS server as a jump host for
   VLAN-isolated machines). Re-running is safe — hosts already enrolled in the
   correct group are skipped; hosts enrolled in the wrong group are
   automatically reinstalled into the correct group.

5. **Configures Intel AMT credentials** in MeshCentral for any machine whose
   YAML config has `power_type: amt`. MeshCentral's AMT manager then attempts
   out-of-band connectivity automatically.

## Usage

```bash
./run --build      # Regenerate inventory and enroll all managed hosts
./run --test       # Verify the agent is running on each host
./run --deps       # Install Python and Ansible requirements only
./run --status     # Show the current inventory file
./run --clean      # Remove tmp files
./run --clean-all  # Remove tmp files and Python venv
make               # Equivalent to --build then --test
```

## What hosts are enrolled

Hosts are enrolled when they carry a tag matching `role_mgmt_group_<name>` in
their config. The tag can be set in two places:

- **MaaS machines**: `additional_tags` under
  `providers.maas.config_params[<unit_path>]` in `pwy-home-lab-pkg.yaml`
- **Proxmox VMs**: `additional_tags` under
  `providers.proxmox.config_params[<unit_path>]` in `pwy-home-lab-pkg.yaml`

The inventory generator picks these up and places each host in the Ansible
group `mgmt_group_<name>`. All such groups are enrolled automatically — no
code change is needed to add a new group.

Currently enrolled groups:
- `mgmt_group_ms01` — ms01-02 (Minisforum MS-01 physical server, VLAN 12)
- `mgmt_group_vms` — Proxmox VMs tagged at the `pve-1` level

## Intel AMT configuration

Machines with `power_type: amt` in their YAML config also get their AMT
credentials (`power_user` / `power_pass` from SOPS secrets) and their AMT NIC
IP (`power_address`) configured in MeshCentral via the `changedevice` WebSocket
API. MeshCentral's AMT manager then connects to the AMT host and enables
out-of-band power/KVM control in the GUI.

### AMT and agent IP differences

On machines where the MeshAgent connects via a jump host (e.g. the MaaS server
at VLAN 12), the agent's connecting IP differs from the AMT NIC IP. Setting
`power_address` (the AMT NIC IP) as `node.host` via `changedevice` tells the
AMT scanner where to reach AMT.

A patch to MeshCentral (`meshagent.js`) prevents the agent's connection IP from
overwriting the configured AMT NIC IP on each reconnect. A second patch
(`amtmanager.js`) handles `IPS_HostBasedSetupService` returning HTTP 400
`AccessDenied` on ACM-provisioned devices (AMT 16.x), which is normal behaviour
once provisioning is complete. Both patches are applied by `install-mesh-central`
automatically after npm install.

## Prerequisites

- MeshCentral is installed and the service is running (`install-mesh-central`
  must have been run first).
- The MaaS server (jump host at `maas_server_ip`) is up and reachable.
- All managed hosts are deployed and SSHable (Ubuntu).
- MeshCentral admin credentials are in the SOPS secrets file under:
  `providers.null.config_params["mesh-central-pkg/_stack/null/examples/example-lab/mesh-central/configure-server"]`
- AMT credentials for physical machines are in SOPS under:
  `providers.maas.config_params["maas-pkg/_stack/maas/examples/example-lab/machines/<name>"]`
  keys `power_user` and `power_pass`

## Connecting to enrolled devices

After enrollment, open MeshCentral at `https://<mesh-central-ip>` and navigate
to the relevant device group (e.g. `mgmt_group_ms01`) to see and connect to
enrolled hosts. For AMT-capable machines, the AMT tab provides out-of-band
power control and KVM access.
