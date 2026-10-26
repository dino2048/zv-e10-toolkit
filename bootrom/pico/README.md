# Pico sender setup

[简体中文](README.zh-CN.md) · [Bare-metal guide](../README.md) · [Wiring](../docs/hardware.md)

Use an RP2040 Raspberry Pi Pico. Sender firmware `zve10_uart_od 15` provides
PIO/DMA transmission, open-drain output and GP27 reset.

## Build and install

Install `arduino-cli` and the Arduino-Pico `rp2040:rp2040` core (build checked with core 6.3.0). From `bootrom/`:

```sh
arduino-cli compile --fqbn rp2040:rp2040:rpipico \
  --build-property build.extra_flags=-DOPEN_DRAIN \
  --output-dir /tmp/zve10-pico-build pico/firmware/zve10_pico_od_reset
```

Hold BOOTSEL while connecting Pico to USB, then copy the compiled UF2 to the
`RPI-RP2` volume. Keep `serialboot.pio.h` alongside `.pio`: it is a required
source header for the sketch.

## Inspect and use

```sh
.venv/bin/python pico/inspect_pico.py --port /dev/cu.usbmodemXXXX
.venv/bin/python pico/inject_payload.py --port /dev/cu.usbmodemXXXX \
  --file prebuilt/stage1.bin --duration 15 --record-gap 0.002
```

Replace the serial port. Injection checks the firmware version, idle state and
open-drain configuration. See wiring for connections and handoff timing, and
[the protocol](PROTOCOL.md) for record encoding.
