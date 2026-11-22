
[[ -s "$HOME/.profile" ]] && source "$HOME/.profile" # Load the default .profile

export RIG_MODE=user
if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then . "$HOME/.nix-profile/etc/profile.d/nix.sh"; fi # added by Nix installer

# adds gpg key to bash profile
export GPG_TTY=$(tty)
