#!/usr/bin/env python3
"""Experimental two-pass BootROM dump over the service terminal.

Method (proven on firmware 30110_05.2025031501):

1. upload the 460-byte ARM helper in helpers/bootrom-reader/ to /tmp_bt (tmpfs);
2. run it once per 4 KiB page; it opens /dev/mem read-only, maps
   0xffff0000 + index * 0x1000, and prints 4096 bytes as hex;
3. repeat all pages for a second pass and compare;
4. write the dump, manifest and SHA256SUMS on the host;
5. delete the helper from the camera.

The helper only supports page indices 0..5, i.e. the proven range
0xffff0000-0xffff5fff (24 KiB). Pages beyond that are unverified.

This writes a temporary helper to the camera's tmpfs and executes it. It does
not write eMMC, flash, configuration, or kernel modules. Because it executes
code on the camera, it requires --owner-authorized-exec.

The resulting dump is Sony firmware content. Keep it private and never commit
it to this repository.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from pathlib import Path

import zve10_common as common

BASE = 0xFFFF0000
PAGE = 0x1000
MAX_PAGES = 6
HELPER = common.ROOT / "helpers" / "bootrom-reader" / "read_page.elf"
CHUNK = 114


def hex_bytes(output: str) -> str:
    lines = []
    for line in re.split(r"[\r\n]+", output or ""):
        line = line.strip()
        if line and re.fullmatch(r"[0-9a-fA-F]+", line):
            lines.append(line)
    return "".join(lines)


def shell(dev, name: str, command: str, timeout: float = 30.0) -> dict:
    return common.command(dev, name, command, timeout)


def check_mounts(dev) -> None:
    result = shell(dev, "mounts", "busybox cat /proc/mounts", 20)
    if result["exit_code"] != 0:
        raise RuntimeError("cannot read /proc/mounts")
    if not re.search(r"/tmp_bt\s+tmpfs\b", result["output"]):
        raise RuntimeError("/tmp_bt is not tmpfs; refusing to write the helper")


def make_helper_dir(dev) -> str:
    result = shell(dev, "mktemp", "busybox mktemp -d /tmp_bt/br.XXXXXX", 20)
    if result["exit_code"] != 0:
        raise RuntimeError("mktemp failed")
    for line in result["output"].replace("\r", "").splitlines():
        line = line.strip()
        if line.startswith("/tmp_bt/br.") and not any(c in line for c in " '\"`$;&|"):
            return line
    raise RuntimeError("unexpected mktemp output: %r" % result["output"])


def upload(dev, helper_dir: str) -> dict:
    data = HELPER.read_bytes()
    expected = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode("ascii")
    target = helper_dir + "/read_page.b64"
    for index in range(0, len(encoded), CHUNK):
        chunk = encoded[index:index + CHUNK]
        command = "printf '%s' " + common.shquote(chunk) + " >> " + common.shquote(target)
        result = shell(dev, "upload%d" % (index // CHUNK), command, 20)
        if result["exit_code"] != 0:
            raise RuntimeError("helper upload failed at chunk %d" % (index // CHUNK))

    commands = (
        ("decode", "busybox base64 -d %s > %s" % (common.shquote(target),
                                                   common.shquote(helper_dir + "/read_page.elf"))),
        ("size", "busybox wc -c < " + common.shquote(helper_dir + "/read_page.elf")),
        ("hash", "busybox sha256sum " + common.shquote(helper_dir + "/read_page.elf")),
        ("chmod", "busybox chmod 755 " + common.shquote(helper_dir + "/read_page.elf")),
    )
    for name, command in commands:
        result = shell(dev, name, command, 20)
        if result["exit_code"] != 0 and name != "chmod":
            raise RuntimeError("%s failed: %r" % (name, result["output"]))
        if name == "size":
            match = re.search(r"(\d+)", result["output"])
            if not match or int(match.group(1)) != len(data):
                raise RuntimeError("uploaded helper size mismatch")
        if name == "hash":
            match = re.search(r"([0-9a-fA-F]{64})", result["output"])
            if not match or match.group(1).lower() != expected:
                raise RuntimeError("uploaded helper hash mismatch")
    return {"size": len(data), "sha256": expected}


def read_page(dev, helper_dir: str, index: int) -> bytes:
    command = "%s/read_page.elf %d" % (common.shquote(helper_dir), index)
    result = shell(dev, "page%d" % index, command, 40)
    if result["exit_code"] != 0:
        raise RuntimeError("page %d failed with exit %s" % (index, result["exit_code"]))
    digits = hex_bytes(result["output"])
    if len(digits) != PAGE * 2:
        raise RuntimeError("page %d returned %d hex chars, expected %d"
                           % (index, len(digits), PAGE * 2))
    return bytes.fromhex(digits)


def cleanup(dev, helper_dir: str) -> bool:
    command = "busybox rm -f %s %s" % (
        common.shquote(helper_dir + "/read_page.b64"),
        common.shquote(helper_dir + "/read_page.elf"),
    )
    shell(dev, "cleanup_files", command, 20)
    shell(dev, "cleanup_dir", "busybox rmdir " + common.shquote(helper_dir), 20)
    result = shell(dev, "cleanup_check", "busybox ls -ld " + common.shquote(helper_dir), 20)
    return result["exit_code"] != 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", help="output directory (default: ./backups/...)")
    parser.add_argument("--pages", type=int, default=MAX_PAGES,
                        help="number of 4 KiB pages, 1..%d (default: %d)"
                             % (MAX_PAGES, MAX_PAGES))
    parser.add_argument("--passes", type=int, default=2, choices=(1, 2),
                        help="1 for a quick read, 2 for the verified two-pass method")
    parser.add_argument("--keep-helper", action="store_true",
                        help="do not delete the helper from /tmp_bt (debugging)")
    parser.add_argument("--owner-authorized-exec", action="store_true",
                        help="required: confirms you understand this executes code on the camera")
    parser.add_argument("--driver", default="libusb")
    args = parser.parse_args()

    if not args.owner_authorized_exec:
        raise SystemExit("refusing to execute: pass --owner-authorized-exec")
    if not 1 <= args.pages <= MAX_PAGES:
        raise SystemExit("--pages must be 1..%d; the helper supports 0..5 only" % MAX_PAGES)
    if not HELPER.is_file():
        raise SystemExit("helper not found: %s" % HELPER)

    out = Path(args.out).resolve() if args.out else common.default_out("zve10-bootrom-")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    (out / "pages").mkdir()
    print("OUTPUT:", out, flush=True)

    result = {
        "scope": "two-pass 4 KiB-page BootROM read via /dev/mem read-only mmap",
        "firmware": common.EXPECTED_VERSION.decode("ascii"),
        "base": hex(BASE),
        "page_size": PAGE,
        "pages": args.pages,
        "passes": args.passes,
        "helper": {"file": str(HELPER.relative_to(common.ROOT)),
                   "size": HELPER.stat().st_size,
                   "sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest()},
        "helper_tmpfs": "/tmp_bt",
        "camera_side_writes": "temporary helper in /tmp_bt (tmpfs); no eMMC/flash/config writes",
        "pass_data": [],
        "two_pass_match": None,
        "completed": False,
    }

    def callback(camera):
        camera.readHasp()
        common.check_version(camera)
        helper_dir = None
        attempted = False
        try:
            attempted = True
            camera.setTerminalEnable(True)
            common.drain(camera.dev, 1.0)
            check_mounts(camera.dev)
            helper_dir = make_helper_dir(camera.dev)
            result["helper_dir"] = helper_dir
            result["helper_upload"] = upload(camera.dev, helper_dir)

            passes = []
            for pass_number in range(1, args.passes + 1):
                segments = []
                for index in range(args.pages):
                    print("pass %d page %d/%d" % (pass_number, index + 1, args.pages),
                          flush=True)
                    data = read_page(camera.dev, helper_dir, index)
                    segment = out / "pages" / ("pass%d_seg%d.bin" % (pass_number, index))
                    segment.write_bytes(data)
                    segments.append(data)
                    result["pass_data"].append({
                        "pass": pass_number,
                        "index": index,
                        "address": hex(BASE + index * PAGE),
                        "file": str(segment.relative_to(out)),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    })
                passes.append(b"".join(segments))

            dump = passes[0]
            if args.passes == 2:
                result["two_pass_match"] = passes[0] == passes[1]
                if not result["two_pass_match"]:
                    raise RuntimeError("two passes differ")
            (out / "dump.bin").write_bytes(dump)
            result["dump_size"] = len(dump)
            result["dump_sha256"] = hashlib.sha256(dump).hexdigest()
            (out / "SHA256SUMS").write_text(
                "%s  dump.bin\n" % result["dump_sha256"], encoding="utf-8"
            )
            result["completed"] = True
        finally:
            if helper_dir and not args.keep_helper:
                try:
                    result["helper_removed"] = cleanup(camera.dev, helper_dir)
                except Exception as exc:  # noqa: BLE001
                    result["helper_removed"] = "error: %r" % (exc,)
            if attempted:
                camera.setTerminalEnable(False)
                result["terminal_closed"] = True

    try:
        common.connect(callback, args.driver)
    except Exception as exc:  # noqa: BLE001 - recorded in the manifest
        result["error"] = repr(exc)
        raise
    finally:
        if not result.get("completed"):
            result.setdefault("error", "callback did not complete")
        (out / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        common.restore_tree_owner(out)
        print("DUMP:", out / "dump.bin", flush=True)
        print("MANIFEST:", out / "manifest.json", flush=True)


if __name__ == "__main__":
    main()
