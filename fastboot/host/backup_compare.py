#!/usr/bin/env python3
"""Read-only comparison: fastboot fetch vs the 2026-10-22 raw backup.

Loads the published stage2, fetches the selected partitions,
and compares each SHA-256 with both reads recorded in the backup's
`offline-verification.json`.

    python host/backup_compare.py \
      --backup-dir /path/to/backup

This script issues no flash command; stage2 itself permits writes. Partition images are not saved unless
--save is given.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bootstrap as bs  # noqa: E402


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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--backup-dir', type=Path, required=True)
    ap.add_argument('--partitions', default='nflasha7,nflasha3,nflasha15')
    ap.add_argument('--file', type=Path,
                    default=HERE.parent / 'prebuilt/stage2-flash.bin')
    ap.add_argument('--save', action='store_true',
                    help='save fetched partition images under /tmp')
    args = ap.parse_args()

    rows = {p['name']: p for p in
            json.loads((args.backup_dir / 'offline-verification.json').read_text())['partitions']}
    wanted = [n.strip() for n in args.partitions.split(',') if n.strip()]
    missing = [n for n in wanted if n not in rows]
    if missing:
        raise SystemExit(f'not in the backup: {missing}')

    expected = bs.verify()
    blob = args.file.read_bytes()
    identity = bs.verify_stage2(blob, args.file.with_suffix('.elf'), allow_writer=True)
    dev = bs.Device(bs.wait_for_device(60))
    results = []
    try:
        bs.handoff(dev, blob, expected, identity, allow_writer=True)
        print(f'handoff ok, identity {identity}', flush=True)
        for name in wanted:
            row = rows[name]
            t = time.monotonic()
            data = fetch(dev, name, row['bytes'])
            elapsed = time.monotonic() - t
            sha = hashlib.sha256(data).hexdigest()
            ok1 = sha == row.get('read1_sha256')
            ok2 = sha == row.get('read2_sha256')
            results.append((name, ok1 and ok2))
            print(f'[{"PASS" if ok1 and ok2 else "DIFF"}] {name}: '
                  f'{len(data)} B {elapsed:.1f}s sha {sha[:16]} '
                  f'read1={"same" if ok1 else "diff"} read2={"same" if ok2 else "diff"}',
                  flush=True)
            if args.save:
                out = Path('/tmp') / f'fastboot-{name}.bin'
                out.write_bytes(data)
                print(f'  saved {out}', flush=True)
    finally:
        dev.close()

    failed = [n for n, ok in results if not ok]
    print('\nSUMMARY:', 'ALL SAME' if not failed else f'{len(failed)} DIFFER', flush=True)
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
