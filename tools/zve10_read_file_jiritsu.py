#!/usr/bin/env python3
"""Optional read-only file reader for the Jiritsu GET_FILE path.

This is a separate, experimental path from the FileControl backup tools:

  AdjustControl block 0x1001, command 0x4008 (GET_FILE)
  payload: [mode=1][area=0][f2=1] + "/.." + absolute path
  response body: AES-128-CTR, key = MD5("jiritsu team" padded to 16), IV = 00..0f

The path traversal escapes the workspace prefix so that absolute paths can be
read.  This technique is documented in public prior work (see
docs/related-work.md); it is not used by the backup tools.

Read-only: GET_FILE is the only camera command issued here, apart from the
version check and service-session setup.  No writes, uploads, or mounts.

Tested camera: Sony ZV-E10, firmware 30110_05.2025031501.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
from pathlib import Path

from Cryptodome.Cipher import AES
from Cryptodome.Hash import MD5

import zve10_common as common

JIRITSU_BLOCK = 0x1001
JIRITSU_GET_FILE = 0x4008


def derive_key() -> bytes:
    material = b"jiritsu team"
    return MD5.new(material + b"\0" * (16 - len(material))).digest()


def decrypt(data: bytes) -> bytes:
    iv = bytes(range(16))
    return AES.new(derive_key(), AES.MODE_CTR, nonce=b"", initial_value=iv).decrypt(data)


def read_file(camera, path: str, max_bytes: int) -> bytes:
    if not path.startswith("/"):
        raise SystemExit("path must be absolute")
    if path.startswith("/.."):
        raise SystemExit("path must not start with /..")
    transport = ("/.." + path).encode("latin1")
    payload = bytes([1, 0, 1]) + transport
    response = camera._sendAdjustControlPacket(JIRITSU_BLOCK, JIRITSU_GET_FILE, payload)
    if len(response) < 4:
        raise RuntimeError("short response: %d bytes" % len(response))
    status = struct.unpack_from("<I", response)[0]
    if status != 0:
        raise RuntimeError("GET_FILE status 0x%08x" % status)
    body = response[4:]
    if len(body) > max_bytes:
        raise RuntimeError("response larger than --max-bytes (%d)" % max_bytes)
    return decrypt(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", required=True, help="absolute camera path")
    parser.add_argument("--out", type=Path, help="write decrypted bytes here")
    parser.add_argument("--max-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--driver", default="libusb")
    args = parser.parse_args()

    result = {}

    def callback(camera):
        camera.readHasp()
        common.check_version(camera)
        data = read_file(camera, args.path, args.max_bytes)
        result["data"] = data

    common.connect(callback, args.driver)
    data = result.get("data")
    if data is None:
        raise SystemExit("no data returned")
    digest = hashlib.sha256(data).hexdigest()
    print("path:", args.path)
    print("bytes:", len(data))
    print("sha256:", digest)
    if args.out:
        args.out.write_bytes(data)
        os.chmod(args.out, 0o600)
        print("written:", args.out)
    else:
        printable = sum(1 for byte in data if 32 <= byte < 127 or byte in (9, 10, 13))
        if printable == len(data) and data:
            print("--- text ---")
            print(data.decode("ascii", errors="replace"))
            print("--- end ---")
        else:
            print("repr:", repr(data[:512]))


if __name__ == "__main__":
    main()
