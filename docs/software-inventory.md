# Laptop software inventory and declarative coverage

## Scope and confidence

This is a read-only snapshot of the physical laptop, captured 2026-11-21. The
host is Ubuntu 20.04.6 LTS (Focal); it is separate from the Ubuntu 26.04
Resolute test VM. Package evidence came from `dpkg-query`, tool evidence from
the repository audit scripts and user-level tool managers, and Snap application
versions from the installed `/snap/*/current/meta/snap.yaml` files. The Snap
daemon did not return a fresh `snap list` during this inspection, so mounted
Snap versions are reported as observed but that interface needs rechecking.

The audit establishes broad application coverage, not every system package or
project dependency. Hardware drivers, services, project virtual environments,
IDrive restore testing, and all files under `~/mywd` still need separate review.
No software was installed or removed during this inventory.

## Declarative tooling that currently converges

| Tooling | Observed on laptop | Dotfiles coverage | Status |
| --- | --- | --- | --- |
| Python shared CLI tools | Declared Python 3.12.16; pipx 1.17.6; Hatch, PDM, Poetry, pip-tools, Pipenv, python-lsp-server, yamllint | `config/shared-python-tools.json`, `bootstrap-tools`, Ansible audit | Audit reported no changes. |
| Node | fnm 1.39.0; Node 14.18.3, 16.13.2, 26.13.1 default; pnpm 12.20.0 and declared global CLIs | `config/node-tools.json`, `bootstrap-node-tools`; project `.nvmrc` files found in `~/mywd` | Audit reported no changes. The Codex ACP Node 24.22.2 runtime is separate and declared with Emacs tooling. |
| Ruby | Mise Ruby 4.0.9 | `config/mise/config.toml`, `bootstrap-ruby-tools` | Declared version is installed. APT RVM 1.29.12 remains installed despite the decision to retire it. |
| R | System R 4.4.2; CRAN renv 1.3.1; Rig launcher installed | `config/r-tools.json`, `bootstrap-r-tools`, `docs/r-tools.md` | Audit converges using system-R fallback. `rig list` has no managed R versions because portable Rig R is unsupported on this host's glibc 2.31. |
| Emacs/Codex/ACP | Emacs 31.1, standalone Codex, Mise, and codex-acp | Dotfiles provisions the separate private `~/.emacs.d` repository; see `docs/emacs-tools.md` | Previously validated in the Resolute VM. |
| Firefox LastPass extension | Firefox and managed extension policy | `config/firefox-extensions.json`, enabled with `--install-apps` or separately with `--provision-lastpass` | Extension policy was enabled and manually verified in the Resolute VM; account sign-in and MFA remain manual. |

## Application decisions and coverage

