# Repaired Ubuntu APT baseline

This records the existing laptop after the package-repair checkpoint. It is an
observed baseline and a starting point for declarative configuration, not a
complete fresh-machine installation specification.

## Repository policy

| Source | Current state | Rebuild policy |
| --- | --- | --- |
| Ubuntu Focal, updates, security, backports | Enabled | Match the installed Ubuntu release |
| Ubuntu Pro ESM Apps and Infrastructure | Enabled | Enroll using recoverable account credentials; never commit tokens |
| Canonical partner | Disabled after connection failures | Leave disabled unless an application requires it and availability is verified |
| Albert, R, RVM, LLVM Bionic sources | Renamed to `.list.disabled` | Leave disabled pending application and supported-release review |
| Chrome, Brave, Yarn, Google Cloud | Enabled | Review necessity, signing keys, and supported release before recreating |
| MongoDB 5.0 | Enabled | Review database usage and migration separately; do not silently change database major version |
| Toolchain test PPA | Enabled, Focal | Explicit opt-in only; current GDB came from this PPA |

The filename `ubuntu-toolchain-r-ubuntu-test-bionic.list` and its trailing
`disabled on upgrade` comment are misleading: the active entry uses Focal and is
not commented out. Do not infer repository state from filenames or comments.

The root sources file retains the partner entry as a comment. A pre-change copy
was saved as `/etc/apt/sources.list.before-partner-disable`. The four disabled
third-party files preserve their previous definitions for reference.

## Package repair

The four installed Bionic packages `python3.8`, `python3.8-minimal`,
`libpython3.8-minimal`, and `libpython3.8-stdlib` were replaced together with
Focal ESM version `3.8.10-0ubuntu1~20.04.18+esm7`; matching `libpython3.8` was added.
This exact version documents the repair, not a permanent version pin. Future
maintenance should use compatible, supported candidates from the intended release.

The system Python remains `/usr/bin/python3`. User Python environments should be
managed separately; do not redirect the system interpreter to pyenv or Conda.

Subsequent upgrades resolved libpeas, GDB, and Samba packages. Samba's dependency
transition replaced `libldb1` with `libldb2` and added Python 3 dependencies.
The final reported state has no pending upgrades in currently enabled sources,
no dependency errors, and no incomplete packages. Disabled sources are excluded
from that claim. Automatic removal has not been performed.

## Requirements for the next configuration change

- Replace the legacy helper's unconditional source declarations with explicit
  enabled/disabled repository policy before using its `--apply` mode.
- Keep account secrets and machine-specific credentials outside Git.
- Install reviewed application groups, not the entire historical package list.
- Keep system configuration separate from user dotfile linking and data restores.
- Test convergence on a supported Ubuntu LTS and verify hardware on this laptop.
- Review unattended update behavior on battery/AC power and verify later successful
  IDrive backups rather than assuming the manual backup fixed scheduling.
