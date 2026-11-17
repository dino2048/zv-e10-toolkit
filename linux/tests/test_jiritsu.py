import hashlib
import struct
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'host'))
import zve10_common as common
import zve10_jiritsu as jit
import zve10_backup_session as backup

class Tests(unittest.TestCase):
    def backend(self):
        camera = type('Camera', (), {})()
        camera.dev = type('Device', (), {})()
        b = jit.JiritsuBackend(camera, Path('.'), '2.03')
        b.started = True
        return b

    def test_unknown_version_never_uploads(self):
        b = self.backend()
        for versions in ([b'unknown', b'unknown'], [b.expected, b'unknown'],
                         [b'unknown', b.expected]):
            with self.subTest(versions=versions), \
                 patch.object(jit, 'read_file', side_effect=versions), \
                 patch.object(jit, 'jcmd') as command, \
                 patch.object(jit, 'upload_verified') as upload:
                with self.assertRaises(RuntimeError): b.start()
                command.assert_not_called()
                upload.assert_not_called()

    def test_existing_workspace_never_overwritten(self):
        b = self.backend()
        with patch.object(jit, 'read_file', side_effect=[b.expected,b.expected,b'old file']), \
             patch.object(jit, 'jcmd') as command, patch.object(jit, 'upload_verified') as upload:
            with self.assertRaisesRegex(RuntimeError, 'Existing'): b.start()
            command.assert_called_once_with(b.camera, 2, b'\x00\x00')
            upload.assert_not_called()

    def test_workspace_initialized_before_loader_checks_and_uploads(self):
        # Model a first-use camera: loader reads/uploads fail until MOUNT.
        for firmware in jit.FIRMWARES:
            with self.subTest(firmware=firmware), tempfile.TemporaryDirectory() as folder:
                camera = Mock()
                b = jit.JiritsuBackend(camera, folder, firmware)
                events = []
                initialized = False

                def command(group, code, data):
                    nonlocal initialized
                    self.assertEqual(events, ['/version.txt', '/version.txt'])
                    self.assertEqual((group, code, data), (0x1001, 2, b'\x00\x00'))
                    events.append('MOUNT')
                    initialized = True
                    return bytes(4)

                def read(camera, path, limit):
                    events.append(path)
                    if path == '/version.txt':
                        return b.expected
                    self.assertTrue(initialized)
                    if path == b.ram + '/ready':
                        return b'Uid:\t0\t0\t0\t0\n'
                    raise RuntimeError('GET_FILE status 0x10000006')

                def upload(camera, path, data):
                    self.assertTrue(initialized)
                    events.append('upload:' + path)

                camera._sendAdjustControlPacket.side_effect = command
                with patch.object(jit, 'read_file', side_effect=read), \
                     patch.object(jit, 'upload_verified', side_effect=upload), \
                     patch.object(common, 'restore_owner'):
                    b.start()
                self.assertEqual(events[3:6], ['/tmp/jiritsu/run.sh', '/tmp/jiritsu/libJit.so',
                                               '/tmp/jiritsu/out.txt'])
                self.assertEqual(events[6:8], ['upload:/tmp/jiritsu/run.sh',
                                               'upload:/tmp/jiritsu/libJit.so'])
                self.assertTrue(b.started)
                self.assertTrue(b.status['workspace_initialized'])

    def test_initialization_failure_stops_before_loader_checks_or_uploads(self):
        for response in (struct.pack('<I', 0x10000004), struct.pack('<I', 0x1000000d), b'\x00'):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as folder:
                b = jit.JiritsuBackend(Mock(), folder, '2.03')
                b.camera._sendAdjustControlPacket.return_value = response
                with patch.object(jit, 'read_file', return_value=b.expected) as read, \
                     patch.object(jit, 'upload_verified') as upload:
                    with self.assertRaises(RuntimeError): b.start()
                    self.assertEqual(read.call_count, 2)
                    upload.assert_not_called()
                b.camera._sendAdjustControlPacket.assert_called_once_with(0x1001, 2, b'\x00\x00')
                self.assertFalse(b.status['workspace_initialized'])
                self.assertFalse(b.started)
                self.assertFalse(b.status['requires_power_cycle'])
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_jcmd_reports_full_status_and_rejects_short_reply(self):
        camera = Mock()
        for code in (2, 16):
            camera._sendAdjustControlPacket.return_value = struct.pack('<I', 0x10000004)
            with self.assertRaisesRegex(RuntimeError, 'command %d failed: status 0x10000004' % code):
                jit.jcmd(camera, code)
        for length in range(4):
            camera._sendAdjustControlPacket.return_value = bytes(length)
            with self.assertRaisesRegex(RuntimeError, 'short status reply'):
                jit.jcmd(camera, 2)
        camera._sendAdjustControlPacket.return_value = bytes(4) + b'result'
        self.assertEqual(jit.jcmd(camera, 2), b'result')

    def test_original_payload_is_pinned(self):
        data = (common.ROOT/'helpers/jiritsu-shell/launch.so').read_bytes()
        self.assertEqual(len(data),440)
        self.assertEqual(hashlib.sha256(data).hexdigest(),jit.PAYLOAD_SHA)

    def test_common_transport_hooks_keep_one_camera(self):
        b = self.backend()
        b.camera._session_read = Mock(return_value=(0,b'known'))
        b.camera.dev._session_command = Mock(return_value={'exit_code':0,'output':'ok'})
        self.assertEqual(common.read_path(b.camera,'/version.txt'),(0,b'known'))
        self.assertEqual(common.command(b.camera.dev,'test','pwd',1)['output'],'ok')

    def test_pseudo_files_never_use_get_file(self):
        b=self.backend()
        with patch.object(jit,'read_file') as read:
            for path in ('/proc/self/status','/sys/class/block/nflasha/size'):
                with self.assertRaisesRegex(ValueError,'shell cat'):b.read_path(path)
            read.assert_not_called()

    def test_unknown_block_and_changed_capacity_refused(self):
        b=self.backend();b.run=Mock(return_value='1')
        with self.assertRaises(ValueError): b.read_path('/dev/unknown')
        with self.assertRaisesRegex(ValueError,'capacity'): b.read_path('/dev/nflasha5')
        self.assertEqual(b.run.call_count,1)

    def test_invalid_chunk_size_refused_before_camera_io(self):
        b=self.backend();b.chunk_bytes=8388608;b.run=Mock()
        with self.assertRaisesRegex(ValueError,'chunk size'):b.read_path('/dev/nflashaB0')
        b.run.assert_not_called()

    def test_large_chunk_requires_exclusive_tmpfs_before_dd(self):
        b=self.backend();b.chunk_bytes=1048576;b.run=Mock(return_value='8192')
        with patch.object(jit,'read_file') as read:
            with self.assertRaisesRegex(ValueError,'dedicated tmpfs'):b.read_path('/dev/nflashaB0')
            read.assert_not_called()
        self.assertFalse(any(' dd ' in call.args[0] for call in b.run.call_args_list))

    def test_bad_chunk_hash_stops_and_cleans_ram(self):
        b=self.backend();b.run=Mock(side_effect=['1','', '0'*64+'  chunk\n',''])
        with patch.dict(jit.REGIONS,{'/dev/nflasha5':512}), patch.object(jit,'read_file',return_value=b'x'*512):
            with self.assertRaisesRegex(RuntimeError,'hash'): b.read_path('/dev/nflasha5')
        self.assertIn('rm -f',b.run.call_args.args[0])

    def test_cancel_at_boundary_does_not_read_next_block(self):
        b=self.backend();b.cancellable=True;b.cancelled=lambda:True
        b.run=Mock(side_effect=['1','',''])
        with patch.dict(jit.REGIONS,{'/dev/nflasha5':512}), patch.object(jit,'read_file') as read:
            with self.assertRaises(jit.BackupCancelled): b.read_path('/dev/nflasha5')
            read.assert_not_called()
        self.assertIn('rm -f',b.run.call_args.args[0])

    def test_regular_file_chunks_verify_size_hash_and_ram_mount(self):
        b = self.backend()
        data = b'known' * 1000
        checksum = hashlib.sha256(data).hexdigest() + '  regular-chunk\n'
        b.run = Mock(side_effect=['none /tmp_network tmpfs rw,size=1024k 0 0', '',
                                  str(len(data)), checksum, ''])
        with patch.object(jit, 'read_file', return_value=data), \
             patch.object(jit.common, 'set_terminal_timeout') as timeout:
            self.assertEqual(b.read_regular_chunks('/usr/lib/example.so', len(data)), data)
            timeout.assert_called_once_with(b.camera, 30000)
        self.assertEqual(b.status['regular_read_bytes'], len(data))
        self.assertIn('/tmp_network/', b.run.call_args.args[0])
        self.assertFalse(any('/tmp/jiritsu/' in call.args[0] for call in b.run.call_args_list))

    def test_regular_file_chunk_size_selection(self):
        b = self.backend()
        b.run = Mock(side_effect=['none /tmp_network tmpfs rw,size=1024k 0 0', '', '4',
                                  hashlib.sha256(b'data').hexdigest() + '  regular-chunk\n', ''])
        with patch.object(jit, 'read_file', return_value=b'data'):
            self.assertEqual(b.read_regular_chunks('/usr/lib/example.so', 4, 512), b'data')
        self.assertEqual(b.status['regular_chunk_kib'], 512)
        self.assertIn('/tmp_network/', b.run.call_args.args[0])

    def test_regular_file_enables_fast_poll_and_restores_it(self):
        b = self.backend()
        b.run = Mock(side_effect=['none /tmp_network tmpfs rw,size=1024k 0 0', '', '1',
                                  hashlib.sha256(b'x').hexdigest() + '  regular-chunk\n', ''])
        with patch.object(jit, 'read_file', return_value=b'x'):
            b.read_regular_chunks('/usr/lib/example.so', 1)
        commands = [call.args[0] for call in b.run.call_args_list]
        self.assertIn('ZV_POLL=0.01', commands[1])
        self.assertIn('ZV_POLL=1', commands[-1])

    def test_large_regular_chunks_need_a_verified_dedicated_buffer(self):
        b = self.backend()
        b.run = Mock()
        with self.assertRaisesRegex(ValueError, 'dedicated tmpfs'):
            b.read_regular_chunks('/usr/lib/example.so', 4, 4096)
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            b.read_regular_chunks('/usr/lib/example.so', 4, 128)
        b.run.assert_not_called()

    def test_regular_file_chunk_mismatch_cleans_ram(self):
        b = self.backend()
        b.run = Mock(side_effect=['none /tmp_network tmpfs rw,size=1024k 0 0', '',
                                  '4', '0'*64 + '  regular-chunk\n', ''])
        with patch.object(jit, 'read_file', return_value=b'data'):
            with self.assertRaisesRegex(RuntimeError, 'hash'):
                b.read_regular_chunks('/usr/lib/example.so', 4)
        self.assertIn('rm -f', b.run.call_args.args[0])

    def test_close_cleans_files_before_service_handoff_without_child_exit(self):
        b=self.backend();b.run=Mock(return_value='')
        with patch.object(jit,'read_file',side_effect=RuntimeError('GET_FILE status 0x10000006')):
            b.close()
        self.assertTrue(b.status['loader_files_removed'])
        self.assertNotIn('/stop',b.run.call_args.args[0])
        self.assertNotIn('exit',b.run.call_args.args[0])

    def test_cancelled_manifest_keeps_partial_and_never_claims_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            b=self.backend();b.run=Mock(return_value='metadata')
            b.camera._jiritsu_backend=b
            def receive(camera,name,iteration):
                path=backup.raw.OUT/(name+'.read1.bin.part');path.write_bytes(b'partial')
                backup.raw.RESULT['reads'].append({'file':name+'.read1.bin','complete':False})
                raise jit.BackupCancelled()
            with patch.object(backup.raw,'receive',side_effect=receive):
                result=backup.dispatch(b.camera,{'passes':1},Path(folder),False)
            self.assertTrue(result['cancelled']);self.assertFalse(result['completed'])
            self.assertTrue(list(Path(folder).rglob('*.part')))
            self.assertFalse(list(Path(folder).rglob('SHA256SUMS')))

if __name__=='__main__':unittest.main()
