"""User-local tooling reconciliation, compatible with Ubuntu Focal's Python 3.8."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(args, env=None):
    result = subprocess.run([str(a) for a in args], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('{} failed:\n{}'.format(Path(str(args[0])).name, result.stderr[-4000:]))
    return result.stdout.strip()


def probe(python, package=None):
    if not python.is_file():
        return None
    code = ('import json,sys; print(json.dumps({"version":".".join(map(str,sys.version_info[:3])), '
            '"prefix":sys.base_prefix}))')
    if package:
        code = ('import importlib.metadata; print(importlib.metadata.version({!r}))'.format(package))
    try:
        value = run([python, '-I', '-c', code])
        return value if package else json.loads(value)
    except (RuntimeError, ValueError, OSError):
        return None


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or str(path) == '.':
        raise ValueError('Managed paths must be relative and remain inside the user directory')
    return value


def load_policy(path):
    policy = json.loads(path.read_text())
    if policy['platform'] != 'linux-x86_64':
        raise ValueError('Only the reviewed Linux x86_64 profile is supported')
    for section, keys in [('python', ['data_relative_path', 'compatibility_alias', 'executable']),
                          ('pipx', ['data_relative_path', 'home_relative_path', 'bin_relative_path'])]:
        for key in keys:
            relative_path(policy[section][key])
    for section in ['python', 'pipx']:
        if not re.fullmatch(r'\d+\.\d+\.\d+', policy[section]['version']):
            raise ValueError('Explicit release versions are required')
    if not re.fullmatch('[a-f0-9]{64}', policy['python']['sha256']):
        raise ValueError('A Python archive SHA-256 is required')
    if not policy['python']['url'].startswith('https://github.com/astral-sh/python-build-standalone/releases/download/'):
        raise ValueError('Python archive must use the reviewed release source')
    if set(policy['applications']) != {'hatch'}:
        raise ValueError('This milestone manages Hatch only')
    if not re.fullmatch(r'\d+\.\d+\.\d+', policy['applications']['hatch']['version']):
        raise ValueError('An explicit Hatch release is required')
    if policy['system_packages'] != ['direnv']:
        raise ValueError('Review changes to the system prerequisite policy')
    return policy


def extract_verified_archive(archive, destination, checksum):
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != checksum:
        raise ValueError('Python archive checksum mismatch; nothing extracted')
    with tarfile.open(str(archive), 'r:gz') as stream:
        members = stream.getmembers()
        # The reviewed archive extracts under python/. Reject traversal and devices.
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'python':
                raise ValueError('Unsafe Python archive member')
            if member.isdev() or member.isfifo():
                raise ValueError('Unsupported Python archive member')
            if member.issym() or member.islnk():
                target = PurePosixPath(member.linkname)
                if target.is_absolute() or '..' in target.parts:
                    raise ValueError('Unsafe Python archive link')
        if hasattr(tarfile, 'data_filter'):
            stream.extractall(str(destination), filter='data')
        else:
            # Focal's Python predates extraction filters; members were checked above.
            stream.extractall(str(destination))


class SharedTools:
    def __init__(self, policy, home=None, data=None):
        self.policy = policy
        self.home = Path.home() if home is None else Path(home)
        self.data = Path(os.environ.get('XDG_DATA_HOME', str(self.home / '.local/share'))) if data is None else Path(data)
        self.runtime = self.data / policy['python']['data_relative_path']
        self.python = self.runtime / policy['python']['executable']
        self.alias = self.data / policy['python']['compatibility_alias']
        self.pipx_environment = self.data / policy['pipx']['data_relative_path']
        self.pipx_python = self.pipx_environment / 'bin/python'
        self.pipx_home = self.home / policy['pipx']['home_relative_path']
        self.bin = self.home / policy['pipx']['bin_relative_path']
        self.backups = self.data / 'laptop-tools/backups'
        self.hatch_environment = self.pipx_home / 'venvs/hatch'

    def pipx_env(self):
        return {**os.environ, 'PIPX_HOME': str(self.pipx_home), 'PIPX_BIN_DIR': str(self.bin),
                'PIPX_DEFAULT_PYTHON': str(self.python), 'PYTHONNOUSERSITE': '1'}

    def wrapper(self):
        return ('#!/bin/sh\n# Managed by dotfiles shared tool policy.\n'
                'export PIPX_HOME={}\nexport PIPX_BIN_DIR={}\nexport PIPX_DEFAULT_PYTHON={}\n'
                'exec {} -m pipx "$@"\n').format(
                    shlex.quote(str(self.pipx_home)), shlex.quote(str(self.bin)),
                    shlex.quote(str(self.python)), shlex.quote(str(self.pipx_python)))

    def audit(self):
        changes = []
        actual = probe(self.python)
        if not actual or actual['version'] != self.policy['python']['version']:
            changes.append('install declared standalone Python')
        if self.alias.resolve() != self.runtime.resolve():
            changes.append('create compatibility Python alias')
        pipx_runtime = probe(self.pipx_python)
        if (probe(self.pipx_python, 'pipx') != self.policy['pipx']['version'] or
                not pipx_runtime or Path(pipx_runtime['prefix']).resolve() != self.runtime.resolve()):
            changes.append('install isolated pipx {}'.format(self.policy['pipx']['version']))
        wrapper = self.bin / 'pipx'
        if wrapper.is_symlink() or not wrapper.is_file() or wrapper.read_text() != self.wrapper():
            changes.append('publish shared pipx command (back up existing entry)')
        actual_hatch = probe(self.hatch_environment / 'bin/python', 'hatch')
        hatch_runtime = probe(self.hatch_environment / 'bin/python')
        if (actual_hatch != self.policy['applications']['hatch']['version'] or not hatch_runtime or
                Path(hatch_runtime['prefix']).resolve() != self.runtime.resolve()):
            changes.append('install Hatch through pipx using declared Python')
        if (self.bin / 'hatch').resolve() != (self.hatch_environment / 'bin/hatch').resolve():
            changes.append('publish shared Hatch command')
        missing = []
        for name in self.policy['system_packages']:
            result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', name],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if result.returncode or result.stdout != 'install ok installed':
                missing.append(name)
        return {'changes': changes, 'missing_system_packages': missing,
                'python': str(self.python), 'pipx_home': str(self.pipx_home)}

    def backup(self, path):
        if not path.exists() and not path.is_symlink():
            return
        self.backups.mkdir(parents=True, exist_ok=True)
        name = path.name + '-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        destination = self.backups / name
        if path.is_dir() and not path.is_symlink():
            shutil.copytree(str(path), str(destination), symlinks=True)
        else:
            shutil.copy2(str(path), str(destination), follow_symlinks=False)

    def install_python(self):
        actual = probe(self.python)
        if actual and actual['version'] == self.policy['python']['version']:
            return
        if self.runtime.exists() or self.runtime.is_symlink():
            raise ValueError('Existing Python directory is incompatible; inspect it before replacement')
        self.runtime.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(self.runtime.parent)) as directory:
            stage = Path(directory)
            archive = stage / 'python.tar.gz'
            request = urllib.request.Request(self.policy['python']['url'], headers={'User-Agent': 'dotfiles-bootstrap'})
            with urllib.request.urlopen(request, timeout=60) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
            extract_verified_archive(archive, stage, self.policy['python']['sha256'])
            candidate = stage / 'python' / self.policy['python']['executable']
            actual = probe(candidate)
            if not actual or actual['version'] != self.policy['python']['version']:
                raise ValueError('Extracted Python does not match declared version')
            os.rename(str(stage / 'python'), str(self.runtime))
        if probe(self.python)['version'] != self.policy['python']['version']:
            raise ValueError('Python failed verification after relocation')

    def apply(self):
        # Fail before provisioning if a system prerequisite requires administrator action.
        before = self.audit()
        if before['missing_system_packages']:
            raise ValueError('Install the declared system packages first: ' + ', '.join(before['missing_system_packages']))
        self.install_python()
        if self.alias.resolve() != self.runtime.resolve():
            if self.alias.exists() or self.alias.is_symlink():
                raise ValueError('Existing compatibility alias targets another runtime; review dependents first')
            self.alias.parent.mkdir(parents=True, exist_ok=True)
            self.alias.symlink_to(self.runtime, target_is_directory=True)
        if not self.pipx_python.exists():
            if self.pipx_environment.exists():
                raise ValueError('Inspect the incomplete pipx environment before retrying')
            run([self.python, '-m', 'venv', self.pipx_environment])
        pipx_runtime = probe(self.pipx_python)
        if not pipx_runtime or Path(pipx_runtime['prefix']).resolve() != self.runtime.resolve():
            raise ValueError('Existing pipx environment uses an unexpected Python; inspect it first')
        if probe(self.pipx_python, 'pipx') != self.policy['pipx']['version']:
            run([self.pipx_python, '-m', 'pip', 'install', 'pipx==' + self.policy['pipx']['version']])
        if probe(self.pipx_python, 'pipx') != self.policy['pipx']['version']:
            raise ValueError('pipx version verification failed')
        self.bin.mkdir(parents=True, exist_ok=True)
        wrapper = self.bin / 'pipx'
        if wrapper.is_symlink() or not wrapper.is_file() or wrapper.read_text() != self.wrapper():
            self.backup(wrapper)
            with tempfile.NamedTemporaryFile(mode='w', dir=str(self.bin), delete=False) as stream:
                stream.write(self.wrapper())
                staged_wrapper = Path(stream.name)
            staged_wrapper.chmod(0o755)
            os.replace(str(staged_wrapper), str(wrapper))
        # Unrelated pipx applications are never reinstalled or removed.
        if 'install Hatch through pipx using declared Python' in self.audit()['changes']:
            self.backup(self.hatch_environment)
            run([self.pipx_python, '-m', 'pipx', 'install', '--force', '--python', self.python,
                 'hatch==' + self.policy['applications']['hatch']['version']], env=self.pipx_env())
        desired = self.hatch_environment / 'bin/hatch'
        entry = self.bin / 'hatch'
        if entry.resolve() != desired.resolve():
            if not desired.is_file():
                raise ValueError('Hatch command is missing after installation')
            self.backup(entry)
            staged_link = self.bin / '.hatch-managed-link'
            if staged_link.exists() or staged_link.is_symlink():
                raise ValueError('Temporary Hatch link exists; inspect it before retrying')
            staged_link.symlink_to(desired)
            os.replace(str(staged_link), str(entry))
        after = self.audit()
        if after['changes']:
            raise ValueError('Tooling did not converge: ' + ', '.join(after['changes']))
        return {'changed': bool(before['changes']), 'planned_changes': before['changes'], **after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true', help='apply user-local tool policy; default is audit only')
    modes.add_argument('--python-path', action='store_true', help='print the verified declared interpreter for project bootstrap')
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError('Run as the laptop user, not root or sudo')
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise ValueError('Only the reviewed Linux x86_64 profile is supported')
        tools = SharedTools(load_policy(ROOT / 'config/shared-python-tools.json'))
        if args.python_path:
            actual = probe(tools.python)
            if not actual or actual['version'] != tools.policy['python']['version']:
                raise ValueError('Declared Python is missing; run ./bootstrap-tools --apply first')
            print(tools.python)
            return
        report = tools.apply() if args.apply else {'changed': False, **tools.audit()}
        print(json.dumps(report, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
