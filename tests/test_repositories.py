"""Offline checks: key validation, reconciliation, and failure before publication."""
import os
from pathlib import Path
import subprocess
import tempfile
import json
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'add_repositories.sh'


class RepositoryTests(unittest.TestCase):
    # Public OBS project signing key used only as a parser fixture, never trusted.
    key = Path(__file__).resolve().parent / 'fixtures' / 'public-key.gpg'

    def run_shell(self, body, **variables):
        return subprocess.run(['bash', '-c', 'source "$SCRIPT"\n' + body],
                              env={**os.environ, 'SCRIPT': str(SCRIPT),
                                   'FIXTURE': str(self.key), **variables},
                              capture_output=True, text=True)

    def test_source_line_replaces_old_release(self):
        result = self.run_shell('repository_line example "https://example.invalid focal main" "" "" true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('arch=', result.stdout)
        self.assertIn('signed-by=/usr/share/keyrings/example-archive-keyring.gpg', result.stdout)
        self.assertIn(' focal main', result.stdout)

    def test_valid_public_key_is_staged(self):
        result = self.run_shell('''
            staging=$(mktemp -d)
            trap 'rm -rf "$staging"' EXIT
            curl() { cp "$FIXTURE" "${@: -1}"; }
            stage_repository example 'https://example.invalid focal main' https://example.invalid/key
            test -s "$staging/example.gpg"
            test -s "$staging/example.list"
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_download_stops_before_publication(self):
        result = self.run_shell('''
            id() { printf '0\\n'; }
            curl() { return 22; }
            publish_repository() { echo UNEXPECTED_PUBLICATION; }
            main --apply
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED_PUBLICATION', result.stdout)

    def test_invalid_key_stops_before_publication(self):
        result = self.run_shell('''
            id() { printf '0\\n'; }
            curl() { printf '<html>error</html>' > "${@: -1}"; }
            publish_repository() { echo UNEXPECTED_PUBLICATION; }
            main --apply
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED_PUBLICATION', result.stdout)

    def test_later_failure_preserves_all_live_repositories(self):
        result = self.run_shell('''
            id() { printf '0\\n'; }
            curl() {
                if [[ "$*" == *brave* ]]; then cp "$FIXTURE" "${@: -1}";
                else return 22; fi
            }
            publish_repository() { echo UNEXPECTED_PUBLICATION; }
            main --apply
        ''')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('UNEXPECTED_PUBLICATION', result.stdout)

    def test_policy_keeps_legacy_sources_disabled(self):
        result = self.run_shell('''
            load_repository_policy
            check_repository() { echo "ENABLED $1"; }
            check_disabled_repository() { echo "DISABLED $1"; }
            repositories check_repository
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ['albert', 'r-4', 'rvm', 'llvm']:
            self.assertIn('DISABLED ' + name, result.stdout)
            self.assertNotIn('ENABLED ' + name, result.stdout)

    def test_disabled_sources_skip_key_downloads(self):
        result = self.run_shell('''
            load_repository_policy
            stage_repository() { echo "STAGED $1"; }
            stage_disabled_repository() { echo "PRESERVED $1"; }
            repositories stage_repository
        ''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('STAGED brave-browser', result.stdout)
        for name in ['albert', 'r-4', 'rvm', 'llvm']:
            self.assertIn('PRESERVED ' + name, result.stdout)
            self.assertNotIn('STAGED ' + name, result.stdout)

    def test_disabling_source_is_repeatable_and_preserves_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'example.list'
            source.write_text('deb https://example.invalid bionic main\n')
            result = self.run_shell('''
                stage_disabled_repository example "$SOURCES"
                publish_disabled_repository example "$SOURCES"
                stage_disabled_repository example "$SOURCES"
                publish_disabled_repository example "$SOURCES"
            ''', SOURCES=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(source.exists())
            self.assertEqual(source.with_suffix('.list.disabled').read_text(),
                             'deb https://example.invalid bionic main\n')
            self.assertEqual(result.stdout.count('DISABLED:'), 1)

    def test_existing_backup_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'example.list'
            source.write_text('active')
            source.with_suffix('.list.disabled').write_text('previous backup')
            result = self.run_shell('stage_disabled_repository example "$SOURCES"',
                                    SOURCES=directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_text(), 'active')
            self.assertEqual(source.with_suffix('.list.disabled').read_text(), 'previous backup')

    def test_deb822_source_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'example.sources'
            source.write_text('Enabled: yes\n')
            result = self.run_shell('stage_disabled_repository example "$SOURCES"',
                                    SOURCES=directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_text(), 'Enabled: yes\n')

    def test_invalid_policy_stops_before_network_or_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'policy.json'
            policy.write_text(json.dumps({'ubuntu_codename': 'focal', 'repositories': {}}))
            result = self.run_shell('''
                load_repository_policy "$POLICY"
                echo UNEXPECTED_CONTINUATION
            ''', POLICY=str(policy))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('UNEXPECTED_CONTINUATION', result.stdout)


if __name__ == '__main__':
    unittest.main()
