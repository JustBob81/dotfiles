"""Offline behavioral checks; Ansible runtime validation remains a separate gate."""
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class FoundationTests(unittest.TestCase):
    def run_wrapper(self, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            self.wrapper_root = Path(directory) / 'project'
            (self.wrapper_root / 'ansible').mkdir(parents=True)
            (self.wrapper_root / '.hatch/bin').mkdir(parents=True)
            shutil.copy(ROOT / 'ansible/run', self.wrapper_root / 'ansible/run')
            executable = self.wrapper_root / '.hatch/bin/ansible-playbook'
            executable.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                                  'print(json.dumps({"args": sys.argv[1:], '
                                  '"config": os.environ.get("ANSIBLE_CONFIG")}))\n')
            executable.chmod(0o755)
            return subprocess.run([str(self.wrapper_root / 'ansible/run'), *arguments],
                                  env={**os.environ, 'PATH': directory + ':' + os.environ['PATH']},
                                  capture_output=True, text=True, cwd='/tmp')

    def test_preview_is_default_even_from_another_directory(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads(result.stdout)
        self.assertIn('--check', call['args'])
        self.assertIn('--diff', call['args'])
        self.assertEqual(call['config'], str(self.wrapper_root / 'ansible/ansible.cfg'))
        self.assertEqual(json.loads(call['args'][-1]), {'laptop_manage_packages': False})

    def test_application_requires_explicit_mode(self):
        result = self.run_wrapper('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(result.stdout)['args']
        self.assertNotIn('--check', args)
        self.assertIn('--ask-become-pass', args)
        self.assertEqual(json.loads(args[-1]), {'laptop_manage_packages': False})

    def test_package_management_is_explicit(self):
        result = self.run_wrapper('--check', '--install-packages')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(result.stdout)['args']
        self.assertIn('--check', args)
        self.assertEqual(json.loads(args[-1]), {'laptop_manage_packages': True})

    def test_unknown_flags_do_not_reach_ansible(self):
        result = self.run_wrapper('--apply', '--extra-vars', 'laptop_manage_packages=true')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')

    def test_yaml_documents_parse(self):
        for path in (ROOT / 'ansible').rglob('*.yml'):
            with self.subTest(path=path):
                self.assertIsNotNone(yaml.safe_load(path.read_text()))

    def test_partner_rewrite_preserves_other_sources_and_is_repeatable(self):
        tasks = yaml.safe_load((ROOT / 'ansible/roles/repositories/tasks/main.yml').read_text())
        operation = next(t['ansible.builtin.replace'] for t in tasks if 'ansible.builtin.replace' in t)
        pattern = operation['regexp']
        replacement = operation['replace']
        for line in [
            'deb http://archive.canonical.com/ubuntu focal partner',
            'deb-src https://archive.canonical.com/ubuntu/ focal partner',
            'deb [arch=amd64] http://archive.canonical.com/ubuntu focal partner',
        ]:
            with self.subTest(line=line):
                changed = re.sub(pattern, replacement, line, flags=re.MULTILINE)
                self.assertTrue(changed.startswith('# Disabled by laptop repository policy: '))
                self.assertEqual(re.sub(pattern, replacement, changed, flags=re.MULTILINE), changed)
        for line in [
            '# deb http://archive.canonical.com/ubuntu focal partner',
            'deb http://archive.ubuntu.com/ubuntu focal main',
            'deb https://example.invalid/ubuntu focal partner',
        ]:
            self.assertEqual(re.sub(pattern, replacement, line, flags=re.MULTILINE), line)

    def test_wrapper_refuses_global_ansible_when_project_environment_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            (project / 'ansible').mkdir(parents=True)
            shutil.copy(ROOT / 'ansible/run', project / 'ansible/run')
            fake_global = Path(directory) / 'ansible-playbook'
            fake_global.write_text('#!/bin/sh\necho WRONG_ANSIBLE\n')
            fake_global.chmod(0o755)
            result = subprocess.run([str(project / 'ansible/run'), '--syntax-check'],
                                    env={**os.environ, 'PATH': directory + ':' + os.environ['PATH']},
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('WRONG_ANSIBLE', result.stdout)

    @unittest.skipUnless(shutil.which('direnv'), 'direnv is required for activation checks')
    def test_direnv_selects_project_hatch_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            project.mkdir()
            (project / 'config/direnv').mkdir(parents=True)
            shutil.copy(ROOT / '.envrc', project / '.envrc')
            shutil.copy(ROOT / 'config/direnv/direnvrc', project / 'config/direnv/direnvrc')
            shutil.copy(ROOT / 'hatch.toml', project / 'hatch.toml')
            (project / '.hatch/bin').mkdir(parents=True)
            (project / '.hatch/bin/python').symlink_to('/usr/bin/python3')
            env = {**os.environ, 'DIRENV_CONFIG': str(Path(directory) / 'direnv-config'),
                   'VIRTUAL_ENV': '/other/project/environment',
                   'HATCH_ENV_TYPE_VIRTUAL_PATH': '/other/project/environment',
                   'ANSIBLE_CONFIG': '/other/project/ansible.cfg'}
            subprocess.run(['direnv', 'allow', str(project)], env=env, check=True,
                           capture_output=True)
            result = subprocess.run([
                'direnv', 'exec', str(project), '/usr/bin/python3', '-c',
                'import os,json,shutil; print(json.dumps({'
                '"venv":os.environ["VIRTUAL_ENV"],'
                '"hatch":os.environ["HATCH_ENV_TYPE_VIRTUAL_PATH"],'
                '"python":shutil.which("python"),'
                '"config":os.environ["ANSIBLE_CONFIG"]}))'
            ], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            values = json.loads(result.stdout)
            self.assertEqual(values['venv'], str(project / '.hatch'))
            self.assertEqual(values['hatch'], str(project / '.hatch'))
            self.assertEqual(values['python'], str(project / '.hatch/bin/python'))
            self.assertEqual(values['config'], str(project / 'ansible/ansible.cfg'))

    @unittest.skipUnless(shutil.which('direnv'), 'direnv is required for activation checks')
    def test_direnv_reports_missing_environment_without_bootstrapping(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            (project / 'config/direnv').mkdir(parents=True)
            shutil.copy(ROOT / '.envrc', project / '.envrc')
            shutil.copy(ROOT / 'config/direnv/direnvrc', project / 'config/direnv/direnvrc')
            shutil.copy(ROOT / 'hatch.toml', project / 'hatch.toml')
            env = {**os.environ, 'DIRENV_CONFIG': str(Path(directory) / 'direnv-config')}
            subprocess.run(['direnv', 'allow', str(project)], env=env, check=True,
                           capture_output=True)
            result = subprocess.run(['direnv', 'exec', str(project), '/bin/true'],
                                    env=env, capture_output=True, text=True)
            self.assertIn('Missing .hatch environment', result.stderr)
            self.assertFalse((project / '.hatch').exists())


if __name__ == '__main__':
    unittest.main()
