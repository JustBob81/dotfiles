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

The system interpreter `/usr/bin/python3` stays on Python 3.8. Ansible's controller
runtime is separate: use Python 3.11 through 3.13 in a virtual environment and the
Focal-compatible core 2.19 range in `requirements-controller.txt`. Core 2.20 drops
target Python 3.8 support. Core 2.19 upstream maintenance ends in November 2026;
this is a temporary migration bridge, not the final supported-OS runtime policy.
Review the [Ansible support matrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)
when choosing the new Ubuntu release and controller requirements.

This laptop currently has Python 3.8 system Python and older pyenv interpreters.
Ansible and a compatible controller interpreter have not been installed during
this milestone. Do not change `/usr/bin/python3`, add another system Python PPA,
or install Ansible with `sudo pip`. Prepare the isolated controller separately.

Once a compatible interpreter is available (example using Python 3.12), from the
repository root:

```sh
python3.12 -m venv .venv-ansible
.venv-ansible/bin/python -m pip install -r ansible/requirements-controller.txt
. .venv-ansible/bin/activate
```

The virtual environment is excluded from Git. It is recreated from requirements,
not restored as application data. No external Ansible collections are required.

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
```

Check mode does not change system configuration, but Ansible may create temporary
execution files. All managed-host modules use `/usr/bin/python3` explicitly even
when the controller uses the virtual environment. No passphrases are stored in
inventory. Run from a normal terminal: this agent session cannot use sudo or
reach external download services.

Review output before application. On the repaired laptop, repository enforcement
should report no changes. Run application twice to establish convergence; the
second run should report `changed=0`. That runtime check has not been performed.
Ansible stops after a failed task; do not bypass failures with `ignore_errors`.

## Configuration

- `group_vars/all.yml`: reviewed package groups and shared policy loading.
- `inventories/local.yml`: this laptop over the local connection.
- `laptop.yml`: platform and policy checks followed by the two roles.
- `roles/repositories`: disabled-source enforcement.
- `roles/packages`: package audit and optional installation.

Select packages intentionally; the historical full installer is not a package
manifest. Credentials, IDrive configuration, encryption keys, private keys, and
machine-specific secrets stay outside Git.

## Validation available without Ansible

```sh
bash -n ansible/run
shellcheck ansible/run
/usr/bin/python3 ansible/tests/test_foundation.py
python3 tests/test_repositories.py
```

These checks cover YAML parsing, preview/apply command dispatch, package opt-in,
and partner-source matching. They do not replace Ansible syntax validation,
check mode, or real convergence testing.

## Next milestones

1. Prepare the isolated controller; run syntax validation and a preview locally.
2. Test enforcement and repeat application; review all enabled sources and keys.
3. Move enabled-source URLs and key identities into shared policy and implement
   their fresh-machine provisioning, including duplicate-source checks.
4. Inventory optional application groups and add user, update, service, backup,
   and hardware roles. Keep credentials and data restoration separate.
5. Select a supported Ubuntu LTS and test its profile on a clean VM plus hardware.
