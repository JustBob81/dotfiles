"""User-local fnm and Node.js reconciliation, compatible with Python 3.8."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_policy(path):
    policy = json.loads(path.read_text())
    if policy.get('platform') != 'linux-x86_64':
        raise ValueError('Only the reviewed Linux x86_64 profile is supported')
    fnm = policy['fnm']
    if not re.fullmatch(r'\d+\.\d+\.\d+', fnm['version']):
        raise ValueError('An explicit fnm version is required')
    if not re.fullmatch('[a-f0-9]{64}', fnm['sha256']):
        raise ValueError('An fnm archive SHA-256 is required')
    expected_url = 'https://github.com/Schniz/fnm/releases/download/v{}/fnm-linux.zip'.format(fnm['version'])
    if fnm['url'] != expected_url:
        raise ValueError('The fnm archive must use the reviewed official release URL')
    for value in [fnm['data_relative_path'], fnm['bin_relative_path'], policy['node']['data_relative_path']]:
        path_value = PurePosixPath(value)
        if path_value.is_absolute() or '..' in path_value.parts:
            raise ValueError('Managed paths must remain inside the user data directories')
    versions = policy['node']['project_versions']
    if not versions or len(versions) != len(set(versions)) or any(
            not re.fullmatch(r'\d+\.\d+\.\d+', version) for version in versions):
        raise ValueError('Declare unique exact Node.js project versions')
    if not re.fullmatch(r'\d+\.\d+\.\d+', policy['node']['default']):
        raise ValueError('Pin the reviewed latest LTS release as the default')
    return policy


def command(args, env=None, check=True):
    result = subprocess.run([str(arg) for arg in args], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        detail = '\n'.join(part[-4000:] for part in (result.stderr, result.stdout) if part)
        raise RuntimeError('{} failed:\n{}'.format(Path(str(args[0])).name, detail))
    return result


class NodeTools:
    def __init__(self, policy, home=None, data=None):
        self.policy = policy
        self.home = Path.home() if home is None else Path(home)
        self.data = Path(os.environ.get('XDG_DATA_HOME', str(self.home / '.local/share'))) if data is None else Path(data)
        self.fnm_dir = self.data / policy['node']['data_relative_path']
        self.fnm_runtime = self.data / policy['fnm']['data_relative_path']
        self.fnm_binary = self.fnm_runtime / 'fnm'
        self.fnm_link = self.home / policy['fnm']['bin_relative_path']
        self.backups = self.data / 'laptop-tools/backups'

    def fnm_env(self):
        return {**os.environ, 'FNM_DIR': str(self.fnm_dir)}

    def fnm_version(self, path=None):
        path = self.fnm_binary if path is None else Path(path)
        if not path.is_file():
            return None
        result = command([path, '--version'], check=False)
        if result.returncode:
            return None
        match = re.search(r'\b(\d+\.\d+\.\d+)\b', result.stdout)
        return match.group(1) if match else None

    def backup(self, path):
        path = Path(path)
        if not path.exists() and not path.is_symlink():
            return None
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        target = self.backups / '{}-{}'.format(path.name, stamp)
        os.replace(str(path), str(target))
        return target

    def manager_is_published(self):
        return self.fnm_link.is_symlink() and self.fnm_link.resolve() == self.fnm_binary.resolve()

    def installed_node(self, version):
        if self.fnm_version() != self.policy['fnm']['version']:
            return False
        result = command([self.fnm_link, 'exec', '--using', version, 'node', '--version'],
                         env=self.fnm_env(), check=False)
        return result.returncode == 0 and result.stdout.strip().lstrip('v') == version

    def default_is_set(self):
        if self.fnm_version() != self.policy['fnm']['version']:
            return False
        result = command([self.fnm_link, 'ls'], env=self.fnm_env(), check=False)
        if result.returncode:
            return False
        expected = 'v' + self.policy['node']['default']
        return any(expected in line and 'default' in line for line in result.stdout.splitlines())

    def audit(self):
        changes = []
        if self.fnm_version() != self.policy['fnm']['version']:
            changes.append('install fnm {}'.format(self.policy['fnm']['version']))
        if not self.manager_is_published():
            changes.append('publish fnm command (preserve any existing entry)')
        if self.fnm_version() == self.policy['fnm']['version'] and self.manager_is_published():
            for version in self.policy['node']['project_versions']:
                if not self.installed_node(version):
                    changes.append('install Node.js {}'.format(version))
            if not self.installed_node(self.policy['node']['default']):
                changes.append('install latest Node.js LTS and set it as default')
            elif not self.default_is_set():
                changes.append('set latest Node.js LTS as default')
        elif self.fnm_version() != self.policy['fnm']['version']:
            for version in self.policy['node']['project_versions']:
                changes.append('install Node.js {}'.format(version))
            changes.append('install latest Node.js LTS and set it as default')
        return {'changed': bool(changes), 'changes': changes,
                'fnm': str(self.fnm_link), 'fnm_dir': str(self.fnm_dir),
                'project_versions': self.policy['node']['project_versions'],
                'default': self.policy['node']['default']}

    def install_fnm(self):
        if self.fnm_version() != self.policy['fnm']['version']:
            if self.fnm_runtime.exists():
                self.backup(self.fnm_runtime)
            self.fnm_runtime.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.fnm-stage-', dir=str(self.fnm_runtime.parent)) as stage_name:
                stage = Path(stage_name)
                archive = stage / 'fnm-linux.zip'
                request = urllib.request.Request(self.policy['fnm']['url'], headers={'User-Agent': 'dotfiles-node-bootstrap'})
                with urllib.request.urlopen(request, timeout=60) as response, archive.open('wb') as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                if digest != self.policy['fnm']['sha256']:
                    raise ValueError('fnm archive checksum mismatch; nothing installed')
                with zipfile.ZipFile(str(archive)) as bundle:
                    names = bundle.namelist()
                    if names != ['fnm']:
                        raise ValueError('Unexpected fnm archive contents')
                    candidate = stage / 'fnm'
                    with bundle.open('fnm') as source, candidate.open('wb') as output:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                candidate.chmod(0o755)
                if self.fnm_version(candidate) != self.policy['fnm']['version']:
                    raise ValueError('Downloaded fnm version did not match the declaration')
                staged_runtime = stage / 'runtime'
                staged_runtime.mkdir()
                os.replace(str(candidate), str(staged_runtime / 'fnm'))
                os.replace(str(staged_runtime), str(self.fnm_runtime))
        self.fnm_link.parent.mkdir(parents=True, exist_ok=True)
        if not self.manager_is_published():
            if self.fnm_link.exists() or self.fnm_link.is_symlink():
                self.backup(self.fnm_link)
            self.fnm_link.symlink_to(self.fnm_binary)

    def apply(self):
        before = self.audit()
        self.install_fnm()
        for version in self.policy['node']['project_versions']:
            command([self.fnm_link, 'install', version], env=self.fnm_env())
        command([self.fnm_link, 'install', self.policy['node']['default']], env=self.fnm_env())
        command([self.fnm_link, 'default', self.policy['node']['default']], env=self.fnm_env())
        after = self.audit()
        if after['changes']:
            raise ValueError('Node tooling did not converge: ' + ', '.join(after['changes']))
        return {'changed': before['changed'], 'applied': before['changes'], **after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true', help='download and install the declared Node tooling')
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError('Run as the laptop user, not root or sudo')
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise ValueError('Only the reviewed Linux x86_64 profile is supported')
        tools = NodeTools(load_policy(ROOT / 'config/node-tools.json'))
        report = tools.apply() if args.apply else tools.audit()
        print(json.dumps(report, indent=2))
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
