#!/bin/sh
# Validate official ZV-E10 USB Streaming through serial-safe null-sink captures.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")
cd "$REPO_DIR"

if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
else
    PY=$(command -v python3 || true)
fi
[ -n "$PY" ] || { echo "python3 not found; run scripts/setup.sh" >&2; exit 1; }
exec "$PY" -B host/zve10_usb_stream_probe.py "$@"
