"""Offline checks for host/zve10_senser.py, using a synthetic service endpoint.

The fake endpoint models what the camera puts on the wire: a 16-byte reply
header for the 0x0336 service identity, payload chunks of at most 32 KiB, and an
optional empty transfer after each chunk.  ``strict`` models the Windows
observation: the empty transfer is not delivered, so a read that expects one
fails the way the 2026-11-16 camera session did.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import zve10_senser as senser
from pmca.usb.driver.generic import GenericUsbException

HEADER = senser.StockSenserDevice.SenserPacketHeader
MAX = senser.StockSenserDevice.SenserMaxSize
CHUNK = senser.StockSenserDevice.SenserChunkSize


def wire(payload, pfunc=0x40, sequence=1, response=0, empty_transfers=True):
    """Return the endpoint's reply as a list of transfers; b'' is a ZLP."""
    transfers, remaining = [], payload
    while True:
        piece = remaining[:MAX]
        transfers.append(HEADER.pack(size=len(remaining), pFunc=pfunc,
                                     sequence=sequence, version=0, miconType=0,
                                     offsetType=0, response=response))
        for offset in range(0, len(piece), CHUNK):
            transfers.append(piece[offset:offset + CHUNK])
            if empty_transfers:
                transfers.append(b'')
        remaining = remaining[len(piece):]
        if not remaining:
            return transfers


class FakeEndpoint:
    def __init__(self, transfers, strict=True, pid=0x0336):
        self.transfers = list(transfers)
        self.strict = strict
        self.pid = pid
        self.reads = []
        self.writes = []

    def reset(self):
        pass

    def getId(self):
        return 0x054C, self.pid

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, length, ep=0, timeout=None):
        self.reads.append(length)
        if not self.transfers:
            if self.strict:
                raise GenericUsbException('simulated USB timeout')
            return b''
        front = self.transfers[0]
        if front == b'':
            self.transfers.pop(0)
            return b''
        data = front[:length]
        rest = front[length:]
        if rest:
            self.transfers[0] = rest
        else:
            self.transfers.pop(0)
        return data


class Tests(unittest.TestCase):
    def test_payload_is_read_without_a_trailing_512_byte_read(self):
        payload = bytes(range(256)) * 400
        endpoint = FakeEndpoint(wire(payload, empty_transfers=False))
        device = senser.LengthDelimitedSenserDevice(endpoint)
        self.assertEqual(device.sendSenserPacket(0x40, b'request'), (0, payload))
        self.assertNotIn(512, endpoint.reads)
        self.assertEqual(endpoint.reads[0], HEADER.size)
        self.assertLessEqual(max(endpoint.reads), CHUNK)

    def test_vendor_reader_fails_when_the_empty_transfer_is_missing(self):
        endpoint = FakeEndpoint(wire(b'x' * (CHUNK + 100), empty_transfers=False))
        device = senser.StockSenserDevice(endpoint)
        with self.assertRaises(GenericUsbException):
            device.sendSenserPacket(0x40, b'request')
        self.assertIn(512, endpoint.reads)

    def test_empty_transfers_delivered_by_the_host_are_skipped(self):
        payload = b'camera' * 20000
        endpoint = FakeEndpoint(wire(payload, empty_transfers=True))
        device = senser.LengthDelimitedSenserDevice(endpoint)
        self.assertEqual(device.sendSenserPacket(0x40, b'request'), (0, payload))

    def test_response_larger_than_one_packet(self):
        payload = os.urandom(MAX * 2 + 1234)
        endpoint = FakeEndpoint(wire(payload, empty_transfers=False))
        device = senser.LengthDelimitedSenserDevice(endpoint)
        self.assertEqual(device.sendSenserPacket(0x40, b'request'), (0, payload))

    def test_wrong_sequence_or_function_disables_the_channel(self):
        for kwargs in ({'sequence': 2}, {'pfunc': 0x41}):
            endpoint = FakeEndpoint(wire(b'data', **kwargs))
            device = senser.LengthDelimitedSenserDevice(endpoint)
            with self.assertRaisesRegex(RuntimeError, 'Wrong Senser reply'):
                device.sendSenserPacket(0x40, b'request')
            writes = len(endpoint.writes)
            with self.assertRaisesRegex(RuntimeError, 'unusable'):
                device.sendSenserPacket(0x40, b'request')
            self.assertEqual(len(endpoint.writes), writes)

    def test_short_header_is_rejected(self):
        endpoint = FakeEndpoint([b'short'], strict=False)
        device = senser.LengthDelimitedSenserDevice(endpoint)
        with self.assertRaisesRegex(RuntimeError, 'Short Senser header'):
            device.sendSenserPacket(0x40, b'request')

    def test_selection_defaults_to_vendor_reader_on_posix(self):
        with patch.object(senser.os, 'name', 'posix'), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(senser.choice(), 'stock')
        with patch.object(senser.os, 'name', 'nt'), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(senser.choice(), 'length')
        with patch.dict(os.environ, {'ZVE10_SENSER_FRAMING': 'length'}):
            self.assertEqual(senser.choice(), 'length')
        with patch.dict(os.environ, {'ZVE10_SENSER_FRAMING': 'board'}), self.assertRaises(ValueError):
            senser.choice()

    def test_connect_selects_the_reader_before_opening_the_camera(self):
        import zve10_common as common
        order = []

        def record_install():
            order.append('install')
            return False

        def record_shell(**kwargs):
            order.append('shell')

        with patch.object(senser, 'install', side_effect=record_install), \
             patch('pmca.commands.usb.senserShellCommand', side_effect=record_shell):
            common.connect(lambda camera: None)
        self.assertEqual(order, ['install', 'shell'])

    def test_install_replaces_the_factory_name_only_when_selected(self):
        from pmca.commands import usb as pmca_usb
        original = pmca_usb.SonySenserDevice
        try:
            self.assertFalse(senser.install('stock'))
            self.assertIs(pmca_usb.SonySenserDevice, original)
            self.assertTrue(senser.install('length'))
            self.assertIs(pmca_usb.SonySenserDevice, senser.LengthDelimitedSenserDevice)
            self.assertTrue(issubclass(pmca_usb.SonySenserDevice, original))
            self.assertFalse(senser.install('stock'))
            self.assertIs(pmca_usb.SonySenserDevice, original)
        finally:
            pmca_usb.SonySenserDevice = original


if __name__ == '__main__':
    unittest.main()
