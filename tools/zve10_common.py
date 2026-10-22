#!/usr/bin/env python3
"""Shared helpers for the ZV-E10 read-only toolkit.

The USB service-mode transport is provided by Sony-PMCA-RE (MIT).  Nothing in
this module writes to the camera: the only data path used here is FileControl
READ (pFunc 0xff01) and the service terminal, both of which are read-only in
this toolkit.

Tested camera: Sony ZV-E10, firmware 30110_05.2025031501.
"""
from __future__ import annotations

import ctypes.util
import os
import re
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "Sony-PMCA-RE"
if VENDOR.is_dir() and str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

EXPECTED_VERSION = b"30110_05.2025031501"
FILE_CONTROL = 0xFF01
FILE_CONTROL_READ = 2
TERMINAL_OUTPUT_LIMIT = 128 * 1024


def _patch_libusb() -> None:
    """Point pyusb at a usable libusb on macOS.

    Set LIBUSB_PATH to override.  On Linux the system library is normally found
    without help, so this function does nothing when no candidate exists.
    """
    candidates = []
    explicit = os.environ.get("LIBUSB_PATH")
    if explicit:
        candidates.append(explicit)
    candidates += [
        "/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib",
        "/usr/local/opt/libusb/lib/libusb-1.0.dylib",
    ]
    path = next((c for c in candidates if Path(c).is_file()), None)
    if path is None:
        return

    original = ctypes.util.find_library

    def find_library(name: str):
        if name in ("usb-1.0", "libusb-1.0", "usb"):
            return path
        return original(name)

    ctypes.util.find_library = find_library


_patch_libusb()

try:
    from pmca.commands.usb import senserShellCommand  # noqa: E402
except ImportError as exc:  # pragma: no cover - environment guidance
    raise SystemExit(
        "Sony-PMCA-RE is not available. Run scripts/setup.sh, or set "
        "PYTHONPATH to a Sony-PMCA-RE checkout."
    ) from exc


def connect(complete, driver: str = "libusb") -> None:
    """Open one authenticated service session and call ``complete(camera)``.

    The camera must already be in USB mass-storage mode.  One administrator
    popup is required on macOS because libusb needs raw device access.
    """
    senserShellCommand(driverName=driver, complete=complete)


def set_terminal_timeout(camera, milliseconds: int = 30000) -> None:
    """Raise the raw USB timeout for large FileControl reads (best effort)."""
    try:
        camera.dev.driver.backend.dev.default_timeout = milliseconds
    except AttributeError:
        pass


def read_path(camera, path: str, sink=None):
    """Read one path through FileControl READ (pFunc 0xff01).

    The request carries only a path: the camera decides what the path means.
    Block-device nodes such as ``/dev/nflasha`` are readable this way without
    opening a camera shell.  Returns ``(response, data)``; ``data`` is ``None``
    when a sink is supplied.
    """
    name = path.encode("ascii")
    name += b"\0" * (4 - len(name) % 4)
    payload = struct.pack("<HH", FILE_CONTROL_READ, len(name)) + name
    return camera.dev.sendSenserPacket(FILE_CONTROL, payload, sink)


def check_version(camera, expected: bytes = EXPECTED_VERSION) -> bytes:
    """Read /version.txt through FileControl and enforce the tested baseline."""
    response, data = read_path(camera, "/version.txt")
    if response not in (0, 1):
        raise RuntimeError("FileControl READ failed for /version.txt: %r" % (response,))
    if data != expected:
        raise RuntimeError(
            "firmware baseline mismatch: expected %r, got %r" % (expected, data)
        )
    return data


def drain(dev, seconds: float) -> bytes:
    """Discard pending terminal output for a fixed interval."""
    deadline = time.monotonic() + seconds
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = dev.readTerminal()
        if chunk:
            buf.extend(chunk)
        if len(buf) > TERMINAL_OUTPUT_LIMIT:
            raise RuntimeError("unexpected terminal output volume")
    return bytes(buf)


def frame(command: str, token: str) -> str:
    """Wrap one shell command with machine-readable begin/end markers."""
    return (
        "printf '\\n__ZV_BEGIN_%s__\\n' '" + token + "'; " + command +
        "; zv_status=$?; printf '\\n__ZV_DONE_%s__:%s\\n' '" + token + "' \"$zv_status\"\n"
    )


def parse_frame(raw: bytes, token: str):
    """Return ``(exit_code, text)`` for a completed frame, else ``None``."""
    begin = re.search(rb"(?:^|\n)__ZV_BEGIN_" + token.encode() + rb"__\r?\n", raw)
    if not begin:
        return None
    end = re.search(
        rb"(?:^|\n)__ZV_DONE_" + token.encode() + rb"__:(\d+)\r?(?:\n|$)",
        raw[begin.end():],
    )
    if not end:
        return None
    body = raw[begin.end():begin.end() + end.start()]
    return int(end.group(1)), body.decode("utf-8", errors="replace")


def command(dev, name: str, text: str, timeout: float) -> dict:
    """Run one fixed command on the service terminal and wait for its frame."""
    token = "%s_%d" % (name, time.monotonic_ns())
    dev.writeTerminal(frame(text, token).encode("ascii"))
    deadline = time.monotonic() + timeout
    raw = bytearray()
    while time.monotonic() < deadline:
        chunk = dev.readTerminal()
        if chunk:
            raw.extend(chunk)
        if len(raw) > TERMINAL_OUTPUT_LIMIT:
            raise RuntimeError("terminal output limit exceeded")
        parsed = parse_frame(bytes(raw), token)
        if parsed is not None:
            status, output = parsed
            return {
                "name": name,
                "command": text,
                "exit_code": status,
                "output": output,
                "raw": raw.decode("utf-8", errors="replace"),
            }
    raise TimeoutError("no complete terminal frame for %s" % name)


def shquote(text: str) -> str:
    """Single-quote a string for the camera's busybox ash."""
    return "'" + text.replace("'", "'\\''") + "'"


def default_out(prefix: str) -> Path:
    """Default output directory next to the caller's working directory."""
    return Path.cwd() / "backups" / (prefix + time.strftime("%Y%m%d-%H%M%S"))


def restore_owner(*paths) -> None:
    """When running as root, hand output back to the repository owner."""
    if os.geteuid() != 0:
        return
    stat = ROOT.stat()
    for path in paths:
        try:
            os.chown(path, stat.st_uid, stat.st_gid)
        except OSError:
            pass


def restore_tree_owner(root: Path) -> None:
    """Recursively hand an output tree back to the repository owner."""
    if os.geteuid() != 0:
        return
    stat = ROOT.stat()
    for path in [root, *root.rglob("*")]:
        try:
            os.chown(path, stat.st_uid, stat.st_gid)
        except OSError:
            pass
