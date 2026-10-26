# BootROM 注入与裸机操作

**简体中文** | [English](README.md) · [项目首页](../README.zh-CN.md)

本目录包含两级裸机程序：Pico 经 BootROM 串口接口注入 stage1，电脑通过 USB 加载 stage2。stage1 提供 USB 通信和内存访问；stage2 提供 eMMC 分区读取和写入功能。主机工具可从已有备份恢复受支持的用户分区。
现有实机记录覆盖 ZV-E10 固件 `30110_05.2025031501`，主机为 macOS。

## 两级执行关系

Pico 串口注入 `stage1` → stage1 建立 USB 通信 → 电脑端 `host/` 加载 `stage2` → 通过 fastboot 读取或写入 eMMC 分区。

- `stage1/`：[第一级源码](stage1/README.md)，负责 USB 传输、内存访问与程序加载。
- `stage2/`：[第二级源码](stage2/README.md)，复用 stage1 的 USB 接口，负责 eMMC 和 fastboot 命令。
- `host/` 在电脑上运行；`pico/` 包含 Pico 固件与电脑端串口注入工具。
- `Makefile` 统一提供 `make build`、`make check`、`make test` 和 `make clean`。

## 先准备什么

- RP2040 Pico、24pin USB-C 转接板、复位电阻与 CC 下拉，按 [硬件说明](docs/hardware.zh-CN.md)接线；相机装好电池。
- 按 [Pico 准备说明](pico/README.zh-CN.md)编译并安装发送固件。
- Python 3.10+、libusb、Android platform-tools 中的 `fastboot`。本路线不需要 Sony-PMCA-RE。

以下命令从仓库根目录进入 `bootrom/` 后执行。创建独立虚拟环境，并安装依赖：

```sh
cd bootrom
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

macOS 可用 Homebrew 安装 `libusb` 和 `android-platform-tools`。
使用正式镜像不需要 C 交叉编译器、ARM binutils 或 ELF 文件。

## 正式配套镜像

| 文件 | 大小 | 用途 |
|---|---:|---|
| `prebuilt/stage1.bin` | 8028 B | 串口注入；USB 传输与内存访问 |
| `prebuilt/stage2-flash.bin` | 10588 B | 支持 raw/sparse 写入的 fastboot |

完整 SHA-256 见 [SHA256SUMS](prebuilt/SHA256SUMS)，版本与能力见 [manifest](prebuilt/manifest.json)。
这两份镜像与已有实机验证版本逐字节一致。stage2 同时支持读取和写入分区；只有执行 `fastboot flash` 等写入命令时才会修改 eMMC。
主机工具校验本地镜像，并在交接前读取正在运行的 stage1，确认其配对关系。

## 注入并读取

```sh
# 1. 相机接 Pico 转接板，装电池、开关 ON；替换串口名
.venv/bin/python pico/inject_payload.py \
  --port /dev/cu.usbmodemXXXX --file prebuilt/stage1.bin \
  --duration 15 --record-gap 0.002

# 2. payload 启动后 30 秒内，将相机 USB 换接电脑

# 3. 加载 stage2，并检查状态
.venv/bin/python host/bootstrap.py

# 4. 使用标准 fastboot CLI
fastboot devices
fastboot getvar all
fastboot oem partition
fastboot fetch nflasha10 backup.bin
```

内存访问命令见[内存与分区读取说明](docs/exploration.zh-CN.md)。
`host/backup_compare.py` 可将读取结果与自己的备份分区清单比较。

## 写入与恢复

按 [恢复流程](docs/recovery.zh-CN.md)准备清单、离线切片、刷入并回读。
读取与写入使用同一份 stage2。执行写入前，按恢复说明核对目标分区与备份。

`fastboot flash <分区> <镜像>` 会修改该分区；完成并核对读取结果后可用 `fastboot reboot` 重启。
恢复工具不会自动选择故障分区，也不提供测试图案演练入口。

## 范围与限制

- 约 4 分钟后外部电源侧复位；大量读取或恢复需分批，每个新会话重新注入。
- stage1 串口注入上限 8168 B；stage2 暂存区 1 MiB，sparse 头部开销也计入传输大小。
- 提供 `fetch`、raw/sparse `flash`、`reboot`，不提供 `erase`；stage2 没有分区写保护。
- 恢复脚本支持 16 个用户分区，不处理 boot0/boot1 和分区表，不能覆盖所有变砖原因。
- 注入只写 SRAM；执行 `fastboot flash` 后才会写入 eMMC。
- 仓库不含设备镜像、BootROM 转储或可供通刷的 Sony 固件。

## 源码与开发

见 [开发与验证](../CONTRIBUTING.md)。stage1 位于 `stage1/`，stage2 位于 `stage2/`，电脑端工具位于 `host/`；`stage1/build/` 与 `stage2/build-flash/` 只用于本地构建，不随仓库发布。
修改 stage1 后必须重新检查固定地址 ABI，不能任意混用 stage2。
