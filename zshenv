# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# renv path
export RENV_ROOT="$HOME/.renv"
export PATH="$RENV_ROOT/bin:$PATH"

# pyenv path
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"

# Add RVM to PATH for scripting. Make sure this is the last PATH variable change.
export PATH="$PATH:$HOME/.rvm/bin"

export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm

# Add krew to Path
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"

export PIPENV_VENV_IN_PROJECT=1
export GPG_TTY=$(tty)
export GPGKEY=C139069E66B8E5C6
export PATH="$(yarn global bin):$PATH"