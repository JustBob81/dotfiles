# Shared Python tooling and fresh-machine bootstrap

## Ownership

- Ubuntu owns `/usr/bin/python3` and the `direnv` package.
- `config/shared-python-tools.json` declares the independent Python archive,
  checksum, install location, pipx version, and shared application versions.
- pipx owns shared Python applications: Hatch, PDM, Poetry, pip-tools, Pipenv,
  python-lsp-server, and yamllint are available as user commands to all projects.
- Hatch owns private Python 3.9 and 3.10 distributions required by existing
  Pipenv projects.
- Hatch owns each project's `.hatch` virtual environment.
- direnv selects the project environment and unloads it on leaving the directory.

The bootstrap does not require uv, pipx, Hatch, PDM, Poetry, or Ansible. It uses
the installed Ubuntu Python standard library. It never uses sudo or installs system packages.
The Ansible role calls the same bootstrap, avoiding two provisioning implementations.

## Current profile and provenance

The reviewed profile is Linux x86_64, CPython 3.12.16, Hatch-managed Python 3.9
and 3.10, pipx 1.17.6, Hatch
1.18.2, PDM 2.29.7, Poetry 2.5.1, pip-tools 7.7.0, Pipenv 2026.10.4,
python-lsp-server 1.15.0, and yamllint 1.38.0. These are explicit version
decisions, not rolling
requests for the latest release. Their declared command names are in the
manifest because some package names differ from their commands (`pip-tools`
provides `pip-compile` and `pip-sync`; `python-lsp-server` provides `pylsp`).
The PDM, Poetry, pip-tools, Pipenv, and python-lsp-server pins were checked
against their upstream [PDM changelog](https://pdm-project.org/en/latest/dev/changelog/),
[Poetry release history](https://github.com/python-poetry/poetry/releases),
and [PyPI release records for pip-tools](https://pypi.org/project/pip-tools/),
[Pipenv](https://pypi.org/project/pipenv/),
[python-lsp-server](https://pypi.org/project/python-lsp-server/), and
[yamllint](https://pypi.org/project/yamllint/).
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
home is retained so older application environments remain visible. Every managed
application environment uses the declared standalone Python; unrelated pipx
environments remain untouched. Pyenv initialization has been removed from shell
startup and fresh setup. The existing `~/.pyenv` checkout and its Python versions
are retained as an inert local recovery copy. All managed pipx apps now use the
declared standalone Python. The active `waterRA` and `advent_code_2021` Pipenv
environments now use Hatch-managed Python 3.9.25 and 3.10.22 respectively. Their
former pyenv environments remain in the laptop-tools backup directory. Keep the
pyenv runtime data until the project environments and other consumers have been
reviewed; no pyenv data was deleted during migration.

`XDG_DATA_HOME`, when set, determines the data-directory prefix. Backups are
stored under that prefix's `laptop-tools/backups`. A pre-existing pipx launcher
or managed app command is backed up before replacement; an existing managed
application environment is backed up before a required reinstall. Unrelated pipx
apps are neither reinstalled nor removed. Their old interpreter/shared-pip
dependencies require separate review.

## Fresh laptop sequence

This profile currently covers Linux x86_64 tooling. Ansible's complete laptop
profile still targets Focal, so supported-LTS policies require separate validation.
Starting from a clean Ubuntu installation with working official repositories:

```sh
sudo apt-get install git python3 ca-certificates direnv
# Clone this repository, then enter it.
./bootstrap-tools              # audit only: no downloads or installs
./bootstrap-tools --apply      # user-local Python, pipx, CLIs and project runtimes
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

The existing laptop's managed pipx applications now match policy: Hatch 1.18.2,
PDM 2.29.7, Poetry 2.5.1, pip-tools 7.7.0, Pipenv 2026.10.4,
python-lsp-server 1.15.0, and yamllint 1.38.0, all using the declared Python
3.12.16. The audit reports no changes and no missing system packages. When a
managed app's interpreter changes, the bootstrap backs up its environment and
command links, uninstalls that pipx environment, and recreates it with the declared
Python; pipx `--force` alone would not change the interpreter. Fresh-machine
archive download/extraction remains untested.

For Pipenv projects, `layout_pipenv` reads `python_version` from the Pipfile and
sets `PIPENV_PYTHON` to the matching Hatch-managed runtime. Run
`./bootstrap-tools --apply` before entering those projects on a fresh machine.
Hatch selects the current patch release within each declared Python minor line;
the Pipfiles do not pin the interpreter patch version. Existing environments are
left as they are. If a project environment is missing, direnv reports that and
does not install project dependencies on directory entry; create and sync it
explicitly after reviewing the lockfile.

One compatibility edge is known on the current profile: Pipenv 2026.10.4 bundles
a pip runner requiring Python 3.10+, so `pipenv sync` cannot install a Python 3.9
environment. For a locked Python 3.9 project, use its selected Hatch interpreter
to create `.venv`, export locked requirements with hashes using
`pipenv requirements --dev --hash`, and install them with that environment's pip
and `--require-hashes`. This preserves the lockfile and uses pip compatible with
Python 3.9. This was used to migrate `waterRA`; `pip check` passed. The Python
3.10 `advent_code_2021` lock includes `lazy-object-proxy==1.6.0`, which builds
from source on that interpreter. Its legacy build expects `pkg_resources`,
removed from setuptools 82, so sync requires a temporary build constraint such
as `setuptools<82` via `PIP_BUILD_CONSTRAINT`. This was used for the migration;
`pip check` passed. Neither migration changed its Pipfile or lockfile. Previous
and failed venvs are preserved under
`~/.local/share/laptop-tools/backups/python-project-venvs/` (or the equivalent
`XDG_DATA_HOME` location).

The Pipfiles and lockfiles remain in their respective project directories; they
are not copied into dotfiles. A fresh restore needs those project files as well
as this repository. When recreating `advent_code_2021`, apply the setuptools build
constraint during `pipenv sync --dev` as described above.

Existing incompatible Python directories, conflicting compatibility aliases, and
incomplete pipx environments stop provisioning for inspection. Failed package
downloads can leave an incomplete new tool environment, but launchers are not
published until their tool installation is verified. Backups support recovery of
previous launchers and managed application environments; other tools remain
untouched.

## Boundaries

This does not perform OS upgrades, apt repository changes, project dependency
installation on directory entry, secret enrollment, or data restores. It does
not remove uv or any older interpreter/environment: retain them until dependents
are inventoried. Python archive checksums and top-level package versions are
pinned; transitive PyPI dependencies are not yet a full locked artifact set.
Runtime updates require a reviewed manifest change and compatibility validation.

The Ansible core 2.19 bridge still needs replacement with the supported-Ubuntu
migration; provisioning a persistent Python does not change that constraint.
