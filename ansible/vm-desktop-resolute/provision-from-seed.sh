#!/usr/bin/env bash
set -euo pipefail
seed_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
results="$HOME/resolute-desktop-results"
mkdir -p "$results" "$HOME/.dotfiles"
exec > >(tee -a "$results/provision.log") 2>&1
phase() { printf '\n%s\n' "$1" | tee "$results/phase"; }
trap 'printf "%s\n" "$?" > "$results/exit-status"' EXIT

phase 'Verify installed Ubuntu Resolute Desktop and source media'
cat /etc/os-release
test "$(. /etc/os-release; printf '%s' "${VERSION_CODENAME:-}")" = resolute
(cd "$seed_dir" && sha256sum --check dotfiles-snapshot.sha256)
tar -xzf "$seed_dir/dotfiles-snapshot.tar.gz" -C "$HOME/.dotfiles"
cd "$HOME/.dotfiles"

phase 'Install base bootstrap prerequisite'
sudo apt-get update
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y direnv

phase 'Bootstrap maintained Resolute controller'
./bootstrap-tools --apply | tee "$results/shared-tools-first.json"
./bootstrap-tools --apply | tee "$results/shared-tools-repeat.json"
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads((Path.home() / 'resolute-desktop-results/shared-tools-repeat.json').read_text())
assert report['changed'] is False and report['changes'] == [], report
PY
export PATH="$HOME/.local/bin:$PATH"
./ansible/bootstrap-resolute | tee "$results/controller-bootstrap.log"
./ansible/run-resolute --syntax-check | tee "$results/syntax-check.log"

phase 'Preview Resolute baseline'
./ansible/run-resolute --check | tee "$results/check.log"

phase 'Apply selected package baseline'
./ansible/run-resolute --apply --install-packages | tee "$results/apply-first.log"

phase 'Repeat application and verify convergence'
./ansible/run-resolute --apply --install-packages | tee "$results/apply-repeat.log"
python3 - <<'PY'
from pathlib import Path
import re
text = (Path.home() / 'resolute-desktop-results/apply-repeat.log').read_text()
assert re.search(r'localhost\s*:\s*ok=\d+\s+changed=0\s+unreachable=0\s+failed=0', text), text[-4000:]
PY
phase 'RESOLUTE_DESKTOP_PROFILE_SETUP_COMPLETE'
df -h /
