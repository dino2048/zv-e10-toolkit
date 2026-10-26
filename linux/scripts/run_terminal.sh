#!/bin/sh
# One administrator popup; starts the service-terminal server.
# Read-only by default. Add --owner-authorized-write for a full shell.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/lib.sh"

if [ "$(id -u)" = 0 ]; then
    echo "run this as your normal user; the popup grants temporary admin rights" >&2
    exit 1
fi

admin_run "$SCRIPT_DIR/launch_terminal.sh" --client-uid "$(id -u)" "$@"
