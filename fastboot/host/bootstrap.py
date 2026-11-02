#!/usr/bin/env python3
"""Load and inspect a paired stage2 over USB. This tool does not flash blocks."""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import time

import usb.core
import usb.control
import usb.util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_abi import verify, verify_stage2, EXPECTED_SHA, IMMUTABLE_SIZE

VID, PID = 0x18D1, 0x4EE0
LOAD = 0xFE300000
STAGE1_LOAD = 0xFE020000
CHUNK = 4096
DIAGNOSTICS = ('emmc-status', 'emmc-init-rc', 'part-load-rc', 'part-count',
               'mmc-last-cmd', 'mmc-last-error', 'mmc-last-r1', 'mmc-ocr',
               'block0-head', 'entry-stack-sp', 'usb-last-error')


class Device:
    def __init__(self, dev):
        self.dev = dev
        self.intf = None
        # GET_CONFIGURATION distinguishes state 0 from a transport failure;
        # a stalled/timed-out EP0 is propagated, never swallowed as "unconfigured".
        configuration = usb.control.get_configuration(dev)
        if configuration == 0:
            dev.set_configuration(1)
        elif configuration != 1:
            raise ValueError(f'Unexpected USB configuration: {configuration}')
        cfg = dev.get_active_configuration()
        self.intf = cfg[(0, 0)]
        usb.util.claim_interface(dev, self.intf)
        self.ep_out = usb.util.find_descriptor(self.intf,
            custom_match=lambda e: e.bEndpointAddress == 0x01)
        self.ep_in = usb.util.find_descriptor(self.intf,
            custom_match=lambda e: e.bEndpointAddress == 0x81)
        if self.ep_out is None or self.ep_in is None:
            self.close()
            raise ValueError('Required bulk endpoints 01/81 not found')

    def close(self):
        try:
            if self.intf is not None:
                usb.util.release_interface(self.dev, self.intf)
        finally:
            usb.util.dispose_resources(self.dev)

    def write(self, data):
        if self.ep_out.write(data, timeout=10000) != len(data):
            raise ValueError('Short USB write; stop and reinject instead of retrying partial state')

    def read_reply(self, timeout=15000):
        infos = []
        # Bound INFO processing as well as individual USB reads.
        for _ in range(1024):
            raw = bytes(self.ep_in.read(64, timeout=timeout))
            if len(raw) < 4:
                raise ValueError('Malformed short fastboot reply')
            tag, body = raw[:4], raw[4:]
            if tag == b'INFO':
                infos.append(body.decode('ascii'))
                continue
            if tag not in (b'OKAY', b'FAIL', b'DATA'):
                raise ValueError(f'Unknown fastboot tag: {tag!r}')
            return tag, body, infos
        raise ValueError('Excessive INFO replies')

    def command(self, command):
        self.write(command.encode('ascii'))
        return self.read_reply()

    def require(self, command):
        tag, body, infos = self.command(command)
        if tag != b'OKAY':
            raise ValueError(f'{command}: {tag!r} {body!r}')
        return body, infos


def target_fingerprint(d, expected):
    """Read-only oem peek verifies *running* code, not just a local filename."""
    expected = expected[:IMMUTABLE_SIZE]
    result = bytearray()
    for offset in range(0, len(expected), 4096):
        count = min(4096, len(expected) - offset)
        _, infos = d.require(f'oem peek:{STAGE1_LOAD + offset:08x}:{count:08x}')
        address = STAGE1_LOAD + offset
        for line in infos:
            match = re.fullmatch(r'([0-9a-fA-F]{8}):((?: [0-9a-fA-F]{8}){1,4})', line)
            if not match or int(match[1], 16) != address:
                raise ValueError('Unexpected oem peek format/address')
            for word in match[2].split():
                result.extend(int(word, 16).to_bytes(4, 'little'))
                address += 4
        if address != STAGE1_LOAD + offset + count:
            raise ValueError('Incomplete stage 1 readback')
    if bytes(result) != expected:
        raise ValueError('Running stage 1 does not match the pinned ABI; refusing call')


def download(d, blob):
    tag, body, _ = d.command(f'download:{len(blob):08x}')
    if tag != b'DATA' or body != f'{len(blob):08x}'.encode('ascii'):
        raise ValueError(f'Unexpected download response: {tag!r} {body!r}')
    for offset in range(0, len(blob), CHUNK):
        d.write(blob[offset:offset + CHUNK])
    tag, body, _ = d.read_reply()
    if tag != b'OKAY':
        raise ValueError(f'Download failed: {tag!r} {body!r}')


def handoff(d, blob, expected_stage1, identity, *, allow_writer=False):
    """Verify running stage 1 before downloading or calling any stage 2 code."""
    version, _ = d.require('getvar:version')
    if version != b'0.4':
        raise ValueError(f'Unexpected stage 1 protocol version: {version!r}')
    target_fingerprint(d, expected_stage1)
    download(d, blob)
    d.require(f'oem load:{LOAD:08x}')
    d.write(f'oem call:{LOAD | 1:08x}'.encode('ascii'))
    verify_running_stage2(d, identity, allow_writer=allow_writer)


