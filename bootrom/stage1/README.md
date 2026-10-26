# Stage1 — USB transport / 第一级：USB 传输

Loaded into SRAM by Pico through the BootROM serial path. Provides USB
communication, bounded memory reads and the load/call interface used by stage2.
It stays resident while stage2 runs; its function addresses form the pinned ABI.

通过 Pico 经 BootROM 串口注入 SRAM，提供 USB 通信、内存读取和 stage2 加载接口。
stage2 运行时 stage1 仍常驻，其函数地址是两级配对的 ABI。注入上限为 8168 B。

Published image / 正式镜像：`../prebuilt/stage1.bin`。
From `bootrom/`, run `make build` to build the complete pair.
See [usage](../README.md), [中文说明](../README.zh-CN.md) and
[development](../../CONTRIBUTING.md).
