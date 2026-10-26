#!/usr/bin/env python3
"""Client for the owner-authorized service terminal.

Start the server first with ``scripts/run_terminal.sh`` (one administrator
popup), then run this client in another terminal:

    .venv/bin/python host/zve10_terminal_client.py

The server writes a pointer to ``session/latest.txt``.  Commands are
single-line ASCII.  In the default read-only mode the server enforces a small
allow-list; ``--owner-authorized-write`` must be passed to the server to lift
it.  ``exit`` or ``quit`` closes the session.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

import zve10_common as common


def resolve(session_arg: str | None) -> Path:
    if session_arg:
        return Path(session_arg).resolve()
    pointer = common.ROOT / "session" / "latest.txt"
    if not pointer.is_file():
        raise SystemExit("no session pointer; run scripts/run_terminal.sh first")
    return Path(pointer.read_text(encoding="utf-8").strip()).resolve()


def read_state(session: Path) -> dict:
    path = session / "state.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def submit(session: Path, payload: dict, timeout: float = 45.0) -> dict:
    name = uuid.uuid4().hex + ".json"
    temp = session / "requests" / ("." + name + ".tmp")
    temp.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    temp.replace(session / "requests" / name)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session / "responses" / name
        if response.is_file():
            return json.loads(response.read_text(encoding="utf-8"))
        state = read_state(session)
        if state.get("state") in ("closed", "failed"):
            detail = state.get("error") or state.get("close_reason") or ""
            return {"error": "session ended (%s): %s" % (state.get("state"), detail)}
        time.sleep(0.15)
    return {"error": "timed out waiting for the camera"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-dir", help="session directory (default: session/latest.txt)")
    args = parser.parse_args()
    session = resolve(args.session_dir)

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = read_state(session)
        if state.get("state") == "ready":
            break
        if state.get("state") in ("closed", "failed"):
            raise SystemExit("session unavailable: " + json.dumps(state, ensure_ascii=False))
        time.sleep(0.5)
    else:
        raise SystemExit("session was not ready within 60 seconds")

    state = read_state(session)
    print("connected; mode: " + ("read-write" if state.get("write_mode") else "read-only"),
          flush=True)
    print("commands are single-line ASCII; 'exit' closes the session", flush=True)

    while True:
        try:
            line = input("zve10:/ # ")
        except EOFError:
            line = "exit"
        except KeyboardInterrupt:
            print()
            submit(session, {"action": "close"})
            print("close request sent")
            break
        line = line.strip()
        if not line:
            continue
        if line in ("exit", "quit"):
            submit(session, {"action": "close"})
            print("session closed")
            break
        response = submit(session, {"action": "shell", "command": line})
        if "refused" in response:
            print("[refused] " + str(response["refused"]))
            continue
        if "error" in response:
            print("[error] " + str(response["error"]))
            continue
        text = response.get("output", "")
        print(text, end="" if text.endswith("\n") else "\n")
        if response.get("exit_code"):
            print("[exit %s]" % response["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
