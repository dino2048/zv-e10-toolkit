# BootROM injection and bare-metal operations

**English** | [简体中文](README.zh-CN.md) · [Project home](../README.md)

This directory contains two bare-metal stages. Pico injects stage1 through the BootROM serial interface; the host loads stage2 over USB. Stage1 provides USB communication and memory access. Stage2 provides eMMC partition reads and writes. Host tools can restore supported user partitions from an existing backup. Existing hardware records cover ZV-E10 firmware `30110_05.2025031501`
with macOS hosts.

## Two-stage execution

Pico serial injection → stage1 establishes USB → computer-side `host/` loads stage2 → fastboot reads or writes eMMC partitions.

- `stage1/`: [first-stage source](stage1/README.md), providing USB transport, memory access and program loading.
- `stage2/`: [second-stage source](stage2/README.md), reusing stage1 USB callbacks for eMMC and fastboot commands.
- `host/` runs on the computer; `pico/` contains Pico firmware and computer-side serial injection tools.
- `Makefile` provides `make build`, `make check`, `make test` and `make clean`.

## Prerequisites

- RP2040 Pico, a 24-pin USB-C breakout, reset resistor and CC pull-downs: follow [wiring](docs/hardware.md), with a battery installed.
- Build and install the sender firmware using the [Pico setup guide](pico/README.md).
- Python 3.10+, libusb and `fastboot` from Android platform-tools. Sony-PMCA-RE is not required.

From the repository root, enter this route and install its Python dependencies:

```sh
cd bootrom
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On macOS, Homebrew provides `libusb` and `android-platform-tools`. Using the
published images requires no C cross-compiler, ARM binutils or ELF files.

## Published pair

| File | Size | Purpose |
|---|---:|---|
| `prebuilt/stage1.bin` | 8028 B | Serial injection, USB transport and memory access |
| `prebuilt/stage2-flash.bin` | 10588 B | Fastboot with raw/sparse writes |

Full hashes: [SHA256SUMS](prebuilt/SHA256SUMS). Versions and capabilities:
[manifest](prebuilt/manifest.json). The two images are byte-identical to previously hardware-validated versions. Stage2 supports both partition reads and writes; eMMC changes only when a write command such as `fastboot flash` is issued. Host tools verify local images and fingerprint the
running stage1 before handing over to stage2.

## Inject and read

```sh
# 1. Camera connected to Pico breakout, battery installed, power switch ON
.venv/bin/python pico/inject_payload.py \
  --port /dev/cu.usbmodemXXXX --file prebuilt/stage1.bin \
  --duration 15 --record-gap 0.002

# 2. Within 30 seconds of payload startup, move camera USB to the computer

# 3. Load stage2 and inspect status
.venv/bin/python host/bootstrap.py

# 4. Standard fastboot CLI
fastboot devices
fastboot getvar all
fastboot oem partition
fastboot fetch nflasha10 backup.bin
```

See [exploration](docs/exploration.md) for memory access.
`host/backup_compare.py` compares reads with your backup's
partition verification report.

## Write and recover

Follow [recovery](docs/recovery.md) to prepare a report, slice offline, flash and
verify readback. The same stage2 handles reads and writes. Check the target partition and backup against the recovery guide before issuing a write command.

`fastboot flash <partition> <image>` modifies that partition. After checking the
result, use `fastboot reboot`. Recovery does not automatically diagnose failed
partitions or expose test-pattern drills.

## Scope and limitations

- External power-side reset after approximately four minutes: batch long reads/restores and reinject for each session.
- Stage1 serial injection limit: 8168 B. Stage2 staging limit: 1 MiB including sparse headers.
- Supports `fetch`, raw/sparse `flash` and `reboot`; no `erase` or partition write protection.
- Recovery covers 16 user partitions, excluding boot0/boot1 and the partition table. It cannot resolve every cause of a bricked camera.
- Injection writes SRAM only; eMMC changes when `fastboot flash` is executed.
- No device images, BootROM dumps or Sony firmware for cross-flashing are distributed.

## Development

See [development and validation](../CONTRIBUTING.md). Stage1 is in `stage1/`; stage2 is in `stage2/`. Computer-side tools live in `host/`. Local `stage1/build/` and `stage2/build-flash/`
outputs are excluded from publication. Changes to stage1 require checking the
fixed-address ABI and rebuilding its paired stage2.
