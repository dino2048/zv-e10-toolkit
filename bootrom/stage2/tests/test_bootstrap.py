import importlib.util
from pathlib import Path
import sys
import types
import unittest

# No USB library/hardware is needed for protocol validation.
usb = types.ModuleType('usb')
usb.core = types.ModuleType('usb.core')
usb.util = types.ModuleType('usb.util')
usb.control = types.ModuleType('usb.control')
sys.modules.update({'usb': usb, 'usb.core': usb.core, 'usb.util': usb.util, 'usb.control': usb.control})
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', root.parent / 'host/bootstrap.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class MemoryDevice:
    def __init__(self, data, corrupt=False):
        self.data, self.corrupt = data, corrupt

    def require(self, command):
        _, address, count = command.split(':')
        address, count = int(address,16), int(count,16)
        raw = bytearray(self.data[address-b.STAGE1_LOAD:address-b.STAGE1_LOAD+count])
        if self.corrupt:
            raw[0] ^= 1
        lines = []
        for offset in range(0,len(raw),16):
            words = [f'{int.from_bytes(raw[i:i+4],"little"):08x}'
                     for i in range(offset,min(offset+16,len(raw)),4)]
            lines.append(f'{address+offset:08x}: ' + ' '.join(words))
        return b'', lines


class DownloadDevice:
    def __init__(self, wanted, success=True):
        self.wanted, self.success, self.parts = wanted, success, []

    def command(self, command):
        return b'DATA', f'{self.wanted:08x}'.encode(), []

    def write(self, data):
        self.parts.append(data)

    def read_reply(self):
        return (b'OKAY' if self.success else b'FAIL'), b'', []


class ProtocolTests(unittest.TestCase):
    def test_handoff_rejects_old_stage1_before_download(self):
        expected = bytes(i & 255 for i in range(b.IMMUTABLE_SIZE))
        class OldStage1(MemoryDevice):
            def require(self, command):
                if command == 'getvar:version':
                    return b'0.4', []
                return super().require(command)
            def command(self, command):
                raise AssertionError('must not download to a mismatched stage1')
            def write(self, payload):
                raise AssertionError('must not call stage2 on a mismatched stage1')
        with self.assertRaisesRegex(ValueError, 'pinned ABI'):
            b.handoff(OldStage1(expected, corrupt=True), b'image', expected,
                      'stage2-flash-20261026', allow_writer=True)

    def test_verified_handoff(self):
        expected = bytes(i & 255 for i in range(b.IMMUTABLE_SIZE))
        payload = b'x' * 5172
        class Stage1(MemoryDevice):
            def __init__(self):
                super().__init__(expected)
                self.parts = []
                self.called = False
            def require(self, command):
                if command == 'getvar:version':
                    return b'0.4', []
                if command == 'oem load:fe300000':
                    assert b''.join(self.parts) == payload
                    return b'', []
                if command == 'getvar:version-bootloader':
                    assert self.called
                    return b'stage2-flash-20261026', []
                if command == 'getvar:read-only':
                    return b'no', []
                return super().require(command)
            def command(self, command):
                self.test_command = command
                return b'DATA', f'{len(payload):08x}'.encode(), []
            def write(self, data):
                if data == b'oem call:fe300001':
                    self.called = True
                else:
                    self.parts.append(data)
            def read_reply(self):
                return b'OKAY', b'', []
        d = Stage1()
        b.handoff(d, payload, expected, 'stage2-flash-20261026', allow_writer=True)
        self.assertTrue(d.called)
        self.assertEqual(d.test_command, 'download:00001434')

    def test_idle_sends_no_commands_until_interval_ends(self):
        now, calls, logs = [0.0], [], []
        def require(command):
            calls.append((now[0], command))
            return (b'stage2-flash-20261026' if command.endswith('bootloader') else b'no'), []
        d = types.SimpleNamespace(require=require)
        b.idle_check(d, 'stage2-flash-20261026', 330, logs.append,
                     clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0]+seconds),
                     allow_writer=True)
        self.assertEqual(now[0], 330)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(t == 330 for t, command in calls))

    def test_wrong_stage2_identity_and_capability_are_rejected(self):
        d = types.SimpleNamespace(require=lambda command: (b'single', []))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            b.verify_running_stage2(d, 'stage2-flash-20261026', allow_writer=True)
        d.require = lambda command: (b'stage2-flash-20261026' if command.endswith('bootloader') else b'yes', [])
        with self.assertRaisesRegex(ValueError, 'capability mismatch'):
            b.verify_running_stage2(d, 'stage2-flash-20261026', allow_writer=True)

    def test_preserve_existing_configuration(self):
        dev = types.SimpleNamespace(configuration=1, changes=[], get_active_configuration=lambda: {(0,0): 'interface'})
        dev.set_configuration=lambda value: dev.changes.append(value)
        usb.control.get_configuration=lambda dev: dev.configuration
        usb.util.claim_interface=lambda *args: None
        usb.util.find_descriptor=lambda intf, custom_match: object()
        usb.util.release_interface=lambda *args: None
        usb.util.dispose_resources=lambda *args: None
        d=b.Device(dev)
        self.assertEqual(dev.changes, [])
        d.close()
        dev.configuration=0
        d=b.Device(dev)
        self.assertEqual(dev.changes, [1])
        d.close()

    def test_running_immutable_fingerprint(self):
        data = bytes(i&255 for i in range(7908))
        b.target_fingerprint(MemoryDevice(data), data)
        changed = data[:b.IMMUTABLE_SIZE] + b'xxxx'  # mutable .data is excluded
        b.target_fingerprint(MemoryDevice(changed), data)
        with self.assertRaises(ValueError):
            b.target_fingerprint(MemoryDevice(data, True), data)

    def test_download_length_and_data_phase(self):
        data = b'x' * 5172
        d = DownloadDevice(len(data))
        b.download(d, data)
        self.assertEqual([len(p) for p in d.parts], [4096, 1076])
        self.assertEqual(b''.join(d.parts), data)
        with self.assertRaises(ValueError):
            b.download(DownloadDevice(4096), data)
        with self.assertRaises(ValueError):
            b.download(DownloadDevice(len(data), False), data)

    def test_actual_short_write_is_rejected(self):
        d = b.Device.__new__(b.Device)
        d.ep_out = types.SimpleNamespace(write=lambda data, timeout: len(data)-1)
        with self.assertRaises(ValueError):
            d.write(b'abcd')

    def test_replies(self):
        d = b.Device.__new__(b.Device)
        replies = iter([b'INFOhello', b'OKAYyes'])
        d.ep_in = types.SimpleNamespace(read=lambda n, timeout: next(replies))
        self.assertEqual(d.read_reply(), (b'OKAY', b'yes', ['hello']))
        d.ep_in = types.SimpleNamespace(read=lambda n, timeout: b'BAD')
        with self.assertRaises(ValueError):
            d.read_reply()


if __name__ == '__main__':
    unittest.main()
