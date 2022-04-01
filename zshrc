# Load Antigen

source ~/antigen/antigen.zsh
# Load Antigen configurations
antigen init ~/.antigenrc

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
if command -v renv 1>/dev/null 2>&1; then
  eval "$(renv init -)"
fi

# pyenv initialization
if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi

[[ -s "$HOME/.rvm/scripts/rvm" ]] && source "$HOME/.rvm/scripts/rvm" # Load RVM into a shell session *as a function*


if [ -e /home/bobo51881/.nix-profile/etc/profile.d/nix.sh ]; then . /home/bobo51881/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer

PROMPT='$(kube_ps1)'$PROMPT
kubeoff
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# initialize fasd
eval "$(fasd --init auto)"

[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
