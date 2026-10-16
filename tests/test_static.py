import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SourceChecks(unittest.TestCase):
    def test_json(self):
        files = list(ROOT.rglob('*.json')) + list(ROOT.rglob('*.json.example'))
        self.assertGreater(len(files), 4)
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                json.loads(path.read_text())

    def test_javascript(self):
        for path in ROOT.rglob('*.js'):
            subprocess.run(['node', '--check', str(path)], check=True, capture_output=True)

    def test_ruby(self):
        files = list(ROOT.rglob('*.rb')) + [ROOT/'f50-xiaojing/root/usr/libexec/f50-xiaojing',
                                          ROOT/'f50-xiaojing/root/usr/libexec/rpcd/f50.xiaojing']
        for path in files:
            subprocess.run(['ruby', '-c', str(path)], check=True, capture_output=True)

    def test_shell(self):
        for path in ROOT.rglob('*'):
            if path.is_file() and path.read_bytes().startswith(b'#!/bin/sh'):
                subprocess.run(['sh', '-n', str(path)], check=True, capture_output=True)

    def test_default_disabled(self):
        defaults = json.loads((ROOT/'f50-xiaojing/root/etc/f50-xiaojing/config.json.example').read_text())
        self.assertFalse(defaults['enabled'])
        self.assertFalse(defaults['allow_http'])
        self.assertEqual(defaults['card'], '')
        self.assertEqual(defaults['verify'], '')
        self.assertIn("option enabled '0'", (ROOT/'f50-ra-refresh/root/etc/config/f50_ra').read_text())

    def test_no_network_mutation_in_ra(self):
        script = (ROOT/'f50-ra-refresh/root/usr/sbin/f50-ra-refresh').read_text()
        for pattern in [r'\bip\s+[^\n]*(?:\bdel\b|\breplace\b|\bflush\b)',
                        r'\b(?:ifdown|ifup|reboot)\b', r'/etc/init.d/network']:
            self.assertIsNone(re.search(pattern, script))
        self.assertIn('flock -n 9', script)

    def test_no_wildcard_acl(self):
        for path in ROOT.rglob('acl.d/*.json'):
            self.assertNotIn('"*"', path.read_text())

    def test_publish_tree_is_source_only(self):
        forbidden = {'.img', '.bin', '.key', '.pem', '.log', '.apk', '.ipk'}
        for path in ROOT.rglob('*'):
            if '.git' in path.parts or not path.is_file():
                continue
            self.assertNotIn(path.suffix, forbidden, str(path))
            if path.suffix not in {'.pyc'}:
                text = path.read_text(errors='ignore')
                self.assertIsNone(re.search(r'/Users/' + r'[^/\s]+/', text))
                self.assertNotIn('BEGIN ' + 'OPENSSH PRIVATE KEY', text)


if __name__ == '__main__':
    unittest.main()
