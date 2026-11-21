# Next recovery milestone: Ubuntu 26.04 LTS profile

## Target

Build a separate Ubuntu 26.04.1 LTS profile on the `feature/ubuntu-26-04-profile`
branch. Preserve the proven Focal profile until the new profile passes clean-VM and
laptop hardware checks. Do not point the installed laptop at the new profile or
upgrade it as part of this milestone.

Ubuntu 26.04 LTS was released April 23, 2026; Canonical lists standard support
through May 2031. Ubuntu 26.04.1 desktop was released August 27, 2026. Ubuntu
24.04 remains supported through May 2029, but has a shorter remaining standard
support window. This milestone selects 26.04.1 for the fresh-install profile and
will validate the XPS 13 9380 by booting live media before considering an OS change.
See [Ubuntu release lifecycle](https://ubuntu.com/about/release-cycle),
[release list](https://ubuntu.com/project/docs/release-team/list-of-releases/), and
[Ubuntu 26.04.1 Desktop](https://ubuntu.com/download/desktop).

## Current boundary

`ansible/laptop.yml`, `config/apt-repositories.json`, and the package/repository
roles enforce Focal and encode historical source filenames. Keep that policy
isolated. A 26.04 run must require `resolute` and must never derive a release by
rewriting a Focal/Bionic source URL. Enabled vendor sources and keys remain
unmanaged until each vendor's 26.04 support, signing instructions, and source
format are reviewed. The old MongoDB 5.0, Yarn, RVM, Google Cloud, Brave, browser
and compiler sources are not copied forward. MongoDB 9.0 is separately declared
as an opt-in Resolute source; see [system application policy](system-applications.md).

An initial separate profile entry point and repository policy now exist:
`ansible/resolute.yml`, `ansible/run-resolute`, and
`config/apt-repositories-resolute.json`. It manages only Ubuntu's own sources and
a small package baseline; package installation is opt-in. The MongoDB source is
declared separately and remains opt-in; Canonical partner entries are left untouched. The normal
Focal entry point remains the default. This profile passed a clean Ubuntu 26.04.1
Server cloud-image replay on November 17, 2026. Laptop hardware and the Desktop
installer have not been validated.

The clean VM runner is `ansible/vm-resolute/run`. It verifies signed Ubuntu cloud
image checksums, bootstraps Ansible Core 2.21.6 in `.hatch-resolute`, then runs
syntax check, check mode, and two package applications on a fresh virtual disk.
The run passed: check mode found only `zsh` missing, the first apply installed
it, and the repeat reported `changed=0 failed=0`. Guest root used 2.5 GiB of its
19 GiB filesystem. Evidence is at
`~/.emacs.d/var/vm-resolute-20261117-045406`, including the dotfiles worktree
snapshot hash and source status. This is a Server cloud-image test, not a Desktop
installer or laptop hardware test.

The interactive Desktop installer runner is `ansible/vm-desktop-resolute/run`.
It verifies the signed 26.04.1 Desktop ISO, launches a new 40 GiB UEFI guest disk,
and attaches the current dotfiles snapshot for post-install profile validation.
The interactive install and profile setup completed on November 17, 2026. The
guest emitted `RESOLUTE_DESKTOP_PROFILE_SETUP_COMPLETE` after syntax check,
check mode, package application, and the repeat `changed=0` assertion. Evidence
is at `~/.emacs.d/var/vm-desktop-resolute-20261117-051623`. The VM was shut down,
restarted, accepted a login, and shut down again. Emacs/Codex was provisioned
in the guest; startup/shutdown, ERT, authenticated ACP, and interactive Agent
Shell all passed. Agent-shell 20261113.1059 remains unpatched because the
temporary patch does not support that version. This does not substitute for
live-booting the XPS. The
`ansible/vm-desktop-resolute/refresh-seed` helper updates the read-only `DOTFILES`
disc for another provisioning pass without reinstalling the guest OS. An opt-in
Firefox policy installed the removable LastPass extension in the guest. Firefox
reported `ExtensionSettings` for `support@lastpass.com`, and the user confirmed
the enabled extension opened and worked.

## Controller and host Python

The existing controller is Ansible Core 2.19, kept only to support Focal's system
Python 3.8. The separate profile selects Ansible Core 2.21 in `.hatch-resolute`,
with Python 3.12 on the controller. The managed-host guard accepts Python 3.9–3.14,
matching the official Core 2.21 support matrix. The clean Resolute replay passed
the managed-host Python guard. The separate range leaves the Focal constraint
unchanged.
See the [Ansible release/support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html).

The standalone shared-tools bootstrap uses Python 3.8-compatible syntax and was
run on Focal. Validate it on Resolute's system Python, the 26.04 tarfile extractor,
package names, `/usr/bin/python3`, Snap, and all Ansible modules. Preserve the
independent Python 3.12/pipx/Hatch design.

## Work sequence and acceptance

1. Inventory 26.04 hardware and OS facts in a live USB on the XPS:
   Wi-Fi, suspend/resume, graphics, audio, webcam, fingerprint reader, dock/USB-C,
   external display, battery, firmware and encrypted storage.
2. Completed: the separate profile's release guard, maintained controller, and
   repository/package roles passed a clean Resolute cloud-image replay. Audit
   third-party repository support independently; default unverified vendors to absent.
3. Completed: interactive Desktop installation and Resolute profile setup passed,
   including repeat convergence and VM restart/login/shutdown. Emacs/Codex
   provisioning, startup/shutdown, ERT, authenticated ACP, and interactive Agent
   Shell also passed, as did LastPass policy recognition and extension use.
   Review the newer package warning and Snap recovery notes.
4. Live-boot the laptop and compare hardware results with Focal. Back up and verify
   user data and credentials before any in-place upgrade or reinstall decision.

Passing the VM establishes software repeatability, not laptop hardware support or
successful migration. Keep those as separate acceptance gates. This branch is the
profile foundation only; no OS upgrade has been performed.
