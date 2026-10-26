# Operations inside Linux

[简体中文](README.zh-CN.md) | **English**

This directory contains host tools for the ZV-E10 USB service interface: terminal access, file reads, eMMC backup, BootROM reads and offline verification. The camera must boot Linux and accept a USB service connection.

Run the commands below from `linux/` (`cd linux` from the repository root).
See the [BootROM route](../bootrom/README.md) for bare-metal injection and partition recovery.
Tested on firmware `30110_05.2025031501` with macOS.

## Layout

```text
host/                     Computer-side Python tools
scripts/                  Setup, launchers and privilege handling
helpers/bootrom-reader/   Reader executed under camera Linux
examples/                 Manifest and partition-layout examples
docs/                     Operation guides
```

## Tools

| Tool | Purpose | Camera side effect |
|---|---|---|
| `host/zve10_backup_raw.py` | Read the Linux-visible user area and B0/B1 twice; save raw images and hashes | None |
| `host/zve10_backup_files.py` | Copy selected ordinary files over the service terminal | None |
| `host/zve10_verify.py` | Verify manifests, `SHA256SUMS`, and partition slices offline | None |
| `host/zve10_terminal_server.py` + client | Service shell; read-only allow-list by default | None by default; write mode optional |
| `host/zve10_read_file_jiritsu.py` | Optional Jiritsu `GET_FILE` reader | None |
| `host/zve10_bootrom_dump.py` | Two-pass BootROM read through `/dev/mem` | Temporary helper in `/tmp_bt` tmpfs |

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

.venv/bin/python host/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python host/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

./scripts/run_terminal.sh
.venv/bin/python host/zve10_terminal_client.py

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

- The Python tools here do not write back images or restore partitions; `../bootrom/`
  does have a verified partition-level restore (see its README).
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
- [Fastboot / eMMC](../bootrom/README.md)

Not affiliated with or endorsed by Sony.

## License

See [LICENSE](../LICENSE) and the [project acknowledgements](../README.md#sources-and-acknowledgements).
