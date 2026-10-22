#!/usr/bin/env python3
"""Owner-authorized service-terminal server.

One authenticated service session keeps the camera terminal open.  A local
client (``zve10_terminal_client.py``) submits single-line commands through a
request queue and reads the replies.

Default mode is read-only:
  * commands must match a small allow-list;
  * shell metacharacters, /dev access, and find action flags are refused.

``--owner-authorized-write`` lifts the allow-list for this session only.  The
catastrophic-command denylist always stays in place.  These checks are
guardrails, not a security boundary.

This tool provides a root service shell on the camera.  It does not read or
write the eMMC images; use the backup tools for that.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from pathlib import Path

import zve10_common as common

IDLE_TIMEOUT = 600
DENY = (
    (r"\bmkfs\b|\bmke2fs\b|\bfdisk\b|\bflashcp\b|\bflash_erase\b",
     "filesystem/partition tooling"),
    (r"/dev/nflasha|/dev/mmcblk|/dev/mtd|\bdd\b.*\bof=/dev/",
     "block-device access"),
    (r"\brm\b[^|;&]*\s(-[a-z]*r[a-z]*|--recursive)\b", "recursive removal"),
    (r"\bmount\b|\bumount\b|\bremount\b", "mount operation"),
    (r"\binsmod\b|\brmmod\b|\bmodprobe\b", "kernel module operation"),
    (r"\breboot\b|\bhalt\b|\bpoweroff\b", "system power command"),
    (r"\bdate\b.*\s(-s\b|--set)", "setting the clock"),
    (r"\bdmesg\b.*\s-c\b", "clearing the kernel log"),
)
READ_ONLY = re.compile(
    r"^\s*(busybox\s+)?(cat|ls|find|ps|du|df|grep|head|tail|wc|sha256sum|"
    r"md5sum|stat|readlink|pwd|uptime|date|uname|free|echo|id|dmesg)\b"
)
METACHARS = re.compile(r"[;|&<>`]|\$\(")
FIND_WRITE = re.compile(
    r"\bfind\b.*\s(-exec|-execdir|-delete|-ok|-okdir|-fprint|-fprintf|-fls)\b"
)

CLIENT_UID = None
CLIENT_GID = None


def refuse_reason(command: str, write_mode: bool = False,
                  allow_module_ops: bool = False):
    if "\n" in command or "\r" in command:
        return "single-line commands only"
    if not command.isascii():
        return "ASCII only"
    if len(command) > 200:
        return "command too long (max 200)"
    low = command.lower()
    for pattern, why in DENY:
        if why == "kernel module operation" and allow_module_ops:
            continue
        if re.search(pattern, low):
            return "refused: " + why
    if not write_mode:
        # Ignore metacharacters inside single quotes: the camera shell does not
        # expand them there, and grep patterns commonly contain '|'.
        unquoted = re.sub(r"'[^']*'", "", command)
        if METACHARS.search(unquoted):
            return "refused: shell metacharacters are disabled in read-only mode"
        if "/dev/" in unquoted:
            return "refused: /dev access is disabled in read-only mode"
        if FIND_WRITE.search(low):
            return "refused: find action flags are disabled in read-only mode"
        if not READ_ONLY.match(command):
            return ("refused: not in the read-only allow-list "
                    "(use --owner-authorized-write for a full shell)")
    return None


def self_test() -> None:
    checks = 0
    allowed_ro = (
        "busybox cat /proc/partitions",
        "ls -la /",
        "busybox grep -E '^(Name|Pid):' /proc/$$/status",
        "cat /version.txt",
        "busybox df -h",
    )
    for command in allowed_ro:
        assert refuse_reason(command) is None, command
        checks += 1
    refused_ro = (
        "touch /tmp/x",
        "rm /tmp/x",
        "cat /dev/nflasha",
        "ls; rm -rf /",
        "find / -exec rm {} +",
        "echo $(reboot)",
        "busybox mount -o remount,rw /",
        "reboot",
    )
    for command in refused_ro:
        assert refuse_reason(command) is not None, command
        checks += 1
    allowed_write = (
        "touch /tmp/x",
        "busybox rm /tmp/foo",
        "dd if=/tmp/a of=/tmp/b",
        "busybox cat /proc/uptime",
    )
    for command in allowed_write:
        assert refuse_reason(command, write_mode=True) is None, command
        checks += 1
    refused_write = (
        "rm -rf /",
        "cat /dev/mmcblk0",
        "mount -o remount,rw /",
        "insmod /usr/kmod/bcmdhd.ko",
        "reboot",
        "dd if=/dev/zero of=/dev/nflasha",
    )
    for command in refused_write:
        assert refuse_reason(command, write_mode=True) is not None, command
        checks += 1
    assert refuse_reason("busybox insmod /usr/kmod/bcmdhd.ko",
                         write_mode=True, allow_module_ops=True) is None
    assert refuse_reason("reboot", write_mode=True, allow_module_ops=True) is not None
    checks += 2
    print("SELFTEST_PASS:", checks, "checks")


def publish(path: Path, obj: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    if os.geteuid() == 0 and CLIENT_UID is not None:
        os.chown(temp, CLIENT_UID, CLIENT_GID)
    temp.replace(path)


def prepare_session(path: Path) -> Path:
    if path.is_symlink():
        raise SystemExit("session directory must not be a symlink")
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    if os.geteuid() == 0 and CLIENT_UID is not None:
        os.chown(path, CLIENT_UID, CLIENT_GID)
    for child in (path / "requests", path / "responses"):
        child.mkdir(exist_ok=True, mode=0o700)
        os.chmod(child, 0o700)
        if os.geteuid() == 0 and CLIENT_UID is not None:
            os.chown(child, CLIENT_UID, CLIENT_GID)
    return path


def serve(session: Path, write_mode: bool, allow_module_ops: bool,
          driver: str) -> None:
    inbox = session / "requests"
    responses = session / "responses"
    scope = (
        "one authenticated service session; owner-submitted single-line commands "
        "via a local queue; read-only allow-list"
    )
    if write_mode:
        scope += "; OWNER-AUTHORIZED: read-only allow-list lifted for this session"
    if allow_module_ops:
        scope += "; OWNER-AUTHORIZED: insmod/rmmod permitted for this session"
    state = {
        "state": "connecting",
        "write_mode": write_mode,
        "module_ops_authorized": allow_module_ops,
        "idle_timeout_seconds": IDLE_TIMEOUT,
        "scope": scope,
        "commands_completed": 0,
        "refused_count": 0,
    }
    publish(session / "state.json", state)

    def callback(camera):
        camera.readHasp()
        common.check_version(camera)
        attempted = False
        try:
            attempted = True
            camera.setTerminalEnable(True)
            common.drain(camera.dev, 1.0)
            state["state"] = "ready"
            state["session_started"] = time.time()
            publish(session / "state.json", state)

            last = time.monotonic()
            closing = False
            while not closing:
                requests = sorted(inbox.glob("*.json"))
                if not requests:
                    if time.monotonic() - last > IDLE_TIMEOUT:
                        state["close_reason"] = "idle timeout"
                        break
                    time.sleep(0.15)
                    continue
                for request_path in requests:
                    if request_path.name.startswith("."):
                        # Client-side temporary file; it will be renamed shortly.
                        continue
                    if (request_path.is_symlink() or not request_path.is_file()
                            or not re.fullmatch(r"[0-9a-f]{32}\.json", request_path.name)
                            or request_path.stat().st_size >= 4096
                            or (CLIENT_UID is not None
                                and request_path.stat().st_uid != CLIENT_UID)):
                        try:
                            request_path.unlink()
                        except OSError:
                            pass
                        continue
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    request_path.unlink()
                    action = request.get("action")
                    last = time.monotonic()
                    if action == "close":
                        publish(responses / request_path.name,
                                {"action": action, "accepted": True})
                        closing = True
                        break
                    if action != "shell":
                        publish(responses / request_path.name,
                                {"error": "only shell and close are accepted"})
                        continue
                    command = request.get("command", "")
                    if not isinstance(command, str):
                        publish(responses / request_path.name,
                                {"error": "bad command field"})
                        continue
                    reason = refuse_reason(command, write_mode, allow_module_ops)
                    if reason:
                        state["refused_count"] += 1
                        publish(responses / request_path.name,
                                {"action": "shell", "command": command,
                                 "refused": reason})
                        publish(session / "state.json", state)
                        continue
                    try:
                        state["state"] = "executing"
                        state["action"] = "shell"
                        publish(session / "state.json", state)
                        result = common.command(camera.dev, "shell", command,
                                                60 if write_mode else 20)
                        state["commands_completed"] += 1
                        result.pop("raw", None)
                        result["sequence"] = state["commands_completed"]
                        publish(responses / request_path.name, result)
                        state["state"] = "ready"
                        state.pop("action", None)
                        publish(session / "state.json", state)
                    except Exception as exc:  # noqa: BLE001
                        publish(responses / request_path.name,
                                {"action": "shell", "command": command,
                                 "error": repr(exc)})
                        raise
        finally:
            if attempted:
                camera.setTerminalEnable(False)
                state["terminal_closed"] = True

    try:
        common.connect(callback, driver)
        if state.get("state") == "connecting":
            raise RuntimeError("no authenticated camera callback")
        state["state"] = "closed"
        state["service_returned"] = True
    except Exception as exc:  # noqa: BLE001
        state["state"] = "failed"
        state["error"] = repr(exc)
        raise
    finally:
        publish(session / "state.json", state)
        common.restore_tree_owner(session)


def main() -> None:
    global CLIENT_UID, CLIENT_GID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="serve", choices=("serve",))
    parser.add_argument("--session-dir", type=Path,
                        default=common.ROOT / "session" / time.strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--client-uid", type=int,
                        help="UID that owns the request queue (set by the run script)")
    parser.add_argument("--owner-authorized-write", action="store_true",
                        help="lift the read-only allow-list for this session")
    parser.add_argument("--allow-module-swap", action="store_true",
                        help="also allow insmod/rmmod (requires write mode)")
    parser.add_argument("--driver", default="libusb")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if args.allow_module_swap and not args.owner_authorized_write:
        raise SystemExit("--allow-module-swap requires --owner-authorized-write")

    CLIENT_UID = args.client_uid
    if CLIENT_UID is None:
        CLIENT_UID = os.getuid()
        if CLIENT_UID == 0:
            CLIENT_UID = int(os.environ.get("SUDO_UID", "0"))
    CLIENT_GID = os.getgid()
    if CLIENT_UID:
        try:
            import pwd
            CLIENT_GID = pwd.getpwuid(CLIENT_UID).pw_gid
        except (KeyError, ImportError):
            pass

    session = prepare_session(args.session_dir)
    pointer = common.ROOT / "session" / "latest.txt"
    pointer.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    pointer.write_text(str(session) + "\n", encoding="utf-8")
    if os.geteuid() == 0 and CLIENT_UID is not None:
        os.chown(pointer, CLIENT_UID, CLIENT_GID)

    try:
        with (session / "server.log").open("w") as log:
            with contextlib.redirect_stdout(_Tee(sys.stdout, log)), \
                 contextlib.redirect_stderr(_Tee(sys.stderr, log)):
                print("SESSION_DIR: " + str(session), flush=True)
                print("MODE: " + ("read-write (owner-authorized)" if
                                  args.owner_authorized_write else "read-only"),
                      flush=True)
                print("Client: .venv/bin/python tools/zve10_terminal_client.py",
                      flush=True)
                serve(session, args.owner_authorized_write,
                      args.allow_module_swap, args.driver)
    finally:
        if os.geteuid() == 0 and CLIENT_UID is not None:
            common.restore_owner(pointer)


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


if __name__ == "__main__":
    main()
