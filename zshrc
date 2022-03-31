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

# pyenv initialization
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi

export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm


# Add RVM to PATH for scripting. Make sure this is the last PATH variable change.
export PATH="$PATH:$HOME/.rvm/bin"
if [ -e /home/bobo51881/.nix-profile/etc/profile.d/nix.sh ]; then . /home/bobo51881/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer

# Add krew to Path
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"

PROMPT='$(kube_ps1)'$PROMPT
kubeoff
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# initialize fasd
eval "$(fasd --init auto)"

[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
