#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$HOME/vm-results" "$HOME/.dotfiles"
exec > >(tee "$HOME/vm-results/provision.log") 2>&1
phase() { printf '%s\n' "$1" | tee "$HOME/vm-results/phase"; }
trap 'printf "%s\n" "$?" > "$HOME/vm-results/exit-status"' EXIT

phase 'Verify fresh Ubuntu Resolute cloud image'
date -u
cat /etc/os-release
test "$(. /etc/os-release; printf '%s' "${VERSION_CODENAME:-}")" = resolute
python3 -c 'import sys; assert sys.version_info >= (3, 9), sys.version'
(cd /tmp && sha256sum --check dotfiles-snapshot.sha256)
tar -xzf /tmp/dotfiles-snapshot.tar.gz -C "$HOME/.dotfiles"
cd "$HOME/.dotfiles"

phase 'Install declared shared bootstrap prerequisite'
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y direnv

phase 'Bootstrap project controller'
./bootstrap-tools --apply | tee "$HOME/vm-results/shared-tools-first.json"
./bootstrap-tools --apply | tee "$HOME/vm-results/shared-tools-repeat.json"
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads((Path.home() / 'vm-results/shared-tools-repeat.json').read_text())
assert report['changed'] is False and report['changes'] == [], report
PY
export PATH="$HOME/.local/bin:$PATH"
command -v hatch | tee "$HOME/vm-results/hatch-command.txt"
./ansible/bootstrap-resolute | tee "$HOME/vm-results/controller-bootstrap.log"
./ansible/run-resolute --syntax-check | tee "$HOME/vm-results/syntax-check.log"

phase 'Check mode against fresh Resolute'
printf '\n' | ./ansible/run-resolute --check | tee "$HOME/vm-results/check.log"

phase 'First package-baseline application'
printf '\n' | ./ansible/run-resolute --apply --install-packages | tee "$HOME/vm-results/apply-first.log"

phase 'Repeat package-baseline application and verify convergence'
printf '\n' | ./ansible/run-resolute --apply --install-packages | tee "$HOME/vm-results/apply-repeat.log"
python3 - <<'PY'
from pathlib import Path
import re
text = (Path.home() / 'vm-results/apply-repeat.log').read_text()
assert re.search(r'localhost\s*:\s*ok=\d+\s+changed=0\s+unreachable=0\s+failed=0', text), text[-4000:]
PY
phase 'RESOLUTE_PROFILE_REPLAY_COMPLETE'
df -h /
