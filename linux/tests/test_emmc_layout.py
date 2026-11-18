"""Capacity variants and fail-closed backup preflight; no hardware access."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import zve10_emmc_layout as emmc
import zve10_backup_raw as raw
import zve10_backup_session as backup
import zve10_jiritsu as jit


def fixture(user=1954545664, boot=4194304):
    rows = [('nflasha', 0, user, 0)]
    for line in (emmc.common.ROOT / 'examples/partitions.sample.tsv').read_text().splitlines():
        if line and not line.startswith('#'):
            name, start, size = line.split()
            rows.append((name, int(start), int(size), int(name[7:])))
    rows += [('nflashaB0', 0, boot, 126), ('nflashaB1', 0, boot, 127)]
    proc = ''.join('252 %d %d %s\n' % (minor, size // 1024, name) for name, start, size, minor in rows)
    layout = ''.join('DEVICE:/sys/class/block/%s\nFIELD:dev\n252:%d\nFIELD:size\n%d\n'
                     'FIELD:start\n%d\nFIELD:ro\n0\n' % (name, minor, size // 512, start // 512)
                     for name, start, size, minor in rows)
    return {'partitions': proc, 'layout': layout}


class LayoutTests(unittest.TestCase):
    def test_standalone_probe_accepts_variant_and_reads_each_area_twice(self):
        data = fixture(1979711488, 2097152)
        camera = Mock()
        def command(dev, name, text, timeout):
            return {'name': name, 'exit_code': 0, 'output': data.get(name, '')}
        def receive(cam, name, iteration):
            self.assertEqual(raw.RESULT['regions'][name], 1979711488 if name == 'nflasha' else 2097152)
            return {'sha256': 'a' * 64, 'chunk_sha256_1MiB': []}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(raw, 'OUT', Path(directory)), \
             patch.object(raw, 'RESULT', {'reads': [], 'metadata': [], 'completed': False}), \
             patch.object(raw.common, 'check_version'), patch.object(raw.common, 'drain'), \
             patch.object(raw.common, 'set_terminal_timeout'), \
             patch.object(raw.common, 'command', side_effect=command), \
             patch.object(raw.shutil, 'disk_usage', return_value=Mock(free=10**12)), \
             patch.object(raw, 'receive', side_effect=receive) as read:
            raw.probe(camera, b'known')
            self.assertTrue(raw.RESULT['completed'])
            self.assertEqual(read.call_count, 6)
            self.assertTrue(all(c['identical'] for c in raw.RESULT['comparisons'].values()))

    def test_session_pins_variant_regions_and_releases_them_afterwards(self):
        from contextlib import nullcontext
        data = fixture(1979711488, 2097152)
        camera = type('Camera', (), {'dev': object()})()
        backend = jit.JiritsuBackend(camera, '.', '2.03')
        camera._jiritsu_backend = backend
        backend.backup_buffer = lambda size: nullcontext({})
        backend.run = lambda cmd: data['partitions'] if 'partitions' in cmd else data['layout'] if 'FIELD:' in cmd else ''
        def receive(cam, name, iteration):
            self.assertEqual(backend.backup_regions, emmc.validate(**data))
            row = {'file': name + str(iteration), 'sha256': 'a' * 64,
                   'complete': True, 'chunk_sha256_1MiB': []}
            raw.RESULT['reads'].append(row)
            return row
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(backup.shutil, 'disk_usage', return_value=Mock(free=10**12)), \
             patch.object(raw, 'receive', side_effect=receive):
            result = backup.dispatch(camera, {'passes': 2}, Path(directory), False)
            self.assertTrue(result['completed'])
            self.assertEqual(raw.RESULT['regions']['nflashaB0'], 2097152)
        self.assertFalse(hasattr(backend, 'backup_regions'))

    def test_geometry_failure_prevents_both_paths_from_reading_blocks(self):
        data = fixture()
        data['partitions'] = data['partitions'].replace('1908736', '1933312')
        from contextlib import nullcontext
        camera = type('Camera', (), {'dev': object(), 'setTerminalEnable': lambda self, on: None})()
        backend = jit.JiritsuBackend(camera, '.', '2.03')
        camera._jiritsu_backend = backend
        backend.backup_buffer = lambda size: nullcontext({})
        backend.run = lambda cmd: data['partitions'] if 'partitions' in cmd else data['layout'] if 'FIELD:' in cmd else ''
        with tempfile.TemporaryDirectory() as directory, patch.object(raw, 'receive') as read:
            with self.assertRaises(ValueError):
                backup.dispatch(camera, {}, Path(directory), False)
            read.assert_not_called()
            self.assertFalse(raw.RESULT['completed'])
            def command(dev, name, text, timeout):
                return {'name': name, 'exit_code': 0, 'output': data.get(name, '')}
            with patch.object(raw, 'OUT', Path(directory)), \
                 patch.object(raw, 'RESULT', {'metadata': [], 'reads': [], 'completed': False}), \
                 patch.object(raw.common, 'check_version'), patch.object(raw.common, 'drain'), \
                 patch.object(raw.common, 'set_terminal_timeout'), \
                 patch.object(raw.common, 'command', side_effect=command):
                with self.assertRaises(ValueError):
                    raw.probe(camera, b'known')
                read.assert_not_called()
                self.assertFalse(raw.RESULT['completed'])

    def test_emmc_info_dispatch_overrides_companion_handler_without_new_usb(self):
        import json
        import os
        import zve10_terminal_server as server
        camera = type('Camera', (), {'dev': object(), 'setTerminalEnable': lambda self, on: None,
                                    'readHasp': lambda self: None})()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'requests').mkdir()
            (folder / 'responses').mkdir()
            (folder / 'requests' / ('0' * 32 + '.json')).write_text('{"action":"emmc-info"}')
            (folder / 'requests' / ('1' * 32 + '.json')).write_text('{"action":"close"}')
            with patch.object(server.common, 'connect', side_effect=lambda cb, driver: cb(camera)), \
                 patch.object(server.common, 'check_version'), patch.object(server.common, 'drain'), \
                 patch.object(server, 'CLIENT_UID', os.getuid() if hasattr(os, 'getuid') else None), \
                 patch.object(server, 'REQUEST_HANDLER') as extension, \
                 patch.object(emmc, 'dispatch', return_value={'action': 'emmc-info'}) as query:
                server.serve(folder, False, False, 'libusb')
            extension.assert_not_called()
            query.assert_called_once_with(camera, {'action': 'emmc-info'}, folder, False)
            self.assertEqual(json.loads((folder / 'state.json').read_text())['state'], 'closed')

    def test_original_and_reported_variant_keep_full_user_tail(self):
        for user, boot in ((1954545664, 4194304), (1979711488, 2097152)):
            result = emmc.validate(**fixture(user, boot))
            self.assertEqual(result, dict(nflasha=user, nflashaB0=boot, nflashaB1=boot))
            self.assertGreater(result['nflasha'], 1417674752)

    def test_disagreement_missing_duplicate_and_changed_partition_refused(self):
        known = fixture()
        cases = [dict(known, partitions=known['partitions'].replace('1908736', '1933312')),
                 dict(known, layout=known['layout'] + known['layout']),
                 dict(known, partitions=known['partitions'].split('\n', 1)[1]),
                 dict(known, layout=known['layout'].replace('FIELD:start\n128\n', 'FIELD:start\n136\n')),
                 dict(known, layout=known['layout'].replace('FIELD:dev\n252:1\n', 'FIELD:dev\n252:0\n')),
                 fixture(1400 * 1048576 - 64 * 1048576), fixture(2**32), fixture(1954545664, 0),
                 fixture(1954545664, 64 * 1048576)]
        for data in cases:
            with self.subTest(data=str(data)[:100]), self.assertRaises(ValueError):
                emmc.validate(**data)

    def test_receive_rechecks_geometry_before_any_block_read(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(raw, 'OUT', Path(folder)), \
             patch.object(raw, 'RESULT', {'regions': emmc.validate(**fixture()), 'reads': []}), \
             patch.object(emmc, 'collect', return_value=fixture(1979711488, 2097152)), \
             patch.object(raw.common, 'read_path') as read:
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                raw.receive(Mock(), 'nflasha', 1)
            read.assert_not_called()
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['manifest.json'])
            self.assertEqual(len(raw.RESULT['geometry_checks']), 1)

    def test_jiritsu_small_boot_area_is_read_at_its_actual_size(self):
        import hashlib
        camera = Mock()
        backend = jit.JiritsuBackend(camera, '.', '2.03')
        geometry = fixture(1979711488, 2097152)
        backend.backup_regions = emmc.validate(**geometry)
        chunk = b'x' * 524288
        checksum = hashlib.sha256(chunk).hexdigest() + '  chunk\n'
        backend.run = Mock(side_effect=['4096', ''] + [checksum] * 4 + [''])
        with patch.object(emmc, 'collect', return_value=geometry), \
             patch.object(jit, 'read_file', return_value=chunk) as read:
            status, data = backend.read_path('/dev/nflashaB0')
        self.assertEqual(status, 0)
        self.assertEqual(len(data), 2097152)
        self.assertEqual(read.call_count, 4)

    def test_identity_action_is_readonly_and_identity_may_be_unavailable(self):
        geometry = fixture(1979711488, 2097152)
        with patch.object(emmc.common, 'check_version') as version, \
             patch.object(emmc, 'collect', return_value=geometry), \
             patch.object(emmc.common, 'command', return_value={'exit_code': 0, 'output': ''}) as command:
            camera = type('Camera', (), {'dev': object()})()
            result = emmc.dispatch(camera, {'action': 'emmc-info'}, Path('.'), False)
        self.assertEqual(version.call_count, 2)
        self.assertFalse(result['identity_available'])
        self.assertEqual(result['regions']['nflashaB1'], 2097152)
        self.assertEqual(command.call_args.args[2], emmc.INFO_COMMAND)


if __name__ == '__main__':
    unittest.main()
