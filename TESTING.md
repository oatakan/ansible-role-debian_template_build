# Testing Guide for debian_template_build Role

This document explains the testing strategy for the `oatakan.debian_template_build` Ansible role.

## Overview

This role prepares Debian-family VM templates. Some tasks (e.g., kernel headers, disk cleanup) are VM-oriented and are not suitable for container environments.

Testing is split into:

- **Static analysis**: `yamllint`, `ansible-lint`, and playbook `--syntax-check`
- **Container testing**: Molecule Docker scenario for Debian + Ubuntu

## CI

GitHub Actions runs:

- Linting (`yamllint`, `ansible-lint`)
- Syntax check (`ansible-playbook --syntax-check`)
- Molecule Docker matrix:
  - `debian:12`
  - `ubuntu:22.04`
  - `ubuntu:24.04`

## Running Tests Locally

### Prerequisites

```bash
pip install ansible ansible-lint yamllint
pip install molecule molecule-plugins[docker]
ansible-galaxy collection install community.general community.docker ansible.posix

docker --version
```

### Linting

```bash
yamllint .
ansible-lint
```

### Syntax check

```bash
mkdir -p /tmp/roles
ln -sf "$(pwd)" /tmp/roles/oatakan.debian_template_build
ANSIBLE_ROLES_PATH=/tmp/roles ansible-playbook -i tests/inventory tests/test.yml --syntax-check
```

### Molecule (Docker)

```bash
mkdir -p /tmp/roles
ln -sf "$(pwd)" /tmp/roles/oatakan.debian_template_build

# Debian 12
ANSIBLE_ROLES_PATH=/tmp/roles MOLECULE_DISTRO=debian:12 molecule test -s default

# Ubuntu
ANSIBLE_ROLES_PATH=/tmp/roles MOLECULE_DISTRO=ubuntu:22.04 molecule test -s default
```

## Notes on Container Testing

The Molecule scenario disables VM-only operations via role vars:

- `install_kernel_headers: false` (container kernel headers don’t match apt packages)
- `zero_free_space: false` (avoid filling container disk)
- `enable_grow_part: false` (avoid system/disk behaviors that aren’t meaningful in containers)

Ubuntu-specific netplan configuration remains enabled and is asserted in `verify.yml`.
