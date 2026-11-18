# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# renv path
export RENV_ROOT="$HOME/.renv"
export PATH="$RENV_ROOT/bin:$PATH"

# Add RVM to PATH for scripting. Make sure this is the last PATH variable change.
export PATH="$PATH:$HOME/.rvm/bin"

unset NVM_DIR
if [ -x "$HOME/.local/bin/fnm" ]; then
    export FNM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fnm"
    eval "$("$HOME/.local/bin/fnm" env --use-on-cd --shell zsh)"
fi

# Keep shared Node CLI tools independent of individual fnm installations.
export PNPM_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/laptop-tools/pnpm-home"
export PATH="$PNPM_HOME/bin:$PATH"

# Add krew to Path
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"

export PIPENV_VENV_IN_PROJECT=1
export GPG_TTY=$(tty)
export GPGKEY=C139069E66B8E5C6
if [ -d "$HOME/.yarn/bin" ]; then export PATH="$PATH:$HOME/.yarn/bin"; fi
if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then . "$HOME/.nix-profile/etc/profile.d/nix.sh"; fi # added by Nix installer
