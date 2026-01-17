# oatakan.debian_template_build


[![Ansible Role Version](https://img.shields.io/github/v/tag/oatakan/ansible-role-debian_template_build?label=version)](https://galaxy.ansible.com/oatakan/debian_template_build)
[![CI](https://github.com/oatakan/ansible-role-debian_template_build/actions/workflows/ci.yml/badge.svg)](https://github.com/oatakan/ansible-role-debian_template_build/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Role Downloads](https://img.shields.io/ansible/role/d/oatakan/debian_template_build?label=downloads&logo=ansible)](https://galaxy.ansible.com/oatakan/debian_template_build)

This role transforms a minimal Debian-family system into a VM template that can be safely cloned. It is intended for use in image build pipelines (Packer, CI/CD, internal template build tooling) and focuses on:

- Consistent SSH configuration for automation
- Optional cloud-init setup
- Guest agent installation for specific virtualization targets (oVirt/QEMU, Tart)
- Cleanup tasks for template safety (machine-id reset, SSH host key regeneration on next boot)

## Supported Systems

This role is designed for and tested on Debian-family systems:

### Primary Target

- Debian 12
- Ubuntu 22.04
- Ubuntu 24.04

Automated tests run in containers (Molecule + Docker). A delegated Tart scenario is also provided for macOS-based image builds.

## Requirements

- Ansible (recommended: ansible-core >= 2.14)
- Root privileges on the target system
- Collections used by this role/tests:
  - community.general
  - ansible.posix

Optional (for guest tools scenarios): access to a virtualization platform (oVirt/QEMU, Tart, VMware/VirtualBox/Parallels).

## Role Variables

The most common variables are listed below. See [defaults/main.yml](defaults/main.yml) for the full list and defaults.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| target_vagrant | false | When true, Vagrant user configuration is enabled (used in some image pipelines). |
| target_ovirt | false | Enables oVirt/QEMU guest agent setup. |
| target_tart | false | Installs and enables a guest agent suitable for Tart-built images (see options below). |
| enable_cloud_init | false | Enables cloud-init configuration where applicable. |
| local_account_username | ansible | User name used by some guest-tool checks and file ownership operations. |
| vmware_install_open_vm_tools | true | Install Open VM Tools when VMware is detected (where supported by the platform). |

### Container/test safety toggles

The role is primarily intended for VM template preparation. Some steps do not make sense in containerized tests; these toggles let CI/Molecule disable them.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| install_kernel_headers | true | Installs kernel headers for the running kernel (commonly disabled in containers). |
| zero_free_space | true | Fills free space with zeros to improve image compression (disabled in most tests). |
| configure_netplan | true | Applies netplan settings on Ubuntu only. |
| enable_grow_part | true | Configures grow-part-on-boot behavior for cloud images. |
| reset_machine_id | true | Resets machine-id related artifacts so clones get fresh identity. |

### Tart guest agent options

When `target_tart: true`, the role can install the guest agent in one of the following ways:

- `tart_guest_agent_install_method: repo` (default) installs `qemu-guest-agent` from OS repositories.
- `tart_guest_agent_install_method: github` installs CirrusLabs `tart-guest-agent` from GitHub releases.
- `tart_guest_agent_install_method: auto` tries GitHub first, then falls back to repo.

Relevant variables:

- `tart_guest_agent_install_method` (`repo|github|auto`)
- `tart_guest_agent_package_name` / `tart_guest_agent_service_name` (repo path)
- `tart_guest_agent_github_repo` (default `cirruslabs/tart-guest-agent`)
- `tart_guest_agent_github_release` (default `latest`)
- `tart_guest_agent_base_url_override` (skip GitHub API; provide a precomputed base URL without the `.deb` suffix)
- `tart_guest_agent_github_service_name` (default `tart-guest-agent`)

## Dependencies

If Parallels guest tools are required, ensure the role referenced by `parallels_tools_role` is available (default: `oatakan.linux_parallels_tools`).

## Example Playbook

```yaml
- name: Build Debian/Ubuntu template
  hosts: all
  become: true
  roles:
    - role: oatakan.debian_template_build
      vars:
        target_vagrant: false
        target_ovirt: false
        target_tart: false
        enable_cloud_init: true
```

## Testing

### Local lint and syntax check

This repository is structured as an Ansible role (Galaxy name: `oatakan.debian_template_build`). A convenient way to run lint and syntax checks locally is to create a temporary roles directory and point `ANSIBLE_ROLES_PATH` at it.

```bash
tmp_dir=$(mktemp -d)
mkdir -p "$tmp_dir/roles"
ln -s "$(pwd)" "$tmp_dir/roles/oatakan.debian_template_build"

ANSIBLE_ROLES_PATH="$tmp_dir/roles" ansible-lint
ANSIBLE_ROLES_PATH="$tmp_dir/roles" ansible-playbook -i tests/inventory tests/test.yml --syntax-check
```

### Molecule (Docker)

```bash
python -m pip install --upgrade pip
pip install 'ansible-core>=2.14,<2.17' molecule molecule-plugins[docker]
ansible-galaxy collection install community.general community.docker ansible.posix

molecule test --scenario-name default
```

### Molecule (Tart on macOS)

The Tart scenario is a delegated driver that uses the `tart` CLI to create/clone a VM, then provisions it over SSH.

Requirements:

- macOS host with `tart` installed
- `sshpass` available on the controller (password-based SSH)

Run with a pre-existing Tart VM as the source (recommended, avoids passing host paths):

```bash
MOLECULE_TART_SOURCE_VM=<existing_tart_vm_name> \
MOLECULE_TART_VM=molecule-ubuntu-24-04 \
MOLECULE_TART_USER=vagrant \
MOLECULE_TART_PASSWORD=vagrant \
MOLECULE_TART_BECOME_PASSWORD=vagrant \
MOLECULE_TART_AGENT_METHOD=auto \
molecule test -s tart
```

Alternatively, you can import a `.tvm` into Tart first and then use it as `MOLECULE_TART_SOURCE_VM`. If you use `MOLECULE_TART_IMPORT_TVM`, note that the scenario overwrites the inventory state file during `molecule create`; do not commit local state.

### Testing Coverage

The automated and local test tooling is intended to validate:

- Debian 12 and Ubuntu (22.04, 24.04) using Molecule with Docker
- Template-safety behaviors (SSH hardening, machine-id reset, SSH host key regeneration on next boot)
- Tart provisioning path using the delegated Molecule Tart scenario on macOS

## License

MIT

## Author Information

Orcun Atakan

