#!/usr/bin/env python3
"""Host-side fastboot transport for the ZV-E10 payload.

The Android `fastboot` CLI does not pick this device up on macOS even though
it enumerates correctly (device-level class 0xff), so this speaks the same
wire protocol through pyusb.

    python zve10_fb.py info
    python zve10_fb.py getvar product
    python zve10_fb.py oem help
    python zve10_fb.py oem peek:0xf020c120:4
    python zve10_fb.py oem poke:0xfe100000:0x12345678
    python zve10_fb.py oem call:0xfe300001
    python zve10_fb.py download stage2/build/stage2.bin
    python zve10_fb.py oem load:0xfe100000
    python zve10_fb.py reboot
"""
import argparse
import sys
import time

import usb.core
import usb.util

VID = 0x18d1
PID = 0x4ee0
CHUNK = 4096            # matches the payload's bulk TRB size


class Device:
    def __init__(self):
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            raise SystemExit('ZV-E10 fastboot device not found (18d1:4ee0)')

        # macOS usually sets the configuration during enumeration already;
        # a second one is harmless now but may transiently fail.
        try:
            self.dev.set_configuration()
        except usb.core.USBError:
            pass
        cfg = self.dev.get_active_configuration()
        self.intf = cfg[(0, 0)]
        usb.util.claim_interface(self.dev, self.intf)

        self.ep_out = usb.util.find_descriptor(
            self.intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT)
        self.ep_in = usb.util.find_descriptor(
            self.intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN)

        if self.ep_out is None or self.ep_in is None:
            raise SystemExit('bulk endpoints missing')

    def close(self):
        try:
            usb.util.release_interface(self.dev, self.intf)
        except Exception:
            pass
        usb.util.dispose_resources(self.dev)

    def _read(self, timeout=5000):
        return bytes(self.ep_in.read(64, timeout=timeout))

    def command(self, cmd, timeout=5000):
        """Send one command; return (status, payload). Handles INFO/DATA."""
        if isinstance(cmd, str):
            cmd = cmd.encode()
        self.ep_out.write(cmd, timeout=timeout)

        while True:
            resp = self._read(timeout)
            if len(resp) < 4:
                return 'BAD', resp
            tag, msg = resp[:4], resp[4:]
            if tag == b'INFO':
                print(msg.decode('utf-8', 'replace'))
                continue
            if tag == b'OKAY':
                return 'OKAY', msg
            if tag == b'FAIL':
                return 'FAIL', msg
            if tag == b'DATA':
                return 'DATA', msg
            return 'UNKNOWN', resp

    def download(self, blob):
        status, msg = self.command('download:%08x' % len(blob))
        if status != 'DATA':
            raise SystemExit('download rejected: %s %r' % (status, msg))
        want = int(msg[:8], 16)
        if want != len(blob):
            raise SystemExit('device asked for %d bytes, sending %d' % (want, len(blob)))

        sent = 0
        while sent < len(blob):
            piece = blob[sent:sent + CHUNK]
            self.ep_out.write(piece, timeout=10000)
            sent += len(piece)

        status, msg = self.command_result()
        if status != 'OKAY':
            raise SystemExit('download failed: %s %r' % (status, msg))
        return len(blob)

    def command_result(self):
        """Read the reply that follows a data phase already sent."""
        while True:
            resp = self._read(10000)
            tag, msg = resp[:4], resp[4:]
            if tag == b'INFO':
                print(msg.decode('utf-8', 'replace'))
                continue
            return tag.decode('latin-1'), msg


SAFE_WINDOWS = ((0xF0000000, 0xF4000000), (0xFE000000, 0xFF000000))


def guard_address(text):
    """Reject the typo class that wedged a payload: a 33+-bit value that the
    device would have truncated into untrained DRAM (an AXI stall, not an
    abort)."""
    value = int(text, 0)
    if value > 0xFFFFFFFF:
        raise SystemExit('address %s is wider than 32 bits' % text)
    if not any(lo <= value < hi for lo, hi in SAFE_WINDOWS):
        raise SystemExit('address 0x%08x is outside the peripheral/eSRAM windows' % value)
    return value


def fmt(msg):
    return msg.decode('utf-8', 'replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', nargs='+', help='e.g. "oem peek:0xf020c120:4"')
    parser.add_argument('--timeout', type=int, default=5000)
    args = parser.parse_args()

    words = args.command
    if words[0] == 'download':
        if len(words) != 2:
            raise SystemExit('usage: download <file>')
        blob = open(words[1], 'rb').read()
        dev = Device()
        try:
            n = dev.download(blob)
            print('staged %d bytes' % n)
        finally:
            dev.close()
        return 0

    if words[0] == 'oem' and len(words) > 1:
        for prefix in ('peek:', 'poke:', 'call:', 'load:'):
            rest = words[1][len(prefix):]
            if words[1].startswith(prefix) and rest:
                parts = rest.split(':')
                guard_address(parts[0])
                if prefix == 'poke:' and len(parts) >= 2:
                    if int(parts[1], 0) > 0xFFFFFFFF:
                        raise SystemExit('poke value is wider than 32 bits')

    if words[0] in ('getvar', 'download', 'flash', 'erase') and len(words) > 1:
        cmd = words[0] + ':' + ' '.join(words[1:])
    else:
        cmd = ' '.join(words)
    dev = Device()
    try:
        status, msg = dev.command(cmd, args.timeout)
    finally:
        dev.close()

    if status == 'OKAY':
        text = fmt(msg)
        if text:
            print(text)
        return 0
    print('%s %s' % (status, fmt(msg)), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
