"""Offline checks: key validation, reconciliation, and failure before publication."""
import os
from pathlib import Path
import subprocess
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


if __name__ == '__main__':
    unittest.main()
