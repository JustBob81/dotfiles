# Laptop configuration and recovery

## Step 1: make configuration changes reviewable

The default `./install` now applies user dotfile links only. It does not add
repositories, install packages, upgrade the system, or run non-package installers.
Shell errors are visible. The original combined configuration is preserved in
`legacy-system-install.conf.yaml` for inventory/reference only. Do not run it:
its shell commands continue after failures and include broad package upgrades.

Inspect declared repositories without root or network access:

```sh
./add_repositories.sh --check
```

This compares source definitions and checks for missing/empty key files. It does
not establish remote availability, key freshness, or successful APT refreshes.
At the initial assessment, four live sources differed: Albert, R, RVM, LLVM
(Bionic vs Focal). They are now disabled; see [the repaired APT baseline](apt-baseline.md).

Repository states are now declared in `config/apt-repositories.json`. The helper
keeps Albert, R, RVM, and LLVM disabled, preserving their source files as
`.list.disabled`. Existing disabled backups are not overwritten. Enabled source
URLs still come from the transitional helper; other entries in `external_sources`
are documented policy only and are not changed by it.

The explicit `sudo ./add_repositories.sh --apply` path is not needed on the
repaired laptop: read-only inspection already matches its policy. Before using
it on another installation, review enabled vendor endpoints and signing keys.
The helper stages enabled keys and disabled-source checks before live writes;
failed downloads or invalid keys stop the script. Changed files are replaced
individually by rename, not as one transaction across all files. Alternate deb822
files for disabled repositories require manual review rather than being silently
modified.

Application is limited to Focal until repository compatibility is reviewed for
the next release. This is a transitional repair, not the final Ansible setup.
Repository endpoints, MongoDB version policy, expired/revoked keys, duplicate
sources outside the managed filenames, and the existing toolchain PPA still need
review before application. The helper no longer implicitly enables the toolchain
test PPA or triggers its automatic APT refresh. Existing PPA settings are untouched.
The previous Kubernetes and GitHub declarations remain inactive.

Validation:

```sh
bash -n add_repositories.sh
shellcheck add_repositories.sh
python3 tests/test_repositories.py
```

## Verified checkpoints

- IDrive account login and backup location were restored. A manual backup reported
  431,637 files considered, 183,086 uploaded, and zero failures.
- A downloaded copy of `docs/recovery-plan.md` had the same SHA-256 hash as the
  original. This verifies that file, not every backed-up file or full recovery.
- APT refresh completes without warnings after disabling the unavailable partner
  source and four sources for the wrong Ubuntu release.
- The Bionic Python 3.8 packages were replaced with matching Focal ESM packages.
  System Python imports `apt` successfully.
- Pending updates, including GDB and Samba libraries, were installed. The user
  verified `sudo apt-get check` succeeds and `dpkg --audit` produces no output.

Backup coverage, unattended backup execution, independent credential recovery,
and a second copy of irreplaceable data still need verification. Repository and
application inventory remains necessary before building the Ansible configuration.

## Remaining work, in order

1. Verify IDrive selection, recent runs, exclusions, recovery credentials, and
   restore representative recent and versioned files to a separate location.
   Make a second copy of irreplaceable data before package repair or reinstall.
2. Inventory intended applications and services; review third-party endpoints
   against vendor instructions. Resolve current APT refresh failures explicitly.
3. Repair the installed Bionic Python 3.8 packages using a simulated and reviewed
   coordinated transaction, then complete pending updates. Do not remove Python
   blindly or change `/usr/bin/python3` manually.
4. Introduce Ansible roles for repositories, selected packages, services,
   security/update policy, user configuration, backups, and hardware differences.
   Keep Dotbot for links initially. Separate desktop essentials from optional
   databases, containers, language tools, and large applications such as TeX.
5. Resolve disk-space pressure, firmware refresh failures, Postfix configuration,
   Brother scanner rules, and remaining Bluetooth issues. Verify firewall and
   Livepatch state from an unrestricted local terminal.
6. Choose a supported Ubuntu LTS after VM and live-USB validation. Test the setup
   on a clean installation and repeat it to check for unexpected changes.
7. Document data/secret restoration and manual steps. Demonstrate recovery before
   reinstalling this laptop. Adopt Autoinstall only after the setup is reliable.

