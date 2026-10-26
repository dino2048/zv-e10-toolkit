# Pico 发送端准备

[English](README.md) · [裸机入口](../README.zh-CN.md) · [接线](../docs/hardware.zh-CN.md)

使用 RP2040 Raspberry Pi Pico。发送固件为 `zve10_uart_od 15`，
包含 PIO/DMA 串口发送、开漏输出和 GP27 复位。

## 构建与安装

需要 `arduino-cli` 和 Arduino-Pico 的 `rp2040:rp2040` core（本次构建使用 6.3.0）。
在 `bootrom/` 目录执行：

```sh
arduino-cli compile --fqbn rp2040:rp2040:rpipico \
  --build-property build.extra_flags=-DOPEN_DRAIN \
  --output-dir /tmp/zve10-pico-build pico/firmware/zve10_pico_od_reset
```

编译得到 UF2 后，按住 Pico 的 BOOTSEL 接入 USB，将 UF2 拷入出现的 `RPI-RP2` 磁盘。
固件目录里的 `serialboot.pio.h` 是与 `.pio` 对应、构建所需的源代码头文件，应一起保留。

## 检查与使用

```sh
.venv/bin/python pico/inspect_pico.py --port /dev/cu.usbmodemXXXX
.venv/bin/python pico/inject_payload.py --port /dev/cu.usbmodemXXXX \
  --file prebuilt/stage1.bin --duration 15 --record-gap 0.002
```

串口名替换为实际设备。注入工具会检查固件版本、空闲状态和开漏配置。
线序与换线时机见硬件说明；记录格式见 [协议](PROTOCOL.md)。
