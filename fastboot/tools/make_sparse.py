#!/usr/bin/env python3
"""Build a libsparse image from a raw file or a repeating pattern.

Sparse is how `fastboot` gets more than max-download-size to a device with a
small staging buffer: the host splits an oversized sparse file into several
download/flash pairs, and each split after the first opens with a DONT_CARE
chunk covering the bytes already written, which tells the device the offset.

    python tools/make_sparse.py --pattern 4M --output /tmp/test.simg
    python tools/make_sparse.py --raw nflasha10.img --output /tmp/p.simg

The chunk layout here mirrors libsparse: 28-byte file header, 12-byte chunk
headers, 4096-byte sparse blocks, little-endian throughout.
"""
import argparse
import struct
import sys

MAGIC = 0xED26FF3A
BLK = 4096
CHUNK_RAW = 0xCAC1
CHUNK_FILL = 0xCAC2
CHUNK_SKIP = 0xCAC3


def build(data, blk=BLK):
    if len(data) % blk:
        raise ValueError('raw data must be a multiple of the sparse block size')
    blocks = len(data) // blk
    hdr = struct.pack('<IHHHHIIII', MAGIC, 1, 0, 28, 12, blk, blocks, 1, 0)
    chunk = struct.pack('<HHII', CHUNK_RAW, 0, blocks, 12 + len(data))
    return hdr + chunk + data


def parse_size(text):
    text = text.strip().upper()
    mult = 1
    if text.endswith('M'):
        mult, text = 1024 * 1024, text[:-1]
    elif text.endswith('K'):
        mult, text = 1024, text[:-1]
    return int(text, 0) * mult


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--raw', help='raw image to wrap')
    src.add_argument('--pattern', help='size, e.g. 4M; filled with a 32-bit ramp')
    ap.add_argument('--output', required=True)
    args = ap.parse_args()

    if args.raw:
        data = open(args.raw, 'rb').read()
    else:
        size = parse_size(args.pattern)
        if size % BLK:
            sys.exit(f'size must be a multiple of {BLK}')
        data = b''.join(struct.pack('<I', (i // 4) & 0xFFFFFFFF)
                        for i in range(0, size, 4))

    image = build(data)
    with open(args.output, 'wb') as handle:
        handle.write(image)
    # A split only happens above max-download-size, so report both numbers.
    print(f'{args.output}: raw {len(data)} B, sparse {len(image)} B, '
          f'{"needs splitting" if len(image) > 0x100000 else "single transfer"}')


if __name__ == '__main__':
    main()
