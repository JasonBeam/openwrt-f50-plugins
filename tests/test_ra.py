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
*.adaptive) echo "${TEST_ADAPTIVE:-1}";;
esac
''',
            'ubus': '''#!/bin/sh
device=${TEST_DEVICE:-sipa_eth0}
[ ! -e "$TEST_AFTER" ] || device=${TEST_AFTER_DEVICE:-$device}
printf '{"up":true,"l3_device":"%s"}\\n' "$device"
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
 if [ -e "$TEST_AFTER" ]; then
  [ "${TEST_AFTER_MISSING:-0}" = 1 ] || printf 'default via %s dev sipa_eth0 proto ra expires %ssec\\n' "${TEST_AFTER_GATEWAY:-fe80::1}" "${TEST_AFTER_LIFETIME:-3598}"
 else
  [ "${TEST_ROUTE_MISSING:-0}" = 1 ] || printf 'default via %s dev sipa_eth0 proto ra expires %ssec\\n' "${TEST_GATEWAY:-fe80::1}" "${TEST_LIFETIME:-60000}"
 fi;;
*) echo "FORBIDDEN_IP:$*" >> "$TEST_CALLS"; exit 99;;
esac
''',
            'rdisc6': '''#!/bin/sh
printf "RS:%s\\n" "$*" >> "$TEST_CALLS"
touch "$TEST_AFTER"
printf ' Router lifetime : %s seconds\\n from %s\\n' "${TEST_ADVERTISED:-3600}" "${TEST_REPLY_GATEWAY:-fe80::1}"
exit "${TEST_RC:-0}"
''',
            'cat': '''#!/bin/sh
