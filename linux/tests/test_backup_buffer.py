"""Failure boundaries for dedicated RAM buffers and saved-file promotion."""
import hashlib
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import zve10_jiritsu as jit
import zve10_backup_raw as raw
import zve10_backup_session as backup


class BufferTests(unittest.TestCase):
    def backend(self, fail_mount_response=False, foreign_mount=False):
        cam = type('Camera', (), {'dev': object()})()
        b = jit.JiritsuBackend(cam, Path('.'), '2.03')
        b.ram = '/tmp_network/zve10-test'
        b.mounted = False
        b.commands = []
        bulk = b.ram + '/backup-buffer'
        def run(cmd):
            b.commands.append(cmd)
            if cmd == 'busybox cat /proc/meminfo':
                return 'MemFree: 2048 kB\nCached: 60000 kB\nBuffers: 2048 kB\nShmem: 32 kB\n'
            if cmd.startswith('busybox mount '):
                b.mounted = True
                if fail_mount_response:
                    raise RuntimeError('Lost mount response')
            if cmd == 'busybox cat /proc/mounts':
                return (('other' if foreign_mount else 'zvbackup') + ' ' + bulk + ' tmpfs rw,size=8192k 0 0\n') if b.mounted else ''
            if 'busybox umount ' in cmd:
                b.mounted = False
            return ''
        b.run = run
        return b

    def test_cancel_unmounts_before_restoring_buffer(self):
        b = self.backend()
        with self.assertRaises(jit.BackupCancelled):
            with b.backup_buffer(4096):
                self.assertTrue(b.mounted)
                self.assertEqual(b.chunk_bytes, 4194304)
                raise jit.BackupCancelled()
        self.assertFalse(b.mounted)
        self.assertTrue(b.status['backup_buffer_removed'])
        self.assertFalse(hasattr(b, 'chunk_dir'))
        self.assertEqual(b.chunk_bytes, 524288)
        self.assertIn('busybox rmdir', b.commands[-1])

    def test_successful_mount_with_lost_response_is_still_cleaned(self):
        b = self.backend(fail_mount_response=True)
        with self.assertRaisesRegex(RuntimeError, 'Lost mount response'):
            with b.backup_buffer(4096):
                self.fail('must not start reading')
        self.assertFalse(b.mounted)
        self.assertTrue(b.status['backup_buffer_removed'])

    def test_foreign_mount_is_never_removed(self):
        b = self.backend(foreign_mount=True)
        with self.assertRaisesRegex(RuntimeError, 'Unexpected mount'):
            with b.backup_buffer(4096):
                self.fail('must not read')
        self.assertTrue(b.mounted)
        self.assertFalse(any('umount' in cmd or 'rm -f' in cmd for cmd in b.commands))
        self.assertIn('backup_buffer_cleanup_error', b.status)

    def test_low_memory_stops_before_mkdir(self):
        b = self.backend()
        b.run = Mock(return_value='MemFree: 512 kB\nCached: 1024 kB\nBuffers: 256 kB\n')
        with self.assertRaisesRegex(ValueError, '32 MiB'):
            with b.backup_buffer(4096):
                self.fail('must not read')
        commands = [call.args[0] for call in b.run.call_args_list]
        self.assertFalse(any('mkdir' in cmd or 'mount -t' in cmd for cmd in commands))

    def test_sums_file_uses_lf_endings_for_portable_checking(self):
        with tempfile.TemporaryDirectory() as directory:
            backup.write_sums(directory, [{'sha256': 'a' * 64, 'file': 'nflasha.read1.bin'}])
            data = (Path(directory) / 'SHA256SUMS').read_bytes()
        self.assertEqual(data, b'a' * 64 + b'  nflasha.read1.bin\n')

    def test_bad_saved_hash_keeps_part_and_never_promotes(self):
        with tempfile.TemporaryDirectory() as directory:
            real_hash = hashlib.sha256
            mismatch = Mock()
            mismatch.hexdigest.return_value = '0'*64
            def receive(camera, path, sink):
                sink.write(b'x'*512)
                return 0, None
            with patch.object(raw, 'OUT', Path(directory)), \
                    patch.object(raw, 'RESULT', {'reads': [], 'regions': {'nflasha': 512}}), \
                    patch.object(raw.emmc, 'collect', return_value={'partitions': '', 'layout': ''}), \
                    patch.object(raw.emmc, 'validate', return_value={'nflasha': 512}), \
                    patch.object(raw.common, 'read_path', side_effect=receive), \
                    patch.object(raw.hashlib, 'sha256', side_effect=[real_hash(), real_hash(b'x'*512), mismatch]):
                with self.assertRaisesRegex(RuntimeError, 'saved file hash'):
                    raw.receive(object(), 'nflasha', 1)
                self.assertTrue((Path(directory)/'nflasha.read1.bin.part').is_file())
                self.assertFalse((Path(directory)/'nflasha.read1.bin').exists())
                self.assertFalse(raw.RESULT['reads'][0]['complete'])

    def test_cleanup_failure_cannot_mark_backup_complete(self):
        import zve10_backup_session as session_backup
        b = self.backend()
        b.camera._jiritsu_backend = b
        @contextmanager
        def broken_cleanup(chunk_kib):
            yield {'chunk_bytes': 4194304}
            raise RuntimeError('unmount failed')
        b.backup_buffer = broken_cleanup
        b.run = Mock(return_value='metadata')
        def receive(cam, name, iteration):
            row = {'file': name+'.bin', 'sha256':'0'*64, 'complete':True}
            session_backup.raw.RESULT['reads'].append(row)
            return row
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(session_backup.emmc, 'validate', return_value=dict(nflasha=512, nflashaB0=512, nflashaB1=512)), \
                patch.object(session_backup.raw, 'receive', side_effect=receive), \
                patch.object(session_backup.shutil, 'disk_usage', return_value=Mock(free=10**12)):
            with self.assertRaisesRegex(RuntimeError, 'unmount failed'):
                session_backup.dispatch(b.camera, {'chunk_kib':4096}, Path(directory), False)
            self.assertFalse(session_backup.raw.RESULT['completed'])
            self.assertFalse(list(Path(directory).rglob('SHA256SUMS')))

    def test_existing_session_cannot_be_overwritten(self):
        import zve10_terminal_server as server
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            state = folder/'state.json'
            state.write_text('previous session')
            with self.assertRaisesRegex(SystemExit, 'previous session'):
                server.prepare_session(folder)
            self.assertEqual(state.read_text(), 'previous session')
