# BootROM dump

Experimental two-pass read of the ZV-E10 BootROM through the service terminal.

## Method

1. The host checks the firmware baseline and confirms that `/tmp_bt` is tmpfs.
2. It uploads `payload/read_page.elf` (460 bytes) into a fresh
   `/tmp_bt/br.XXXXXX` directory, then verifies size and SHA-256.
3. The helper is run once per 4 KiB page. It opens `/dev/mem` read-only, maps
   `0xffff0000 + index * 0x1000`, prints 4096 bytes as hex, and exits.
4. All pages are read twice and compared, then written to `dump.bin`.
5. The helper and its directory are removed from the camera.

The helper only reads the mapped page. The only camera-side write is the
temporary helper in tmpfs; no eMMC, flash, configuration, or kernel module is
touched.

## Verified range

`0xffff0000–0xffff5fff` (6 pages, 24 KiB), firmware
`30110_05.2025031501`. The two passes matched byte for byte.

Page layout observed:

| Page | Content |
|---|---|
| 0 | ARM vector table and startup code |
| 1 | Thumb code, strings, data |
| 2 | Thumb code, hex table |
| 3–4 | all zero |
| 5 | first 1 KiB non-zero, rest zero |

`0xffff6000` and beyond were not read. The helper only accepts page indices
0..5, and the host refuses anything outside the verified range.

## Usage

```sh
./scripts/run_bootrom_dump.sh --owner-authorized-exec
```

Options:

- `--pages 1..6` — number of 4 KiB pages (default 6);
- `--passes 1|2` — 2 for the verified two-pass method (default 2);
- `--keep-helper` — leave the helper in `/tmp_bt` for debugging.

Output:

```
backups/zve10-bootrom-<timestamp>/
├── dump.bin
├── pages/pass1_seg0.bin ... pass2_seg5.bin
├── manifest.json
└── SHA256SUMS
```

## Requirements and limits

- Camera in USB mass-storage mode; one administrator popup; macOS launchers.
- `/tmp_bt` must be a tmpfs mount. The tool refuses otherwise.
- `--owner-authorized-exec` is required: this executes code on the camera.
- The proven range is small and the helper is fixed to it. Extending the range
  requires rebuilding the helper and re-verifying it.
- Reading unverified addresses can raise SIGBUS/SIGSEGV in the helper. Read
  page by page and stop on the first failure; do not map a large range.
- The dump is Sony firmware content. Keep it private, do not commit it, and do
  not include it in this repository.

## Alternative: BootROM serial injection

The project also has a confirmed UART injection path (RP2040 → camera D−,
battery insertion, `1 long + 7 short` = payload execution in SRAM). That path
works before Linux boots, but it needs hardware wiring and a second-stage
loader. It is not part of this repository.
