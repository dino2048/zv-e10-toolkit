#!/bin/sh
# One administrator popup; runs the experimental BootROM dump.
# The camera must already be in USB mass-storage mode.
# Requires --owner-authorized-exec.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/lib.sh"

if [ "$(id -u)" = 0 ]; then
    echo "run this as your normal user; the popup grants temporary admin rights" >&2
    exit 1
fi

admin_run "$SCRIPT_DIR/launch_bootrom_dump.sh" "$@"
