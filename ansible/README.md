# Laptop configuration: first Ansible milestone

This is the first Ansible layer for the repaired Ubuntu 20.04 laptop. It is not
an end-to-end fresh-machine recovery solution yet. Dotbot still manages user links.

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

Shared tool provisioning is now declared in `../config/shared-python-tools.json`.
From a normal terminal, `./bootstrap-tools` audits it and
`./bootstrap-tools --apply` provisions the independent Python, isolated pipx,
and shared Hatch command before the project environment exists. No uv installation
is required. The Ansible shared-tools role consumes this same implementation.
See [the full bootstrap and migration guide](../docs/shared-python-tools.md).

The historical Python location is retained as a persistent declared location;
pipx moves off its older pyenv interpreter. Existing unrelated pipx apps are
preserved. Directory paths, launcher backups, version pins, system prerequisites,
and fresh-shell direnv setup are documented in that guide.

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
`config/direnv/direnvrc`. Once allowed, direnv selects `.hatch/bin` ahead of pyenv
shims and exports `VIRTUAL_ENV`, `HATCH_ENV`, `HATCH_ENV_TYPE_VIRTUAL_PATH`,
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

# Preview/apply shared Python, pipx, and Hatch provisioning independently.
./ansible/run --check --provision-tools
./ansible/run --apply --provision-tools
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
- `laptop.yml`: platform and policy checks followed by the two roles.
- `roles/repositories`: disabled-source enforcement.
- `roles/packages`: package audit and optional installation.
- `roles/shared_tools`: shared tool audit and opt-in provisioning using the root bootstrap.

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