case "$1" in
/sys/class/net/*/ifindex) echo "${TEST_INDEX:-3}";;
/proc/sys/kernel/random/boot_id) echo "${TEST_BOOT:-test-boot}";;
*) exec /bin/cat "$@";;
esac
''',
            'cut': '''#!/bin/sh
now=${TEST_NOW:-1000}
[ ! -e "$TEST_AFTER" ] || now=$((now + 2))
echo "$now"
''',
            'sleep': '#!/bin/sh\nexit 0\n',
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
        self.state = self.directory / 'state'
        source = source.replace('/var/run/f50-ra-refresh.state', str(self.state))
        self.runner = self.directory / 'runner'
        self.runner.write_text(source)

    def run_script(self, mode='--once', **values):
        env = os.environ.copy()
        env.update(TEST_CALLS=str(self.output), TEST_AFTER=str(self.directory / 'after'), **values)
        result = subprocess.run(['sh', str(self.runner), mode], env=env, text=True, capture_output=True, timeout=10)
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
        result, calls = self.run_script(TEST_LIFETIME='20')
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
        self.assertTrue(data['adaptive'])
        self.assertIsNone(data['natural_interval'])
        self.assertNotIn('RS:', calls)

    def status(self, **values):
        result, _ = self.run_script('--status', **values)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def seed(self, identity='test-boot/sipa_eth0/3/fe80::1',
             observation='940 3600 3600 observed 0 0 0 baseline 0'):
        self.state.write_text(identity + '\n' + observation + '\n')

    def test_short_lifetime_has_adaptive_threshold(self):
        self.seed()
        data = self.status(TEST_LIFETIME='3540')
        self.assertEqual((data['threshold'], data['interval']), (900, 60))

    def test_near_expiry_checks_every_ten_seconds(self):
        data = self.status(TEST_LIFETIME='20')
        self.assertEqual((data['threshold'], data['interval']), (30, 10))

    def test_fixed_mode_keeps_original_policy(self):
        data = self.status(TEST_ADAPTIVE='0')
        self.assertEqual((data['threshold'], data['interval']), (7200, 3600))
        result, calls = self.run_script(TEST_ADAPTIVE='0', TEST_LIFETIME='100')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('RS:', calls)

    def test_invalid_adaptive_mode_rejected(self):
        result, calls = self.run_script(TEST_ADAPTIVE='bad')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('RS:', calls)

    def test_natural_cadence_requires_two_renewals(self):
        for now, remaining in [('1000', '3500'), ('1060', '3440'), ('1120', '3590')]:
            result, calls = self.run_script(TEST_NOW=now, TEST_LIFETIME=remaining)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('RS:', calls)
        first = self.status(TEST_NOW='1120', TEST_LIFETIME='3590')
        self.assertEqual(first['observed_renewals'], 1)
        self.assertIsNone(first['natural_interval'])
        self.run_script(TEST_NOW='1180', TEST_LIFETIME='3590')
        second = self.status(TEST_NOW='1180', TEST_LIFETIME='3590')
        self.assertEqual(second['observed_renewals'], 2)
        self.assertEqual(second['natural_interval'], 60)

    def test_request_exit_zero_without_renewal_is_failure(self):
        result, calls = self.run_script(TEST_LIFETIME='20', TEST_AFTER_LIFETIME='18')
        self.assertEqual(result.returncode, 1)
        self.assertIn('RS:', calls)
        self.assertEqual(self.status(TEST_LIFETIME='18')['last_event'], 'failed')

    def test_reply_lifetime_and_solicited_event(self):
        result, _ = self.run_script(TEST_LIFETIME='20')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.status()
        self.assertEqual(data['lifetime'], 3600)
        self.assertEqual(data['lifetime_source'], 'advertised')
        self.assertEqual(data['last_event'], 'solicited')
        self.assertEqual(data['observed_renewals'], 0)
        self.assertIsNone(data['natural_interval'])
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)

    def test_already_full_requires_matching_reply(self):
        result, _ = self.run_script('--force', TEST_LIFETIME='3599')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.status()['lifetime_source'], 'advertised')

    def test_other_router_reply_cannot_supply_lifetime(self):
        result, _ = self.run_script(TEST_LIFETIME='20', TEST_ADVERTISED='9000', TEST_REPLY_GATEWAY='fe80::2')
        self.assertEqual(result.returncode, 0)
        data = self.status()
        self.assertEqual((data['lifetime'], data['lifetime_source']), (3598, 'observed'))

    def test_other_router_near_full_does_not_prove_renewal(self):
        result, _ = self.run_script('--force', TEST_LIFETIME='3599', TEST_REPLY_GATEWAY='fe80::2')
        self.assertEqual(result.returncode, 1)

    def test_request_failure_never_marked_success(self):
        result, _ = self.run_script(TEST_LIFETIME='20', TEST_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.status()['last_event'], 'failed')

    def test_gateway_changes_during_request_discard_observation(self):
        result, _ = self.run_script(TEST_LIFETIME='20', TEST_AFTER_GATEWAY='fe80::2')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.state.exists())

    def test_device_changes_during_request_discard_observation(self):
        result, _ = self.run_script(TEST_LIFETIME='20', TEST_AFTER_DEVICE='sipa_eth1')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.state.exists())

    def test_reboot_or_interface_change_resets_learning(self):
        for values in ({'TEST_BOOT': 'new-boot'}, {'TEST_INDEX': '4'}, {'TEST_GATEWAY': 'fe80::2'}):
            with self.subTest(values=values):
                self.seed(observation='940 3600 65535 advertised 900 60 4 natural 0')
                data = self.status(TEST_LIFETIME='3500', **values)
                self.assertEqual(data['lifetime'], 3500)
                self.assertEqual(data['observed_renewals'], 0)
                self.assertIsNone(data['natural_interval'])

    def test_corrupt_and_future_state_ignored(self):
        for state in ['bad state', '9999 3600 65535 advertised 900 60 4 natural 0',
                      '940 03600 65535 advertised 900 60 4 natural 0',
                      '940 3600 65535 advertised 900 60 4 natural 0 extra']:
            with self.subTest(state=state):
                self.seed(observation=state)
                data = self.status(TEST_LIFETIME='3500')
                self.assertEqual(data['lifetime'], 3500)
                self.assertEqual(data['observed_renewals'], 0)

    def test_status_does_not_write_learning_state(self):
        self.seed()
        before = self.state.read_bytes()
        self.status()
        self.assertEqual(self.state.read_bytes(), before)

    def test_delayed_own_reply_not_counted_as_natural(self):
        self.seed(observation='990 100 3600 observed 900 60 1 failed 990')
        self.run_script(TEST_LIFETIME='3598')
        data = self.status(TEST_LIFETIME='3598')
        self.assertEqual(data['observed_renewals'], 1)

    def test_force_still_requires_enabled(self):
        result, calls = self.run_script('--force', TEST_ENABLED='0')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('RS:', calls)
        self.assertFalse(self.state.exists())


if __name__ == '__main__':
    unittest.main()
