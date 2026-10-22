#!/bin/sh
# Admin-side launcher for run_terminal.sh.
set -eu
REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_DIR"

if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
else
    PY=$(command -v python3 || true)
fi
[ -n "$PY" ] || { echo "python3 not found; run scripts/setup.sh" >&2; exit 1; }
exec "$PY" -B -u tools/zve10_terminal_server.py serve "$@"
