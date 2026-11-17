"""Offline preservation/protocol tests. No real user configuration is modified."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from emacs_tools import ROOT, EmacsTools, command, binary_version, extract_binary, extract_codex_package, check_codex_layout, inspect_snap, load_policy, read_versions
from acp_probe import probe_session


class EmacsToolTests(unittest.TestCase):
    def policy(self):
        return load_policy(ROOT / 'config/emacs-tools.json')

    def git(self, folder, *args):
        return subprocess.run(['git', '-C', str(folder), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def checkout(self, home):
        tools = EmacsTools(self.policy(), home)
        tools.checkout.mkdir()
        self.git(tools.checkout, 'init', '-q')
        self.git(tools.checkout, 'symbolic-ref', 'HEAD', 'refs/heads/topic')
        (tools.checkout / 'tracked').write_text('original\n')
        self.git(tools.checkout, 'add', 'tracked')
        self.git(tools.checkout, '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture',
                 '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        for remote in ['origin', 'upstream']:
            self.git(tools.checkout, 'remote', 'add', remote, tools.policy['checkout'][remote])
        return tools

    def test_existing_dirty_checkout_and_branch_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = self.checkout(Path(directory))
            (tools.checkout / 'tracked').write_text('uncommitted\n')
            (tools.checkout / 'untracked').write_text('keep me\n')
            before = (self.git(tools.checkout, 'rev-parse', 'HEAD'),
                      self.git(tools.checkout, 'status', '--porcelain'),
                      self.git(tools.checkout, 'branch', '--show-current'))
            tools.ensure_checkout()
            after = (self.git(tools.checkout, 'rev-parse', 'HEAD'),
                     self.git(tools.checkout, 'status', '--porcelain'),
                     self.git(tools.checkout, 'branch', '--show-current'))
            self.assertEqual(before, after)

    def test_conflicting_remote_is_reported_without_changing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = self.checkout(Path(directory))
            self.git(tools.checkout, 'remote', 'set-url', 'origin', 'git@example.invalid:mine.git')
            changes, conflicts = [], []
            tools.inspect_checkout(changes, conflicts)
            self.assertTrue(conflicts)
            self.assertEqual(self.git(tools.checkout, 'remote', 'get-url', 'origin'),
                             'git@example.invalid:mine.git')

    def test_missing_upstream_is_added_without_fetching_or_merging(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = self.checkout(Path(directory))
            self.git(tools.checkout, 'remote', 'remove', 'upstream')
            before = self.git(tools.checkout, 'rev-parse', 'HEAD')
            tools.ensure_checkout()
            self.assertEqual(self.git(tools.checkout, 'remote', 'get-url', 'upstream'),
                             tools.policy['checkout']['upstream'])
            self.assertEqual(self.git(tools.checkout, 'rev-parse', 'HEAD'), before)

    def test_new_clone_keeps_history_and_uses_reviewed_initial_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            source_home = Path(directory) / 'source'
            source_home.mkdir()
            source = self.checkout(source_home)
            initial = self.git(source.checkout, 'rev-parse', 'HEAD')
            (source.checkout / 'tracked').write_text('later\n')
            self.git(source.checkout, 'add', 'tracked')
            self.git(source.checkout, '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture',
                     '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'later')
            home = Path(directory) / 'destination'
            policy = self.policy()
            policy['checkout']['origin'] = str(source.checkout)
            policy['checkout']['initial_revision'] = initial
            tools = EmacsTools(policy, home)
            tools.ensure_checkout()
            self.assertEqual(self.git(tools.checkout, 'rev-parse', 'HEAD'), initial)
            self.assertEqual(self.git(tools.checkout, 'rev-parse', '--is-shallow-repository'), 'false')
            self.assertEqual(self.git(tools.checkout, 'rev-list', '--all', '--count'), '2')

    def test_manifest_is_data_and_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'versions.env'
            path.write_text('NODE_VERSION=24.22.2\nCODEX_ACP_VERSION=2.6.0\n')
            self.assertEqual(read_versions(path)['NODE_VERSION'], '24.22.2')
            path.write_text('NODE_VERSION=$(touch sentinel)\nCODEX_ACP_VERSION=2.6.0\n')
            with self.assertRaises(ValueError):
                read_versions(path)
            self.assertFalse((Path(directory) / 'sentinel').exists())

    def test_mise_calls_ignore_inherited_config_and_use_standalone_codex(self):
        tools = EmacsTools(self.policy())
        with patch.dict(os.environ, {'MISE_CONFIG_FILE': '/other/config', 'MISE_DATA_DIR': '/other/data',
                                     'CODEX_PATH': '/other/codex', 'NVM_DIR': '/keep/nvm'}):
            env = tools.isolated_env()
            self.assertNotIn('MISE_CONFIG_FILE', env)
            self.assertNotIn('MISE_DATA_DIR', env)
            self.assertEqual(env['MISE_NO_CONFIG'], '1')
            self.assertEqual(env['CODEX_PATH'], str(tools.bin / 'codex'))
            self.assertEqual(env['NVM_DIR'], '/keep/nvm')

    def test_binary_archive_checks_digest_without_extracting_archive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'release.tar.gz'
            payload = b'\x7fELFfixture'
            with tarfile.open(archive, 'w:gz') as stream:
                info = tarfile.TarInfo('../../codex')
                info.size = len(payload)
                stream.addfile(info, io.BytesIO(payload))
            destination = Path(directory) / 'verified'
            declaration = {'archive_binary_names': ['codex'],
                           'binary_sha256': hashlib.sha256(payload).hexdigest()}
            extract_binary(archive, destination, declaration)
            self.assertEqual(destination.read_bytes(), payload)
            declaration['binary_sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                extract_binary(archive, destination, declaration)
            self.assertFalse(destination.exists())

    def codex_archive(self, directory, extra=None):
        archive = directory / 'codex.tar.gz'
        declaration = self.policy()['binaries']['codex']
        payload = b'\x7fELFfixture'
        files = {name: payload for name in ['bin/codex', 'bin/codex-code-mode-host',
                 'bin/codex-exec-server', 'codex-resources/bwrap', 'codex-path/rg']}
        files['codex-package.json'] = json.dumps({'version': declaration['version'],
            'target': declaration['target'], 'entrypoint': 'bin/codex'}).encode()
        if extra:
            files.update(extra)
        with tarfile.open(archive, 'w:gz') as stream:
            for name, data in files.items():
                info = tarfile.TarInfo('package/' + name)
                info.size, info.mode = len(data), 0o755
                stream.addfile(info, io.BytesIO(data))
        declaration['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        declaration['binary_sha256'] = hashlib.sha256(payload).hexdigest()
        return archive, declaration

    def test_complete_codex_package_retains_helpers_and_requires_them(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            archive, declaration = self.codex_archive(directory)
            target = directory / 'installed'
            extract_codex_package(archive, target, declaration)
            check_codex_layout(target, declaration)
            (target / 'bin/codex-exec-server').unlink()
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                check_codex_layout(target, declaration)

    def test_codex_archive_digest_failure_prevents_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            archive, declaration = self.codex_archive(directory)
            declaration['archive_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'checksum'):
                extract_codex_package(archive, directory / 'installed', declaration)
            self.assertFalse((directory / 'installed').exists())

    def test_codex_archive_traversal_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            archive, declaration = self.codex_archive(directory, {'../../escape': b'bad'})
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                extract_codex_package(archive, directory / 'installed', declaration)
            self.assertFalse((directory / 'installed').exists())
            self.assertFalse((directory / 'escape').exists())

    def test_npm_codex_wrapper_is_not_accepted_as_standalone(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'codex'
            executable.write_text('#!/bin/sh\necho codex-cli 0.167.0\n')
            executable.chmod(0o755)
            with self.assertRaisesRegex(ValueError, 'standalone native'):
                binary_version(executable, 'codex')

    def test_unsupported_agent_shell_never_invokes_old_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = EmacsTools(self.policy(), Path(directory))
            (tools.checkout / 'elpa-31.1/agent-shell-20261115.1234').mkdir(parents=True)
            with patch('emacs_tools.command') as call:
                state = tools.package_state({'version': '31.1'})
                self.assertEqual(state['status'], 'review')
                call.assert_not_called()

    def test_conflict_stops_before_any_provisioning(self):
        tools = EmacsTools(self.policy())
        with patch.object(tools, 'audit', return_value={'conflicts': ['user file differs']}), \
             patch.object(tools, 'ensure_checkout') as clone, \
             patch.object(tools, 'ensure_binary') as install:
            with self.assertRaises(ValueError):
                tools.apply()
            clone.assert_not_called()
            install.assert_not_called()

    def test_installer_conflicts_are_visible_and_user_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = self.checkout(Path(directory))
            for name in ['LOCAL.md', 'tools/install-local.py', 'tests/test-startup.sh',
                         'tools/codex-acp/codex-acp']:
                path = tools.checkout / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture\n')
            (tools.checkout / tools.policy['adapter_manifest']).write_text('NODE_VERSION=24.22.2\nCODEX_ACP_VERSION=2.6.0\n')
            # Explicit fixture config path avoids touching actual user XDG paths.
            tools.config = Path(directory) / 'config'
            destination = tools.config / 'codex-acp/versions.env'
            destination.parent.mkdir(parents=True)
            destination.write_text('user-managed conflicting contents\n')
            report = tools.audit()
            self.assertTrue(any('Conflicting tooling destination' in c for c in report['conflicts']))
            self.assertEqual(destination.read_text(), 'user-managed conflicting contents\n')

    def test_snap_metadata_inspection_does_not_need_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / 'snap/emacs/current/meta/snap.yaml'
            metadata.parent.mkdir(parents=True)
            metadata.write_text("version: '31.1'\nconfinement: classic\n")
            result = inspect_snap(Path(directory))
            self.assertTrue(result['installed'])
            self.assertTrue(result['classic'])
            self.assertEqual(result['version'], '31.1')

    def test_failed_snap_launcher_cannot_be_reported_as_successful_startup(self):
        tools = EmacsTools(self.policy())
        result = subprocess.CompletedProcess([], 46, '', 'cannot track application process')
        with patch('emacs_tools.command', return_value=result) as call:
            with self.assertRaisesRegex(RuntimeError, 'Snap cannot run'):
                tools.startup_test()
            self.assertEqual(call.call_count, 1)

    def test_cold_package_install_has_separate_bounded_budget(self):
        tools = EmacsTools(self.policy())
        with patch('emacs_tools.inspect_snap', return_value={'version': '31.1'}), \
             patch.object(tools, 'package_state', side_effect=[{'status': 'missing'}, {'status': 'patched'}]), \
             patch.object(tools, 'check_emacs_launcher'), \
             patch.object(tools, 'startup_test') as startup:
            tools.prepare_packages()
            startup.assert_called_once_with(timeout=900)
        result = subprocess.CompletedProcess([], 0, 'Startup successful', '')
        with patch.object(tools, 'check_emacs_launcher'), \
             patch('emacs_tools.command', return_value=result) as call:
            tools.startup_test()
            self.assertEqual(call.call_args.kwargs['timeout'], 300)

    def test_timeout_preserves_bounded_package_diagnostics(self):
        failure = subprocess.TimeoutExpired(['sh'], 900,
            output=b'x' * 5000 + b'package installation progress', stderr=b'last package warning')
        with patch('emacs_tools.subprocess.run', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                command(['sh', '-e', 'tests/test-startup.sh'], timeout=900)
            message = str(caught.exception)
            self.assertIn('900 seconds', message)
            self.assertIn('package installation progress', message)
            self.assertIn('last package warning', message)
            self.assertLess(len(message), 4500)

    def test_timed_out_shell_stops_children_and_keeps_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'orphan-was-running'
            script = ("import subprocess,sys,time; "
                      "subprocess.Popen([sys.executable, '-c', "
                      "'import time,pathlib; time.sleep(0.8); pathlib.Path(' + repr(sys.argv[1]) + ').touch()']); "
                      "print('cold install progress',flush=True); time.sleep(10)")
            with self.assertRaisesRegex(RuntimeError, 'cold install progress'):
                command([sys.executable, '-c', script, sentinel], timeout=0.3, terminate_group=True)
            # Wait longer than the child's write delay to detect leaked installers.
            import time
            time.sleep(0.9)
            self.assertFalse(sentinel.exists())

    def test_acp_probe_sends_no_model_prompt_and_preserves_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / 'fake-acp'
            launcher.write_text('#!' + sys.executable + '\n' + '''import json,sys,os
for line in sys.stdin:
 message=json.loads(line)
 assert message['method'] in ['initialize','session/new']
 if message['method']=='session/new':
  assert message['params']['cwd']==os.getcwd()
 result={'protocolVersion':1} if message['method']=='initialize' else {'sessionId':'fixture'}
 print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
''')
            launcher.chmod(0o755)
            report = probe_session(launcher, directory, dict(os.environ), timeout=5)
            self.assertEqual(report['methods_sent'], ['initialize', 'session/new'])
            self.assertEqual(report['model_prompts_sent'], 0)


if __name__ == '__main__':
    unittest.main()
