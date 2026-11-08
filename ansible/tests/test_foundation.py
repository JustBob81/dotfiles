"""Offline behavioral checks; Ansible runtime validation remains a separate gate."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class FoundationTests(unittest.TestCase):
    def run_wrapper(self, *arguments):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'ansible-playbook'
            executable.write_text('#!/usr/bin/python3\nimport json, os, sys\n'
                                  'print(json.dumps({"args": sys.argv[1:], '
                                  '"config": os.environ.get("ANSIBLE_CONFIG")}))\n')
            executable.chmod(0o755)
            return subprocess.run([str(ROOT / 'ansible/run'), *arguments],
                                  env={**os.environ, 'PATH': directory + ':' + os.environ['PATH']},
                                  capture_output=True, text=True, cwd='/tmp')

    def test_preview_is_default_even_from_another_directory(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads(result.stdout)
        self.assertIn('--check', call['args'])
        self.assertIn('--diff', call['args'])
        self.assertEqual(call['config'], str(ROOT / 'ansible/ansible.cfg'))
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


if __name__ == '__main__':
    unittest.main()
