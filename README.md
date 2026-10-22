# zv-e10-toolkit

[简体中文](README.zh-CN.md) | **English**

A read-only-first toolkit for the Sony ZV-E10: raw eMMC backup, file-level
backup, offline verification, and an owner-authorized service terminal.

> **This is not a rescue or unbrick tool.** It has no block-device write path,
> no restore command, and no way to recover a camera that cannot boot. It also
> does not include any Sony firmware, binaries, keys, certificates, or device
> data.

## What it does

| Tool | Purpose | Writes to camera |
|---|---|---|
| `tools/zve10_backup_raw.py` | Read the Linux-visible user area and B0/B1 twice each; write raw images plus hashes | No |
| `tools/zve10_backup_files.py` | Copy selected ordinary files using `dd` + `base64` over the service terminal | No |
| `tools/zve10_verify.py` | Verify manifests, `SHA256SUMS`, and two reads partition by partition | No (offline) |
| `tools/zve10_terminal_server.py` + client | Owner-authorized service shell; read-only allow-list by default | No by default |
| `tools/zve10_read_file_jiritsu.py` | Optional read-only file read through the Jiritsu `GET_FILE` path | No |

## Tested on

- Sony ZV-E10, firmware `30110_05.2025031501`
- macOS (Apple Silicon, Homebrew libusb)
- Other models or firmware versions may work for service-mode access but the
  fixed device paths and sizes are ZV-E10-specific and unverified.

## Requirements

- Python 3.10+
- [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (MIT) for the USB
  service-mode transport
- `pyusb`, `pycryptodomex`
- macOS: `libusb` (`brew install libusb`) and one administrator popup per run
- Camera in **USB mass-storage** mode, not auto/MTP
- About 4 GB free for a raw backup (two passes of 1.82 GiB plus boot areas),
  plus 1 GiB headroom

## Install

```sh
./scripts/setup.sh
```

This creates `.venv/`, installs the Python dependencies, and clones
Sony-PMCA-RE into `vendor/Sony-PMCA-RE`. Nothing from Sony is bundled.

## Quick start

```sh
# Raw eMMC backup (two passes; camera in mass-storage mode)
./scripts/run_raw_backup.sh

# File-level backup of settings, certificates, /etc, /version.txt
./scripts/run_file_backup.sh --phase critical

# Offline verification
.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

# Service terminal (read-only by default)
./scripts/run_terminal.sh
# then, in another terminal:
.venv/bin/python tools/zve10_terminal_client.py
```

Full shell (high risk; owner-authorized):

```sh
./scripts/run_terminal.sh --owner-authorized-write
```

## Raw backup output

```
backups/zve10-raw-emmc-<timestamp>/
├── nflasha.read1.bin
├── nflasha.read2.bin
├── nflashaB0.read1.bin  nflashaB0.read2.bin
├── nflashaB1.read1.bin  nflashaB1.read2.bin
├── manifest.json          # sizes, hashes, per-MiB hashes, metadata
└── SHA256SUMS
```

Each file is hashed while it is received, `fsync`ed, then independently
re-read from the host disk and hashed again before it is renamed into place.

## What it cannot do

- Write images back to the camera, restore a backup, or unbrick a camera.
- Read RPMB, OTP/eFuse, or storage-controller hidden areas.
- Produce an atomic snapshot: partitions that are mounted read-write may
  change between the two passes. Both images are kept and differences are
  reported, not hidden.
- Guarantee that what the Linux driver exposes equals the physical chip
  layout.
- Run without the camera booting far enough to accept a service session.

## Safety and law

- Default posture is read-only. Full shell requires an explicit flag.
- Use only on hardware you own or are authorized to service.
- Service-mode access is an undocumented vendor interface. Local law
  (anti-circumvention rules, warranty, terms of service) may restrict what you
  may do. This repository is not legal advice.
- No Sony firmware, binaries, service software, certificates, or device data
  are included or redistributed.

See [docs/safety-legal.md](docs/safety-legal.md).

## Documentation

- [Service mode](docs/service-mode.md)
- [Root terminal](docs/root-terminal.md)
- [FileControl read path](docs/filecontrol-read.md)
- [Backup method](docs/backup-method.md)
- [Verification](docs/verification.md)
- [Safety and legal](docs/safety-legal.md)
- [Related work](docs/related-work.md)

## Credits

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (MIT) — USB
  service-mode authentication and transport.
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload)
  and
  [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)
  — public prior work on the service/Jiritsu paths. Their code is not copied
  here.
- This project is not affiliated with or endorsed by Sony.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
