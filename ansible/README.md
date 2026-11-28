# Laptop configuration

This is the first Ansible layer for the repaired Ubuntu 20.04 laptop. It is not
an end-to-end fresh-machine recovery solution yet. Dotbot still manages user links.

## Ubuntu 26.04 profile

The separate Resolute profile is experimental and does not change the default
Focal setup. It starts with Ubuntu-managed repositories only and a small base
package group. No vendor repositories are configured, no partner source is
edited, and package installation remains opt-in.

Create its isolated maintained controller and explicitly run that playbook:

```sh
./ansible/bootstrap-resolute
./ansible/run-resolute --syntax-check
./ansible/run-resolute --check
./ansible/run-resolute --apply --install-packages
```

Emacs/Codex provisioning is separate and opt-in. After private Git access is
configured in the guest, use `./ansible/run-resolute --check --provision-emacs`
then `--apply --provision-emacs` twice; the second apply should report
`changed=0`. Codex sign-in and ACP validation are manual steps; both passed in
the Resolute guest. See
[`../docs/emacs-tools.md`](../docs/emacs-tools.md) for the read-only deploy-key
setup.

Firefox LastPass installation is also opt-in:

```sh
./ansible/run-resolute --check --provision-lastpass
./ansible/run-resolute --apply --provision-lastpass
```

This merges an auto-install policy into `/etc/firefox/policies/policies.json`
without replacing other policies. The extension remains removable. Restart
Firefox, confirm it under `about:policies`, then sign in and complete MFA by hand.
LastPass extension versions follow Mozilla Add-ons updates; credentials are not
managed by Ansible. The same flag is available through the Focal `ansible/run`.

The additional confirmed applications are a separate opt-in:

```sh
./ansible/run-resolute --check --install-additional-apps
./ansible/run-resolute --apply --install-additional-apps
```

This installs Asunder, LibreOffice, Simple Scan, Audacity, and MusicBrainz
Picard. Pandoc and the selected TeX Live subset are part of the main desktop
package group enabled by `--install-apps`, because Emacs uses them for writing
and document export. If this is a fresh install, run this alongside
`--install-apps` to provision the full desktop baseline.
Zoom and Calibre have not yet been added; see
[`../docs/software-inventory.md`](../docs/software-inventory.md) for their
remaining source and update-policy work.

The Resolute environment is `.hatch-resolute`, with Ansible Core 2.21 and
Python 3.12 on the controller. It requires Ubuntu Resolute and a managed-host
Python between 3.9 and 3.14. The regular `.hatch`, `ansible/run`, and Focal
policy are unchanged. A clean Ubuntu 26.04.1 Server cloud-image replay passed on
November 17, 2026: syntax check, check mode, first package application, and repeat
application (`changed=0`). The interactive 26.04.1 Desktop installation and
post-install profile setup also completed; the repeat application passed its
`changed=0` assertion, and the VM restarted, accepted a login, and shut down.
Emacs/Codex provisioning, startup/shutdown, ERT, authenticated ACP, and interactive
Agent Shell also passed in the guest. The newer agent-shell package warning
remains; its old patch was not applied. These runs do not validate XPS hardware
or constitute OS-upgrade tests. The opt-in LastPass Firefox policy was applied;
`about:policies` recognized its extension entry, and the user confirmed the
enabled extension worked. See
[`../docs/ubuntu-26.04-profile.md`](../docs/ubuntu-26.04-profile.md) for the
acceptance gates and third-party review boundary.

The one-use clean cloud-image replay is `./ansible/vm-resolute/run`. It verifies
Canonical's signed Resolute cloud-image checksums, creates a new UEFI guest disk,
captures the current non-ignored dotfiles worktree, bootstraps the controller,
and checks repeat package convergence. It needs KVM access, OVMF, 10 GiB free
space, and host/guest network access to Ubuntu archives, GitHub, and PyPI. The
successful run's evidence is at
`~/.emacs.d/var/vm-resolute-20261117-045406`; other runs are stored under
`~/.emacs.d/var/vm-resolute-*` (override the parent with
`DOTFILES_VM_EVIDENCE_ROOT`). This is a Server cloud image test; it does not
validate the Desktop installer or laptop hardware.

