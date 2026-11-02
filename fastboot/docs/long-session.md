# Long-session fastboot workflow

**English** | [简体中文](long-session.zh-CN.md)

This guide covers long-session fastboot use on the ZV-E10. At stage2 entry the
toolkit performs one Darwin (power MCU) `0x16` keepalive read. The camera no
longer performs its approximately four-minute automatic reset, and fastboot
remains available until you reboot or power off.

Published pair:

| File | Size | SHA-256 |
|---|---:|---|
| `prebuilt/stage1.bin` | 7636 B | `8573b5d1…` |
| `prebuilt/stage2-flash.bin` | 10228 B | `902ed105…` |

## When an AI assistant runs the steps

State these points explicitly; do not assume the user knows them.

1. **When stage1 injection starts**:
   > "Injection started. Move the camera USB-C from the Pico to the computer
   > within 30 seconds."
2. **After `fastboot devices` shows `ZVE10-fastboot`**:
   > "Next step: loading stage2."
3. **If `bootstrap.py` reports `oem peek ... unknown cmd`**:
   - the device is already running stage2; **do not load it again**;
   - reset the camera → re-inject stage1 → load stage2 immediately while only
     stage1 is running.

## 0. Prerequisites

- ZV-E10 firmware `30110_05.2025031501`;
- Pico programmed with sender firmware `zve10_uart_od 15` (see
  [Pico setup](../pico/README.md));
- Wiring per [hardware notes](hardware.md): GP28→D−, GP27→470Ω→D+,
  5V→VBUS, common GND, CC1/CC2 tied with a 5.1 kΩ pull-down;
- battery installed, camera ON; camera USB-C on the Pico, Pico USB on the host;
- host with `fastboot`, `libusb`, and a `.venv` created from `requirements.txt`.

Run the commands below from `fastboot/`.

## 1. Inject stage1

```sh
.venv/bin/python pico/inject_payload.py \
  --port /dev/cu.usbmodemXXXX \
  --file prebuilt/stage1.bin \
  --duration 15 --record-gap 0.002
```

- Within 30 seconds of injection, move the camera USB-C from the Pico to the
  computer.
- Confirm the device appears:

```sh
fastboot devices
# ZVE10-fastboot  fastboot
```

## 2. Load stage2

```sh
.venv/bin/python host/bootstrap.py \
  --file prebuilt/stage2-flash.bin \
  --usb-only
```

- Only run this while stage1 is alive.
- Stage2 performs the one-shot Darwin `0x16` keepalive read automatically; no
  manual command is needed.
- If it reports `oem peek ... unknown cmd`, follow item 3 above; do not reload.

After takeover, use standard fastboot:

```sh
fastboot getvar version-bootloader
fastboot getvar all
fastboot oem partition
```

## 3. Backup

Save partitions with standard fastboot:

```sh
fastboot fetch nflasha1  nflasha1.bin
fastboot fetch nflasha2  nflasha2.bin
# ... all 16 user partitions
fastboot fetch nflashaB0 nflashaB0.bin
fastboot fetch nflashaB1 nflashaB1.bin
```

Alternatively, `fetch nflasha` reads the partitioned extent plus the partition
table; split it by the known offsets. Keep a partition list and SHA-256 with the
backup.

> Backup scope: `fetch nflasha` covers the SDM2 partition extent
> `0x54800000`; the following 512 MiB unpartitioned tail is all zero.
> For an exact whole-block-device image, use the Linux persistent-session
> `/dev/nflasha` (1.8 GB).

## 4. Restore

Restore selected partitions from a raw backup:

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup \
  --partitions nflasha3,nflasha7
```

- Only explicitly named user partitions are written.
- Rehearse with `nflasha10` first.
- Writing `nflashaB0/B1` is not validated; confirm boot-area handling
  separately before using it for brick recovery.
- Read back and verify before rebooting.

## 5. Finish

```sh
fastboot reboot
```

Or use `pico/reset_only.py` / power-cycle to leave fastboot.

## Hardware validation

The published images have been validated on the ZV-E10 for long sessions, eMMC
initialization and a 12 MB partition fetch.

## Notes

- **Do not reload stage2 while it is already running**: `oem peek` returns
  `unknown cmd`; reset → re-inject stage1 → load stage2 immediately.
- **Do not miss the 30-second swap window**: re-inject if missed.

## Limitations

- download staging is 1 MiB; raw images larger than 1 MiB require sparse chunks;
- no `erase`, no partition write protection;
- writing B0/B1 is unvalidated;
- RPMB, OTP/eFuse and hardware faults are out of scope.
