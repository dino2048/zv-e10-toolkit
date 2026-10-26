#!/usr/bin/env python3
"""Two-pass raw backup of the eMMC areas exposed by the ZV-E10 kernel.

Read-only by design.  The only data path is FileControl READ (pFunc 0xff01),
which takes a path and streams the bytes back over USB.  No camera writes,
uploads, mount changes, or module operations are performed.

Scope: ``/dev/nflasha`` (the whole Linux-visible user area) and the two boot
areas ``/dev/nflashaB0`` and ``/dev/nflashaB1``.  Each region is read twice.
This is a raw block-byte image of what the driver exposes; it is not a
physical chip dump and does not include RPMB, OTP/eFuse, or hidden areas.

Usage:
    host/zve10_backup_raw.py --out /path/to/backup

The camera must be in USB mass-storage mode.  On macOS use
scripts/run_raw_backup.sh so the process receives raw USB access through one
administrator popup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import zve10_common as common

REGIONS = {
    "nflasha": 1954545664,
    "nflashaB0": 4194304,
    "nflashaB1": 4194304,
}
OUT = None
RESULT = {
    "scope": (
        "Two reads of the Linux-exposed user area and B0/B1; host files only; "
        "no camera writes/uploads/mounts"
    ),
    "reads": [],
    "metadata": [],
    "completed": False,
}


def save() -> None:
    (OUT / "manifest.json").write_text(
        json.dumps(RESULT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class Sink:
    """Streaming receiver: file writes, whole-file hash, per-MiB hashes."""

    def __init__(self, file, expected: int):
        self.file = file
        self.expected = expected
        self.size = 0
        self.sha = hashlib.sha256()
        self.pending = bytearray()
        self.chunks = []
        self.last_report = time.monotonic()
        self.started = self.last_report

    def write(self, data: bytes) -> None:
        if self.size + len(data) > self.expected:
            raise RuntimeError("response exceeds expected region capacity")
        self.file.write(data)
        self.sha.update(data)
        self.size += len(data)
        self.pending.extend(data)
        while len(self.pending) >= 1048576:
            self.chunks.append(hashlib.sha256(self.pending[:1048576]).hexdigest())
            del self.pending[:1048576]
        now = time.monotonic()
        if now - self.last_report >= 10:
            print(
                "PROGRESS %s %d/%d bytes %.1f MiB/s"
                % (
                    self.file.name,
                    self.size,
                    self.expected,
                    self.size / 1048576 / (now - self.started),
                ),
                flush=True,
            )
            self.last_report = now


def receive(camera, device: str, iteration: int) -> dict:
    size = REGIONS[device]
    path = "/dev/" + device
    dest = OUT / ("%s.read%d.bin" % (device, iteration))
    partial = dest.with_suffix(".bin.part")
    row = {
        "device": path,
        "iteration": iteration,
        "expected_bytes": size,
        "file": dest.name,
        "complete": False,
    }
    RESULT["reads"].append(row)
    save()
    started = time.monotonic()
    with partial.open("xb") as handle:
        os.chmod(partial, 0o600)
        sink = Sink(handle, size)
        try:
            response, _ = common.read_path(camera, path, sink)
            row["response"] = response
            if response not in (0, 1) or sink.size != size:
                raise RuntimeError("read failed or length mismatch: " + device)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            row.update(
                bytes=sink.size,
                sha256=sink.sha.hexdigest(),
                seconds=time.monotonic() - started,
            )
            if sink.pending:
                sink.chunks.append(hashlib.sha256(sink.pending).hexdigest())
            row["chunk_sha256_1MiB"] = sink.chunks
            save()
    partial.rename(dest)

    # Independently re-read from the host disk rather than trusting the
    # receive-time hash alone.
    digest = hashlib.sha256()
    with dest.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1048576), b""):
            digest.update(chunk)
    row["host_reread_sha256"] = digest.hexdigest()
    if row["host_reread_sha256"] != row["sha256"]:
        raise RuntimeError("host saved file hash mismatch")
    row["complete"] = True
    save()
    print(
        "READ_COMPLETE "
        + json.dumps({k: v for k, v in row.items() if k != "chunk_sha256_1MiB"}),
        flush=True,
    )
    return row


def probe(camera, expected: bytes) -> None:
    common.set_terminal_timeout(camera)
    common.check_version(camera, expected)

    enabled = False
    try:
        enabled = True
        camera.setTerminalEnable(True)
        common.drain(camera.dev, 0.5)
        for name, cmd in (
            ("partitions", "busybox cat /proc/partitions"),
            ("mounts", "busybox cat /proc/mounts"),
            (
                "layout",
                'for p in /sys/class/block/nflasha*; do echo DEVICE:$p; '
                'for f in dev size start ro; do echo FIELD:$f; '
                'busybox cat "$p/$f" 2>/dev/null; done; done',
            ),
        ):
            RESULT["metadata"].append(common.command(camera.dev, name, cmd, 30))
            save()
    finally:
        if enabled:
            camera.setTerminalEnable(False)
            RESULT["terminal_closed"] = True
            save()

    # Refuse to continue if the live capacities differ from the fixed scope.
    sizes = {
        match[3]: int(match[2]) * 1024
        for match in re.findall(
            r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s*$",
            RESULT["metadata"][0]["output"],
            re.M,
        )
    }
    for device, size in REGIONS.items():
        if sizes.get(device) != size:
            raise RuntimeError("live capacity changed for " + device)

    for device in REGIONS:
        first = receive(camera, device, 1)
        second = receive(camera, device, 2)
        RESULT.setdefault("comparisons", {})[device] = {
            "identical": first["sha256"] == second["sha256"],
            "differing_1MiB_chunks": [
                index
                for index, (a, b) in enumerate(
                    zip(first["chunk_sha256_1MiB"], second["chunk_sha256_1MiB"])
                )
                if a != b
            ],
        }
        save()
    RESULT["completed"] = True
    save()


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="output directory (default: ./backups/...)")
    parser.add_argument("--driver", default="libusb")
    parser.add_argument(
        "--expect-version",
        default=common.EXPECTED_VERSION.decode("ascii"),
        help="expected /version.txt baseline",
    )
    args = parser.parse_args()

    OUT = Path(args.out).resolve() if args.out else common.default_out("zve10-raw-emmc-")
    probe_dir = OUT.parent if OUT.parent.exists() else Path.cwd()
    needed = 2 * sum(REGIONS.values()) + 1024 ** 3
    free = shutil.disk_usage(probe_dir).free
    if free < needed:
        raise SystemExit(
            "need %.1f GiB free, found %.1f GiB"
            % (needed / 1024 ** 3, free / 1024 ** 3)
        )
    OUT.mkdir(parents=True, exist_ok=False, mode=0o700)
    print("OUTPUT: " + str(OUT), flush=True)

    try:
        common.connect(lambda camera: probe(camera, args.expect_version.encode()), args.driver)
        RESULT["service_returned"] = True
        if not RESULT["completed"]:
            raise RuntimeError("camera callback did not complete")
    except Exception as exc:  # noqa: BLE001 - recorded in the manifest
        RESULT["error"] = repr(exc)
        raise
    finally:
        save()
        common.restore_tree_owner(OUT)


if __name__ == "__main__":
    main()
