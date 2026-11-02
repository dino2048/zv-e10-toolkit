# 长会话 fastboot 操作指南

**简体中文** | [English](long-session.md)

本文说明 ZV-E10 fastboot 的长会话操作。stage2 入口会自动执行一次
Darwin（电源 MCU）`0x16` 保活读，相机不会在约 4 分钟时自动复位；
fastboot 会一直保持，直到主动重启或断电，标准 fastboot 命令可继续使用。

配套镜像：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `prebuilt/stage1.bin` | 7636 B | `8573b5d1…` |
| `prebuilt/stage2-flash.bin` | 10228 B | `902ed105…` |

## 使用 AI 助手操作时

以下节点需要明确提醒，不能默认用户已经知道：

1. **stage1 注入一开始**：
   > “注入已开始，请在 30 秒内把相机 USB-C 从 Pico 移到电脑。”
2. **看到 `fastboot devices` 出现 `ZVE10-fastboot` 后**：
   > “现在进入下一步：加载 stage2。”
3. **如果 `bootstrap.py` 报 `oem peek ... unknown cmd`**：
   - 说明设备已经在 stage2，**不要重复加载**；
   - 正确做法：复位相机 → 重新注入 stage1 → 在只有 stage1 时立刻加载 stage2。

## 0. 前置条件

- 相机 ZV-E10，固件 `30110_05.2025031501`；
- Pico 已烧发送固件 `zve10_uart_od 15`（准备方法见 [Pico 说明](../pico/README.zh-CN.md)）；
- 接线按 [硬件说明](hardware.zh-CN.md)：GP28→D−，GP27→470Ω→D+，5V→VBUS，
  GND 共地，CC1/CC2 并接后 5.1kΩ 下拉；
- 相机装电池、开关 ON；相机 USB-C 先接 Pico，Pico USB 接电脑；
- 主机有 `fastboot`、`libusb`，以及按 `requirements.txt` 创建的 `.venv`。

以下命令从 `fastboot/` 目录执行。

## 1. 注入 stage1

```sh
.venv/bin/python pico/inject_payload.py \
  --port /dev/cu.usbmodemXXXX \
  --file prebuilt/stage1.bin \
  --duration 15 --record-gap 0.002
```

- 注入开始后，在 30 秒内把相机 USB-C 从 Pico 移到电脑；
- 确认设备出现：

```sh
fastboot devices
# ZVE10-fastboot  fastboot
```

## 2. 加载 stage2

```sh
.venv/bin/python host/bootstrap.py \
  --file prebuilt/stage2-flash.bin \
  --usb-only
```

- 只在 **stage1 还活着** 时执行；
- stage2 入口会自动做一次 Darwin `0x16` 保活读，用户不需要手动发命令；
- 如果报 `oem peek ... unknown cmd`，按上面的第 3 条处理，不要重复加载。

加载成功后，直接用标准 fastboot：

```sh
fastboot getvar version-bootloader
fastboot getvar all
fastboot oem partition
```

## 3. 备份

按标准 fastboot 分区方式保存：

```sh
fastboot fetch nflasha1  nflasha1.bin
fastboot fetch nflasha2  nflasha2.bin
# ... 16 个用户分区
fastboot fetch nflashaB0 nflashaB0.bin
fastboot fetch nflashaB1 nflashaB1.bin
```

也可以 `fetch nflasha` 一次读取“所有真实分区 + 分区表”，再按已知
offset/size 拆分。备份目录应保留分区清单和 SHA-256。

> 备份范围说明：`fetch nflasha` 覆盖到 SDM2 分区范围 `0x54800000`；
> 其后的 512 MiB 未分区尾部为全 0。需要逐字节完整块设备镜像时，
> 用 Linux 持久会话读取 `/dev/nflasha`（1.8 GB）。

## 4. 恢复

从原始备份按分区恢复：

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup \
  --partitions nflasha3,nflasha7
```

- 只写入显式列出的用户分区；
- 第一次建议先用 `nflasha10` 做恢复演练；
- `nflashaB0/B1` 的写入尚未验证，救砖时对启动区要单独确认；
- 恢复后按说明回读校验，再重启。

## 5. 收尾

```sh
fastboot reboot
```

或使用 `pico/reset_only.py` / 关机再开，退出 fastboot。

## 实机验证

发布镜像已在 ZV-E10 上验证长会话、eMMC 初始化和 12 MB 分区读取。

## 注意事项

- **不要在 stage2 已运行时重复加载**：`oem peek` 会返回 `unknown cmd`；
  复位 → 重注 stage1 → 立刻加载 stage2。
- **不要漏掉 30 秒换线窗口**：错过就重新注入。

## 限制

- 下载暂存 1 MiB；原始镜像 >1 MiB 需要 sparse 分片；
- 不提供 `erase`，stage2 没有分区写保护；
- B0/B1 写入未验证；
- 不覆盖 RPMB、OTP/eFuse 或硬件故障。
