"""Emacs integration: audit by default; no implicit Git updates or authentication."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile
import urllib.request

from shared_tools import ROOT, relative_path


def command(argv, cwd=None, env=None, timeout=60, check=True, terminate_group=False):
    try:
        arguments = [str(a) for a in argv]
        if terminate_group:
            # A timed-out shell must not leave package-installing Emacs children.
            with subprocess.Popen(arguments, cwd=cwd, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  start_new_session=True) as process:
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate()
                    raise subprocess.TimeoutExpired(arguments, timeout, output=stdout, stderr=stderr)
                result = subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
        else:
            result = subprocess.run(arguments, cwd=cwd, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def tail(output):
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            return (output or '')[-4000:]
        raise RuntimeError('{} timed out after {} seconds.\nstdout:\n{}\nstderr:\n{}'.format(
            Path(str(argv[0])).name, timeout, tail(error.stdout), tail(error.stderr))) from error
    if check and result.returncode:
        raise RuntimeError('{} failed ({}):\n{}'.format(
            Path(str(argv[0])).name, result.returncode, result.stderr[-3000:]))
    return result


def read_versions(path):
    """Read declarations, never execute shell code from the version manifest."""
    versions = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(NODE_VERSION|CODEX_ACP_VERSION)=(\d+\.\d+\.\d+)', line)
        if not match or match[1] in versions:
            raise ValueError('Unsupported or duplicate declaration in adapter manifest')
        versions[match[1]] = match[2]
    if set(versions) != {'NODE_VERSION', 'CODEX_ACP_VERSION'}:
        raise ValueError('Adapter manifest must declare Node and adapter versions')
    return versions


def load_policy(path):
    policy = json.loads(path.read_text())
    if policy['platform'] != 'linux-x86_64':
        raise ValueError('Only the reviewed Linux x86_64 profile is supported')
    relative_path(policy['checkout']['home_relative_path'])
    for name in ['adapter_manifest']:
        relative_path(policy[name])
    for name in ['helper', 'patch_file']:
        relative_path(policy['patch'][name])
    if policy['checkout']['origin'] != 'git@github.com:JustBob81/emacs.d.git':
        raise ValueError('Review the personal repository ownership before changing policy')
    if policy['checkout']['upstream'] != 'https://github.com/purcell/emacs.d.git':
        raise ValueError('Review the upstream repository before changing policy')
    if not re.fullmatch('[a-f0-9]{40}', policy['checkout']['initial_revision']):
        raise ValueError('Fresh checkouts require a full reviewed commit ID')
    if policy['emacs'] != {'provider': 'snap', 'name': 'emacs', 'channel': 'latest/stable',
                           'classic': True, 'last_verified_version': '31.1'}:
        raise ValueError('Review Emacs installation policy before changing it')
    for name, entry in policy['binaries'].items():
        prefixes = {'codex': 'https://github.com/openai/codex/releases/download/',
                    'mise': 'https://github.com/jdx/mise/releases/download/'}
        if name not in prefixes or not entry['url'].startswith(prefixes[name]):
            raise ValueError('Unreviewed binary release source')
        if not re.fullmatch('[a-f0-9]{64}', entry['binary_sha256']):
            raise ValueError('A pinned executable digest is required')
        if not re.fullmatch(r'\d+\.\d+\.\d+', entry['version']):
            raise ValueError('A pinned binary version is required')
    if set(policy['binaries']) != {'codex', 'mise'}:
        raise ValueError('Codex and Mise declarations are required')
    codex = policy['binaries']['codex']
    if not re.fullmatch('[a-f0-9]{64}', codex['archive_sha256']):
        raise ValueError('A pinned complete Codex archive digest is required')
    if codex['target'] != 'x86_64-unknown-linux-musl':
        raise ValueError('Unreviewed Codex package target')
    return policy


def inspect_snap(root=Path('/')):
    metadata = root / 'snap/emacs/current/meta/snap.yaml'
    result = {'installed': metadata.is_file(), 'version': None, 'classic': None, 'channel': None}
    if metadata.is_file():
        text = metadata.read_text()
        for key in ['version', 'confinement']:
            found = re.search(r'^' + key + r':\s*[\'\"]?([^\n\'\"]+)', text, re.MULTILINE)
            if found:
                result['version' if key == 'version' else 'classic'] = found[1].strip() if key == 'version' else found[1].strip() == 'classic'
    try:
        entry = json.loads((root / 'var/lib/snapd/state.json').read_text())['data']['snaps']['emacs']
        result['channel'] = entry.get('tracking-channel') or entry.get('channel')
    except (OSError, ValueError, KeyError):
        pass
    if root == Path('/') and result['installed'] and not result['channel']:
        try:
            listing = command(['snap', 'list', 'emacs'], check=False, timeout=3)
            for line in listing.stdout.splitlines():
                fields = line.split()
                if len(fields) >= 6 and fields[0] == 'emacs':
                    result['channel'] = fields[3]
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            pass
    return result


def binary_version(path, name):
    if not path.exists():
        return None
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            raise ValueError('{} is not a standalone native binary: {}'.format(name, path))
    output = command([path, '--version']).stdout
    found = re.search(r'\b(\d+\.\d+\.\d+)\b', output)
    if not found:
        raise ValueError('Could not inspect {} version'.format(name))
    return found[1]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def extract_binary(archive, destination, declaration):
    """Extract one regular executable without materializing arbitrary archive paths."""
    with tarfile.open(str(archive), 'r:gz') as stream:
        members = [m for m in stream.getmembers()
                   if m.isfile() and Path(m.name).name in declaration['archive_binary_names']]
        if len(members) != 1:
            raise ValueError('Expected exactly one declared executable in release archive')
        member = members[0]
        with stream.extractfile(member) as source, destination.open('wb') as output:
            shutil.copyfileobj(source, output)
    if sha256_file(destination) != declaration['binary_sha256']:
        destination.unlink()
        raise ValueError('Release executable digest mismatch')
    destination.chmod(0o755)


def check_codex_layout(directory, declaration):
    metadata = json.loads((directory / 'codex-package.json').read_text())
    if (metadata.get('version') != declaration['version'] or
            metadata.get('target') != declaration['target'] or metadata.get('entrypoint') != 'bin/codex'):
        raise ValueError('Codex package metadata differs from policy')
    for name in ['bin/codex', 'bin/codex-code-mode-host', 'bin/codex-exec-server',
                 'codex-resources/bwrap', 'codex-path/rg']:
        if not (directory / name).is_file() or not os.access(directory / name, os.X_OK):
            raise ValueError('Codex standalone package is incomplete: ' + name)


def extract_codex_package(archive, destination, declaration):
    if sha256_file(archive) != declaration['archive_sha256']:
        raise ValueError('Codex package archive checksum mismatch')
    with tarfile.open(str(archive), 'r:gz') as stream:
        members = stream.getmembers()
        manifests = [m for m in members if m.isfile() and Path(m.name).name == 'codex-package.json']
        if len(manifests) != 1:
            raise ValueError('Expected one standalone Codex package manifest')
        prefix = PurePosixPath(manifests[0].name).parent
        prepared = []
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe or unsupported Codex archive entry')
            try:
                relative = path.relative_to(prefix)
            except ValueError:
                # Permit the enclosing directory itself, never unrelated payloads.
                if member.isdir() and path in prefix.parents:
                    continue
                raise ValueError('Codex archive entry is outside its package root')
            prepared.append((member, relative))
        for member, relative in prepared:
            target = destination / str(relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with stream.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
    check_codex_layout(destination, declaration)
    if sha256_file(destination / 'bin/codex') != declaration['binary_sha256']:
        raise ValueError('Codex executable digest differs from reviewed binary')


class EmacsTools:
    def __init__(self, policy, home=None):
        self.policy = policy
        self.home = Path.home() if home is None else Path(home)
        self.checkout = self.home / policy['checkout']['home_relative_path']
        self.bin = self.home / '.local/bin'
        self.config = Path(os.environ.get('XDG_CONFIG_HOME', str(self.home / '.config')))
        self.data = Path(os.environ.get('XDG_DATA_HOME', str(self.home / '.local/share'))) / 'emacs-tools'
        self.emacs = Path('/snap/bin/emacs')

    def links(self):
        return {self.config / 'codex-acp/versions.env': self.checkout / self.policy['adapter_manifest'],
                self.bin / 'codex-acp': self.checkout / 'tools/codex-acp/codex-acp'}

    def isolated_env(self):
        env = dict(os.environ)
        # Do not inherit project redirection of the runtime manager or auth binary.
        for key in list(env):
            if key.startswith('MISE_'):
                del env[key]
        env['MISE_NO_CONFIG'] = '1'
        env['CODEX_PATH'] = str(self.bin / 'codex')
        return env

    def inspect_checkout(self, changes, conflicts):
        if not self.checkout.exists() and not self.checkout.is_symlink():
            changes.append('clone full personal emacs.d repository at reviewed initial revision')
            return False
        top = command(['git', '-C', self.checkout, 'rev-parse', '--show-toplevel'], check=False)
        if top.returncode or Path(top.stdout.strip()).resolve() != self.checkout.resolve():
            conflicts.append('Existing Emacs path is not its own Git checkout')
            return False
        for remote in ['origin', 'upstream']:
            result = command(['git', '-C', self.checkout, 'remote', 'get-url', remote], check=False)
            if result.returncode:
                changes.append('add missing {} remote'.format(remote))
            elif result.stdout.strip() != self.policy['checkout'][remote]:
                conflicts.append('{} remote differs; preserve and review it'.format(remote))
        return True

    def package_state(self, snap):
        version = snap.get('version')
        if not version:
            return {'status': 'unknown'}
        # Matches init-elpa.el's per-major/minor package directory convention.
        pieces = version.split('.')
        directory = self.checkout / ('elpa-' + '.'.join(pieces[:2]))
        packages = sorted(directory.glob('agent-shell-*')) if directory.is_dir() else []
        if not packages:
            return {'status': 'missing'}
        if len(packages) != 1:
            return {'status': 'review', 'reason': 'Multiple installed package versions; inspect package.el selection'}
        package = packages[0]
        installed = package.name[len('agent-shell-'):]
        if installed != self.policy['patch']['supported_agent_shell'] or int(pieces[0]) < self.policy['patch']['minimum_emacs_major']:
            return {'status': 'review', 'version': installed,
                    'reason': 'Old patch not applied: review newer/unsupported package source and test it'}
        if not shutil.which('patch'):
            return {'status': 'review', 'reason': 'Install the declared patch system prerequisite'}
        patch = self.checkout / self.policy['patch']['patch_file']
        if not patch.is_file():
            return {'status': 'review', 'reason': 'Patch source missing from checkout'}
        args = ['patch', '--dry-run', '--batch', '--forward', '-p1', '-i', patch]
        if command(args, cwd=package, check=False).returncode == 0:
            return {'status': 'patch-needed', 'version': installed}
        if command(args + ['-R'], cwd=package, check=False).returncode != 0:
            return {'status': 'conflict', 'reason': 'Supported package differs from original and patched source'}
        targets = ['agent-shell-artist.el', 'agent-shell-devcontainer.el', 'agent-shell-viewport.el', 'agent-shell.el']
        stale = any(not (package / (name + 'c')).is_file() or
                    (package / (name + 'c')).stat().st_mtime < (package / name).stat().st_mtime
                    for name in targets)
        return {'status': 'compile-needed' if stale else 'patched', 'version': installed}

    def runtime_installed(self, versions):
        specs = ['node@' + versions['NODE_VERSION'],
                 'npm:@agentclientprotocol/codex-acp@' + versions['CODEX_ACP_VERSION']]
        paths = []
        for spec in specs:
            result = command([self.bin / 'mise', 'where', spec], cwd=self.checkout,
                             env=self.isolated_env(), check=False)
            if result.returncode or not Path(result.stdout.strip()).is_dir():
                return False
            paths.append(result.stdout.strip())
        return bool(paths)

    def audit(self):
        changes, conflicts, warnings = [], [], []
        snap = inspect_snap()
        if not snap['installed']:
            changes.append('install Emacs classic Snap from latest/stable')
        elif not snap['classic']:
            conflicts.append('Existing Emacs Snap is not classic; review before changing')
        if snap['channel'] and snap['channel'] != self.policy['emacs']['channel']:
            conflicts.append('Existing Emacs Snap tracks another channel; no automatic switch')
        if snap['installed'] and not snap['channel']:
            warnings.append('Snap tracking channel is not readable here; verify snap list emacs in a normal terminal')
        present = self.inspect_checkout(changes, conflicts)
        installed = {}
        for name, declaration in self.policy['binaries'].items():
            target = self.bin / name
            try:
                actual = binary_version(target, name)
                if actual is None:
                    if target.is_symlink():
                        conflicts.append('{} is a broken user-managed link'.format(target))
                    else:
                        changes.append('install standalone {} {}'.format(name, declaration['version']))
                elif actual != declaration['version']:
                    conflicts.append('Existing {} {} differs from {}; not replaced'.format(name, actual, declaration['version']))
                installed[name] = actual == declaration['version']
                if name == 'codex' and installed[name]:
                    check_codex_layout(target.resolve().parent.parent, declaration)
            except (ValueError, RuntimeError, OSError) as error:
                conflicts.append(str(error))
                installed[name] = False
        versions, package = None, {'status': 'unknown'}
        if present:
            for required in ['LOCAL.md', 'tools/install-local.py', self.policy['adapter_manifest'],
                             'tools/codex-acp/codex-acp', 'tests/test-startup.sh']:
                if not (self.checkout / required).is_file():
                    conflicts.append('Missing required Emacs source: ' + required)
            manifest = self.checkout / self.policy['adapter_manifest']
            if manifest.is_file():
                versions = read_versions(manifest)
            for destination, source in self.links().items():
                temporary = destination.with_name(destination.name + '.emacs-config-link')
                if temporary.exists() or temporary.is_symlink():
                    conflicts.append('Installer temporary path already exists: ' + str(temporary))
                if not source.is_file():
                    continue
                if destination.exists() or destination.is_symlink():
                    if not destination.is_file() or destination.read_bytes() != source.read_bytes():
                        conflicts.append('Conflicting tooling destination: ' + str(destination))
                        continue
                if not destination.is_symlink() or destination.resolve() != source.resolve():
                    changes.append('link ' + str(destination))
            if versions and installed.get('mise') and not self.runtime_installed(versions):
                changes.append('install manifest-selected Node and ACP adapter with isolated Mise')
            package = self.package_state(snap)
            if package['status'] in ['missing', 'patch-needed', 'compile-needed']:
                changes.append('prepare agent-shell through package.el and its guarded patch')
            elif package['status'] == 'conflict':
                conflicts.append(package['reason'])
            elif package['status'] == 'review':
                warnings.append(package['reason'])
        return {'changes': changes, 'conflicts': conflicts, 'warnings': warnings,
                'snap': snap, 'adapter_versions': versions, 'agent_shell': package,
                'checkout': str(self.checkout)}

    def ensure_checkout(self):
        if not self.checkout.exists():
            self.checkout.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=str(self.checkout.parent), prefix='.emacs-clone-') as folder:
                clone = Path(folder) / 'checkout'
                command(['git', 'clone', '--no-checkout', self.policy['checkout']['origin'], clone], timeout=300)
                command(['git', '-C', clone, 'checkout', '--detach', self.policy['checkout']['initial_revision']])
                os.rename(str(clone), str(self.checkout))
        # Existing checkout, local changes, branch and history are never updated/reset.
        for remote in ['origin', 'upstream']:
            result = command(['git', '-C', self.checkout, 'remote', 'get-url', remote], check=False)
            if result.returncode:
                command(['git', '-C', self.checkout, 'remote', 'add', remote, self.policy['checkout'][remote]])

    def ensure_binary(self, name):
        declaration = self.policy['binaries'][name]
        target = self.bin / name
        if target.exists():
            return
        if name == 'codex':
            return self.install_codex_package()
        directory = self.data / (name + '-' + declaration['version'])
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / name
        if not executable.exists():
            with tempfile.TemporaryDirectory(dir=str(directory)) as folder:
                archive, staged = Path(folder) / 'release.tar.gz', Path(folder) / name
                with urllib.request.urlopen(declaration['url'], timeout=60) as response, archive.open('wb') as output:
                    shutil.copyfileobj(response, output)
                extract_binary(archive, staged, declaration)
                if binary_version(staged, name) != declaration['version']:
                    raise ValueError('Downloaded binary version mismatch')
                os.rename(str(staged), str(executable))
        if (sha256_file(executable) != declaration['binary_sha256'] or
                binary_version(executable, name) != declaration['version']):
            raise ValueError('Existing managed executable does not match release policy')
        self.bin.mkdir(parents=True, exist_ok=True)
        target.symlink_to(executable)

    def install_codex_package(self):
        declaration = self.policy['binaries']['codex']
        directory = self.data / ('codex-' + declaration['version'])
        self.data.mkdir(parents=True, exist_ok=True)
        if not directory.exists():
            with tempfile.TemporaryDirectory(dir=str(self.data)) as folder:
                archive = Path(folder) / 'codex.tar.gz'
                staged = Path(folder) / 'package'
                with urllib.request.urlopen(declaration['url'], timeout=60) as response, archive.open('wb') as output:
                    shutil.copyfileobj(response, output)
                extract_codex_package(archive, staged, declaration)
                if binary_version(staged / 'bin/codex', 'codex') != declaration['version']:
                    raise ValueError('Codex package version check failed')
                os.rename(str(staged), str(directory))
        check_codex_layout(directory, declaration)
        if sha256_file(directory / 'bin/codex') != declaration['binary_sha256']:
            raise ValueError('Existing managed Codex executable differs from policy')
        self.bin.mkdir(parents=True, exist_ok=True)
        (self.bin / 'codex').symlink_to(directory / 'bin/codex')

    def check_emacs_launcher(self):
        result = command([self.emacs, '--version'], check=False, timeout=20)
        if result.returncode or not re.search(r'GNU Emacs \d+', result.stdout):
            raise RuntimeError('Emacs Snap cannot run here; use a normal local terminal.\n' + result.stderr[-1500:])

    def prepare_packages(self):
        snap = inspect_snap()
        state = self.package_state(snap)
        if state['status'] == 'missing':
            self.check_emacs_launcher()
            # The repo's complete init lets package.el/MELPA own dependencies.
            self.startup_test(timeout=900)
            state = self.package_state(snap)
        if state['status'] in ['patch-needed', 'compile-needed']:
            self.check_emacs_launcher()
            command([self.emacs, '-Q', '--batch', '-l', 'early-init.el', '-L', 'lisp', '-l', 'init-elpa.el',
                     '-l', self.policy['patch']['helper']], cwd=self.checkout, timeout=180)
        elif state['status'] in ['missing', 'unknown', 'conflict']:
            raise ValueError('Cannot determine a usable agent-shell installation: ' + str(state))
        # Unsupported/newer releases are preserved and explicitly flagged for review.

    def apply(self):
        before = self.audit()
        if before['conflicts']:
            raise ValueError('Provisioning refused:\n' + '\n'.join(before['conflicts']))
        if not before['snap']['installed']:
            raise ValueError('Install the declared Emacs Snap through the Ansible role first')
        self.ensure_checkout()
        # Inspect a fresh clone before executing its installer or changing global tools.
        inspected = self.audit()
        if inspected['conflicts']:
            raise ValueError('Checkout preflight failed:\n' + '\n'.join(inspected['conflicts']))
        for name in ['codex', 'mise']:
            self.ensure_binary(name)
        command(['/usr/bin/python3', 'tools/install-local.py'], cwd=self.checkout)
        versions = read_versions(self.checkout / self.policy['adapter_manifest'])
        if not self.runtime_installed(versions):
            command([self.bin / 'mise', 'install', 'node@' + versions['NODE_VERSION'],
                     'npm:@agentclientprotocol/codex-acp@' + versions['CODEX_ACP_VERSION']],
                    cwd=self.checkout, env=self.isolated_env(), timeout=600)
        self.prepare_packages()
        after = self.audit()
        if after['changes'] or after['conflicts']:
            raise ValueError('Provisioning did not converge: ' + json.dumps(after))
        return {'changed': bool(before['changes']), **after}

    def startup_test(self, timeout=300):
        self.check_emacs_launcher()  # The shell test alone may falsely return zero.
        env = {**os.environ, 'EMACS': str(self.emacs), 'EMACS_CONFIG_DIR': str(self.checkout)}
        result = command(['sh', '-e', 'tests/test-startup.sh'], cwd=self.checkout, env=env, timeout=timeout, terminate_group=True)
        errors = ['cannot run snap applications', 'cannot track application process', 'Debugger entered--Lisp error']
        if any(marker in result.stdout + result.stderr for marker in errors) or 'Startup successful' not in result.stdout:
            raise RuntimeError('Startup did not actually succeed:\n' + result.stderr[-2000:])

    def validate(self):
        report = self.audit()
        if report['changes'] or report['conflicts']:
            raise ValueError('Provisioning needs attention before validation: ' + json.dumps(report))
        self.startup_test()
        result = command([self.emacs, '-Q', '--batch', '-l', 'early-init.el', '-l', 'init.el',
                          '-l', 'tests/init-sessions-tests.el', '-l', 'tests/agent-shell-compat-tests.el',
                          '--eval', '(setq kill-emacs-hook nil)', '-f', 'ert-run-tests-batch-and-exit'],
                         cwd=self.checkout, timeout=300)
        output = result.stdout + result.stderr
        if not re.search(r'Ran [1-9]\d* tests, [1-9]\d* results as expected, 0 unexpected', output):
            raise RuntimeError('ERT did not report successful regression tests:\n' + output[-3000:])
        return {'startup_shutdown': 'passed', 'ert': 'passed', 'warnings': report['warnings'],
                'interactive_verification': 'Run M-x agent-shell / C-c C-a in a project; C-c a remains Org agenda'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--apply', action='store_true')
    modes.add_argument('--validate', action='store_true')
    modes.add_argument('--validate-acp', action='store_true', help='initialize and create an ACP session without any model prompt')
    args = parser.parse_args()
    try:
        if os.geteuid() == 0:
            raise ValueError('Run as the laptop user, not root or sudo')
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise ValueError('Only Linux x86_64 is currently reviewed')
        tools = EmacsTools(load_policy(ROOT / 'config/emacs-tools.json'))
        if args.validate_acp:
            from acp_probe import probe_session
            report = probe_session(tools.bin / 'codex-acp', tools.checkout, tools.isolated_env())
        else:
            report = tools.apply() if args.apply else tools.validate() if args.validate else {'changed': False, **tools.audit()}
        print(json.dumps(report, indent=2))
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
