# Load Antigen

source ~/antigen/antigen.zsh
# Load Antigen configurations
antigen init ~/.antigenrc

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$("$HOME/anaconda3/bin/conda" 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        . "$HOME/anaconda3/etc/profile.d/conda.sh"
    else
        export PATH="$HOME/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

source "$HOME/.dotfiles/tooling/disable-rvm-shell.sh"
export MISE_GLOBAL_CONFIG_FILE="$HOME/.dotfiles/config/mise/config.toml"
if [ -x "$HOME/.local/bin/mise" ]; then
  eval "$("$HOME/.local/bin/mise" activate zsh)"
fi

if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then . "$HOME/.nix-profile/etc/profile.d/nix.sh"; fi # added by Nix installer

PROMPT='$(kube_ps1)'$PROMPT
kubeoff
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# initialize fasd
eval "$(fasd --init auto)"
