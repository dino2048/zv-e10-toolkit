# Stage2 — eMMC and fastboot / 第二级：eMMC 与 fastboot

Loaded over USB by `../host/bootstrap.py`. Reuses the pinned stage1 USB callbacks
and provides eMMC partition reads, raw/sparse writes and reboot.
`tests/` contains offline C and Python validation.

由电脑端 `../host/bootstrap.py` 经 USB 加载，复用 stage1 的固定地址 USB 接口。
提供 eMMC 分区读取，以及可写版本中的 raw/sparse 写入和重启。`tests/` 为离线验证。

Published image / 正式镜像：`../prebuilt/stage2-flash.bin`。
From `bootrom/`, run `make build` to build the complete pair and `make test` for offline tests.
See [usage](../README.md), [中文说明](../README.zh-CN.md) and
[development](../../CONTRIBUTING.md).
