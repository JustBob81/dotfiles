
[[ -s "$HOME/.profile" ]] && source "$HOME/.profile" # Load the default .profile

[[ -s "$HOME/.rvm/scripts/rvm" ]] && source "$HOME/.rvm/scripts/rvm" # Load RVM into a shell session *as a function*
export RENV_ROOT="$HOME/.renv"
export PATH="$RENV_ROOT/bin:$PATH"
if command -v renv 1>/dev/null 2>&1; then
  eval "$(renv init -)"
fi
if [ -e /home/bobo51881/.nix-profile/etc/profile.d/nix.sh ]; then . /home/bobo51881/.nix-profile/etc/profile.d/nix.sh; fi # added by Nix installer