Configuration in Git, encrypted data backups, and independently recoverable
credentials are separate requirements. None substitutes for the others.


## Ansible foundation

The first Ansible profile is in [`ansible/README.md`](../ansible/README.md).
It consumes the shared repository-state policy, enforces disabled legacy/partner
sources, and audits reviewed base and backup prerequisite packages. Package
installation requires a separate opt-in. Dotbot remains responsible for links.

Hatch owns the project-local `.hatch` environment selected by direnv. With
Python 3.12.16 and Ansible core 2.19.15, syntax validation, a check-mode preview,
and two consecutive application runs passed. Each preview/application reported
`changed=0 failed=0`, with no missing baseline packages and installation disabled.
This verifies repeatability on the repaired laptop, not fresh provisioning.
The Focal profile is not yet the fresh-machine recovery solution. Enabled-source/key
provisioning and supported-LTS profiles remain subsequent milestones.


## Shared tool provisioning

The shared tooling branch declares persistent user-level Python, pipx, and CLI tools in
`config/shared-python-tools.json`, with a standard-library bootstrap usable before
Ansible exists. direnv is a declared APT prerequisite. The default run only audits;
`--provision-tools` explicitly enables user-level provisioning. The old Python
location and pipx application home are retained to preserve dependents. Pyenv shell
initialization is retired and all managed pipx apps have moved to the declared
Python. Existing project virtual environments still point to pyenv's Python 3.9.2
and 3.10.0; preserve those runtime files until those project environments migrate.
No uv
installation is needed on a fresh machine. See
[shared Python tooling](shared-python-tools.md) for preview and validation steps.
Live provisioning succeeded on the repaired laptop: one changed task on first
application, then `changed=0 failed=0` on the repeat. The shared tools audit now
reports no drift across all declared CLI apps. Fresh-machine archive installation
and a complete restore still need validation.


## Emacs and Codex provisioning

The complete private `~/.emacs.d` checkout and both remotes are now declared in
`config/emacs-tools.json`. Its sources remain in that repository. The opt-in
`--provision-emacs` role preserves existing checkouts and provisions standalone
Codex, Mise, repository-owned links, and the manifest-selected ACP runtime.
The historical emacs-local repository is superseded. See
[Emacs recovery](emacs-tools.md) for commands, package patch guards, authentication,
validation blockers, and the limits of version pinning. Current Snap execution
and authenticated ACP validation must be repeated in a normal local terminal
before this recovery checkpoint can be considered complete.
See [credential and secret recovery](credential-recovery.md) for LastPass,
`authinfo.gpg`, SSH/GPG key migration, and IDrive recovery boundaries.

Fresh-VM testing found gaps hidden by the repaired laptop. Dotfiles now handles
internal Python archive aliases, a longer bounded cold package bootstrap, and
clearer command-failure reporting. The Emacs `session` dependency fix is committed
as `4d1c0d58e466ccf65786c9dbdac54bc35fe4e23f`, now selected by the initial-revision
pin. The Emacs session reports startup/shutdown and all three ERT tests passed. The VM's successful
continuation required retries and a signed Snap workaround; it is not clean replay
evidence. See [the November 16 VM findings](vm-test-20261116.md).


## Supported Ubuntu profile milestone

The clean Focal recovery replay passed. The next profile is Ubuntu 26.04.1 LTS on
`feature/ubuntu-26-04-profile`, selected for its longer standard-support runway.
The separate Resolute profile passed both a clean Ubuntu 26.04.1 Server cloud-image
replay and the interactive Desktop install/profile setup. The Desktop guest emitted
`RESOLUTE_DESKTOP_PROFILE_SETUP_COMPLETE` after its repeat package run passed
`changed=0`. The guest then passed restart/login/shutdown and Emacs/Codex
provisioning, startup/shutdown, ERT, authenticated ACP, and interactive Agent
Shell checks. Next live-boot the XPS 13 9380 and check its hardware. Keep the
validated Focal profile as-is.
Vendor repositories and packages need fresh compatibility review; do not carry
Bionic/Focal endpoints forward by string substitution. See
[the 26.04 profile milestone](ubuntu-26.04-profile.md).
