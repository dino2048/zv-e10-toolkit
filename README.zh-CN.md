# zv-e10-toolkit

**简体中文** | [English](README.md)

面向 Sony ZV-E10 的只读备份与服务模式工具箱。
在固件 `30110_05.2025031501`、macOS 上实测。

## 工具

| 工具 | 用途 | 是否写相机 |
|---|---|---|
| `tools/zve10_backup_raw.py` | 读取内核暴露的用户区和 B0/B1，各读两遍，保存原始镜像和哈希 | 否 |
| `tools/zve10_backup_files.py` | 通过服务终端复制指定普通文件 | 否 |
| `tools/zve10_verify.py` | 离线校验 manifest、`SHA256SUMS` 和分区切片 | 否 |
| `tools/zve10_terminal_server.py` + 客户端 | 服务 shell；默认只读白名单 | 默认否 |
| `tools/zve10_read_file_jiritsu.py` | 可选的 Jiritsu `GET_FILE` 只读文件读取 | 否 |

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

.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

./scripts/run_terminal.sh
.venv/bin/python tools/zve10_terminal_client.py
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

## 限制

- 没有写回、恢复或救砖路径。
- 原始镜像是 Linux 驱动暴露的内容，不是物理芯片转储；不含 RPMB、OTP/eFuse 或隐藏区域。
- 不是原子快照：rw 分区在两遍读取之间可能变化。两份镜像都会保留，差异如实报告。
- 要求相机能启动到接受服务会话的程度。
- 只在上述固件实测；设备路径和容量是 ZV-E10 专用的。

## 说明

- 仅用于你拥有或有权维修的设备。
- 仓库不包含 Sony 固件、二进制、服务密钥表或设备数据。
- 服务模式是未公开的厂商接口，当地法律可能限制使用。这不是法律意见。

## 文档

- [服务模式](docs/service-mode.zh-CN.md)
- [root 终端](docs/root-terminal.zh-CN.md)
- [FileControl 读取路径](docs/filecontrol-read.zh-CN.md)（含可选的 Jiritsu 路径）
- [备份方法](docs/backup-method.zh-CN.md)
- [校验](docs/verification.zh-CN.md)

## 致谢

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)（MIT）——USB 服务模式传输与认证。
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload) 与 [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)——服务/Jiritsu 路径的公开前置工作。

与 Sony 无关，也未获 Sony 认可。

## 许可证

MIT。见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
