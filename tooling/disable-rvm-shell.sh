# Remove effects of Ubuntu's /etc/profile.d/rvm.sh in interactive shells.
unset -f rvm 2>/dev/null || true

PATH=$(printf '%s' "$PATH" | awk -v RS=: -v ORS=: -v user_rvm="$HOME/.rvm/" \
  'NF && index($0, user_rvm) != 1 && index($0, "/usr/share/rvm/") != 1 && index($0, "/usr/local/rvm/") != 1 { print }')
PATH=${PATH%:}
export PATH

case "${GEM_HOME:-}" in
  "$HOME/.rvm/"*|/usr/share/rvm/*|/usr/local/rvm/*) unset GEM_HOME ;;
esac
case "${GEM_PATH:-}" in
  *"$HOME/.rvm/"*|*/usr/share/rvm/*|*/usr/local/rvm/*) unset GEM_PATH ;;
esac
case "${MY_RUBY_HOME:-}" in
  "$HOME/.rvm/"*|/usr/share/rvm/*|/usr/local/rvm/*) unset MY_RUBY_HOME ;;
esac
unset rvm_path rvm_bin_path rvm_prefix
hash -r 2>/dev/null || true
