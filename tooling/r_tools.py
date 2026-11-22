"""User-local Rig and R provisioning, compatible with system Python 3.8."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_policy(path):
    policy = json.loads(path.read_text())
    if policy.get('platform') != 'linux-x86_64' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('Only the reviewed Linux x86_64 profile is supported')
    rig = policy['rig']
    if rig['version'] != '0.11.1' or rig['url'] != (
            'https://github.com/r-lib/rig/releases/download/v0.11.1/'
            'r-rig_0.11.1-1_amd64.deb'):
        raise ValueError('The Rig archive must use the reviewed official release')
    if len(rig['sha256']) != 64 or any(char not in '0123456789abcdef' for char in rig['sha256']):
        raise ValueError('A Rig archive SHA-256 is required')
    for value in (rig['data_relative_path'], policy['r']['data_relative_path'], rig['bin_relative_path']):
        parsed = PurePosixPath(value)
        if parsed.is_absolute() or '..' in parsed.parts:
            raise ValueError('Managed paths must remain inside user directories')
    for value in (policy['r']['default_version'], policy['renv']['version']):
        if len(value.split('.')) != 3 or any(not part.isdigit() for part in value.split('.')):
            raise ValueError('Declare exact R and renv versions')
    glibc = policy['r']['portable_minimum_glibc'].split('.')
    if len(glibc) != 2 or any(not part.isdigit() for part in glibc):
        raise ValueError('Declare a major.minor glibc minimum')
    return policy


def run(args, env=None, check=True, capture=True):
    kwargs = {'env': env, 'text': True}
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = subprocess.run([str(arg) for arg in args], **kwargs)
    if check and result.returncode:
        detail = '\n'.join(part[-3000:] for part in (result.stderr, result.stdout) if part) if capture else ''
        raise RuntimeError('{} failed{}'.format(Path(str(args[0])).name,
                                                ':\n' + detail if detail else ''))
    return result


def inside(path, root):
    try:
        return os.path.commonpath([str(path), str(root)]) == str(root)
    except ValueError:
        return False


class RTools:
    def __init__(self, policy):
        self.policy = policy
        self.home = Path.home()
        self.data = Path(os.environ.get('XDG_DATA_HOME', str(self.home / '.local/share')))
        self.rig_binary = self.data / policy['rig']['data_relative_path'] / 'rig'
        self.rig_link = self.home / policy['rig']['bin_relative_path']
        self.r_root = self.data / policy['r']['data_relative_path']
        self.r_version = policy['r']['default_version']
        self.r_dir = self.r_root / self.r_version
        self.r_binary = self.r_dir / 'bin/R'
        self.rscript = self.r_dir / 'bin/Rscript'
        self.runtime = None
        self.runtime_r = None
        self.runtime_rscript = None
        self.package_library = self.home / 'R' / '{}-library'.format(platform.machine() + '-pc-linux-gnu') / '.'.join(self.r_version.split('.')[:2])
        self.env = {**os.environ, 'RIG_MODE': 'user', 'R_LIBS_USER': str(self.package_library)}
        self.r_link = self.home / '.local/bin/R'
        self.rscript_link = self.home / '.local/bin/Rscript'

    def glibc_version(self):
        try:
            value = os.confstr('CS_GNU_LIBC_VERSION').split()[-1]
            return tuple(int(part) for part in value.split('.'))
        except (AttributeError, OSError, ValueError, IndexError):
            return None

    def select_runtime(self):
        minimum = tuple(int(part) for part in self.policy['r']['portable_minimum_glibc'].split('.'))
        glibc = self.glibc_version()
        if glibc is not None and glibc >= minimum:
            self.runtime = 'rig-user'
            self.runtime_r = self.r_binary
            self.runtime_rscript = self.rscript
            return
        system_r = Path('/usr/bin/R')
        system_rscript = Path('/usr/bin/Rscript')
        if system_r.is_file() and system_rscript.is_file():
            result = run([system_r, '--version'], check=False)
            if result.returncode == 0 and 'R version ' + self.r_version in result.stdout:
                self.runtime = 'system-fallback'
                self.runtime_r = system_r
                self.runtime_rscript = system_rscript
                return
        actual = '.'.join(str(part) for part in glibc) if glibc else 'unknown'
        raise RuntimeError('portable Rig R requires glibc {}; this host has glibc {} and no matching system R {} is available'.format(
            self.policy['r']['portable_minimum_glibc'], actual, self.r_version))

    def rig_version(self, path=None):
        path = self.rig_binary if path is None else Path(path)
        if not path.is_file():
            return None
        result = run([path, '--version'], check=False)
        return self.policy['rig']['version'] if result.returncode == 0 and \
            self.policy['rig']['version'] in result.stdout + result.stderr else None

    def installed_r_version(self):
        if self.runtime is None:
            self.select_runtime()
        if not self.runtime_r.is_file() or not self.runtime_rscript.is_file():
            return None
        result = run([self.runtime_r, '--version'], check=False)
        if result.returncode:
            return None
        expected = 'R version ' + self.r_version
        return self.r_version if expected in result.stdout else None

    def default_r_version(self):
        if self.runtime == 'system-fallback' or not self.rig_binary.is_file():
            return None
        result = run([self.rig_link, 'default', '--user'], env=self.env, check=False)
        if result.returncode:
            return None
        return self.r_version if self.r_version in result.stdout.strip() else result.stdout.strip()

    def renv_installed(self):
        if self.installed_r_version() != self.r_version:
            return False
        expression = (
            "if (requireNamespace('renv', quietly=TRUE) && "
            "as.character(utils::packageVersion('renv')) == '{}') quit(save='no', status=0) "
            "else quit(save='no', status=1)"
        ).format(self.policy['renv']['version'])
        return run([self.runtime_rscript, '--slave', '-e', expression], env=self.env,
                   check=False).returncode == 0

    def managed_link(self, path):
        path = Path(path)
        if not (path.exists() or path.is_symlink()):
            return True
        target = Path(os.path.realpath(str(path)))
        return inside(target, self.r_root)

    def conflicts(self):
        conflicts = []
        if (self.rig_binary.exists() or self.rig_binary.is_symlink()) and self.rig_version() is None:
            conflicts.append('existing managed Rig path does not match the declared version: {}'.format(self.rig_binary))
        if (self.rig_link.exists() or self.rig_link.is_symlink()) and not (
                self.rig_link.is_symlink() and self.rig_link.resolve() == self.rig_binary.resolve()):
            conflicts.append('preserving existing Rig command: {}'.format(self.rig_link))
        if self.r_dir.exists() or self.r_dir.is_symlink():
            rig_r = self.r_dir / 'bin/R'
            result = run([rig_r, '--version'], check=False) if rig_r.is_file() else None
            if result is None or result.returncode or 'R version ' + self.r_version not in result.stdout:
                conflicts.append('existing Rig R path does not match the declared version: {}'.format(self.r_dir))
        if self.runtime != 'system-fallback':
            for link in (self.r_link, self.rscript_link):
                if not self.managed_link(link):
                    conflicts.append('preserving existing R command outside the Rig data directory: {}'.format(link))
        return conflicts

    def audit(self):
        self.select_runtime()
        changes = []
        if self.rig_version() != self.policy['rig']['version']:
            changes.append('install Rig {}'.format(self.policy['rig']['version']))
        if not (self.rig_link.is_symlink() and self.rig_link.resolve() == self.rig_binary.resolve()):
            changes.append('publish user-local rig command')
        if self.runtime == 'rig-user' and self.installed_r_version() != self.r_version:
            changes.append('install R {} in Rig user mode'.format(self.r_version))
        if self.runtime == 'rig-user' and self.default_r_version() != self.r_version:
            changes.append('set Rig default R to {}'.format(self.r_version))
        if not self.renv_installed():
            changes.append('install CRAN renv {}'.format(self.policy['renv']['version']))
        return {'changed': bool(changes), 'changes': changes, 'conflicts': self.conflicts(),
                'rig': str(self.rig_link), 'r_version': self.r_version,
                'runtime': self.runtime, 'r_binary': str(self.runtime_r),
                'renv_version': self.policy['renv']['version'],
                'r_data': str(self.r_root)}

    def install_rig(self):
        if self.rig_version() != self.policy['rig']['version']:
            if self.rig_binary.exists() or self.rig_binary.is_symlink():
                raise RuntimeError('Refusing to replace existing Rig data: {}'.format(self.rig_binary))
            dpkg_deb = shutil.which('dpkg-deb')
            if not dpkg_deb:
                raise RuntimeError('dpkg-deb is required to unpack the verified Rig package')
            request = urllib.request.Request(self.policy['rig']['url'], headers={'User-Agent': 'dotfiles-r-bootstrap'})
            with tempfile.TemporaryDirectory(prefix='.rig-bootstrap-') as temporary:
                stage = Path(temporary)
                package = stage / 'r-rig.deb'
                with urllib.request.urlopen(request, timeout=90) as response, package.open('wb') as output:
                    shutil.copyfileobj(response, output)
                digest = hashlib.sha256(package.read_bytes()).hexdigest()
                if digest != self.policy['rig']['sha256']:
                    raise RuntimeError('Rig package checksum mismatch; nothing installed')
                extracted = stage / 'root'
                extracted.mkdir()
                run([dpkg_deb, '-x', package, extracted])
                candidates = [item for item in extracted.rglob('rig')
                              if item.is_file() and os.access(str(item), os.X_OK)]
                if len(candidates) != 1:
                    found = [str(item.relative_to(extracted)) for item in candidates]
                    raise RuntimeError('Expected one executable named rig in the verified package; found {}'.format(found))
                candidate = candidates[0]
                if self.rig_version(candidate) != self.policy['rig']['version']:
                    raise RuntimeError('Rig binary version did not match the declaration')
                self.rig_binary.parent.mkdir(parents=True, exist_ok=True)
                staged_binary = self.rig_binary.parent / '.rig-staged'
                shutil.copy2(candidate, staged_binary)
                os.replace(str(staged_binary), str(self.rig_binary))
        self.rig_link.parent.mkdir(parents=True, exist_ok=True)
        if self.rig_link.exists() or self.rig_link.is_symlink():
            if not (self.rig_link.is_symlink() and self.rig_link.resolve() == self.rig_binary.resolve()):
                raise RuntimeError('Refusing to replace existing Rig command: {}'.format(self.rig_link))
        else:
            self.rig_link.symlink_to(self.rig_binary)

    def install_r(self):
        if self.runtime == 'system-fallback':
            return
        if self.installed_r_version() != self.r_version:
            if self.r_dir.exists() or self.r_dir.is_symlink():
                raise RuntimeError('Refusing to replace existing Rig R directory: {}'.format(self.r_dir))
            run([self.rig_link, 'add', self.r_version, '--user', '--no-default',
                 '--without-path', '--without-pak'], env=self.env, capture=False)
        if self.installed_r_version() != self.r_version:
            raise RuntimeError('Installed R did not match declared version {}'.format(self.r_version))
        if self.default_r_version() != self.r_version:
            run([self.rig_link, 'default', self.r_version, '--user'], env=self.env, capture=False)
        if self.default_r_version() != self.r_version:
            raise RuntimeError('Rig default did not converge to R {}'.format(self.r_version))

    def install_renv(self):
        if self.renv_installed():
            return
        if self.runtime == 'rig-user':
            run([self.rig_link, 'pkg', 'install', '--user', '--no-sysreqs',
                 '--r-version', self.r_version,
                 'renv@=' + self.policy['renv']['version']], env=self.env, capture=False)
        else:
            self.package_library.mkdir(parents=True, exist_ok=True)
            source = 'https://cran.r-project.org/src/contrib/renv_{}.tar.gz'.format(
                self.policy['renv']['version'])
            expression = "utils::install.packages('{}', repos=NULL, type='source', lib=Sys.getenv('R_LIBS_USER'))".format(source)
            run([self.runtime_rscript, '--slave', '-e', expression], env=self.env, capture=False)
        if not self.renv_installed():
            raise RuntimeError('CRAN renv did not match declared version {}'.format(self.policy['renv']['version']))

    def apply(self):
        self.select_runtime()
        audit = self.audit()
        if audit['conflicts']:
            raise RuntimeError('Resolve existing command/config conflicts manually: ' + '; '.join(audit['conflicts']))
        self.install_rig()
        self.install_r()
        self.install_renv()
        return self.audit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='download and install declared user tools')
    args = parser.parse_args()
    policy = load_policy(ROOT / 'config/r-tools.json')
    tools = RTools(policy)
    try:
        result = tools.apply() if args.apply else tools.audit()
    except (OSError, RuntimeError, ValueError) as error:
        print('R tooling did not converge: {}'.format(error), file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(result, indent=2))
    if result['conflicts']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
