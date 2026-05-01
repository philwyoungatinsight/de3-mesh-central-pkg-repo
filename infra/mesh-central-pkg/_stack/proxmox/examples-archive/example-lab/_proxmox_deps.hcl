# _proxmox_deps.hcl — include in every proxmox unit in your deployment package.
#
# In a real deployment, uncomment the dependencies block below and set the path
# to your configure-proxmox unit so that Proxmox is configured before any VMs
# are created or destroyed.
#
# Example:
#   locals {
#     _stack_root = dirname(find_in_parent_folders("root.hcl"))
#   }
#   dependencies {
#     paths = [
#       "${local._stack_root}/infra/<your-pkg>/_stack/null/<your-region>/proxmox/configure-proxmox",
#     ]
#   }