def verify_running_stage2(d, identity, *, allow_writer=False):
    version, _ = d.require('getvar:version-bootloader')
    if version != identity.encode('ascii'):
        raise ValueError(f'Stage 2 identity mismatch: expected {identity}, got {version!r}')
    mode, _ = d.require('getvar:read-only')
    if mode != (b'no' if allow_writer else b'yes'):
        raise ValueError(f'Stage 2 write capability mismatch: {mode!r}')


def idle_check(d, identity, seconds, record=print, *, clock=time.monotonic,
               sleep=time.sleep, allow_writer=False):
    """Keep the USB handle, send no traffic during the measured idle interval."""
    start = clock()
    record(f'idle start: {seconds:g} s; injector must already be stopped')
    next_report = 30
    while True:
        elapsed = clock() - start
        if elapsed >= seconds:
            break
        if elapsed >= next_report:
            record(f'idle host clock: {elapsed:.1f} s (no USB commands sent)')
            next_report += 30
        sleep(min(1.0, seconds - elapsed))
    elapsed = clock() - start
    verify_running_stage2(d, identity, allow_writer=allow_writer)
    record(f'idle end: {elapsed:.3f} s; stage 2 identity and write capability verified')


def wait_for_device(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is not None:
            return dev
        time.sleep(0.5)
    raise ValueError('Device never appeared')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seconds', type=int, default=120)
    ap.add_argument('--file', type=Path, default=ROOT / 'prebuilt/stage2-flash.bin')
    ap.add_argument('--log', type=Path,
                    default=ROOT / 'logs' / time.strftime('bootstrap-%Y%m%d-%H%M%S.log'))
    ap.add_argument('--idle-seconds', type=float, default=0,
                    help='after takeover, send no commands for this many seconds, then verify identity')
    ap.add_argument('--usb-only', action='store_true', help='verify handoff without accessing eMMC')
    ap.add_argument('--read-lba', type=lambda v: int(v, 0), help='read one additional nonzero LBA (accepts 0x prefix)')
    args = ap.parse_args()
    if args.seconds <= 0 or not 0 <= args.idle_seconds <= 86400 or (args.read_lba is not None and not 0 <= args.read_lba <= 0xffffffff):
        ap.error('Invalid timeout or LBA')
    if args.usb_only and args.read_lba is not None:
        ap.error('--read-lba requires eMMC initialization')
    expected = verify()
    blob = args.file.read_bytes()
    if not 0 < len(blob) <= 0x10000:
        raise ValueError('Stage 2 must be nonempty and fit its 64 KiB linked window')
    identity = verify_stage2(blob, args.file.with_suffix('.elf'),
                             allow_writer=True)
    # Reject accidental injection of unrelated files and log the chosen artifact.
    print(f'stage2 SHA256: {hashlib.sha256(blob).hexdigest()}', flush=True)
    dev = wait_for_device(args.seconds)
    d = Device(dev)
    lines = []
    def record(text):
        print(text, flush=True)
        lines.append(text)
    failed = False
    try:
        record('stage2 SHA256: ' + hashlib.sha256(blob).hexdigest())
        handoff(d, blob, expected, identity, allow_writer=True)
        record('running stage1 text/rodata verified; pinned binary SHA256: ' + EXPECTED_SHA)
        record('version-bootloader: ' + identity)
        if args.idle_seconds:
            idle_check(d, identity, args.idle_seconds, record, allow_writer=True)
        if not args.usb_only:
            tag, body, _ = d.command('oem emmc-init')
            record(f'emmc-init: {tag.decode()} {body.decode()}')
            failed = tag != b'OKAY'
        for name in DIAGNOSTICS:
            value, _ = d.require('getvar:' + name)
            record(f'{name}: {value.decode()}')
        if not args.usb_only and not failed:
            value, _ = d.require('getvar:partition-size:nflasha1')
            record('partition-size:nflasha1: ' + value.decode())
            if args.read_lba is not None:
                _, infos = d.require(f'oem read-block:{args.read_lba:08x}')
                raw = bytearray()
                for index, line in enumerate(infos):
                    match = re.fullmatch(r'([0-9a-f]{8}):([0-9a-f]{32})', line)
                    if not match or int(match[1],16) != index*16:
                        raise ValueError('Invalid block dump')
                    raw.extend(bytes.fromhex(match[2]))
                    record(line)
                if len(raw) != 512:
                    raise ValueError('Incomplete block dump')
                record(f'LBA {args.read_lba:#x} SHA256: {hashlib.sha256(raw).hexdigest()}')
    except Exception as error:
        record(f'ERROR: {type(error).__name__}: {error}')
        raise
    finally:
        try:
            d.close()
        finally:
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.log.write_text('\n'.join(lines) + '\n')
    print('Stage2 checks finished in one USB handle; no flash performed.')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
