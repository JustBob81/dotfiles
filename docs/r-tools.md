# R versions and project packages

Rig manages R installations; the CRAN `renv` package manages each project's R
package library and lockfile. The old `~/.renv` checkout is the unrelated
`renv-installer` shim manager, not the CRAN package. Dotfiles no longer clone
or initialize that manager. Its checkout, its R 4.0.2 files, and the system
`r-base-core` installation remain on disk for recovery.

`config/r-tools.json` pins Rig 0.11.1, its official Ubuntu package checksum,
the initial default R 4.4.2, and CRAN renv 1.3.1. R 4.4.2 matches the active
system R version, so this migration avoids a runtime upgrade while the existing
R projects are reviewed. CRAN's current release is R 4.6.2; move the default in
a separate change after checking project compatibility. See the [R release
page](https://www.r-project.org/) and [CRAN renv package](https://cran.r-project.org/web/packages/renv/).

Audit and provision explicitly:

```sh
./bootstrap-r-tools
./bootstrap-r-tools --apply
```

The bootstrap installs Rig under user-owned data directories. On glibc 2.34 or
newer it uses Rig user mode for R and installs CRAN renv into that R version's
user library. On older glibc, it keeps the matching system R selected and
installs the pinned CRAN renv into a user library; it does not try to install
an incompatible portable R build. This is the path for the current Ubuntu 20.04
Focal laptop (glibc 2.31, system R 4.4.2). `use_rig` selects a project R from
Rig when installed, or uses the system R only when its full version exactly
matches the project declaration. Thus Focal can use package isolation with
renv, but cannot install multiple user-mode R versions. The Ubuntu 26.04
Resolute profile uses Rig user mode. Rig's portable builds require glibc 2.34;
Rig itself can run on older glibc, but that does not make those R builds
compatible. See [Rig's user-mode guide](https://rig.r-lib.org/tutorial-user.html),
[mode tradeoffs](https://rig.r-lib.org/admin-vs-user-mode.html), and [Posit's
portable R requirements](https://github.com/rstudio/r-builds#portable-builds-experimental).

The fallback does not use sudo, add an APT repository, remove system R, copy
packages, or modify R projects. The existing system R is 4.4.2 and its site
library currently has only base packages, so there are no additional system
packages to migrate. On Focal, a project requiring another R version must wait
for an OS upgrade or a separately reviewed system-managed R installation.

## Project setup

For a project using R, add `use_rig` to its `.envrc`. It reads an exact version
from `.R-version`, or from `R.Version` in `renv.lock`, and puts that already
installed Rig version first on PATH. It does not install R when entering a
directory. If neither marker exists, the default R remains selected.

Initialize package isolation in a reviewed project directory, then commit its
lockfile and activation files:

```sh
R -q -e 'renv::init()'
R -q -e 'renv::snapshot()'
```

To recover a project's runtime on a fresh machine, read its lockfile's R
version, install that version explicitly, then allow direnv and restore packages:

```sh
R_VERSION=$(/usr/bin/python3 -c 'import json; print(json.load(open("renv.lock"))["R"]["Version"])')
rig add "$R_VERSION" --user --without-path --without-pak
direnv allow
R -q -e 'renv::restore()'
```

On glibc below 2.34, these runtime installation commands are not supported by
the portable R build; use a matching system R or upgrade the OS first.

CRAN `renv` isolates and restores package versions but does not switch R by
itself; `use_rig` connects its recorded R version to Rig. The helper requires
that version to be installed and never downloads on `cd`. Project `.Rprofile`,
`.R-version`, and `renv.lock` files are project-owned and should be reviewed
before committing. The global Git ignore excludes generated R history and
libraries while leaving `renv.lock` trackable.

No existing project was initialized or edited. The reviewed `~/mywd` tree has
R scripts but no `.R-version`, `.Rprofile`, or `renv.lock` files. Those projects
need individual package and runtime inventories before adopting renv. Top-level
R and renv versions are pinned, but Rig's portable R builds and package binary
repositories can be updated upstream; project lockfiles pin R and package
metadata, not every system library or build tool needed by native packages.
