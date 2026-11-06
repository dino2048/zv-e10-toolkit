#!/usr/bin/env python3
"""Read-only, file-level backup of the ZV-E10 over the service terminal.

This is a companion to ``zve10_backup_raw.py``.  It copies ordinary files from
selected mount points; it never touches block devices.  Data is moved with
``busybox dd ... | busybox base64`` in 32 KiB chunks, and every file is checked
against the camera-side size and SHA-256 before it is kept.

Default mode is ``critical`` (settings, certificates, lens data, /etc, and
/version.txt).  Larger modes are best effort: the service terminal has a
128 KiB output cap per command, so very large trees take a long time.

The camera must be in USB mass-storage mode.  On macOS use
scripts/run_file_backup.sh.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import posixpath
import re
import time
from pathlib import Path

import zve10_common as common

MODES = {
    "inventory": (),
    "critical": ("/setting", "/cert", "/lens", "/etc"),
    "system": ("/setting", "/cert", "/lens", "/etc", "/system", "/bin", "/sbin", "/lib"),
    "usr": (
        "/setting", "/cert", "/lens", "/etc", "/system", "/bin", "/sbin", "/lib", "/usr",
    ),
    "log": (
        "/setting", "/cert", "/lens", "/etc", "/system", "/bin", "/sbin", "/lib",
        "/usr", "/log",
    ),
}
INVENTORY_ROOTS = (
    "/setting", "/cert", "/lens", "/etc", "/system", "/bin", "/sbin", "/lib",
    "/usr", "/tmp", "/log",
)
CHUNK = 32768
COMMAND_TIMEOUT = 120


def run(dev, label: str, text: str, timeout: float = COMMAND_TIMEOUT) -> dict:
    result = common.command(dev, label, text, timeout)
    if result["exit_code"] != 0 and not result["output"].strip():
        # Some busybox applets return non-zero after producing useful output;
        # an empty body is the reliable failure signal here.
        raise RuntimeError("%s failed with exit %s" % (label, result["exit_code"]))
    return result


def camera_size(dev, path: str) -> int:
    result = run(dev, "size", "busybox wc -c < %s" % common.shquote(path))
    match = re.search(r"(\d+)", result["output"])
    if not match:
        raise RuntimeError("cannot parse size for " + path)
    return int(match.group(1))


def camera_sha256(dev, path: str) -> str:
    result = run(dev, "sha256", "busybox sha256sum %s" % common.shquote(path))
    match = re.search(r"^([0-9a-fA-F]{64})", result["output"])
    if not match:
        raise RuntimeError("cannot parse sha256 for " + path)
    return match.group(1).lower()


def safe_destination(root: Path, camera_path: str) -> Path:
    parts = [part for part in camera_path.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise RuntimeError("refusing unsafe camera path: " + camera_path)
    return root.joinpath(*parts)


def transfer(dev, camera_path: str, size: int, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with destination.open("xb") as handle:
        os.chmod(destination, 0o600)
        offset = 0
        while offset < size:
            length = min(CHUNK, size - offset)
            command = (
                "busybox dd if=%s bs=%d skip=%d count=1 2>/dev/null | busybox base64"
                % (common.shquote(camera_path), CHUNK, offset // CHUNK)
            )
            result = run(dev, "read", command)
            try:
                data = base64.b64decode(result["output"], validate=False)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("base64 decode failed for %s: %r" % (camera_path, exc))
            if len(data) != length:
                raise RuntimeError(
                    "short read for %s at %d: %d != %d"
                    % (camera_path, offset, len(data), length)
                )
            handle.write(data)
            digest.update(data)
            offset += length
        handle.flush()
        os.fsync(handle.fileno())
    return digest.hexdigest()


# Only camera-shell builtins: this firmware has no find or stat applet.
# NUL-separated records preserve spaces and distinguish files/directories.
DIRECTORY_LOOP = (
    '[ ! -L "$d" ]&&[ -d "$d" ]&&[ -r "$d" ]&&[ -x "$d" ]&&{ '
    'for p in "$d"/* "$d"/.[!.]* "$d"/..?*;do '
    '[ -L "$p" ]||{ [ -f "$p" ]&&printf \'F%s\\0\' "$p";'
    '[ -d "$p" ]&&printf \'D%s\\0\' "$p";};done;true;}'
)


def mount_devices(dev) -> dict[str, str]:
    result = common.command(dev, "inventory_mounts",
                            "busybox cat /proc/self/mountinfo", COMMAND_TIMEOUT)
    if result["exit_code"] != 0:
        raise RuntimeError("cannot read mountinfo: " + result["output"].strip())
    mounts = {}
    for line in result["output"].splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 10 or "-" not in fields or not re.fullmatch(r"\d+:\d+", fields[2]):
            raise RuntimeError("invalid mountinfo record")
        mountpoint = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4])
        mounts[mountpoint] = fields[2]
    if "/" not in mounts:
        raise RuntimeError("mountinfo has no root filesystem")
    return mounts


def device_for(path: str, mounts: dict[str, str]) -> str:
    matches = [mount for mount in mounts
               if mount == "/" or path == mount or path.startswith(mount.rstrip("/") + "/")]
    return mounts[max(matches, key=len)]


def directory_entries(dev, directory: str) -> list[tuple[str, str]]:
    # Keep terminal requests short. This tool owns one connection and executes
    # the path assignment and listing sequentially.
    assigned = common.command(dev, "inventory_path", "d=" + common.shquote(directory), COMMAND_TIMEOUT)
    if assigned["exit_code"] != 0:
        raise RuntimeError("cannot select directory: " + assigned["output"].strip())
    result = common.command(dev, "inventory", DIRECTORY_LOOP, COMMAND_TIMEOUT)
    if result["exit_code"] != 0:
        raise RuntimeError("directory missing, not readable/searchable, or a symlink: "
                           + directory + ": " + result["output"].strip())
    body = result["output"].rstrip("\r\n")
    if not body:
        return []
    if not body.endswith("\0"):
        raise RuntimeError("incomplete directory listing: " + directory)
    entries = []
    for record in body[:-1].split("\0"):
        kind, path = record[:1], record[1:]
        if directory == "/" and path.startswith("//"):
            path = path[1:]  # shell glob "$d"/* prefixes root entries with //
        # Terminal commands use ASCII; reject unsupported names explicitly.
        if (kind not in ("F", "D") or not path.isascii() or "\r" in path
                or "\n" in path or posixpath.dirname(path) != directory
                or posixpath.basename(path) in ("", ".", "..")):
            raise RuntimeError("invalid/unsupported directory entry under " + directory)
        entries.append((kind, path))
    return entries


def inventory(dev, roots) -> tuple[list[str], list[dict]]:
    files: list[str] = []
    errors: list[dict] = []
    seen = set()
    try:
        mounts = mount_devices(dev)
    except Exception as exc:
        return files, [{"root": "/proc/self/mountinfo", "error": str(exc)}]
    for root in roots:
        if root == "/version.txt":
            if root not in seen:
                seen.add(root)
                files.append(root)
            continue
        root = posixpath.normpath(root)
        root_device = device_for(root, mounts)
        pending = [root]
        visited = set()
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            visited.add(directory)
            try:
                entries = directory_entries(dev, directory)
            except Exception as exc:
                errors.append({"root": root, "path": directory, "error": str(exc)})
                continue
            for kind, path in entries:
                # Like find -xdev, do not descend/read entries on another device.
                if device_for(path, mounts) != root_device:
                    continue
                if kind == "D":
                    pending.append(path)
                elif path not in seen:
                    seen.add(path)
                    files.append(path)
    return files, errors


def metadata(dev) -> dict:
    result = {}
    for name, cmd in (
        ("version", "busybox cat /version.txt"),
        ("identity", "busybox grep -E '^(Name|Pid|PPid|Uid|Gid):' /proc/$$/status"),
        ("partitions", "busybox cat /proc/partitions"),
        ("mounts", "busybox cat /proc/mounts"),
    ):
        try:
            result[name] = run(dev, name, cmd, 60)["output"]
        except Exception as exc:  # noqa: BLE001
            result[name] = "ERROR: %r" % (exc,)
    return result


def backup(dev, out: Path, phase: str, *, max_file_bytes: int, max_files: int,
           double_read_all: bool) -> dict:
    meta = metadata(dev)
    result = {
        "tool": "zve10_backup_files.py",
        "phase": phase,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metadata": meta,
        "files": [],
        "inventory_errors": [],
        "completed": False,
        "camera_side_writes": "none by this tool; service authentication may update /setting/.etools and /setting/.hasp",
    }
    if phase == "inventory":
        files, errors = inventory(dev, INVENTORY_ROOTS)
        result["inventory"] = files
        result["inventory_errors"] = errors
        result["completed"] = not errors
        return result

    roots = list(MODES[phase]) + ["/version.txt"]
    files, errors = inventory(dev, roots)
    result["inventory_errors"] = errors
    if max_files:
        files = files[:max_files]
    result["inventory_count"] = len(files)

    for index, camera_path in enumerate(files, 1):
        print("FILE %d/%d %s" % (index, len(files), camera_path), flush=True)
        record = {"path": camera_path}
        result["files"].append(record)
        try:
            size = camera_size(dev, camera_path)
            record["size"] = size
            if max_file_bytes and size > max_file_bytes:
                record["skipped"] = "larger than --max-file-bytes"
                continue
            first_sha = camera_sha256(dev, camera_path)
            record["camera_sha256"] = first_sha
            if double_read_all:
                second_sha = camera_sha256(dev, camera_path)
                record["camera_sha256_second_read"] = second_sha
                record["camera_reads_match"] = first_sha == second_sha
                if first_sha != second_sha:
                    raise RuntimeError("camera-side double read mismatch: " + camera_path)
            destination = safe_destination(out / "files", camera_path)
            host_sha = transfer(dev, camera_path, size, destination)
            record["file"] = str(destination.relative_to(out))
            record["host_sha256"] = host_sha
            record["host_size"] = destination.stat().st_size
            record["match"] = host_sha == first_sha and record["host_size"] == size
            if not record["match"]:
                raise RuntimeError("hash mismatch for " + camera_path)
        except Exception as exc:  # noqa: BLE001
            record["error"] = repr(exc)
    result["completed"] = not errors and all("error" not in item for item in result["files"])
    return result


def write_report(out: Path, result: dict) -> None:
    lines = [
        "# ZV-E10 file-level backup",
        "",
        "Phase: `%s`" % result["phase"],
        "Started: %s" % result["started"],
        "Completed: **%s**" % result["completed"],
    ]
    if "inventory" in result:
        lines += ["Inventory entries: %d" % len(result["inventory"])]
    lines += [
        "",
        "| file | size | match |",
        "|---|---:|---|",
    ]
    for item in result.get("files", []):
        lines.append(
            "| `%s` | %s | %s |"
            % (
                item["path"],
                item.get("size", "-"),
                "OK" if item.get("match") else item.get("error", "skipped"),
            )
        )
    if result.get("inventory_errors"):
        lines += ["", "## Inventory errors", ""]
        for error in result["inventory_errors"]:
            lines.append("- `%s`: %s" % (error.get("path", error["root"]), error["error"]))
    lines += [
        "",
        "## Caveats",
        "",
        "- This tool never reads or writes block devices.",
        "- It cannot restore anything; there is no write-back path.",
        "- Files larger than `--max-file-bytes` are skipped by design.",
        "- The service terminal is read-only in this tool.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=tuple(MODES), default="critical")
    parser.add_argument("--out", help="output directory (default: ./backups/...)")
    parser.add_argument("--max-file-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--double-read-all", action="store_true")
    parser.add_argument("--driver", default="libusb")
    args = parser.parse_args()

    out = Path(args.out).resolve() if args.out else common.default_out("zve10-file-")
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    print("OUTPUT: " + str(out), flush=True)

    result = None

    def callback(camera):
        nonlocal result
        camera.readHasp()
        common.check_version(camera)
        enabled = False
        try:
            enabled = True
            camera.setTerminalEnable(True)
            common.drain(camera.dev, 1.0)
            result = backup(
                camera.dev,
                out,
                args.phase,
                max_file_bytes=args.max_file_bytes,
                max_files=args.max_files,
                double_read_all=args.double_read_all,
            )
        finally:
            if enabled:
                camera.setTerminalEnable(False)
                result = result or {
                    "tool": "zve10_backup_files.py",
                    "phase": args.phase,
                    "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "metadata": {},
                    "files": [],
                    "completed": False,
                }
                result["terminal_closed"] = True

    try:
        common.connect(callback, args.driver)
    finally:
        if result is None:
            result = {
                "tool": "zve10_backup_files.py",
                "phase": args.phase,
                "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "files": [],
                "metadata": {},
                "completed": False,
                "error": "backup did not return a result",
            }
        (out / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        write_report(out, result)
        common.restore_tree_owner(out)
        print("BACKUP_OUT:", out, flush=True)
    if not result.get("completed"):
        raise SystemExit(1)
        print("BACKUP_REPORT:", out / "REPORT.md", flush=True)


if __name__ == "__main__":
    main()
