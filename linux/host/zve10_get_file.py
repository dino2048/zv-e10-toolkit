#!/usr/bin/env python3
"""Read one file from the camera through FileControl READ (pFunc 0xff01).

Read-only counterpart of the backup tools, for a single explicit path.

Usage: zve10_get_file.py --path /setting/Backup.bin --out ./Backup.bin
"""
import argparse
from pathlib import Path

import zve10_common as common


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--driver", default="libusb")
    args = ap.parse_args()

    def done(camera):
        common.set_terminal_timeout(camera, 60000)
        common.check_version(camera)
        with open(args.out, "wb") as sink:
            response, _ = common.read_path(camera, args.path, sink=sink)
        size = Path(args.out).stat().st_size
        print(f"resp={response} bytes={size} out={args.out}")

    common.connect(done, args.driver)


if __name__ == "__main__":
    main()
