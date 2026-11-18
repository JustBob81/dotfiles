# Node.js version management

`config/node-tools.json` declares fnm and the Node versions currently required by
projects in `~/mywd`. `bootstrap-node-tools` audits by default and provisions
only when called with `--apply`. The fnm 1.39.0 Linux archive is downloaded from
the official GitHub release and checked against its published SHA-256 before
installation. The binary is stored under the XDG data directory and exposed as
`~/.local/bin/fnm`; conflicting commands are backed up before replacement.

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

The shell setup gives fnm priority for Node selection and keeps NVM loaded during
the transition so existing global npm command paths remain available. Existing
NVM installations and `~/.nvm/default-packages` are not removed or copied.
Verify project command availability before retiring NVM; global npm tools may
need to be provisioned under the fnm-managed Node separately. The direnv `use_fnm` helper handles
existing `.nvmrc` files without installing tools on directory entry;
`use_nvm` remains as a compatibility alias to that helper.

Node 26's official Linux binaries may require `libatomic1`; the package is
declared in the Ubuntu base groups. The Node manager script does not install
system packages, change `/usr/bin/node`, or alter project lockfiles. The current
Node 14 and 16 project pins are retained for compatibility even though those
release lines are end-of-life; review and update each project independently.
