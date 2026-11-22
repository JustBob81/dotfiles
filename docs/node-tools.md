# Node.js version management

`config/node-tools.json` declares fnm, the Node versions currently required by
projects in `~/mywd`, pnpm, and the shared Node command-line tools. `bootstrap-node-tools`
audits by default and provisions only when called with `--apply`. The fnm 1.39.0
Linux archive is downloaded from the official GitHub release and checked against
its published SHA-256 before installation. The binary is stored under the XDG
data directory and exposed as `~/.local/bin/fnm`; conflicting commands are
backed up before replacement.

The existing `.nvmrc` files select Node 14.18.3 and 16.13.2. fnm reads those
files when entering a project. Outside a project with a version file, fnm uses
the declared default, Node 26.13.1. On November 18, 2026, the Node release
table lists 26.13.1 as the newest LTS. This patch is pinned for repeatable
setup; update the manifest after reviewing a newer LTS release. See the [Node
release table](https://nodejs.org/en/about/previous-releases) and [fnm shell
setup and `.nvmrc` support](https://github.com/Schniz/fnm).

Run the audit and apply from the dotfiles checkout:

```sh
./bootstrap-node-tools
./bootstrap-node-tools --apply
```

The standalone pnpm 12.20.0 binary is installed under
`$XDG_DATA_HOME/laptop-tools/pnpm-home` (default `~/.local/share/laptop-tools/pnpm-home`).
Its official installer and checksum are verified with pnpm's published OpenPGP
signature and pinned release key before execution. The installer then verifies
the requested pnpm release. Global CLIs are installed by exact top-level version
into pnpm's isolated global package directories and their commands are exposed
through `$PNPM_HOME/bin`. The set preserves the existing installed npm and Yarn
global commands; `jsonlint` remains only in the old NVM default list because it
was not installed in the audited environment.

The shell setup uses fnm for Node selection and no longer sources NVM. Existing
`.nvmrc` files still work: the direnv `use_fnm` helper and the temporary
`use_nvm` compatibility alias both select Node through fnm without installing
versions on directory entry. Existing `~/.nvm` files and global packages are
preserved for rollback; the legacy `nvm/default-packages` file is retained as an
archive and is no longer linked by the active install profile. The old Yarn
global directory also remains intact, with pnpm's commands taking precedence.

Package versions are pinned at the top level. pnpm's global package metadata and
transitive dependency lock live in user data rather than the repository, so
fresh-machine provisioning does not guarantee identical transitive npm package
versions. Review and refresh those pins deliberately when updating the tool set.
Global package installation streams output to the terminal so pnpm can show any
build-script approval prompts. The two approvals recorded during migration,
`core-js` and `yarn`, are declared beside their packages and passed explicitly
with pnpm's `--allow-build` option. Other package scripts remain blocked unless
they are reviewed and added to the manifest.

Node 26's official Linux binaries may require `libatomic1`; the package is
declared in the Ubuntu base groups. The Node manager script does not install
system packages, change `/usr/bin/node`, or alter project lockfiles. The current
Node 14 and 16 project pins are retained for compatibility even though those
release lines are end-of-life; review and update each project independently.
