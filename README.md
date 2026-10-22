# zv-e10-toolkit

[简体中文](README.zh-CN.md) | **English**

Read-only backup and service-mode toolkit for the Sony ZV-E10.
Tested on firmware `30110_05.2025031501` with macOS.

## Tools

| Tool | Purpose | Writes camera |
|---|---|---|
| `tools/zve10_backup_raw.py` | Read the Linux-visible user area and B0/B1 twice; save raw images and hashes | No |
| `tools/zve10_backup_files.py` | Copy selected ordinary files over the service terminal | No |
| `tools/zve10_verify.py` | Verify manifests, `SHA256SUMS`, and partition slices offline | No |
| `tools/zve10_terminal_server.py` + client | Service shell; read-only allow-list by default | No by default |
| `tools/zve10_read_file_jiritsu.py` | Optional read-only Jiritsu `GET_FILE` reader | No |

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
- Only the firmware above is tested; device paths and sizes are ZV-E10-specific.

## Notes

- Use only on hardware you own or are authorized to service.
- No Sony firmware, binaries, service key tables, or device data are included.
- Service-mode access is an undocumented vendor interface; local law may
  restrict it. This is not legal advice.

## Documentation

- [Service mode](docs/service-mode.md)
- [Root terminal](docs/root-terminal.md)
- [FileControl read path](docs/filecontrol-read.md) (includes the optional Jiritsu path)
- [Backup method](docs/backup-method.md)
- [Verification](docs/verification.md)

## Credits

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (MIT) — USB
  service-mode transport and authentication.
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload)
  and [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)
  — public prior work on the service/Jiritsu paths.

Not affiliated with or endorsed by Sony.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
