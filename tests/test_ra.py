import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RaBehavior(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='f50-ra-test-')
        self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name)
        self.output = self.directory / 'calls'
        stubs = {
            'uci': '''#!/bin/sh
case "$3" in
*.enabled) echo "${TEST_ENABLED:-1}";;
*.network) echo wan;;
*.device_prefix) echo sipa_eth;;
*.interval) echo "${TEST_INTERVAL:-3600}";;
*.threshold) echo 7200;;
esac
''',
            'ubus': '''#!/bin/sh
printf '{"up":true,"l3_device":"%s"}\\n' "${TEST_DEVICE:-sipa_eth0}"
''',
            'jsonfilter': '''#!/bin/sh
text=$(cat)
case "$2" in
@.up) echo true;;
@.l3_device) printf '%s' "$text" | sed -n 's/.*"l3_device":"\\([^"]*\\)".*/\\1/p';;
esac
''',
            'ip': '''#!/bin/sh
case "$*" in
link\\ show\\ dev\\ *) exit 0;;
-6\\ route\\ show\\ default\\ dev\\ *\\ proto\\ ra)
 [ "${TEST_ROUTE_MISSING:-0}" = 1 ] || printf 'default via fe80::1 dev sipa_eth0 proto ra expires %ssec\\n' "${TEST_LIFETIME:-60000}";;
*) echo "FORBIDDEN_IP:$*" >> "$TEST_CALLS"; exit 99;;
esac
''',
            'rdisc6': '#!/bin/sh\nprintf "RS:%s\\n" "$*" >> "$TEST_CALLS"\n',
            'logger': '#!/bin/sh\nexit 0\n',
            'flock': '#!/bin/sh\nexit 0\n',
        }
        for name, content in stubs.items():
            target = self.directory / name
            target.write_text(content)
            target.chmod(0o755)
        source = (ROOT / 'f50-ra-refresh/root/usr/sbin/f50-ra-refresh').read_text()
        source = source.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin', f'PATH={self.directory}:/usr/bin:/bin')
        source = source.replace('/usr/bin/rdisc6 /usr/sbin/rdisc6 /usr/libexec/f50-rdisc6', str(self.directory / 'rdisc6'))
        source = source.replace('/var/run/f50-ra-refresh.lock', str(self.directory / 'lock'))
        self.runner = self.directory / 'runner'
        self.runner.write_text(source)

    def run_script(self, mode='--once', **values):
        env = os.environ.copy()
        env.update(TEST_CALLS=str(self.output), **values)
        result = subprocess.run(['sh', str(self.runner), mode], env=env, text=True, capture_output=True)
        calls = self.output.read_text() if self.output.exists() else ''
        self.assertNotIn('FORBIDDEN_IP', calls)
        return result, calls

    def test_disabled_never_solicits(self):
        result, calls = self.run_script(TEST_ENABLED='0', TEST_LIFETIME='100')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('RS:', calls)

    def test_healthy_never_solicits(self):
        result, calls = self.run_script(TEST_LIFETIME='60000')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('RS:', calls)

    def test_low_lifetime_requests_authentic_ra(self):
        result, calls = self.run_script(TEST_LIFETIME='100')
        self.assertEqual(result.returncode, 0)
        self.assertIn('RS:-1 -n -r 2 -w 3000 sipa_eth0', calls)

    def test_missing_route_requests_ra(self):
        result, calls = self.run_script(TEST_ROUTE_MISSING='1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('RS:', calls)

    def test_non_cellular_interface_skipped(self):
        _, calls = self.run_script(TEST_DEVICE='br-lan', TEST_LIFETIME='100')
        self.assertNotIn('RS:', calls)

    def test_unknown_lifetime_preserved(self):
        _, calls = self.run_script(TEST_LIFETIME='forever')
        self.assertNotIn('RS:', calls)

    def test_invalid_config_rejected(self):
        result, calls = self.run_script(TEST_INTERVAL='001')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('RS:', calls)

    def test_status_is_json_and_read_only(self):
        result, calls = self.run_script('--status', TEST_LIFETIME='64000')
        data = json.loads(result.stdout)
        self.assertEqual(data['remaining'], 64000)
        self.assertTrue(data['wan_ready'])
        self.assertNotIn('RS:', calls)


if __name__ == '__main__':
    unittest.main()
