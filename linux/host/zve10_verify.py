#!/usr/bin/env python3
"""Offline verification for backups produced by this toolkit.

Subcommands
-----------
manifest
    Re-read every saved image, compare size, whole-file SHA-256, host re-read
    hash, and (optionally) the per-MiB chunk hashes recorded in manifest.json.

sums
    Verify a SHA256SUMS file against the files next to it.

slices
    Compare two raw reads partition by partition using a layout file, and
    report differing bytes and 512-byte sectors.  Differences are data, not a
    tool failure; use --fail-on-difference to make them exit non-zero.

No camera connection is needed.  Nothing here writes to a backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BLOCK = 4 * 1024 * 1024
SECTOR = 512


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(BLOCK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def chunk_hashes(path: Path, size: int = 1048576) -> list[str]:
    result = []
    with path.open("rb") as handle:
        while True:
            data = handle.read(size)
            if not data:
                break
            result.append(hashlib.sha256(data).hexdigest())
    return result


def verify_manifest(path: Path, check_chunks: bool = True) -> bool:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent
    ok = True
    reads = manifest.get("reads") or []
    if not reads:
        print("FAIL no reads in manifest")
        return False
    if not manifest.get("completed"):
        print("WARN manifest is not marked completed")
    for row in reads:
        name = row.get("file") or "<missing>"
        target = base / name
        problems = []
        if not target.is_file():
            problems.append("missing file")
        else:
            size = target.stat().st_size
            if "expected_bytes" in row and size != row["expected_bytes"]:
                problems.append("size %d != expected %d" % (size, row["expected_bytes"]))
            if "bytes" in row and size != row["bytes"]:
                problems.append("size %d != recorded %d" % (size, row["bytes"]))
            digest = sha256_file(target)
            if row.get("sha256") and digest != row["sha256"]:
                problems.append("sha256 mismatch")
            if row.get("host_reread_sha256") and digest != row["host_reread_sha256"]:
                problems.append("host re-read hash mismatch")
            if check_chunks and row.get("chunk_sha256_1MiB"):
                actual = chunk_hashes(target)
                if actual != row["chunk_sha256_1MiB"]:
                    problems.append("per-MiB chunk hashes differ")
        if problems:
            ok = False
            print("FAIL %s: %s" % (name, "; ".join(problems)))
        else:
            print("OK   %s" % name)
    return ok


def verify_sums(path: Path) -> bool:
    base = path.resolve().parent
    ok = True
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if not match:
            ok = False
            print("FAIL line %d: unparsable" % number)
            continue
        expected, name = match.group(1).lower(), match.group(2)
        target = base / name
        if not target.is_file():
            ok = False
            print("FAIL %s: missing" % name)
            continue
        actual = sha256_file(target)
        if actual != expected:
            ok = False
            print("FAIL %s: sha256 mismatch" % name)
        else:
            print("OK   %s" % name)
    return ok


def parse_layout(path: Path) -> list[dict]:
    partitions = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            raise SystemExit("layout line %d: expected 'name offset size'" % number)
        name, offset, size = parts
        partitions.append({"name": name, "offset": int(offset, 0), "bytes": int(size, 0)})
    return partitions


def hash_range(handle, offset: int, size: int) -> str:
    digest = hashlib.sha256()
    handle.seek(offset)
    remaining = size
    while remaining:
        data = handle.read(min(BLOCK, remaining))
        if not data:
            raise RuntimeError("unexpected end of file at %d" % offset)
        digest.update(data)
        remaining -= len(data)
    return digest.hexdigest()


def diff_range(handle_a, handle_b, offset: int, size: int) -> tuple[int, list[dict]]:
    """Return (differing byte count, differing sector records) for a range."""
    total = 0
    sectors = []
    handle_a.seek(offset)
    handle_b.seek(offset)
    position = 0
    while position < size:
        length = min(BLOCK, size - position)
        a = handle_a.read(length)
        b = handle_b.read(length)
        if len(a) != length or len(b) != length:
            raise RuntimeError("unexpected end of file at %d" % (offset + position))
        if a != b:
            for start in range(0, length, SECTOR):
                chunk_a = a[start:start + SECTOR]
                chunk_b = b[start:start + SECTOR]
                if chunk_a == chunk_b:
                    continue
                count = sum(x != y for x, y in zip(chunk_a, chunk_b))
                count += abs(len(chunk_a) - len(chunk_b))
                total += count
                absolute = offset + position + start
                sectors.append({"offset": absolute, "sector": absolute // SECTOR,
                                "different_bytes": count})
        position += length
    return total, sectors


def verify_slices(read1: Path, read2: Path, layout: Path, json_out: Path | None,
                  fail_on_difference: bool) -> bool:
    partitions = parse_layout(layout)
    with read1.open("rb") as a, read2.open("rb") as b:
        size = read1.stat().st_size
        if read2.stat().st_size != size:
            raise SystemExit("read1 and read2 differ in file size")
        for partition in partitions:
            end = partition["offset"] + partition["bytes"]
            if end > size:
                raise SystemExit(
                    "layout entry %s exceeds file size" % partition["name"]
                )
        result = {"read1": str(read1), "read2": str(read2), "layout": str(layout),
                  "partitions": [], "different_bytes": 0, "different_sectors": []}
        for partition in partitions:
            first = hash_range(a, partition["offset"], partition["bytes"])
            second = hash_range(b, partition["offset"], partition["bytes"])
            identical = first == second
            result["partitions"].append({
                "name": partition["name"],
                "offset": partition["offset"],
                "bytes": partition["bytes"],
                "read1_sha256": first,
                "read2_sha256": second,
                "identical": identical,
            })
            print("%s %s" % ("OK  " if identical else "DIFF", partition["name"]))
            if not identical:
                count, sectors = diff_range(a, b, partition["offset"], partition["bytes"])
                result["different_bytes"] += count
                for sector in sectors:
                    sector["partitions"] = [partition["name"]]
                result["different_sectors"].extend(sectors)

    if json_out:
        json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print("JSON:", json_out)
    differing = sum(1 for item in result["partitions"] if not item["identical"])
    print("partitions compared: %d; differing: %d; differing bytes: %d"
          % (len(result["partitions"]), differing, result["different_bytes"]))
    if fail_on_difference and differing:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest", help="verify manifest.json and saved images")
    manifest.add_argument("--manifest", required=True, type=Path)
    manifest.add_argument("--no-chunks", action="store_true",
                          help="skip per-MiB chunk verification")

    sums = sub.add_parser("sums", help="verify a SHA256SUMS file")
    sums.add_argument("--sums", required=True, type=Path)

    slices = sub.add_parser("slices", help="compare two raw reads by partition")
    slices.add_argument("--read1", required=True, type=Path)
    slices.add_argument("--read2", required=True, type=Path)
    slices.add_argument("--layout", required=True, type=Path,
                        help="lines: name offset size (offset/size may be decimal or 0x hex)")
    slices.add_argument("--json", type=Path, help="write detailed JSON here")
    slices.add_argument("--fail-on-difference", action="store_true")

    args = parser.parse_args()
    if args.command == "manifest":
        ok = verify_manifest(args.manifest, check_chunks=not args.no_chunks)
    elif args.command == "sums":
        ok = verify_sums(args.sums)
    else:
        ok = verify_slices(args.read1, args.read2, args.layout, args.json,
                           args.fail_on_difference)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
