"""Exercise offline recovery and reject bad backups before device access."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
bootstrap = types.ModuleType('bootstrap')
bootstrap.verify = lambda: (_ for _ in ()).throw(AssertionError('device path reached'))
sys.modules['bootstrap'] = bootstrap
spec = importlib.util.spec_from_file_location('restore', ROOT.parent / 'host/restore_rescue.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = bytes(range(256)) * 16
        self.image = self.base / 'nflasha.read1.bin'
        self.image.write_bytes(bytes(4096) + self.data)
        self.row = dict(name='nflasha10', offset=4096, bytes=4096,
                        read1_sha256=hashlib.sha256(self.data).hexdigest())

    def run_restore(self, *, offline=True, partitions='nflasha10'):
        (self.base / 'offline-verification.json').write_text(
            json.dumps({'partitions': [self.row]}))
        argv = ['restore', '--backup-dir', str(self.base), '--partitions', partitions,
                '--out-dir', str(self.base / 'prepared')]
        if offline:
            argv.append('--prepare-only')
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return restore.main()

    def test_linux_slice_report_drives_complete_offline_restore(self):
        read2 = self.base / 'read2.bin'
        read2.write_bytes(self.image.read_bytes())
        layout = self.base / 'layout.tsv'
        layout.write_text('nflasha10 4096 4096\n')
        report = self.base / 'offline-verification.json'
        subprocess.run([sys.executable, '-B', str(ROOT.parents[1] / 'linux/host/zve10_verify.py'),
                        'slices', '--read1', str(self.image), '--read2', str(read2),
                        '--layout', str(layout), '--json', str(report)],
                       check=True, stdout=subprocess.DEVNULL)
        self.row = json.loads(report.read_text())['partitions'][0]
        self.assertEqual(self.run_restore(), 0)
        self.assertEqual((self.base / 'prepared/nflasha10.bin').read_bytes(), self.data)
        sparse = (self.base / 'prepared/nflasha10.simg').read_bytes()
        self.assertEqual(sparse[:4], bytes.fromhex('3aff26ed'))
        self.assertEqual(sparse[40:], self.data)

    def test_bad_hash_stops_online_flow_before_any_device_access(self):
        self.row['read1_sha256'] = '0' * 64
        self.assertEqual(self.run_restore(offline=False), 1)

    def test_out_of_bounds_partition_is_rejected(self):
        self.row['bytes'] = 8192
        with self.assertRaises(SystemExit):
            self.run_restore()

    def test_boot_partition_is_rejected(self):
        self.row['name'] = 'nflashaB0'
        with self.assertRaises(SystemExit):
            self.run_restore(partitions='nflashaB0')

    def test_duplicate_partition_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_restore(partitions='nflasha10,nflasha10')


if __name__ == '__main__':
    unittest.main()
