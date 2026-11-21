# System application policy

These application choices apply to the separate Ubuntu 26.04 Resolute profile.
They do not change the repaired Focal laptop or its database packages and
repositories. Package installation remains opt-in.

## Selected applications

| Group | Provisioning | Notes |
| --- | --- | --- |
| Firefox | Firefox Snap from Ubuntu's `latest/stable` channel | Included by `--install-apps` for general browsing. The LastPass extension policy is also applied; sign-in and MFA remain manual. Ubuntu's browser is distributed as a Snap. |
| Google Chrome | `google-chrome-stable` from Google's signed Stable APT repository | Included by `--install-apps` for project browser debugging. The key fingerprint is checked against Google's published Linux package key; Google's repository supplies browser updates. |
| Image editor | Official GIMP Snap from the verified GIMP team publisher | Included by `--install-apps` on `latest/stable`; Snap updates follow the stable channel. |
| Music streaming | Spotify Snap from its verified publisher | Included by `--install-apps` on `latest/stable`; Spotify sign-in remains manual. |
| Containers | Ubuntu `docker.io` and `docker-compose-v2` | Uses Ubuntu packages, avoiding a Docker vendor source. Docker starts its daemon; Docker data and access policy remain separate. |
| Keep-awake utility | Ubuntu `caffeine` package (2.9.14-1 in Resolute) | Included by `--install-apps`. Its fullscreen detection depends on X11-related libraries; verify its indicator and behavior in the GNOME Wayland VM. If that is limited, the Caffeine GNOME Shell extension has an active build for GNOME 50. |
| Kubernetes client | `kubectl` from the official Kubernetes Snap | Snap follows its stable channel and updates automatically. Match its minor version to each cluster's supported version skew. `~/.kube` configuration and credentials are not managed. |
| PostgreSQL | Ubuntu `postgresql` metapackage | Resolute selects its current supported major version. Package installation can create and start a local cluster. Database contents and migration are separate recovery work. |
| MongoDB | MongoDB Community 9.0 APT repository and `mongodb-org` | MongoDB documents Resolute support for 9.0.4 and newer. The repository is added only when requested and its signing key fingerprint is checked. Installing the server can start `mongod`; existing data is not migrated. |
| Haskell | Ubuntu `ghc`, `cabal-install`, and `haskell-stack` | Uses the Resolute archive versions. Project-specific compiler versions and packages remain project-managed. |
| API client | Bruno 4.3.0 from the official GitHub release `.deb`, pinned by SHA256 | Opts into `--install-apps`; no vendor APT repository or Snap publisher is trusted. Version updates require a reviewed version and checksum change. |
| Launcher | Ulauncher 6.0.0-beta35 from the maintainer's Resolute development PPA | Included by `--install-apps`. The exact beta package is pinned because it is the currently published Resolute build; Ulauncher v6 remains pre-release and its extension API may change. The stable Ulauncher PPA does not currently publish a Resolute package. Existing Albert configuration stays in dotfiles but is not copied into Ulauncher. On GNOME Wayland, the profile assigns Alt+Space to `ulauncher show` through a GNOME custom shortcut. |
| Alternate launcher | Albert | Explicit alternate via `--install-albert`; this replaces Ulauncher for that run. Albert is currently unavailable from its Ubuntu 26.04 OBS endpoint (HTTP 404), and the profile fails closed without adding its source or installing a package built for another Ubuntu release. Existing settings and web-search declarations remain preserved for when a supported Resolute package source is available. |
| Google Cloud CLI | Official `google-cloud-cli` Snap | Optional and independent of Kubernetes. Google sign-in and account configuration remain manual. |

`./ansible/run-resolute --check --install-apps` previews containers,
PostgreSQL, Haskell, `kubectl`, Bruno, and Ulauncher.
Add `--apply` to install them.
The default launcher is Ulauncher. Albert can be selected explicitly with
`--install-albert`; its current Resolute source is unavailable, so that choice
stops with a clear error until upstream publishes a supported package.
MongoDB and Google Cloud remain separate opt-ins:

```sh
./ansible/run-resolute --check --install-mongodb
./ansible/run-resolute --apply --install-mongodb

./ansible/run-resolute --check --install-google-cloud
./ansible/run-resolute --apply --install-google-cloud
```

These operations can download packages and start local services. They do not
upgrade Ubuntu, migrate Focal databases, restore database contents, configure
cloud credentials, or import Kubernetes credentials. The package names and
source versions are declared, but the latest package revisions in Ubuntu,
MongoDB's 9.0 series, Ulauncher development builds, and Snap stable channels can
change over time. Ulauncher extension data is not managed. Albert's user
configuration seed deliberately excludes its input-history database and
monitor-specific window coordinates. Albert also stores the input history
locally when its window closes; that runtime data is not part of dotfiles.

On GNOME Wayland, the launcher shortcut is owned by GNOME. Ansible configures
Alt+Space to run `ulauncher show` when the default Ulauncher choice is selected.
If provisioning runs without the logged-in session bus, run
`./tooling/launcher-gnome-shortcut.py --launcher ulauncher --apply` from a GNOME
terminal. The helper preserves unrelated custom shortcuts and refuses to take
Alt+Space if another custom shortcut already uses it. Ubuntu's GNOME default
assigns `Alt+Space` to the window menu, so the helper removes only that default
binding. If a supported Albert package becomes available, its optional setup
uses the same helper with `--launcher albert`.
GNOME custom-shortcut management is described in the [GNOME keyboard
guide](https://help.gnome.org/gnome-help/keyboard-shortcuts-set.html), and
Albert documents the Wayland limitation in its [FAQ](https://albertlauncher.github.io/faq/).

The former [X Window Switcher](https://github.com/albertlauncher/albert-plugin-python-x-window-switcher)
plugin used `wmctrl` and supported X11 only. Ubuntu 26.04's GNOME session is
Wayland-only; there is no “Ubuntu on Xorg” login choice, so that plugin is not
part of the carried setup.

On the current Focal installation, Docker CE/Compose, PostgreSQL 12,
MongoDB 5.0, GCloud, kubectl, and Haskell are retained as observed state. This
profile does not replace those versions or relocate their data. In particular,
MongoDB's existing Focal 5.0 repository remains outside this Resolute policy.

For the physical laptop's observed software, prior keep/retire decisions, and
remaining coverage gaps, see [the software inventory](software-inventory.md).
