"""Inject an arbitrary ARMv7 payload through the ZV-E10 BootROM serial boot.

Same record group and v15 reset flow as the earlier injectors, but the payload comes
from a file instead of being generated. The payload is loaded at 0xFE020000
and entered at 0xFE020001 (Thumb).

    python inject_payload.py --port /dev/cu.usbmodemXXXX \
        --file ../build/fastboot.bin --duration 90
"""
import argparse
import hashlib
import json
import struct
import time
import zlib
from pathlib import Path

from inspect_pico import Link

VERSION = b'zve10_uart_od 15'
V = 0x8CB102DC
LOAD = 0xFE020000
ENTRY = 0xFE020001
# The ROM's record limit is 4086 payload bytes (14 B of header/CRC on top of
# a 4100 B frame), but 4086 is not a multiple of 4 and would leave every
# following MEM_WRITE misaligned. 4084 stays under the limit and keeps the
# load address word-aligned; the earlier 8 KB test only proved the first chunk.
CHUNK = 4084


def rec(rtype, value, payload=b''):
    body = struct.pack('<IHI', 10 + len(payload), rtype, value) + payload
    return body + struct.pack('<I', zlib.crc32(body) & 0xffffffff)


def make_records(payload):
    out = [rec(0x0000, V)]
    off = 0
    while off < len(payload):
        chunk = payload[off:off + CHUNK]
        out.append(rec(0x0001, LOAD + off, chunk))
        off += len(chunk)
    out.append(rec(0xffff, ENTRY))
    out.append(rec(0x0000, V))
    return out


def idle(status):
    return (status['mode'] == 0 and status['gpio_function'] == 5 and
            not status['pull_up'] and not status['pull_down'] and
            not status['push_pull_build'] and not status['blob_pending'])


def run(port, payload, payload_name='', duration=90, record_gap=0.0144, group_gap=0.05,
        reset_delay=0.1, reset=True, max_groups=0):
    records = make_records(payload)
    result = {'port': port, 'firmware': VERSION.decode(),
              'payload_file': payload_name,
              'payload_size': len(payload),
              'payload_sha256': hashlib.sha256(payload).hexdigest(),
              'payload_hex_head': payload[:32].hex(),
              'records': len(records),
              'record_lengths': [len(r) for r in records],
              'group_bytes': sum(len(r) for r in records),
              'record_gap_s': record_gap, 'group_gap_s': group_gap,
              'reset_delay_s': reset_delay, 'reset': reset,
              'groups': [], 'resets': 1 if reset else 0}
    link = None
    try:
        link = Link(port)
        if link.exchange(1) != VERSION:
            raise RuntimeError('Unexpected firmware (need zve10_uart_od 15)')
        result['before'] = link.status()
        if not idle(result['before']):
            raise RuntimeError('Pico must be idle input without pulls')

        link.exchange(3, b'\x01')
        if reset:
            link.exchange(2)          # GP27 reset pulse
            time.sleep(reset_delay)
        print(f'{"RESET + " if reset else ""}group: '
              f'{len(payload)} B, {len(records)} records, '
              f'{result["group_bytes"]} B on the wire', flush=True)

        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if max_groups and len(result['groups']) >= max_groups:
                break
            t0 = time.monotonic()
            for record in records:
                link.exchange(4, record)
                time.sleep(record_gap)
            dt = time.monotonic() - t0
            result['groups'].append(round(dt, 4))
            if len(result['groups']) % 10 == 1:
                print(f'  group {len(result["groups"])}: {dt:.3f} s', flush=True)
            time.sleep(group_gap)

        link.exchange(3, b'\x00')
        result['after'] = link.status()
        if not idle(result['after']):
            raise RuntimeError('Pico did not return to idle input')
        result['passed'] = True
    finally:
        if link:
            try:
                link.exchange(3, b'\x00')
            except Exception as error:
                result['cleanup_error'] = str(error)
            finally:
                link.serial.close()
        dest = Path(__file__).parent / 'logs' / (
            f'inject-payload-{time.strftime("%Y%m%d-%H%M%S")}.json')
        dest.write_text(json.dumps(result, indent=2) + '\n')
        print('LOG:', dest, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--file', required=True)
    parser.add_argument('--duration', type=int, default=90)
    parser.add_argument('--record-gap', type=float, default=0.0144)
    parser.add_argument('--group-gap', type=float, default=0.05)
    parser.add_argument('--reset-delay', type=float, default=0.1)
    parser.add_argument('--groups', type=int, default=0,
                        help='stop after N groups (default: until --duration)')
    parser.add_argument('--no-reset', action='store_true',
                        help='cold-boot method: no reset pulse')
    args = parser.parse_args()

    payload_path = Path(args.file)
    data = payload_path.read_bytes()
    if not data:
        raise SystemExit('empty payload')
    if len(data) > 8192:
        print(f'WARNING: {len(data)} B exceeds the measured 8 KB direct limit')
    run(args.port, data, str(payload_path), args.duration, args.record_gap, args.group_gap,
        args.reset_delay, reset=not args.no_reset, max_groups=args.groups)
