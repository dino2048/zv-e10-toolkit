[**English**](README.md) | [简体中文](README.zh-CN.md)

# BootROM helper

`read_page.S` / `read_page.elf` — a 460-byte relocation-free ARM EABI
executable used by `tools/zve10_bootrom_dump.py`.

## What it does

`read_page.elf <0..5>`:

1. bounds-check the page index (0..5);
2. `open("/dev/mem", O_RDONLY)`;
3. `mmap2` one 4 KiB page at `0xffff0000 + index * 0x1000`, `PROT_READ`,
   `MAP_SHARED`;
4. print 4096 bytes as 16 lines of 512 hex characters;
5. exit 0.

It only reads the mapped page. The only writes are to stdout.

## Verified

- Source SHA-256: `5210faa9d38bad75ff2215ddde9be18683fbb13f9f2fa640815649c7091a3f68`
- ELF SHA-256: `a7a8aa74f4e9645af45a94e68719f583389ecfc726d0e5bb97ff1ca6893e1226`
- Size: 460 bytes
- Used for the 24 KiB two-pass read of `0xffff0000–0xffff5fff`

## Rebuild

```sh
pip install pyelftools
python payload/build_page_helper.py
```

Requires `clang` with the `arm-linux-gnueabi` target. The rebuild should
produce the same 460-byte ELF and the same SHA-256; if it does not, do not use
the result without reviewing the disassembly.