For the interactive Desktop installation path, run
`./ansible/vm-desktop-resolute/run`. It verifies Canonical's signed 26.04.1 ISO,
opens a QEMU window with a blank 40 GiB disk, and attaches the current dotfiles
snapshot as a read-only `DOTFILES` disc. In the installer, choose the VM disk for
installation and create a local test account. After first login, open the
`DOTFILES` volume and run `bash ./provision-from-seed.sh` from its directory; it
bootstraps the Resolute controller and applies the package baseline twice.
If the installer asks to remove its medium, run
`./ansible/vm-desktop-resolute/eject-installer EVIDENCE_DIRECTORY` from the host.
The host-side `stop EVIDENCE_DIRECTORY` and `start-installed EVIDENCE_DIRECTORY`
scripts request guest shutdown and restart the installed VM. The runner needs
KVM, OVMF, a graphical session, at least 20 GiB free, and a network connection.
It defaults to 4 GiB guest RAM; set `VM_MEMORY_MIB=6144` only if the host has
enough memory. It does not install anything to the host disk. The completed run's
evidence is at `~/.emacs.d/var/vm-desktop-resolute-20261117-051623`.
To update the read-only `DOTFILES` disc on that installed VM without reinstalling
Ubuntu, shut it down and run
`./ansible/vm-desktop-resolute/refresh-seed EVIDENCE_DIRECTORY`; it preserves
the original seed as `dotfiles-seed-initial.iso`.

## What this milestone manages

- Reads the same `../config/apt-repositories.json` used by the repository helper.
- Requires Ubuntu and the policy's exact release; refuses an unreviewed release.
- Preflights the four disabled sources before touching them. An active managed
  `.list` is renamed to `.list.disabled`; an existing backup collision, symlink,
  or alternate `.sources` definition requires manual review.
- Comments out active Canonical partner entries in `/etc/apt/sources.list`, with
  an Ansible backup if that file changes.
- Audits small, explicit base and IDrive prerequisite package groups.
- Installs only missing selected packages when explicitly requested; never runs
  general upgrades, removals, APT cache refreshes, IDrive setup, or a restore.

Enabled third-party repositories and signing keys are preserved, not created.
Ubuntu/ESM registration, Chrome, and the toolchain PPA remain outside this role.
Duplicate definitions in other filenames require manual review. The partner rule
handles the main sources file, not every possible deb822 definition.

## Runtime prerequisite

Hatch owns the controller environment directly at the repository root's `.hatch`.
It uses Python 3.12 and the dependencies/scripts declared in `../hatch.toml`.
This is a detached tooling environment: the dotfiles repository is not installed
as a Python package. `pyproject.toml` supplies the project identity and Python
constraint; environment contents are excluded from Git.

The system interpreter `/usr/bin/python3` stays on Python 3.8 for managed-host
modules. The temporary core 2.19 range remains necessary for that target Python;
core 2.20 drops Python 3.8 target support. Core 2.19 maintenance ends in November
2026, so update this runtime policy when migrating Ubuntu rather than treating
it as the permanent version. See the
[Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html).

### Hatch and project activation

Hatch is a shared user-level CLI for all Python projects on the laptop. Install
it with pipx, which owns its isolated application environment and exposes `hatch`
in `$HOME/.local/bin`. Hatch then owns each project's `.hatch` environment;
direnv selects it on directory entry. Do not install Hatch into the project venv.

Shared tool provisioning is declared in `../config/shared-python-tools.json`.
From a normal terminal, `./bootstrap-tools` audits it and
`./bootstrap-tools --apply` provisions the independent Python, isolated pipx,
shared Hatch/PDM/Poetry/pip-tools/Pipenv/python-lsp-server/yamllint commands, and
the private Python 3.9/3.10 runtimes required by Pipfile projects before their
project environments exist. `layout_pipenv` selects the Hatch runtime declared by
each Pipfile and activates an existing environment without installing project
dependencies on directory entry. A missing environment must be created and
synced explicitly; the guide documents the Python 3.9 Pipenv compatibility
workaround. No uv installation is required. The Ansible shared-tools role
consumes this same implementation.
See [the full bootstrap and migration guide](../docs/shared-python-tools.md).

Node.js uses fnm in a separate user-local layer. `./bootstrap-node-tools` audits
fnm and the reviewed project Node versions; `./bootstrap-node-tools --apply`
installs them and sets the outside-project default to the reviewed latest LTS.
The manifest pins Node 26.13.1 until a later LTS update is reviewed. The
existing `.nvmrc` pins are preserved. See [Node.js tooling](../docs/node-tools.md).

