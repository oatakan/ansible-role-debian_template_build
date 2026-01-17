# Tart Molecule scenario

This scenario is a local harness for running the role against a Tart VM on macOS.

Molecule does not ship with a built-in Tart driver (like `docker` or `vagrant`).
This scenario uses the delegated driver plus scenario playbooks that call the `tart` CLI to:

- create a VM (import or clone)
- start it
- discover its IP (`tart ip`)
- run the role via SSH
- stop and delete the VM

## Requirements

- macOS host with `tart` installed and working
- `sshpass` on the controller (used for password-based SSH)

## Usage

Run from the repo root.

### Option A: Import from a `.tvm`

```bash
MOLECULE_TART_IMPORT_TVM=/path/to/your-image.tvm \
MOLECULE_TART_VM=debian-template-molecule \
MOLECULE_TART_USER=vagrant \
MOLECULE_TART_PASSWORD=vagrant \
molecule test -s tart
```

### Option B: Clone an existing Tart VM template

```bash
MOLECULE_TART_SOURCE_VM=your-base-vm-name \
MOLECULE_TART_VM=debian-template-molecule \
MOLECULE_TART_USER=vagrant \
MOLECULE_TART_PASSWORD=vagrant \
molecule test -s tart
```

## Notes

- The scenario writes its target host IP into `molecule/tart/state.yml` during `create`.
- `molecule/tart/converge.yml` disables `zero_free_space` to keep runs fast.
