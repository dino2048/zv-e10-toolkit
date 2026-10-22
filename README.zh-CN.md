# zv-e10-toolkit

**简体中文** | [English](README.md)

面向 Sony ZV-E10 的只读优先工具合集：eMMC 原始备份、文件级备份、离线校验，以及机主授权的服务终端。

> **这不是救砖工具。** 它没有块设备写回路径，没有恢复命令，也无法恢复一台已经无法启动的相机。仓库不包含任何 Sony 固件、二进制、密钥、证书或设备数据。

## 能做什么

| 工具 | 用途 | 是否写相机 |
|---|---|---|
| `tools/zve10_backup_raw.py` | 读取内核暴露的用户区和 B0/B1，各读两遍，保存原始镜像和哈希 | 否 |
| `tools/zve10_backup_files.py` | 通过服务终端用 `dd` + `base64` 复制指定普通文件 | 否 |
| `tools/zve10_verify.py` | 校验 manifest、`SHA256SUMS`，按分区比较两遍读取 | 否（离线） |
| `tools/zve10_terminal_server.py` + 客户端 | 机主授权的服务 shell；默认只读白名单 | 默认否 |
| `tools/zve10_read_file_jiritsu.py` | 可选的 Jiritsu `GET_FILE` 只读文件读取 | 否 |

## 实测环境

- Sony ZV-E10，固件 `30110_05.2025031501`
- macOS（Apple Silicon，Homebrew libusb）
- 其他机型或固件可能也能进入服务模式，但固定的设备路径和容量是 ZV-E10 专用的，未验证。

## 依赖

- Python 3.10+
- [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)（MIT），提供 USB 服务模式传输
- `pyusb`、`pycryptodomex`
- macOS：`libusb`（`brew install libusb`），每次运行需要一次管理员弹窗授权
- 相机必须处于 **USB 海量存储**模式，不能是自动/MTP
- eMMC 原始备份约需 4 GB 空闲空间（两遍 1.82 GiB + 启动区），另加 1 GiB 余量

## 安装

```sh
./scripts/setup.sh
```

脚本会创建 `.venv/`、安装 Python 依赖，并把 Sony-PMCA-RE 克隆到 `vendor/Sony-PMCA-RE`。仓库本身不包含 Sony 的任何内容。

## 快速开始

```sh
# eMMC 原始备份（双读；相机处于海量存储模式）
./scripts/run_raw_backup.sh

# 文件级备份（设置、证书、/etc、/version.txt）
./scripts/run_file_backup.sh --phase critical

# 离线校验
.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-*/manifest.json
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-*/SHA256SUMS

# 服务终端（默认只读）
./scripts/run_terminal.sh
# 然后在另一个终端运行：
.venv/bin/python tools/zve10_terminal_client.py
```

完整 shell（高风险，需机主显式授权）：

```sh
./scripts/run_terminal.sh --owner-authorized-write
```

## 原始备份产物

```
backups/zve10-raw-emmc-<时间戳>/
├── nflasha.read1.bin
├── nflasha.read2.bin
├── nflashaB0.read1.bin  nflashaB0.read2.bin
├── nflashaB1.read1.bin  nflashaB1.read2.bin
├── manifest.json          # 长度、整文件哈希、每 MiB 哈希、元数据
└── SHA256SUMS
```

每个文件在接收时计算 SHA-256，完成后 `fsync`，再从主机磁盘独立重读并重新计算哈希，一致后才改名为正式文件。

## 做不到什么

- 不能把镜像写回相机、不能恢复备份、不能救砖。
- 不能读取 RPMB、OTP/eFuse 或存储控制器隐藏区域。
- 不是原子快照：rw 挂载的分区在两遍读取之间可能变化。两份镜像都会保留，差异会如实报告，不会被隐藏。
- 不保证 Linux 驱动暴露的视图等于物理芯片布局。
- 相机如果无法启动到接受服务会话的程度，工具无法工作。

## 安全与法律

- 默认只读；完整 shell 需要显式标志。
- 仅用于你拥有或有权维修的设备。
- 服务模式是未公开的厂商接口。当地法律（反规避条款、保修、服务条款）可能限制你的使用方式。本仓库不构成法律意见。
- 不包含也不重新分发任何 Sony 固件、二进制、服务软件、证书或设备数据。

详见 [docs/safety-legal.zh-CN.md](docs/safety-legal.zh-CN.md)。

## 文档

- [服务模式](docs/service-mode.zh-CN.md)
- [root 终端](docs/root-terminal.zh-CN.md)
- [FileControl 读取路径](docs/filecontrol-read.zh-CN.md)
- [备份方法](docs/backup-method.zh-CN.md)
- [校验](docs/verification.zh-CN.md)
- [安全与法律](docs/safety-legal.zh-CN.md)
- [相关工作](docs/related-work.zh-CN.md)

## 致谢

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)（MIT）——USB 服务模式认证与传输。
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload) 与 [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)——服务/Jiritsu 路径的公开前置工作。本项目没有复制它们的代码。
- 本项目与 Sony 无关，也未获 Sony 认可。

## 许可证

MIT。见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
