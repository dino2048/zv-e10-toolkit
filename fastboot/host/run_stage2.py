#!/usr/bin/env python3
"""Wait for the ZV-E10 payload, then run stage 2 over the USB link.

    python run_stage2.py [--seconds 180] [--file stage2/build/stage2.bin]

Stages the binary at 0xFE300000, calls 0xFE300001, then dumps the result block
at 0xFE308000. If the device is not there yet it polls, so it can be started
before the cable is moved.
"""
import argparse
import sys
import time
from pathlib import Path

import usb.core
import usb.util

VID, PID = 0x18D1, 0x4EE0
CHUNK = 4096
RESULT = 0xFE308000
RESULT_WORDS = 16


class Device:
    def __init__(self, dev):
        self.dev = dev
        try:
            dev.set_configuration()
        except usb.core.USBError:
            pass
        cfg = dev.get_active_configuration()
        self.intf = cfg[(0, 0)]
        usb.util.claim_interface(dev, self.intf)
        self.ep_out = usb.util.find_descriptor(
            self.intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT)
        self.ep_in = usb.util.find_descriptor(
            self.intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_IN)
        if self.ep_out is None or self.ep_in is None:
            raise RuntimeError('bulk endpoints missing')

    def close(self):
        try:
            usb.util.release_interface(self.dev, self.intf)
        except Exception:
            pass
        usb.util.dispose_resources(self.dev)

    def read_reply(self, timeout=10000):
        while True:
            resp = bytes(self.ep_in.read(64, timeout=timeout))
            if len(resp) < 4:
                return 'BAD', resp
            tag, body = resp[:4], resp[4:]
            if tag == b'INFO':
                print('  INFO ' + body.decode('utf-8', 'replace'))
                continue
            return tag.decode('latin-1'), body

    def send_command(self, cmd, timeout=5000):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        self.ep_out.write(cmd, timeout=timeout)
        return self.read_reply(timeout)

    def download(self, blob):
        status, msg = self.send_command('download:%08x' % len(blob))
        if status != 'DATA':
            raise RuntimeError('download rejected: %s %r' % (status, msg))
        want = int(msg[:8], 16)
        if want != len(blob):
            raise RuntimeError('device asked for %d bytes' % want)

        sent = 0
        while sent < len(blob):
            piece = blob[sent:sent + CHUNK]
            self.ep_out.write(piece, timeout=10000)
            sent += len(piece)

        status, msg = self.read_reply()
        if status != 'OKAY':
            raise RuntimeError('data phase failed: %s %r' % (status, msg))


def wait_for_device(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is not None:
            return dev
        time.sleep(0.5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=180)
    ap.add_argument('--file', default=str(Path(__file__).resolve().parent.parent / 'stage2' / 'build' / 'stage2.bin'))
    ap.add_argument('--block', type=lambda v: int(v, 0), default=0,
                    help='first 512-byte block to read')
    ap.add_argument('--count', type=int, default=1, help='blocks, max 64')
    args = ap.parse_args()
    if not 1 <= args.count <= 64:
        raise SystemExit('--count must be 1..64')
    if not 0 <= args.block <= 0xFFFFFFFF:
        raise SystemExit('--block must fit in 32 bits')

    blob = open(args.file, 'rb').read()
    print('waiting up to %ds for %04x:%04x ...' % (args.seconds, VID, PID), flush=True)
    dev = wait_for_device(args.seconds)
    if dev is None:
        raise SystemExit('device never appeared')

    print('found; waiting for enumeration to settle', flush=True)
    time.sleep(2.0)

    d = None
    for attempt in range(5):
        try:
            d = Device(dev)
            break
        except Exception as e:
            print('  open attempt %d failed: %s' % (attempt + 1, e), flush=True)
            time.sleep(1.0)
    if d is None:
        raise SystemExit('could not open the device')

    print('staging %d bytes at 0xfe300000' % len(blob), flush=True)
    try:
        d.download(blob)
        print('staged and loaded', flush=True)

        cmds = ['oem load:0xfe300000',
                'oem poke:0xfe320000:0x%08x' % args.block,
                'oem poke:0xfe320004:0x%08x' % args.count,
                'oem call:0xfe300001']
        for cmd in cmds:
            print('->', cmd, flush=True)
            status, msg = d.send_command(cmd, timeout=20000)
            if status != 'OKAY':
                raise SystemExit('%s: %s %r' % (cmd, status, msg))
            text = msg.decode('utf-8', 'replace').strip()
            if text:
                print('  ' + text)

        print('-> result block', flush=True)
        status, msg = d.send_command(
            'oem peek:0x%08x:%x' % (RESULT, RESULT_WORDS * 4), timeout=10000)
        if status != 'OKAY':
            raise SystemExit('peek: %s %r' % (status, msg))
        for line in msg.decode('utf-8', 'replace').strip().splitlines():
            print('  ' + line)

        nbytes = min(args.count * 512, 0x1000)
        if args.count > 8:
            print('note: oem peek returns 4 KiB; only the first 8 blocks are shown',
                  flush=True)
        print('-> data @0xfe310000 (%d blocks, %d bytes)' % (args.count, nbytes),
              flush=True)
        status, msg = d.send_command(
            'oem peek:0xfe310000:%x' % nbytes, timeout=10000)
        if status != 'OKAY':
            raise SystemExit('peek data: %s %r' % (status, msg))
        for line in msg.decode('utf-8', 'replace').strip().splitlines():
            print('  ' + line)
    finally:
        d.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