Ruby uses the Mise binary already installed for Emacs/Codex tooling. Its tracked
global policy selects Ruby 4.0.9, recognizes project `.ruby-version` and
Gemfile versions, and disables automatic installs. Run
`./bootstrap-ruby-tools` to audit and `./bootstrap-ruby-tools --apply` to
install. RVM startup hooks are retired while `~/.rvm` remains as a local
rollback copy. The interactive shell helper also removes the system profile
hook's RVM effects. See [Ruby version management](../docs/ruby-tools.md).

R uses Rig for user-local R runtimes where portable R supports the host glibc,
and the CRAN `renv` package for project libraries. On older glibc, the bootstrap
uses an exactly matching system R and does not attempt an incompatible portable
build. The legacy `~/.renv` shim checkout and system R are preserved. Projects
opt into runtime selection by adding `use_rig` to `.envrc`, and should commit
reviewed `renv.lock` files. See [R version and package management](../docs/r-tools.md).

The historical Python location is retained as a persistent declared location;
managed pipx applications move off their older pyenv interpreter. Existing
unrelated pipx apps are preserved. Pyenv shell initialization is retired. The
reviewed Pipenv project environments now use Hatch-managed Python 3.9 and 3.10;
the old pyenv checkout and runtimes remain as local recovery copies. Directory
paths, launcher backups, version pins, system prerequisites, and fresh-shell
direnv setup are documented in that guide.

From the repository root, leave the previously activated environment if needed,
then create/synchronize the Hatch environment:

```sh
# Only if the old .venv-ansible environment is currently activated:
deactivate

./ansible/bootstrap
# Review .envrc and config/direnv/direnvrc, then authorize the project:
direnv allow
```

The repository's `.envrc` uses the shared `layout hatch` helper in
`config/direnv/direnvrc`. Once allowed, direnv selects `.hatch/bin` ahead of the
inherited PATH and exports `VIRTUAL_ENV`, `HATCH_ENV`, `HATCH_ENV_TYPE_VIRTUAL_PATH`,
`PYTHONNOUSERSITE`, `PIP_REQUIRE_VIRTUALENV`, `ANSIBLE_CONFIG`, and
`ANSIBLE_INVENTORY`. It unsets `PYTHONHOME`. Changes are unloaded when leaving
the project. Your Antigen configuration already includes the direnv shell hook.
The environment path override keeps inherited Hatch settings from selecting a
virtual environment outside this project.

Activation never downloads packages on `cd`. Run `./ansible/bootstrap` again
when dependencies change; it uses Hatch to create and synchronize the environment
and verifies Python 3.12 and the exact `.hatch` prefix. A missing environment
reports an activation error with instructions. Older direnv may still execute
commands using the inherited PATH after that error, so `ansible/run` explicitly
requires `.hatch/bin/ansible-playbook` and refuses a global fallback.

Verify after direnv loads:

```sh
command -v python ansible-playbook
python -c 'import sys; print(sys.executable); print(sys.prefix)'
printf '%s\n' "$VIRTUAL_ENV" "$ANSIBLE_CONFIG"
./ansible/run --syntax-check
```

Both commands should resolve inside `.hatch/bin`. No manual activation is needed.
Hatch equivalents are `hatch run syntax`, `hatch run preview`, `hatch run apply`,
and `hatch run test`. The wrapper remains available for explicit package opt-in.
The previous `.venv-ansible` is left intact and ignored until migration validation
passes. Do not delete it while it is still activated.

### The same convention in other projects

Use `[envs.default]` with `path = ".hatch"` in `hatch.toml` (or
`[tool.hatch.envs.default]` in `pyproject.toml`). With these dotfiles installed,
project `.envrc` files can use `layout hatch`. Dependencies remain project-specific.
Hatch/direnv itself is installed outside the environments it creates.

The runtime requirement lives only in `hatch.toml`; the separate requirements
file and uv-created controller environment have been superseded. Dependencies
are a reviewed compatibility range, not a locked release snapshot. No external
Ansible collections are required. Secrets belong outside tracked `.envrc` files.

## Preview and application

Run from the repository root:

