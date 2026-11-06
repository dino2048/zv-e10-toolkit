"""Offline only: no USB imports or camera operations."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import zve10_backup_properties as backup
import zve10_terminal_server as server
import zve10_terminal_client as client


class Camera:
    dev = object()

    def __init__(self):
        self.value = b'\x09'; self.writes = []; self.saves = []; self.terminal = []

    def readHasp(self): pass
    def readBackup(self, key): return self.value
    def writeBackup(self, key, value): self.writes.append((key, value)); self.value = value
    def saveBackup(self, subsystem): self.saves.append(subsystem)
    def setTerminalEnable(self, enabled): self.terminal.append(enabled)


class Tests(unittest.TestCase):
    def test_property_guards_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp); camera = Camera()
            req = {'action': 'backup-write', 'id': '0x00A5000B', 'expected': '09', 'value': '02'}
            with self.assertRaises(ValueError): backup.dispatch(camera, req, folder, False)
            with self.assertRaises(ValueError): backup.dispatch(camera, {**req, 'expected':'08'}, folder, True)
            self.assertEqual(camera.writes, [])
            answer = backup.dispatch(camera, req, folder, True)
            self.assertTrue(answer['match']); self.assertEqual(camera.saves, [0xA5])
            self.assertEqual(json.loads((folder/answer['snapshot']).read_text())['original'], '09')
            self.assertEqual((folder/answer['snapshot']).stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup.dispatch(camera, {'action':'backup-read','id':'0xA5000B'}, folder, False)['value'], '02')

    def test_readback_failure_and_snapshot_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            req = {'action':'backup-write','id':'0xA5000B','expected':'09','value':'02'}
            camera = Camera()
            with patch.object(camera, 'readBackup', side_effect=[b'\x09', b'\x08']):
                with self.assertRaises(RuntimeError): backup.dispatch(camera, req, folder, True)
            self.assertEqual(camera.saves, [0xA5])
            self.assertEqual(len(list(folder.glob('*-backup-property.json'))), 1)
            camera = Camera()
            with self.assertRaises(FileNotFoundError): backup.dispatch(camera, req, folder/'missing', True)
            self.assertEqual(camera.writes, [])
            for value in ('', '00'*513):
                with self.assertRaises(ValueError): backup.dispatch(camera, {**req,'expected':value,'value':value}, folder, True)
            self.assertEqual(camera.writes, [])

    def test_existing_server_dispatch_and_teardown(self):
        # Queue and lifecycle are the existing server, not another implementation.
        for error in (False, True):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp); (folder/'requests').mkdir(); (folder/'responses').mkdir()
                camera = Camera()
                req = {'action': 'backup-write' if error else 'backup-read', 'id':'0xA5000B', 'expected':'08', 'value':'02'}
                (folder/'requests'/('0'*32+'.json')).write_text(json.dumps(req))
                (folder/'requests'/('1'*32+'.json')).write_text('{"action":"close"}')
                with patch.object(server.common,'connect',side_effect=lambda cb,driver:cb(camera)), patch.object(server.common,'check_version'), patch.object(server.common,'drain'), patch.object(server,'CLIENT_UID',os.getuid()), patch.object(server,'REQUEST_HANDLER',None):
                    if error:
                        with self.assertRaises(ValueError): server.serve(folder, True, False, 'libusb')
                    else: server.serve(folder, False, False, 'libusb')
                state = client.read_state(folder)
                self.assertEqual(state['state'], 'failed' if error else 'closed')
                self.assertTrue(state['terminal_closed'])
                self.assertEqual(camera.terminal, [True, False])
                self.assertEqual(camera.writes, [])
                if not error:
                    self.assertTrue(state['service_returned'])
                    self.assertEqual(json.loads((folder/'responses'/('0'*32+'.json')).read_text())['value'], '09')

    def test_extension_uses_existing_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'requests').mkdir();(folder/'responses').mkdir()
            (folder/'requests'/('0'*32+'.json')).write_text('{"action":"custom"}')
            (folder/'requests'/('1'*32+'.json')).write_text('{"action":"close"}')
            camera=Camera()
            with patch.object(server.common,'connect',side_effect=lambda cb,driver:cb(camera)), patch.object(server.common,'check_version'), patch.object(server.common,'drain'), patch.object(server,'CLIENT_UID',os.getuid()), patch.object(server,'REQUEST_HANDLER',return_value={'ok':True}) as handler:
                server.serve(folder, False, False, 'libusb')
                self.assertIs(handler.call_args.args[0], camera)
                self.assertEqual(camera.terminal,[True,False])


if __name__ == '__main__': unittest.main()
