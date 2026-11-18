# Operations inside Linux

[简体中文](README.zh-CN.md) | **English**

This directory contains host tools for the ZV-E10 USB service interface: terminal access, file reads, eMMC backup, BootROM reads and offline verification. The camera must boot Linux and accept a USB service connection.

Run the commands below from `linux/` (`cd linux` from the repository root).
See the [fastboot route](../fastboot/README.md) for partition reads, writes and recovery; it is entered through Pico BootROM injection.
USB service operations support macOS and ZV-E10 system 2.03 on Windows; see [compatibility and validation](docs/validation.md) for per-feature platform coverage.

## Layout

```text
host/                     Computer-side Python tools
scripts/                  Setup, launchers and privilege handling
helpers/bootrom-reader/   Reader executed under camera Linux
helpers/jiritsu-shell/    Temporary loader used by the 2.03 backend
examples/                 Manifest and partition-layout examples
docs/                     Operation guides
```

## Tools

| Tool | Purpose | Camera side effect |
|---|---|---|
| `host/zve10_backup_raw.py` | System 2.02: read the user area and B0/B1 twice; save images and hashes | None |
| `host/zve10_backup_files.py` | Copy selected ordinary files over the service terminal | None |
| `host/zve10_get_file.py` | Read one explicit file through FileControl READ | None |
| `host/zve10_verify.py` | Verify manifests, `SHA256SUMS`, and partition slices offline | None |
| `host/zve10_terminal_server.py` + client | Persistent shell and structured backup actions; use this entry for 2.03 | Jiritsu uploads a temporary loader; write actions require authorization |
| `host/zve10_read_file_jiritsu.py` | Optional Jiritsu `GET_FILE` reader | None |
| `host/zve10_bootrom_dump.py` | Two-pass BootROM read through `/dev/mem` | Temporary helper in `/tmp_bt` tmpfs |

## Install

```sh
./scripts/setup.sh
```

Creates `.venv/`, installs the Python dependencies, and clones
[Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) into `vendor/`.
Requires Python 3.10+, `libusb`, the camera in USB mass-storage mode, and about
5 GiB free for a two-pass raw backup.

### Windows

Run from `linux/`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1
```

The script creates the project Python environment and installs the paired dependencies. Add `-Proxy <url>` if required. Install libusb-win32 for the camera's storage identity `054C:0D95` and service identity `054C:0336`; the latter appears after switching modes. The camera will no longer mount as a regular disk until its original driver is restored. Use the Python server directly on Windows, as shown below.

If PyUSB cannot find `libusb0.dll`, set `LIBUSB0_PATH` in the server's PowerShell terminal to the full path of the DLL from the locally installed driver. `LIBUSB_PATH` selects a libusb 1.0 DLL. These settings only load a host library; they do not install a camera driver. The libusb-package wheel's libusb 1.0 is **not** loaded by default: PyUSB takes the first backend that loads, and a camera on the libusb-win32 driver would then no longer be visible. Set `ZVE10_LIBUSB1=1` only after both camera interfaces have been moved to WinUSB or libusbK.

## Windows 2.03 backup

Backups use each camera's validated user/boot capacities. See [capacity variants and read-only eMMC diagnostics](docs/emmc-layout.md) for both backup paths and the `emmc-info` action.

Use `--request-file` for Windows structured actions, including commands or paths containing spaces. Save a single JSON object with `ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8`; UTF-8 files with or without a BOM are accepted. Do not pass both `--request-file` and `--request-json`. The file is parsed before any session request is submitted; server write authorization and confirmation checks still apply. Keep request files inside the ignored `session/` directory.

From `linux/` in PowerShell, start a read-only session:

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -B .\host\zve10_terminal_server.py --backend jiritsu --firmware 2.03 --owner-authorized-exec --session-dir session\backup-01 --idle-timeout 3600
```

The temporary loader provides read access and requires power removal after closing. In another PowerShell terminal, wait for `session/backup-01/state.json` to say `ready`, then request a two-pass backup:

```powershell
$python = ".\.venv\Scripts\python.exe"
$requestFile = 'session/request.json'
@{ action = 'raw-backup'; passes = 2; chunk_kib = 4096 } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $requestFile -Encoding UTF8
& $python -B .\host\zve10_terminal_client.py --session-dir session\backup-01 --timeout 7200 --request-file $requestFile
```

Allow at least 5 GiB free space and [verify the saved files and both passes](docs/verification.md) in the returned backup directory. Finish with `close`, wait for `state=closed`, `service_returned=true` and `loader_files_removed=true`, then switch off, unplug USB and remove the battery for about 30 seconds:

```powershell
$requestFile = 'session/request.json'
@{ action = 'close' } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $requestFile -Encoding UTF8
& $python -B .\host\zve10_terminal_client.py --session-dir session\backup-01 --request-file $requestFile
```

## macOS quick start

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

## Backup properties and project extensions

The existing persistent terminal server also accepts structured `backup-read` and
owner-authorized `backup-write` actions through the same client/connection. These
are settings properties, not disk images. See [Backup property operations and
extension API](docs/backup-properties.md) for original-value guards, private
snapshots, persistence/readback, and the optional project action hook.

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

- The Python tools here do not write back images or restore partitions; `../fastboot/`
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

- [Compatibility and validation](docs/validation.md)
- [Service mode](docs/service-mode.md)
- [Root terminal](docs/root-terminal.md)
- [FileControl read path](docs/filecontrol-read.md) (includes the optional Jiritsu path)
- [Backup method](docs/backup-method.md)
- [Verification](docs/verification.md)
- [BootROM dump](docs/bootrom-dump.md)
- [Fastboot / eMMC](../fastboot/README.md)

Not affiliated with or endorsed by Sony.

## License

See [LICENSE](../LICENSE) and the [project acknowledgements](../README.md#sources-and-acknowledgements).
