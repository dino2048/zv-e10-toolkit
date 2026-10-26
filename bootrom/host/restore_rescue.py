#!/usr/bin/env python3
"""Restore partitions from the raw eMMC backup through fastboot.

The backup directory must contain `offline-verification.json` and the
user-area image (`nflasha.read1.bin` by default). Partitions are sliced at the
recorded offsets, wrapped as sparse images, and (unless --prepare-only)
flashed through stage2-flash with a readback check against the slice.

    # offline: slice + sparse + SHA check, no camera
    python host/restore_rescue.py --backup-dir /path/to/backup \
        --partitions nflasha10 --prepare-only --out-dir /tmp/rescue-prep

    # hardware: restore selected partitions (batch them within the 4 min window)
    python host/restore_rescue.py --backup-dir ... --partitions nflasha3,nflasha7

Only the named partitions are written; boot0/boot1 and the partition table are
deliberately not handled here.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import bootstrap as bs  # noqa: E402

FASTBOOT = 'fastboot'
USER_PARTITIONS = {f'nflasha{i}' for i in (1,2,3,4,5,6,7,10,11,12,13,15,16,17,18,23)}
MAKE_SPARSE = ROOT / 'tools' / 'make_sparse.py'


def cli(*args, timeout=300):
    proc = subprocess.run([FASTBOOT, *map(str, args)],
                          capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip().replace('\n', ' | ')


def make_sparse(raw: Path, simg: Path):
    proc = subprocess.run([sys.executable, str(MAKE_SPARSE),
                           '--raw', str(raw), '--output', str(simg)],
                          capture_output=True, text=True)
    if proc.returncode:
        raise ValueError(proc.stderr.strip()[:300])


def read_exact(dev, size):
    data = bytearray()
    while len(data) < size:
        chunk = bytes(dev.ep_in.read(min(0x8000, size - len(data)), timeout=15000))
        if not chunk:
            raise ValueError(f'short DATA: {len(data)}/{size}')
        data.extend(chunk)
    return bytes(data)


def fetch(dev, name, size):
    dev.write(f'fetch:{name}:0x00000000:{size:#010x}'.encode('ascii'))
    tag, body, _ = dev.read_reply()
    if tag != b'DATA':
        raise ValueError(f'fetch {name}: {tag!r} {body!r}')
    announced = int(body, 16)
    if announced != size:
        raise ValueError(f'fetch {name}: announced {announced}, asked {size}')
    data = read_exact(dev, announced)
    tag, body, _ = dev.read_reply()
    if tag != b'OKAY':
        raise ValueError(f'fetch {name}: tail {tag!r} {body!r}')
    return data


def with_device(seconds, action):
    dev = bs.Device(bs.wait_for_device(seconds))
    try:
        return action(dev)
    finally:
        dev.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--backup-dir', type=Path, required=True)
    ap.add_argument('--image', default='nflasha.read1.bin')
    ap.add_argument('--verification', default='offline-verification.json')
    ap.add_argument('--partitions', required=True,
                    help='comma-separated names, e.g. nflasha3,nflasha7')
    ap.add_argument('--out-dir', type=Path,
                    default=Path('/tmp') / time.strftime('zve10-rescue-%Y%m%d-%H%M%S'))
    ap.add_argument('--prepare-only', action='store_true')
    ap.add_argument('--max-seconds', type=float, default=150,
                    help='stop starting new partitions after this many seconds')
    ap.add_argument('--file', type=Path,
                    default=HERE.parent / 'prebuilt/stage2-flash.bin')
    ap.add_argument('--fastboot', default='fastboot', help='fastboot executable name or path')
    args = ap.parse_args()
    if args.max_seconds <= 0:
        ap.error('--max-seconds must be positive')
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = {p['name']: p for p in
            json.loads((args.backup_dir / args.verification).read_text())['partitions']}
    image_path = args.backup_dir / args.image
    wanted = [n.strip() for n in args.partitions.split(',') if n.strip()]
    if not wanted or len(wanted) != len(set(wanted)):
        ap.error('choose at least one partition, without duplicates')
    if set(wanted) - USER_PARTITIONS:
        ap.error('only the 16 supported user partitions may be restored')
    image_size = image_path.stat().st_size
    ranges = []
    for name in wanted:
        row = rows.get(name, {})
        offset, size = row.get('offset'), row.get('bytes')
        if (type(offset) is not int or type(size) is not int or offset < 0 or
                offset % 512 or size <= 0 or size % 4096 or offset + size > image_size):
            ap.error('invalid or out-of-bounds partition: ' + name)
        if not re.fullmatch(r'[0-9a-fA-F]{64}', row.get('read1_sha256', '')):
            ap.error('missing partition SHA-256: ' + name)
        ranges.append((offset, offset + size))
    ranges.sort()
    if any(end > next_start for (_, end), (next_start, _) in zip(ranges, ranges[1:])):
        ap.error('partition ranges overlap')
    unknown = [n for n in wanted if n not in rows]
    if unknown:
        raise SystemExit(f'not in the backup: {unknown}')

    results = []

    def record(name, ok, detail=''):
        results.append((name, ok))
        print(f'[{"PASS" if ok else "FAIL"}] {name}' + (f': {detail}' if detail else ''),
              flush=True)

    slices = {}
    with image_path.open('rb') as image:
        for name in wanted:
            row = rows[name]
            image.seek(row['offset'])
            data = image.read(row['bytes'])
            raw = args.out_dir / f'{name}.bin'
            simg = args.out_dir / f'{name}.simg'
            raw.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            expect = row['read1_sha256'].lower()
            record(f'slice {name}', sha == expect,
                   f'{len(data)} B {sha[:16]}')
            make_sparse(raw, simg)
            slices[name] = data
    failed = [n for n, ok in results if not ok]
    if failed:
        print('PREPARE: FAIL; no device access or flashing attempted', flush=True)
        return 1
    if args.prepare_only:
        print('\nPREPARE:', 'PASS' if not failed else 'FAIL', flush=True)
        return 0 if not failed else 1

    global FASTBOOT
    FASTBOOT = shutil.which(args.fastboot)
    if not FASTBOOT:
        ap.error('fastboot executable not found; install platform-tools or use --fastboot')
    expected = bs.verify()
    blob = args.file.read_bytes()
    identity = bs.verify_stage2(blob, args.file.with_suffix('.elf'), allow_writer=True)
    dev = bs.Device(bs.wait_for_device(60))
    try:
        bs.handoff(dev, blob, expected, identity, allow_writer=True)
    finally:
        dev.close()
    record('handoff', True, identity)

    start = time.monotonic()
    for name in wanted:
        if time.monotonic() - start > args.max_seconds:
            record(f'{name}', False, 'skipped: max-seconds reached; reinject and continue')
            continue
        code, out = cli('flash', name, args.out_dir / f'{name}.simg')
        record(f'flash {name}', code == 0, out[:240])
        if code != 0:
            continue
        back = with_device(30, lambda d: fetch(d, name, rows[name]['bytes']))
        ok = back == slices[name]
        record(f'verify {name}', ok, hashlib.sha256(back).hexdigest()[:16])

    failed = [n for n, ok in results if not ok]
    print('\nSUMMARY:', 'PASS' if not failed else 'FAIL', flush=True)
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
