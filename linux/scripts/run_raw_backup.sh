#!/bin/sh
# One administrator popup; runs the read-only raw eMMC backup.
# The camera must already be in USB mass-storage mode.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/lib.sh"

if [ "$(id -u)" = 0 ]; then
    echo "run this as your normal user; the popup grants temporary admin rights" >&2
    exit 1
fi

admin_run "$SCRIPT_DIR/launch_raw_backup.sh" "$@"
