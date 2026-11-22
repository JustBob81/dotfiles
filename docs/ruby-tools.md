# Ruby version management

Mise replaces RVM for Ruby version selection. The Mise executable is already
provisioned with the Emacs/Codex tooling. `config/mise/config.toml` is the
tracked global policy: it selects Ruby 4.0.9 outside projects, recognizes
project `.ruby-version` files and Ruby versions declared in Gemfiles, and turns
off automatic installs. Directory changes never download runtimes.

Ruby 4.0.9 is the current stable CRuby release as of November 18, 2026, according
to the [official Ruby download page](https://www.ruby-lang.org/en/downloads/).
Mise uses precompiled Linux x86_64 CRuby builds when available and verifies
their GitHub artifact attestations. On this laptop's glibc 2.31, Mise selects
its compatible no-YJIT build. See [Mise's Ruby documentation](https://mise.jdx.dev/lang/ruby.html).

Audit and install explicitly:

```sh
./bootstrap-ruby-tools
./bootstrap-ruby-tools --apply
```

The bootstrap only installs the declared Ruby version under the Mise data
directory. It does not remove `~/.rvm`, alter system Ruby, install gems, or
modify project files. Existing RVM Ruby 2.5.1 remains on disk as a rollback
copy. Ubuntu's `/etc/profile.d/rvm.sh` still runs for login shells; the shared
shell helper removes its RVM function, environment variables, and PATH entries
before Mise activation. The system package and files remain available for
recovery. Projects needing an older Ruby should declare and review that version
with a project `.ruby-version` or Gemfile `ruby` directive, then run `mise install`
explicitly.

`ruby` in the global config is an exact Ruby release, but there is no committed
`mise.lock`; if Mise republishes its binary for the same Ruby version, a future
installation may use that newer build. Ruby gems and Bundler dependency graphs
remain project-managed through each project's Gemfile and lockfile. No Ruby
project markers were found in the reviewed `~/mywd` tree, so no project runtime
or gem dependencies were changed in this milestone.

Open a new shell after applying the dotfiles links, then verify:

```sh
command -v ruby
ruby --version
mise ls --installed ruby
```

The command should resolve through Mise and report Ruby 4.0.9. The legacy RVM
checkout is preserved for recovery; remove it only after confirming no personal
scripts or projects depend on it.