```sh
# No system privilege required for syntax validation.
./ansible/run --syntax-check

# Default: preview changes only. Sudo password allows inspection of root tasks.
./ansible/run

# Enforce disabled-source policy; packages remain audit-only.
./ansible/run --apply

# Preview or apply the reviewed baseline package groups as well.
./ansible/run --check --install-packages
./ansible/run --apply --install-packages

# On Resolute, opt into the reviewed application groups, including browsers,
# Minikube, Remmina, Parabolic from Flathub, GIMP, Spotify,
# LastPass extension policy, and Caffeine.
# Account sign-in is manual.
./ansible/run-resolute --check --install-apps
./ansible/run-resolute --apply --install-apps
# Use the optional Albert choice instead of default Ulauncher (currently fails closed on Resolute).
./ansible/run-resolute --check --install-apps --install-albert
./ansible/run-resolute --check --install-mongodb
./ansible/run-resolute --check --install-google-cloud

# Preview/apply shared Python, pipx, and Hatch provisioning independently.
./ansible/run --check --provision-tools
./ansible/run --apply --provision-tools

# Audit is automatic; explicitly enable Emacs/Codex provisioning.
./ansible/run --check --provision-emacs
./ansible/run --apply --provision-emacs

# Install the removable LastPass Firefox extension policy; sign-in is manual.
./ansible/run --check --provision-lastpass
./ansible/run --apply --provision-lastpass
```

Check mode does not change system configuration, but Ansible may create temporary
execution files. All managed-host modules use `/usr/bin/python3` explicitly even
when the controller uses the virtual environment. No passphrases are stored in
inventory. Run from a normal terminal: this agent session cannot use sudo or
reach external download services.

Review output before application. On the repaired laptop, repository enforcement
should report no changes. Run application twice to establish convergence; the
second run should report `changed=0`. On the repaired laptop, syntax validation,
check mode, and two consecutive application runs have now passed. Each preview
and application recap reported `ok=16 changed=0 unreachable=0 failed=0 skipped=2`;
no baseline packages were missing and package installation was disabled.
These no-change runs verify the existing baseline, not provisioning from an
unconfigured machine or the optional package-installation path.
Ansible stops after a failed task; do not bypass failures with `ignore_errors`.

## Configuration

- `group_vars/all.yml`: reviewed package groups and shared policy loading.
- `inventories/local.yml`: this laptop over the local connection.
- `laptop.yml`: platform and policy checks followed by repository, package, shared-tool and Emacs roles.
- `roles/repositories`: disabled-source enforcement.
- `roles/packages`: package audit and optional installation.
- Resolute-only `roles/application_tools`: Firefox stable Snap and LastPass
  extension policy, Google Chrome from Google's signed stable APT source,
  GIMP and Spotify stable Snaps, pinned Minikube release binary, Remmina and
  its selected protocol plugins from Ubuntu, opt-in kubectl and Google Cloud
  Snaps, Parabolic from Flathub, Bruno, the pinned Ulauncher
  Resolute development package, and the
  reviewed MongoDB 9 source/key. Albert
  settings and web searches seed only absent config files; Caffeine comes from
  Ubuntu's archive. GNOME shortcut setup
  preserves existing custom bindings and is applied only inside the logged-in
  user's session. The obsolete X11-only window-switcher is excluded. See
  [system application policy](../docs/system-applications.md).
- `roles/shared_tools`: shared tool audit and opt-in provisioning using the root bootstrap.
- `roles/emacs_tools`: complete Emacs checkout, standalone Codex/Mise and ACP provisioning.
  See [Emacs recovery and validation](../docs/emacs-tools.md), including manual sign-in
  and the current Snap/ACP validation blockers.

Select packages intentionally; the historical full installer is not a package
manifest. Credentials, IDrive configuration, encryption keys, private keys, and
machine-specific secrets stay outside Git.

## Validation available without Ansible

```sh
bash -n .envrc config/direnv/direnvrc ansible/run ansible/bootstrap
shellcheck ansible/run ansible/bootstrap
python ansible/tests/test_foundation.py
python3 tests/test_repositories.py
python tooling/test_shared_tools.py
python tooling/test_emacs_tools.py
```

These checks cover YAML parsing, preview/apply command dispatch, package opt-in,
partner-source matching, and real direnv activation using isolated test projects. They do not replace Ansible syntax validation,
check mode, or real convergence testing.

## Next milestones

1. Commit the validated Hatch/direnv migration and update the draft PR.
2. Validate archive installation on a clean test system; shared-tool application
   and convergence have passed on this laptop. Review enabled sources and keys.
3. Move enabled-source URLs and key identities into shared policy and implement
   their fresh-machine provisioning, including duplicate-source checks.
4. Inventory optional application groups and add user, update, service, backup,
   and hardware roles. Keep credentials and data restoration separate.
5. Select a supported Ubuntu LTS and test its profile on a clean VM plus hardware.
