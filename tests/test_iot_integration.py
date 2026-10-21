import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('interval_patch', ROOT/'tools/apply_mu300_interval.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class IntegrationChecks(unittest.TestCase):
    def test_unsupported_version_rejected(self):
        for fn in (patch.patch_worker, patch.patch_rpc, patch.patch_page):
            with self.assertRaises(ValueError):
                fn('unknown source')

    def test_worker_reload_without_forced_sync(self):
        original = "require 'json'\n    system('/usr/bin/ruby', __FILE__, '--sync')\n    sleep 1200\ninterval_seconds: 1200,"
        result = patch.patch_worker(original)
        self.assertIn('sleep 5 while F50IotInterval.due_in > 0', result)
        self.assertIn('interval_seconds: F50IotInterval.seconds', result)
        self.assertNotIn('sleep 1200', result)
        with self.assertRaises(ValueError):
            patch.patch_worker(result)

    def test_rpc_accepts_rpcd_session_metadata_without_saving_it(self):
        original = "require 'json'\ninterval_seconds: 1200,\n> 1500\n{get: {slot: 0}, sync: {slot: 0}}\n%w[get sync].include?\n    if ARGV[1] == 'get'"
        result = patch.patch_rpc(original)
        self.assertIn('input.keys - %w[slot interval_seconds ubus_rpc_session]', result)
        self.assertIn("F50IotInterval.configure(slot, input['interval_seconds'])", result)


if __name__ == '__main__':
    unittest.main()
