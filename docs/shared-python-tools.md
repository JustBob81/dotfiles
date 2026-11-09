# Shared Python tooling and fresh-machine bootstrap

## Ownership

- Ubuntu owns `/usr/bin/python3` and the `direnv` package.
- `config/shared-python-tools.json` declares the independent Python archive,
  checksum, install location, pipx version, and Hatch version.
- pipx owns shared Python applications. Hatch is available to all projects.
- Hatch owns each project's `.hatch` virtual environment.
- direnv selects the project environment and unloads it on leaving the directory.

The bootstrap does not require uv, pipx, Hatch, or Ansible. It uses the installed
Ubuntu Python standard library. It never uses sudo or installs system packages.
The Ansible role calls the same bootstrap, avoiding two provisioning implementations.

## Current profile and provenance

The reviewed profile is Linux x86_64, CPython 3.12.16, pipx 1.17.6, and Hatch
1.18.2. These are explicit version decisions, not requests for the latest version.
The relocatable Python archive and SHA-256 come from the upstream
[python-build-standalone release assets](https://github.com/astral-sh/python-build-standalone/releases/expanded_assets/20261026).
The source is the same distribution previously downloaded by uv. Archive checksums
are verified before extraction; paths and links are checked before extraction.

The historical `~/.local/share/dotfiles-tools/python/...` location is deliberately
retained as the declared persistent location because existing tools depend on it.
The directory name does not make it a project virtual environment. On a fresh
installation the bootstrap recreates it directly; uv is not involved. Existing
interpreters with the matching version are adopted, not overwritten or claimed
to have undergone a new archive-integrity check.

pipx itself gets a separate versioned environment under
`~/.local/share/laptop-tools/pipx-1.17.6`. Its shared command is published to
`~/.local/bin/pipx`, setting `PIPX_HOME`, `PIPX_BIN_DIR`, and
`PIPX_DEFAULT_PYTHON` before invoking pipx. The existing `~/.local/pipx` application
home is retained so older application environments remain visible. The new
launcher is independent of the old pyenv 3.10.4 interpreter.

`XDG_DATA_HOME`, when set, determines the data-directory prefix. Backups are
stored under that prefix's `laptop-tools/backups`. A pre-existing pipx launcher
is backed up before replacement; an existing Hatch environment is backed up
before a required reinstall. Unrelated pipx apps are neither reinstalled nor
removed. Their old interpreter/shared-pip dependencies require separate review.

## Fresh laptop sequence

This profile currently covers Linux x86_64 tooling. Ansible's complete laptop
profile still targets Focal, so supported-LTS policies require separate validation.
Starting from a clean Ubuntu installation with working official repositories:

```sh
sudo apt-get install git python3 ca-certificates direnv
# Clone this repository, then enter it.
./bootstrap-tools              # audit only: no downloads or installs
./bootstrap-tools --apply      # user-local Python/pipx/Hatch provisioning
export PATH="$HOME/.local/bin:$PATH"
./ansible/bootstrap            # Hatch creates/synchronizes project .hatch
# Review .envrc and its helper before authorizing.
direnv allow
./ansible/run --syntax-check
./ansible/run --check
```

The normal shell also needs its direnv hook. Existing dotfiles include the hook
through Antigen; a fresh shell can temporarily enable it with
`eval "$(direnv hook bash)"` or `eval "$(direnv hook zsh)"`, matching the shell.
Until the shell is configured, `hatch run syntax` and `hatch run preview` work
without depending on automatic activation. The earlier manual uv installation
and project `.venv-ansible` are not required for this sequence.

## Existing laptop preview and application

```sh
./bootstrap-tools
./ansible/run --check --provision-tools
./ansible/run --apply --provision-tools
./ansible/run --apply --provision-tools
```

The default Ansible run audits shared tools only. `--provision-tools` opts into
provisioning; check mode reports proposed drift but never invokes bootstrap
application. `--install-packages` remains a separate option. If `direnv` is
missing, install the declared system prerequisite through APT first (or opt into
Ansible's package role); the bootstrap stops before user-tool provisioning.

On the current laptop, check mode proposed installing managed pipx and replacing
its launcher. Existing Python and Hatch matched policy. Application succeeded
with `ok=19 changed=1 failed=0`, and the repeat run reported
`ok=19 changed=0 unreachable=0 failed=0 skipped=3`. Version checks returned pipx
1.17.6 and Hatch 1.18.2. The standalone audit returned an empty `changes` list and
no missing system packages. This validates provisioning and convergence on the
existing laptop; fresh-machine archive download/extraction remains untested.

Existing incompatible Python directories, conflicting compatibility aliases, and
incomplete pipx environments stop provisioning for inspection. Failed package
downloads can leave an incomplete new tool environment, but launchers are not
published until their tool installation is verified. Backups support recovery of
previous launchers and Hatch environments; other tools remain untouched.

## Boundaries

This does not perform OS upgrades, apt repository changes, project dependency
installation on directory entry, secret enrollment, or data restores. It does
not remove uv or any older interpreter/environment: retain them until dependents
are inventoried. Python archive checksums and top-level package versions are
pinned; transitive PyPI dependencies are not yet a full locked artifact set.
Runtime updates require a reviewed manifest change and compatibility validation.

The Ansible core 2.19 bridge still needs replacement with the supported-Ubuntu
migration; provisioning a persistent Python does not change that constraint.
