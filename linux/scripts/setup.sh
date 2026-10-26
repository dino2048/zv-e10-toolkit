#!/bin/sh
# Create the local virtual environment and fetch Sony-PMCA-RE (MIT).
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_DIR=$(dirname "$SCRIPT_DIR")
cd "$REPO_DIR"

PYTHON_BIN=${PYTHON:-python3}
"$PYTHON_BIN" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

PMCA_REV=a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0
if [ ! -d vendor/Sony-PMCA-RE ]; then
    mkdir -p vendor
    git clone --no-checkout https://github.com/ma1co/Sony-PMCA-RE vendor/Sony-PMCA-RE
    git -C vendor/Sony-PMCA-RE checkout --detach "$PMCA_REV"
elif [ "$(git -C vendor/Sony-PMCA-RE rev-parse HEAD)" != "$PMCA_REV" ]; then
    echo "Sony-PMCA-RE revision differs; expected $PMCA_REV. Preserve your changes and prepare the pinned checkout." >&2
    exit 1
fi

if [ "$(uname -s)" = "Darwin" ]; then
    if ! command -v brew >/dev/null 2>&1; then
        echo "note: Homebrew not found; install libusb or set LIBUSB_PATH" >&2
    elif ! brew list libusb >/dev/null 2>&1; then
        echo "note: install libusb with: brew install libusb" >&2
    fi
fi

echo "setup complete: $REPO_DIR"
echo "python: $REPO_DIR/.venv/bin/python"
