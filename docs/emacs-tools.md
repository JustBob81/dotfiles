# Emacs and Codex recovery

`config/emacs-tools.json` declares the complete private Emacs checkout, native
binaries and Snap policy. `bootstrap-emacs` uses system Python's standard library;
the Ansible `emacs_tools` role calls it as the laptop user. Auditing is the default.
Provisioning requires `--provision-emacs`; it does not imply general package
upgrades, shared Python provisioning, or authentication.

## Ownership and preservation

All Emacs configuration, local Lisp modules, adapter launcher, version manifest,
and temporary package patch remain in `~/.emacs.d`. Dotfiles only provisions them:

- `origin`: `git@github.com:JustBob81/emacs.d.git` (requires private Git access).
- `upstream`: `https://github.com/purcell/emacs.d.git`.
- Fresh clones retain full Git history and initially check out the reviewed
  `initial_revision` in detached HEAD state. Create a working branch manually
  before editing a fresh clone. Existing checkouts keep their HEAD, branch,
  local changes and history. Provisioning never fetches, resets or merges them.
- Missing remotes are added; differing existing URLs require manual resolution.
- The superseded emacs-local repository is historical only. It is neither read,
  cloned nor linked by this integration.

Conflicting destinations, broken links and different tool versions stop
application rather than being overwritten. Matching existing native tools are
adopted in place. The Emacs repository's `tools/install-local.py` owns links for
`~/.local/bin/codex-acp` and `$XDG_CONFIG_HOME/codex-acp/versions.env` (default
`~/.config`). Its conflict checks are preserved. No configuration sources or
installed packages are copied into dotfiles.

## Installation policy

Emacs is the classic Snap tracking `latest/stable`. The installed metadata was
31.1, classic, on November 16, 2026. An existing installation is preserved without
refresh; a different readable channel or confinement requires review. An unreadable
tracking channel produces a warning: verify `snap list emacs` locally. The opt-in
role ensures `git`, `patch`, and `snapd` are installed, and installs Emacs only if
missing. Snap service availability is required on a fresh machine.

Standalone Codex 0.167.0 is exposed at `~/.local/bin/codex`, independently of
NVM and system Node. Fresh provisioning downloads the complete native release
package, including its helper binaries and sandbox resources, verifies the pinned
archive and executable SHA-256, and keeps the layout intact. Mise 2026.11.4 is
exposed at `~/.local/bin/mise`; its extracted executable is checked against the
SHA-256 recorded from the working installation. Managed downloads live under
`$XDG_DATA_HOME/emacs-tools` (default `~/.local/share/emacs-tools`). Existing matching
installations retain their current locations. The Codex archive checksum was
checked against the release asset metadata; these pins require explicit review
when updating versions.

Node and adapter versions are read as data exclusively from emacs.d's
`tools/codex-acp/versions.env`. They are deliberately not duplicated in this policy.
Provisioning runs the equivalent of these commands from `~/.emacs.d`:

```sh
python3 tools/install-local.py
. "${XDG_CONFIG_HOME:-$HOME/.config}/codex-acp/versions.env"
MISE_NO_CONFIG=1 ~/.local/bin/mise install \
  "node@$NODE_VERSION" \
  "npm:@agentclientprotocol/codex-acp@$CODEX_ACP_VERSION"
```

Cold package.el installation is bounded at 900 seconds; steady-state startup
validation remains bounded at 300 seconds. Timeouts retain diagnostic output and
terminate the startup process group.

The implementation removes inherited `MISE_*` overrides before provisioning and
sets `MISE_NO_CONFIG=1` and `CODEX_PATH=~/.local/bin/codex`. The existing launcher
selects the isolated runtime, ignores project/global Mise configuration and
preserves the caller's working directory. No shell activation, global Mise
configuration, NVM changes, or system Node changes are needed.

Emacs startup lets package.el/MELPA install agent-shell and its Emacs dependencies.
The adapter is the npm package; the Emacs package is never installed through npm
or Mise. After installation the provisioner inspects the per-Emacs package folder.
Only agent-shell 20261107.1445 on Emacs 31+ qualifies for the repository's temporary
four-warning patch. It checks the patch in forward/reverse dry-run mode and invokes
the version-guarded `tools/agent-shell/apply-fixes.el` only when patching or
recompilation is needed. Different/multiple package versions produce a review
warning; they are preserved without applying the old patch or downgrading. Inspect
newer source for upstream fixes and run regression tests. Modified supported
source that matches neither patch state is a conflict. Connectivity did not depend
on this warning patch.

