#!/bin/sh
# Shared helpers for the macOS launchers. Source this file; do not run it.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")

admin_run() {
    launcher=$1
    shift
    /usr/bin/osascript - "$(id -u)" "$launcher" "$@" <<'APPLESCRIPT'
on run argv
    set uidText to item 1 of argv
    set launcherPath to item 2 of argv
    set commandText to quoted form of launcherPath
    if (count of argv) > 2 then
        repeat with i from 3 to (count of argv)
            set commandText to commandText & " " & quoted form of (item i of argv)
        end repeat
    end if
    do shell script ("/bin/launchctl asuser " & quoted form of uidText & " " & commandText) with administrator privileges
end run
APPLESCRIPT
}
