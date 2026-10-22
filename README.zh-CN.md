# zv-e10-toolkit

**简体中文** | [English](README.md)

面向 Sony ZV-E10 的备份、服务模式、BootROM 与 fastboot/eMMC 工具箱。
在固件 `30110_05.2025031501`、macOS 上实测。

## 工具

| 工具 | 用途 | 相机端影响 |
|---|---|---|
| `tools/zve10_backup_raw.py` | 读取内核暴露的用户区和 B0/B1，各读两遍，保存原始镜像和哈希 | 无 |
| `tools/zve10_backup_files.py` | 通过服务终端复制指定普通文件 | 无 |
| `tools/zve10_verify.py` | 离线校验 manifest、`SHA256SUMS` 和分区切片 | 无 |
| `tools/zve10_terminal_server.py` + 客户端 | 服务 shell；默认只读白名单 | 默认无；可选写模式 |
| `tools/zve10_read_file_jiritsu.py` | 可选的 Jiritsu `GET_FILE` 文件读取 | 无 |
| `tools/zve10_bootrom_dump.py` | 通过 `/dev/mem` 两遍读取 BootROM（实验性） | `/tmp_bt` tmpfs 中的临时助手 |
| `fastboot/` | Pico 注入的 fastboot payload 和 stage2 eMMC 读取（手动，需要硬件） | SRAM payload；不写 eMMC |

## Fastboot / eMMC（手动）

`fastboot/` 是另一条硬件路径：Pico BootROM 串口注入 → DWC3 fastboot payload →
stage2 eMMC 块读取。需要 Pico、470Ω 复位线、CC1/CC2 并接后 5.1kΩ 下拉、电池保持和手动构建，不属于 Python 工具链。

- [fastboot/README.md](fastboot/README.md)
- [硬件与接线](fastboot/docs/hardware.md)
- [USB 成功日志](fastboot/docs/usb-success.md)
- [eMMC 成功日志](fastboot/docs/emmc-success.md)

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

## 限制

- 没有写回、恢复或救砖路径。
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
- [Fastboot / eMMC](fastboot/README.md)

## 致谢

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)（MIT）——USB 服务模式传输与认证。
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload) 与 [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)——服务/Jiritsu 路径的公开前置工作。
- ILCE-7M4-RE 的 fastboot payload 与外部 zve10-qemu 参考——`fastboot/` 里的移植来源。

与 Sony 无关，也未获 Sony 认可。

## 许可证

MIT。见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
