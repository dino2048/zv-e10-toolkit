# zv-e10-toolkit

[简体中文](README.zh-CN.md) | **English**

Backup, service-mode, BootROM dump, and fastboot/eMMC toolkit for the Sony ZV-E10.
Tested on firmware `30110_05.2025031501` with macOS.

## Tools

| Tool | Purpose | Camera side effect |
|---|---|---|
| `tools/zve10_backup_raw.py` | Read the Linux-visible user area and B0/B1 twice; save raw images and hashes | None |
| `tools/zve10_backup_files.py` | Copy selected ordinary files over the service terminal | None |
| `tools/zve10_verify.py` | Verify manifests, `SHA256SUMS`, and partition slices offline | None |
| `tools/zve10_terminal_server.py` + client | Service shell; read-only allow-list by default | None by default; write mode optional |
| `tools/zve10_read_file_jiritsu.py` | Optional Jiritsu `GET_FILE` reader | None |
| `tools/zve10_bootrom_dump.py` | Two-pass BootROM read through `/dev/mem` (experimental) | Temporary helper in `/tmp_bt` tmpfs |
| `fastboot/` | Pico-injected fastboot payload and stage2 eMMC read (manual, hardware required) | SRAM payload; no eMMC writes |

## Fastboot / eMMC (manual)

`fastboot/` is a separate hardware path: Pico BootROM serial injection → DWC3
fastboot payload → stage2 eMMC block read. It needs a Pico, a 470Ω reset line,
CC1/CC2 tied together with a 5.1kΩ pull-down, the battery left in, and a
manual build; it is not part of the Python tools.

- [fastboot/README.md](fastboot/README.md)
- [Hardware and wiring](fastboot/docs/hardware.md)
- [USB success log](fastboot/docs/usb-success.md)
- [eMMC success log](fastboot/docs/emmc-success.md)

## Install

```sh
./scripts/setup.sh
```

Creates `.venv/`, installs the Python dependencies, and clones
[Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) into `vendor/`.
Requires Python 3.10+, `libusb`, the camera in USB mass-storage mode, and about
4 GB free for a raw backup.

## Quick start

```sh
./scripts/run_raw_backup.sh
./scripts/run_file_backup.sh --phase critical

.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

./scripts/run_terminal.sh
.venv/bin/python tools/zve10_terminal_client.py

./scripts/run_bootrom_dump.sh --owner-authorized-exec
```

Full shell:

```sh
./scripts/run_terminal.sh --owner-authorized-write
```

## Raw backup output

```
backups/zve10-raw-emmc-<timestamp>/
├── nflasha.read1.bin   nflasha.read2.bin
├── nflashaB0.read1.bin nflashaB0.read2.bin
├── nflashaB1.read1.bin nflashaB1.read2.bin
├── manifest.json
└── SHA256SUMS
```

Each image is hashed while receiving, `fsync`ed, then re-read from the host
disk and hashed again before being renamed into place.

## Limits

- No write-back, restore, or unbrick path.
- Raw images are what the Linux driver exposes, not a physical chip dump; no
  RPMB, OTP/eFuse, or hidden areas.
- Not an atomic snapshot: read-write partitions can change between the two
  passes. Both images are kept and differences are reported.
- Requires the camera to boot far enough to accept a service session.
- The BootROM dump is limited to the proven `0xffff0000–0xffff5fff` range and
  executes a temporary helper from tmpfs.
- Only the firmware above is tested; device paths and sizes are ZV-E10-specific.

## Notes

- Use only on hardware you own or are authorized to service.
- No Sony firmware, binaries, service key tables, or device data are included.
- BootROM dumps are Sony firmware content. Keep them private and do not commit
  them.
- Service-mode access is an undocumented vendor interface; local law may
  restrict it. This is not legal advice.

## Documentation

- [Service mode](docs/service-mode.md)
- [Root terminal](docs/root-terminal.md)
- [FileControl read path](docs/filecontrol-read.md) (includes the optional Jiritsu path)
- [Backup method](docs/backup-method.md)
- [Verification](docs/verification.md)
- [BootROM dump](docs/bootrom-dump.md)
- [Fastboot / eMMC](fastboot/README.md)

## References

Used by the published tools:

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (MIT) — USB
  service-mode transport and authentication; fetched by `scripts/setup.sh`.
- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)
  — source of the fastboot/UART/eMMC port in `fastboot/`.
- [cokeenet/zve10-qemu](https://github.com/cokeenet/zve10-qemu) (MIT) — UART
  boot protocol, partition map, and hardware reference.
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload)
  — Jiritsu path traversal / service-mode prior work.
- [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)
  (MIT) — Jiritsu read-only dump method.

Method/research references (not required by the published tools):

- [xyzhangxin/sony-a6700-powerful](https://github.com/xyzhangxin/sony-a6700-powerful)
  (GPL-3.0) — Pico/CC method reference.
- [ma1co/OpenMemories-Platform](https://github.com/ma1co/OpenMemories-Platform)
  (MIT) — `BOOTROM_BASE` for the `/dev/mem` BootROM dump.
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) (MIT) and
  [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py)
  — firmware unpacking (research only).

Not affiliated with or endorsed by Sony.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