| Area | Laptop evidence (2026-11-21) | Decision | Declarative coverage / remaining work |
| --- | --- | --- | --- |
| Browsers | Chrome 157, Firefox 136, Chromium 85 APT package plus Chromium 157 Snap, Brave 1.99 | Keep Chrome for project developer tools and Firefox for everyday browsing and LastPass; omit Brave and Chromium from the new setup. | Resolute `--install-apps` provisions Chrome from Google's signed Stable APT source and Firefox from Ubuntu's stable Snap. It also applies the LastPass extension policy; sign-in/MFA remain manual. Chromium and Brave stay excluded. |
| Docker and Compose | Docker CE 24.0.2 from an old Bionic-targeted vendor package set; Compose v1 1.25 and Compose plugin v2 2.18 | Keep Docker and Compose. | Resolute profile declares Ubuntu `docker.io` and `docker-compose-v2`; Focal Docker CE/Compose installation is not reconciled with that future choice. Review daemon/data migration separately. |
| Kubernetes | `kubectl` APT package 1:592.0.0; Minikube 1.6.2 | Keep Kubernetes and include Minikube for local experiments and learning. | Resolute `--install-apps` installs `kubectl` Snap and the checksum-verified Minikube 1.39.0 binary. It does not create a cluster; starting one requires Docker and separate disk, memory, and CPU capacity. Kubernetes credentials are intentionally out of scope. |
| Google Cloud | `google-cloud-sdk` 467 and `google-cloud-cli` 592 packages observed; `gcloud` available | Keep optional. | Resolute has an explicit optional Google Cloud Snap switch, not included in the default app install. Host APT package/source overlap remains to be reviewed. Sign-in is manual. |
| PostgreSQL | PostgreSQL 10 and 12 packages, plus contrib | Keep PostgreSQL. | Resolute profile declares Ubuntu's `postgresql` metapackage under `--install-apps`. Focal versions and database contents are not migrated. |
| MongoDB | Focal MongoDB 5.0.34 and tools installed | Keep MongoDB. | Resolute opt-in installs MongoDB Community 9.0; the package installed successfully in the VM. Host Focal MongoDB 5.0 and its data remain separate. |
| Haskell | GHC 8.8.1, cabal-install 2.4, Stack, and old `haskell-platform` | Keep Haskell. | Resolute declares GHC, Cabal, and Stack under `--install-apps`; the obsolete `haskell-platform` package is not part of that profile. |
| RVM / Python pyenv | RVM package 1.29.12; pyenv executable and Python 3.9.2, 3.10.0, 3.10.4 remain installed | Exclude RVM and pyenv from the new setup; use Mise for Ruby and Hatch/project environments for Python | Replacement tooling is declared. Old-host cleanup is outside this migration inventory. |
| Python projects | WaterRA and advent_code_2021 migrations were completed; other Pipfiles remain in `~/mywd` (including advent_code_2020, cosmicpython, dagster, dagster_sandbox, and mytest) | Use project-specific Hatch/PDM/Poetry/Pipenv as appropriate; omit Anaconda/Conda. | These remaining projects have not been individually reconciled or migrated. |
| Albert, Caffeine | APT Albert 0.17.6; Caffeine 2.9.4 | Keep both. Ulauncher is the default launcher; Albert remains an optional alternate. | Resolute `--install-apps` installs the pinned Ulauncher 6.0.0-beta35 build and configures GNOME Alt+Space to open it. Ulauncher v6 is pre-release. Albert can be selected with `--install-albert`, but its current OBS Ubuntu 26.04 endpoint returns 404, so provisioning fails closed without adding the source. Albert's settings and web searches remain in dotfiles for a future supported package. Its old X11-only window-switcher plugin is excluded. Caffeine is declared from Ubuntu's archive; its X11-based fullscreen detection needs a Wayland VM check. |
| ClipGrab | APT ClipGrab 3.8.10 package built for Bionic | Keep. | Not declared. Its old package source/build needs a supported replacement decision before fresh-machine provisioning. |
| GIMP, Spotify | GIMP Snap 3.2.8; Spotify Snap 1.2.95 | Keep both. | Resolute `--install-apps` installs GIMP and Spotify from their verified Snap publishers on `latest/stable`; Spotify sign-in remains manual. |
| Postman / Bruno | Postman Snap 9.31.30 installed; no Bruno installation found | Replace Postman with Bruno, using the official pinned `.deb` and SHA256 checksum. | Resolute `--install-apps` provisions Bruno 4.3.0 from the official GitHub release asset. Its release page reports the matching SHA256. Validate launch and import/workspace behavior in the VM before considering Postman retired there. The old host Postman is untouched. |
| Thunderbird | Thunderbird 115.18 and locale packages installed | Exclude from the new setup. | Host leftovers are not part of this migration inventory. |
| Wine | Wine 8.0.1, WineHQ packages, Winetricks, and `~/.wine` data present | Exclude Wine from the new setup. | Host leftovers are not part of this migration inventory. |
| Calibre, TeX Live, Pandoc | Calibre installed under `/opt/calibre`; TeX Live full 2019; Pandoc 2.5 | Keep; TeX and Pandoc support Emacs writing workflows. | Not declared in the Resolute profile. Calibre uses a manual install location; choose reproducible install methods and a TeX package scope. |
| Remmina | APT Remmina 1.4.25 with RDP/VNC/secret plugins | Keep. | Resolute `--install-apps` installs Remmina and the Ubuntu archive's RDP, VNC, and secret plugins. Connection profiles and saved credentials remain user data and are not copied or committed. |

## Additional selected applications

The user confirmed these should be included in the new setup: Audacity 3.7.9,
MusicBrainz Picard 3.0.5, Zoom 7.1.5, Asunder, LibreOffice, and Simple Scan.
Their current Snap package versions were read from mounted snap metadata where
applicable. None is yet declared in the Resolute application profile.

IDrive was configured manually and a backup/restore sample was verified earlier.
Its installer, service state, backup schedule, and latest backup freshness are
not represented by the dotfiles Ansible profiles. Keep credentials and backup
data out of Git; verify the IDrive schedule and restore separately.

## Recommended completion order

1. Finish project inventory for remaining Python projects before selecting
   their environment managers.
2. Add the agreed desktop applications to a separate optional Resolute group,
   after selecting supported installation sources. Add Bruno and validate it
   before retiring Postman from the new setup.
4. Keep the Resolute VM package checks and convergence tests separate from the
   physical laptop live-boot/hardware gate. Do not upgrade the Focal host as
   part of this inventory work.
