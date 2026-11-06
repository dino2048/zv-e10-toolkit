# Linux 系统内操作

**简体中文** | [English](README.md)

本目录提供通过 ZV-E10 USB 服务接口使用的主机工具，包括终端连接、文件读取、eMMC 备份、BootROM 读取和离线校验。使用时相机需能够启动 Linux 并接受 USB 服务连接。

以下命令均在 `linux/` 目录执行（先从仓库根目录运行 `cd linux`）。
分区读写与恢复见 [Fastboot 路线](../fastboot/README.zh-CN.md)；它通过 Pico 的 BootROM 注入进入。
在固件 `30110_05.2025031501`、macOS 上实测。

## 目录

```text
host/                     电脑端 Python 工具
scripts/                  安装、启动和权限处理
helpers/bootrom-reader/   在相机 Linux 中执行的读取助手
examples/                 备份清单与分区布局示例
docs/                     操作说明
```

## 工具

| 工具 | 用途 | 相机端影响 |
|---|---|---|
| `host/zve10_backup_raw.py` | 读取内核暴露的用户区和 B0/B1，各读两遍，保存原始镜像和哈希 | 无 |
| `host/zve10_backup_files.py` | 通过服务终端复制指定普通文件 | 无 |
| `host/zve10_get_file.py` | 通过 FileControl READ 读取单个指定文件 | 无 |
| `host/zve10_verify.py` | 离线校验 manifest、`SHA256SUMS` 和分区切片 | 无 |
| `host/zve10_usb_stream_probe.py` | 验证官方 UVC 视频和 USB Audio，不输出相机序列号或保存媒体 | 无 |
| `host/zve10_terminal_server.py` + 客户端 | 服务 shell；默认只读白名单 | 默认无；可选写模式 |
| `host/zve10_read_file_jiritsu.py` | 可选的 Jiritsu `GET_FILE` 文件读取 | 无 |
| `host/zve10_bootrom_dump.py` | 通过 `/dev/mem` 两遍读取 BootROM | `/tmp_bt` tmpfs 中的临时助手 |

## 安装

```sh
./scripts/setup.sh
```

脚本创建 `.venv/`、安装 Python 依赖，并把 [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) 克隆到 `vendor/`。
需要 Python 3.10+、`libusb`、相机处于 USB 海量存储模式，以及约 4 GB 空闲空间。

## 快速开始

```sh
./scripts/run_raw_backup.sh
./scripts/run_file_backup.sh --phase critical
./scripts/probe_usb_streaming.sh --duration 10

.venv/bin/python host/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python host/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

./scripts/run_terminal.sh
.venv/bin/python host/zve10_terminal_client.py

./scripts/run_bootrom_dump.sh --owner-authorized-exec
```

完整 shell：

```sh
./scripts/run_terminal.sh --owner-authorized-write
```

## 原始备份产物

```
backups/zve10-raw-emmc-<时间戳>/
├── nflasha.read1.bin   nflasha.read2.bin
├── nflashaB0.read1.bin nflashaB0.read2.bin
├── nflashaB1.read1.bin nflashaB1.read2.bin
├── manifest.json
└── SHA256SUMS
```

每个文件接收时计算 SHA-256，`fsync` 后从主机磁盘独立重读并重新计算哈希，一致后才改名为正式文件。

## Backup 属性与功能扩展

现有持久终端服务端新增结构化 `backup-read` 和需明确写入授权的 `backup-write`，客户端与 USB 连接继续复用。它们操作相机设置属性，不是磁盘备份镜像。详见 [Backup 属性操作及动作扩展接口](docs/backup-properties.md)，包含原值校验、私密快照、保存及读回。Wi-Fi 等功能项目可复用小型动作入口，不再各自实现服务会话。新增集成仅做离线测试，本轮未连接相机。

## 限制

- 本目录的 Python 工具没有镜像写回或分区恢复功能；`../fastboot/` 提供分区恢复
  （见其 README）。
- 原始镜像是 Linux 驱动暴露的内容，不是物理芯片转储；不含 RPMB、OTP/eFuse 或隐藏区域。
- 不是原子快照：rw 分区在两遍读取之间可能变化。两份镜像都会保留，差异如实报告。
- 要求相机能启动到接受服务会话的程度。
- BootROM 转储只覆盖已验证的 `0xffff0000–0xffff5fff`，并从 tmpfs 执行一个临时助手。
- 只在上述固件实测；设备路径和容量是 ZV-E10 专用的。

## 说明

- 仅用于你拥有或有权维修的设备。
- 仓库不包含 Sony 固件、二进制、服务密钥表或设备数据。
- BootROM 转储属于 Sony 固件内容。请私密保存，不要提交。
- 服务模式是未公开的厂商接口，当地法律可能限制使用。这不是法律意见。

## 文档

- [服务模式](docs/service-mode.zh-CN.md)
- [root 终端](docs/root-terminal.zh-CN.md)
- [FileControl 读取路径](docs/filecontrol-read.zh-CN.md)（含可选的 Jiritsu 路径）
- [备份方法](docs/backup-method.zh-CN.md)
- [校验](docs/verification.zh-CN.md)
- [BootROM dump](docs/bootrom-dump.zh-CN.md)
- [USB 串流](docs/usb-streaming.zh-CN.md)
- [Fastboot / eMMC](../fastboot/README.zh-CN.md)

与 Sony 无关，也未获 Sony 认可。

## 许可证

见 [LICENSE](../LICENSE) 与[项目来源及致谢](../README.zh-CN.md#来源与致谢)。
