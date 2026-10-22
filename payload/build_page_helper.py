#!/usr/bin/env python3
"""Rebuild read_page.elf from read_page.S.

Requires clang with the ARM target and pyelftools:

    pip install pyelftools
    python payload/build_page_helper.py

The helper is a relocation-free ARM EABI executable. It accepts one argument,
a page index 0..5, opens /dev/mem read-only, maps one 4 KiB page starting at
0xffff0000 + index * 0x1000, and writes 4096 bytes as 16 lines of 512 hex
characters to stdout. It never writes to the mapped page.
"""
from __future__ import annotations

import hashlib
import struct
import subprocess
from pathlib import Path

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
SRC = HERE / "read_page.S"
OBJ = HERE / "read_page.o"
ELF = HERE / "read_page.elf"


def main() -> None:
    subprocess.run(
        ["clang", "--target=arm-linux-gnueabi", "-c", str(SRC), "-o", str(OBJ)],
        check=True,
    )
    with OBJ.open("rb") as stream:
        obj = ELFFile(stream)
        if obj["e_machine"] != "EM_ARM":
            raise SystemExit("unexpected ELF machine: %s" % obj["e_machine"])
        for section in obj.iter_sections():
            if section["sh_type"] in ("SHT_REL", "SHT_RELA"):
                if section["sh_size"]:
                    raise SystemExit("relocations are not allowed")
        code = obj.get_section_by_name(".text").data()

    header_size = 52 + 32
    size = header_size + len(code)
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    header = struct.pack(
        "<16sHHIIIIIHHHHHH",
        ident, 2, 40, 1, 0x10000 + header_size, 52, 0, 0x05000000, 52, 32, 1, 0, 0, 0,
    )
    segment = struct.pack("<IIIIIIII", 1, 0, 0x10000, 0x10000, size, size, 5, 4096)
    data = header + segment + code
    ELF.write_bytes(data)
    print("SIZE", len(data), "SHA256", hashlib.sha256(data).hexdigest(),
          "ENTRY", hex(0x10000 + header_size))


if __name__ == "__main__":
    main()
