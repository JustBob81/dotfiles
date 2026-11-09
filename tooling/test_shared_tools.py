"""Offline tests of the bootstrap boundary and archive verification."""
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

from shared_tools import ROOT, SharedTools, extract_verified_archive, load_policy, relative_path


class ToolingTests(unittest.TestCase):
    def test_policy_has_verified_archive_and_explicit_versions(self):
        policy = load_policy(ROOT / 'config/shared-python-tools.json')
        self.assertEqual(policy['python']['version'], '3.12.16')
        self.assertEqual(policy['applications']['hatch']['version'], '1.18.2')
        self.assertEqual(len(policy['python']['sha256']), 64)

    def test_paths_cannot_escape_user_directories(self):
        for value in ['/etc/python', '../escape', 'nested/../../escape', '.', '']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                relative_path(value)

    def archive(self, directory, name='python/example.txt', link=None):
        archive = Path(directory) / 'fixture.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            info = tarfile.TarInfo(name)
            if link:
                info.type = tarfile.SYMTYPE
                info.linkname = link
                stream.addfile(info)
            else:
                payload = b'fixture'
                info.size = len(payload)
                stream.addfile(info, io.BytesIO(payload))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_valid_archive_extracts(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, checksum = self.archive(directory)
            destination = Path(directory) / 'output'
            extract_verified_archive(archive, destination, checksum)
            self.assertEqual((destination / 'python/example.txt').read_bytes(), b'fixture')

    def test_checksum_failure_extracts_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            archive, _ = self.archive(directory)
            destination = Path(directory) / 'output'
            with self.assertRaises(ValueError):
                extract_verified_archive(archive, destination, '0' * 64)
            self.assertFalse(destination.exists())

    def test_archive_traversal_and_escape_links_are_rejected(self):
        for name, link in [('python/../../escape', None), ('/tmp/escape', None),
                           ('python/link', '../../escape')]:
            with self.subTest(name=name, link=link), tempfile.TemporaryDirectory() as directory:
                archive, checksum = self.archive(directory, name, link)
                destination = Path(directory) / 'output'
                with self.assertRaises(ValueError):
                    extract_verified_archive(archive, destination, checksum)
                self.assertFalse(destination.exists())

    def test_pipx_wrapper_quotes_paths_and_forwards_arguments(self):
        with tempfile.TemporaryDirectory(prefix='tooling space ') as directory:
            policy = load_policy(ROOT / 'config/shared-python-tools.json')
            tools = SharedTools(policy, home=Path(directory), data=Path(directory) / 'data')
            tools.pipx_python.parent.mkdir(parents=True)
            tools.pipx_python.write_text('#!/usr/bin/python3\nimport json,os,sys\n'
                                        'print(json.dumps({"args":sys.argv[1:],"home":os.environ["PIPX_HOME"]}))\n')
            tools.pipx_python.chmod(0o755)
            wrapper = Path(directory) / 'pipx'
            wrapper.write_text(tools.wrapper())
            wrapper.chmod(0o755)
            result = subprocess.run([str(wrapper), 'list', 'argument with spaces'],
                                    capture_output=True, text=True, check=True)
            actual = json.loads(result.stdout)
            self.assertEqual(actual['args'], ['-m', 'pipx', 'list', 'argument with spaces'])
            self.assertEqual(actual['home'], str(tools.pipx_home))

    def test_backups_do_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = SharedTools(load_policy(ROOT / 'config/shared-python-tools.json'), root, root / 'data')
            target = root / 'target'
            target.write_text('unchanged')
            link = root / 'link'
            link.symlink_to(target)
            tools.backup(link)
            saved = next(tools.backups.iterdir())
            self.assertTrue(saved.is_symlink())
            self.assertEqual(target.read_text(), 'unchanged')

    def test_audit_does_not_create_directories_or_install_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = SharedTools(load_policy(ROOT / 'config/shared-python-tools.json'), root, root / 'data')
            report = tools.audit()
            self.assertIn('install declared standalone Python', report['changes'])
            self.assertFalse(report.get('changed', False))
            self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
