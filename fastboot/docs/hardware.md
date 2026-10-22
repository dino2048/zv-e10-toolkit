# Hardware and wiring

[**English**](hardware.md) | [简体中文](hardware.zh-CN.md)

## Wiring diagram

```
Camera USB-C receptacle
      ↑ plugged in
USB-C male plug (24-pin breakout, both A and B sides exposed)
      │
      ├─ A7  D− ──[optional 470Ω]── GP28   Pico serial TX (open-drain)
      ├─ A6  D+ ── 470Ω ────────── GP27   reset
      ├─ A5  CC1 ─┐
      ├─ B5  CC2 ─┴─ 5.1kΩ ── GND
      ├─ VBUS (any one of A4/A9/B4/B9) ── Pico 5V
      └─ GND  (any one of A1/A12/B1/B12) ── Pico GND
```

Note: **if A6/A7 do not work, try B6/B7.**

## Notes

- The camera side is a USB-C receptacle; a male 24-pin breakout is required
  to reach the pins.
- During injection the camera USB-C goes to the breakout, not to the PC.
- D− is open-drain; do not use a 3.3V push-pull driver.
- GP28 and GP27 are not interchangeable.
- GP29 (MULTI_RX) is not connected.
- 470Ω: required on GP27 → D+; optional on GP28 → D−.
- VBUS and GND: one wire each is enough; the camera ties the pins internally.

## Battery and reset

- Battery stays in; the camera boots normally.
- The script enables the carrier, sends a 10 µs low pulse on GP27 to reset the
  camera, then replays the record group.
- **No battery removal is needed with reset.** Removing the battery to cold-boot
  is the legacy v7 method and is not used now.

## Switching the cable to the PC

- The payload detects VBUS low → high. After the long flash, unplug the 24-pin
  breakout from the camera and connect a normal USB-C cable to the PC.
- Pico 5V and Mac 5V can back-feed through the camera VBUS; the Pico may drop
  off the Mac. This does not affect the already running payload.

## LED

- One long flash (0.4 s): payload is alive.
- Short pulse count: USB clock/PHY → DWC3 → EP0 configuration → waiting for host.
- One short pulse every 2 s afterwards: waiting for host enumeration.
- Stopping after the Nth short pulse: the corresponding step did not return.

## Stop / return to normal boot

From the repository root:

```sh
python3 fastboot/pico/reset_only.py --port /dev/cu.usbmodemXXXX
```

One GP27 reset, carrier off, and the camera returns to normal boot without
removing the battery. Power-off or battery removal also works: the payload
lives in SRAM and is volatile.

## Boundaries

- This is BootROM serial boot, not a runtime exploit; it needs dedicated wiring
  and reset timing.
- It writes SRAM only; no eMMC, SD, or OTP writes.