## Apply and verify

From dotfiles in a normal terminal:

```sh
./bootstrap-emacs                         # audit only
./ansible/run --syntax-check
./ansible/run --check --provision-emacs
./ansible/run --apply --provision-emacs
./ansible/run --apply --provision-emacs    # expect changed=0
./bootstrap-emacs --validate
```

For an existing Snap, the user-only `./bootstrap-emacs --apply` is also available.
It refuses to install the privileged Snap itself. Authentication is a separate
manual step: run `~/.local/bin/codex` and sign in as prompted. Never put credentials
in policy, inventory, environment files tracked in Git, or this repository. See
[the official Codex CLI instructions](https://learn.chatgpt.com/docs/codex/cli).
After sign-in:

```sh
./bootstrap-emacs --validate-acp
```

This probe sends only ACP `initialize` and `session/new`, then closes the process;
it never sends a model prompt. Session creation can create local runtime/session
state, which stays outside Git. In Emacs, visit a project and use `M-x agent-shell`
or `C-c C-a`. Confirm the project directory and authenticated connection.
`C-c a` remains Org agenda.

The requested regression commands, from `~/.emacs.d`, are:

```sh
sh tests/test-startup.sh
emacs -Q --batch -l early-init.el -l init.el \
  -l tests/init-sessions-tests.el \
  -l tests/agent-shell-compat-tests.el \
  --eval '(setq kill-emacs-hook nil)' \
  -f ert-run-tests-batch-and-exit
```

The validation wrapper first verifies the Snap launcher and additionally runs the
startup shell script with `sh -e`: invoking it with plain `sh` bypasses its shebang's
`-e`, allowing a failed Emacs launch to print “Startup successful.” A zero exit
from that plain shell command alone is insufficient evidence.

## Current evidence and recovery limits

On November 16, 2026, the live audit found matching native tools, repository remotes,
links, manifest-selected runtimes and an already patched supported agent-shell.
Repeated user-only application reported no changes. The adapter's version command
also worked from a temporary project with a conflicting Mise configuration.
Codex reported an existing ChatGPT login; no credential contents were inspected.
A later audit found agent-shell 20261113.1059 and correctly reported a review
warning without applying the old patch; no provisioning conflicts or changes
were proposed.

This agent session cannot launch Snap Emacs (exit 46, application tracking denied),
so current startup/shutdown and ERT success are **not verified**. The direct ACP
probe failed during `initialize` with code 1001; authentication/session connectivity
is likewise **not verified** here. Rerun both wrappers in a normal terminal and
investigate any continuing failure before treating this setup as recovered. The
November 8 successes do not establish today's results. The separate VM test provides exploratory fresh-download/application evidence
with important qualifications; see [the VM findings](vm-test-20261116.md).

The reproducibility guarantee is explicit top-level selections, preserved repository
history and repeatable provisioning on this existing installation. It is not a full
lock of the laptop: Snap's channel floats; existing Emacs source revisions are
preserved; package.el/MELPA and transitive npm dependencies are not locked. Initial
Git revision and standalone release hashes constrain fresh sources/binaries, but
network services, private Git access, Snap, MELPA, npm and Mise downloads must still
be available. A clean Focal VM replay subsequently passed on a new disk with the bounded Store
retry policy: direct classic Emacs Snap installation succeeded, Ansible first
application reported `changed=2`, the repeat reported `changed=0`, and startup/ERT
passed. See [the VM findings](vm-test-20261116.md). Private GitHub authentication
and authenticated ACP/interactive use remain manual; the source-only fixture did
not test real private remote cloning. The VM found an undeclared Emacs
`session` package dependency; its fix is now committed in emacs.d as
`4d1c0d58e466ccf65786c9dbdac54bc35fe4e23f` and selected by the initial revision.
The Emacs session reports startup/shutdown and all three ERT tests passed.
Review confirmed all four warnings remain in agent-shell 20261113.1059; it remains
unpatched. These checks do not replace a clean provisioning replay. See [VM findings](vm-test-20261116.md) for
the Snap Store workaround and remaining recovery gates. The current
Ansible OS guard remains Focal-specific; review a supported Ubuntu profile before
using it on a newer laptop. Back up and restore Custom settings, histories, sessions,
data and credentials separately. They are not configuration sources to commit.
