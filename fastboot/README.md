# ZV-E10 fastboot payload (USB transport)

[**English**](README.md) | [简体中文](README.zh-CN.md)

Bare-metal fastboot for the CXD90045 (ZV-E10, ARMv7-A/Cortex-A9). It is injected
through the BootROM serial boot; once running it hands D−/D+ to the PC, which
talks `fastboot`.

**Status: verified on hardware (2026-10-22), including a stage-2 read of eMMC
(SDM2 partition table and partition data, read-only). The USB device enumerates
as `18d1:4ee0`; `getvar` returns `OKAY0.4`; `oem help/peek` work. The image is
7,908 B, inside the 8 KB direct-injection window.**

Not to be confused with the LED-only payload (not part of this repository).
This payload initializes the USB clock/PHY/DWC3 and exposes the fastboot
transport (`oem peek/poke/call/download/load`). The eMMC driver is not in the
7.9 KB image; it is downloaded at runtime as [stage2/](stage2/) (1,316 B).

## Expected behaviour (v2 diagnostic build)

After injection (battery stays in), the camera gives **one long flash (0.4 s)**
to show the payload is alive, then a series of **short pulses (120 ms)** that
count progress, then one short pulse every 2 s meaning "waiting for host":

| Short pulses | Reached |
|---:|---|
| 1 | USB clock/PHY initialized |
| 2 | DWC3 core initialized (GSNPSID, soft reset, event buffers) |
| 3 | `DEPSTARTCFG` done |
| 4 | EP0 OUT configured |
| 5 | EP0 IN configured |
| 6 | EP0 enabled, SETUP armed |
| then one pulse / 2 s | D+ pull-up on, waiting for PC enumeration |

**Stopping after the Nth short pulse means the next step did not return**,
which localizes failures better than the old "one long + two short, then
silent". Seeing one short pulse every 2 s means the payload is waiting for the
host; the problem is on the PHY/host side, not a hang.

The camera does not reboot itself while waiting; once the PC is connected it
enumerates as `18d1:4ee0` (Google fastboot):

> The LED no longer calls ROM `0xFFFF0D0B`: the local ROM dump shows a
> `b 0xffff0d58` at `0xFFFF0DB0`, which **never returns**, so using it for
> progress would hang. The current build drives GPIO0 bit0 directly through
> the ROM's own register accesses (`0xF2910044/0x48`), with 0.4 s long /
> 120 ms short pulses for counting.

```sh
# The Android fastboot CLI on macOS does not recognize this device
# (device-level class 0xff). Use the pyusb tool in this repository; the
# protocol is identical:
python3 fastboot/host/zve10_fb.py getvar product       # -> ZVE10
python3 fastboot/host/zve10_fb.py oem help
python3 fastboot/host/zve10_fb.py oem peek:0xf020c120:4    # GSNPSID
python3 fastboot/host/zve10_fb.py oem peek:0xfe020000:16   # payload code
python3 fastboot/host/zve10_fb.py reboot
```

Addresses must be 8 hex digits. A 40-bit input such as `0xf02000c120` is
rejected by the device's 64-bit parser (early builds truncated it into DRAM,
which stalled AXI and stopped all USB responses).

`oem` commands:

```
peek:<addr>[:<len>]   dump memory, max 0x1000
poke:<addr>:<val>     32-bit write, reports readback
call:<addr>           call addr as u32 f(void)
load:<addr>           copy staged download to addr
```

`flash:`/`erase:` return FAIL explicitly — this build has no eMMC write path.

## stage 2 (eMMC read)

The main payload is only 7.9 KB and cannot hold the eMMC driver, so the eMMC
code is downloaded at runtime over USB:

```sh
# after enumeration
python3 fastboot/host/run_stage2.py --block 0xe000 --count 1   # first block of nflasha3
```

`run_stage2.py` performs `download → oem load:0xfe300000 → poke parameters →
oem call → peek`. Parameters live at `0xFE320000`: `[0]` = start block (512 B
sectors), `[1]` = block count (≤64). The result block is `0xFE308000`; data is
at `0xFE310000`.

Source is in [stage2/](stage2/), 1,316 B. The register sequence is ported from
CXD90057's `sdhci.c`, with the base changed to ZV-E10's `0xF0304000`. See
[docs/emmc-success.md](docs/emmc-success.md) (Chinese log).

Protocol: [pico/PROTOCOL.md](pico/PROTOCOL.md).

## Hardware and flow

Wiring, battery and cable-swap steps are in [docs/hardware.md](docs/hardware.md).
Summary: GP28 → D−: A7 (A pair), direct, optional 470Ω; GP27 → 470Ω → D+:
A6 (A pair). If A6/A7 do not work, switch the whole pair to B7/B6. 5V → VBUS
(one wire), GND (one wire); CC1/CC2 tied with a 5.1kΩ pull-down to GND. The
camera is not connected to the PC during injection; the battery stays in and
GP27 resets the camera, no battery removal. If it does not work, flip the
USB-C direction and retry.

```sh
# Run from the repository root.

# 1. build
make -C fastboot
make -C fastboot/stage2

# 2. inject (Pico connected, camera on, battery in)
python3 fastboot/pico/inject_payload.py \
    --port /dev/cu.usbmodemXXXX \
    --file fastboot/build/fastboot.bin --duration 90

# 3. after seeing 0x2003, unplug the camera USB-C from the Pico and connect it to the PC
python3 fastboot/host/zve10_fb.py getvar product
```

`inject_payload.py` uses the same record group as the v15 flow:
`SET_UNLOCK → MEM_WRITE(0xFE020000…) → SET_ENTRY(0xFE020001) → SET_UNLOCK`,
with 13.3 ms / 50 ms gaps; 7,908 B fits the verified 8 KB window.

## Source and address map

Most of the USB stack is ported from the
[ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) fastboot payload
(CXD90057, AArch64). Only changes with a concrete basis were made:

| Item | A7M4 (CXD90057) | ZV-E10 (CXD90045) | Basis |
|---|---|---|---|
| DWC3 | `0xF10C0000` | **`0xF0200000`** | `platform.h:191 CXD900X0_USB_DRD_BASE` |
| Global/device registers | `+0xC100/+0xC700` | same | ZV-E10 GPL `drivers/usb/dwc3/core.h` |
| DWC3 IP family | DWC_usb31 | **DWC_usb3 (0x5533)** | ZV-E10 GPL driver |
| DEPCMD status bits | bit12-15 | **bit15** | ZV-E10 `core.h` |
| Clock/reset | SCU `0xF1388000` | **CLKRST3 `0xF2900000`** | `platform.h:111`, `usb_otg_reg.h` |
| IPCLKEN1 | — | `+0x34` bit14 (USB30DRD_ACLK) | `usb_otg.c:311` |
| IPRESET2 | — | `+0xC4` bits 9, 10 | `usb_otg.c:309,317` |
| OTG / REFCLK | — | `0xF2920000` `+0x100` bit16 | `usb_otg.c:307` |
| PHY trim block | `phy_cr 0xF10A0000` | **`0xF0220000`** (DRD+0x20000) | `platform.c:414` |
| TXVREFTUNE | U2PHY_CFGR1 | `0xF0220000+0` low 4 bits = 3 | `usb_otg.c:313-315` |
| ADPADDR/ADPDATA | — | `+0x11080` / `+0x11084` | `usb_otg.c:323-324` |
| TCA | `0xF10D0000` | **absent, not accessed** | no TCA code in ZV-E10 GPL source |
| Timer | `0xF1042000` 4 MHz | `0xF2403000` 1 MHz | `platform.h:60`, `regs-timer.h` |
| Reset | GPIO XRESET_REQ | MISC `0xF2915044` = 0x011 | `core.c:245`, `regs-misc.h` |
| LED | GPIO ch18 | ROM `0xFFFF0D0B(code)` | measured here |

The ZV-E10 init sequence comes directly from Sony's
`drivers/usb/f_usb/usb_otg.c`: REFCLK → release USB30 → enable ACLK →
TXVREFTUNE → release PHY → `GUSB3PIPECTL = 0x11080002` → ADPADDR/ADPDATA.
`GUSB2PHYCFG` keeps its reset value (Sony's driver also does not write
PHYIF/USBTRDTIM); only the suspend bit is cleared.

## Deliberate differences from the A7M4 version

- `start.S` is ARMv7/Thumb: IRQ/FIQ off, I/D cache off, own SP, clear `.bss`.
  Cache is off because DWC3 reads TRBs/event buffers through AXI; with cache on
  it can read stale data.
- `usb_phy.c` was rewritten (ZV-E10's clock/reset/PHY layout is completely
  different from CXD90057).
- `dwc3.c` drops `PWRDNSCALE(2)` and `DSBLCLKGTNG` (the ZV-E10 driver says the
  latter is reserved) and drops the UTMI 8-bit override.
- `led.c`/`log.c` use the ROM flash routine and PL011 UART0 (`0xF2000000`).
- `fastboot_min.c` is a new minimal protocol layer (`fastboot.c` in the A7M4
  tree is 2,000 lines of eMMC/CP/NOR commands; this build does not need them).

## Verified results (2026-10-22)

- Enumeration: `18d1:4ee0`, 480 Mb/s, serial `ZVE10-fastboot`.
- `getvar:version` → `OKAY0.4`; `oem help/peek/poke/call/download/load` all work.
- GSNPSID `0x5533290A` (DWC_usb3 2.90a); PHY/clock/reset registers read back
  the written values.
- stage 2: eMMC identification + SDM2 partition table + partition data
  (nflasha3 = FAT), read-only.
- Evidence: [docs/usb-success.md](docs/usb-success.md) and
  [docs/emmc-success.md](docs/emmc-success.md) (Chinese logs).

## Known issues and limits

- **The payload resets itself after about 15–20 minutes**, cause unknown. The
  ROM dump has no reference to `0xF2402000` (WDT); it may be PMIC-side. Finish
  each session in one pass.
- macOS's Android `fastboot` CLI does not recognize this device (device-level
  class 0xff); use `host/zve10_fb.py` / `host/run_stage2.py`.
- **Repeated SET_CONFIGURATION hangs EP0**: macOS configures once during
  enumeration and libusb configures again; the second one, with bulk transfers
  already queued, can hang the endpoint commands. `src/usb.c` now applies only
  the first one; old firmware still has this risk.
- **An invalid address stalls AXI**: if an `oem peek` address is truncated into
  untrained DRAM, the read does not abort but stalls the bus; even EP0 stops
  responding and only a power cycle recovers. Payload and host tools now have
  whitelists (`0xf0000000-0xf3ffffff`, `0xfe000000-0xfeffffff`).
- `oem peek:<addr>:<len>` parses `len` as **hex**: for 64 bytes write `:40`.
- The LED is driven directly through GPIO0 bit0 (`0xF2910044/0x48`); the ROM's
  `0xFFFF0D0B` is not used (it has a `b 0xffff0d58` at `0xFFFF0DB0` that never
  returns).
- Write boundary unchanged: the main payload and stage2 only read memory and
  eMMC; there is no card-write path.

## Next steps

1. **device→host bulk upload**: one `oem peek` currently returns only 4 KB;
   a full-partition dump needs a bulk IN upload command.
2. **Write path** (CMD6/CMD24/25): only after per-operation authorization;
   start with a RAM image and verify readback.
3. **Find the source of the 15–20 minute reset**: PMIC / another watchdog.
