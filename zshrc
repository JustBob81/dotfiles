# Load Antigen

source ~/antigen/antigen.zsh
# Load Antigen configurations
antigen init ~/.antigenrc

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/bobo51881/anaconda3/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/bobo51881/anaconda3/etc/profile.d/conda.sh" ]; then
        . "/home/bobo51881/anaconda3/etc/profile.d/conda.sh"
    else
        export PATH="/home/bobo51881/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

# renv-installer initialization
export RENV_ROOT="$HOME/.renv"
export PATH="$RENV_ROOT/bin:$PATH"
if command -v renv 1>/dev/null 2>&1; then
  eval "$(renv init -)"
fi

export PIPENV_VENV_IN_PROJECT=1

export NVM_DIR="/home/bobo51881/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm


# Add RVM to PATH for scripting. Make sure this is the last PATH variable change.
export PATH="$PATH:$HOME/.rvm/bin"
if [ -e /home/bobo51881/.nix-profile/etc/profile.d/nix.sh ]; then . /home/bobo51881/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer
