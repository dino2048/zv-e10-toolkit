# 用户分区恢复

[裸机入口](../README.zh-CN.md) · [硬件接线](hardware.zh-CN.md)

当 Linux 无法启动、BootROM 串口注入和 USB 通信仍可用时，可以通过裸机程序从已有备份恢复受支持的用户分区。
前提是串口注入、stage1 USB 通信及 eMMC 访问仍可工作。这条路线已有分区恢复实机记录；
当前脚本不处理 boot0/boot1、分区表和物理硬件故障。

## 准备

1. 相机正常时，用 [Linux 路线](../../linux/README.zh-CN.md)完成原始备份并校验，保留两遍镜像和哈希。
2. 准备恢复清单：在 `linux/` 目录，用自己的两遍用户区镜像和核对后的分区布局生成 `offline-verification.json`，命令见下文。它包含分区名称、偏移、大小和 `read1_sha256`。
3. 安装裸机路线的 Python 依赖和 Android platform-tools；`fastboot` 应在 PATH 中，也可用恢复工具的 `--fastboot /path/to/fastboot` 指定。
4. 使用随仓库发布的 `prebuilt/` 正式配套镜像；主机工具按完整 SHA-256 检查镜像，并在交接前校验正在运行的 stage1。

## 从 Linux 备份生成恢复清单

以下命令在 `linux/` 目录执行。示例布局来自已验证固件，使用前按本机的
`/proc/partitions`、`/sys/class/block` 核对偏移和容量，不要直接套用于其他固件或机型。

```sh
BACKUP=/path/to/backup
.venv/bin/python tools/zve10_verify.py manifest --manifest "$BACKUP/manifest.json"
.venv/bin/python tools/zve10_verify.py sums --sums "$BACKUP/SHA256SUMS"
.venv/bin/python tools/zve10_verify.py slices \
  --read1 "$BACKUP/nflasha.read1.bin" --read2 "$BACKUP/nflasha.read2.bin" \
  --layout examples/partitions.sample.tsv --json "$BACKUP/offline-verification.json"
```

前两项校验应通过。分区切片报告会记录两遍数据的差异；对于有差异的可写分区，
应先判断哪一份内容适合恢复。恢复工具默认使用 `read1`，并校验对应的切片哈希。
`manifest.json` 与分区清单用途不同，不能相互替代。

## 先做离线准备

以下命令从 `bootrom/` 执行，命令使用本路线 `.venv/` 中的解释器。
`/path/to/backup` 替换为实际备份目录，分区名按故障与备份内容选择。

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7 \
  --prepare-only --out-dir /tmp/zve10-recovery-prep
```

此模式在电脑上切片、生成 sparse 并核对备份哈希，不连接相机。
工具使用随仓库提供的 `tools/make_sparse.py`。范围、长度或哈希错误会在接触相机前终止。

## 写入并回读

接好硬件并注入 stage1，再执行：

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7
```

脚本加载可写 stage2，对指定分区执行 sparse 写入与回读校验。确认结果后再重启。
约 4 分钟外部复位限制仍存在，大量分区应分批恢复；重复会话需要重新注入 stage1。
恢复工具只写入显式指定的用户分区，不自动重启。
