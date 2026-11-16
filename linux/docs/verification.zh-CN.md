# 校验

**简体中文** | [English](verification.md)

所有校验都是离线的，不连接相机。

## Windows

在 `linux/` 目录的 PowerShell 中，把 `$backupDir` 换成备份动作返回的 `backup_dir`：

```powershell
$python = '.\.venv\Scripts\python.exe'
$backupDir = 'session\backup-01\raw-backup-<时间戳>'
& $python -B .\host\zve10_verify.py manifest --manifest (Join-Path $backupDir 'manifest.json')
& $python -B .\host\zve10_verify.py sums --sums (Join-Path $backupDir 'SHA256SUMS')
$manifest = Get-Content -Raw (Join-Path $backupDir 'manifest.json') | ConvertFrom-Json
$manifest.comparisons | ConvertTo-Json -Depth 5
```

两条校验命令都应通过。双遍备份还要逐区审阅 `identical` 和 `differing_1MiB_chunks`。运行中可写数据有差异时保留两份文件，查清后再用于恢复；读取完成本身不代表两遍相同。

## manifest

```sh
.venv/bin/python host/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-<时间戳>/manifest.json
```

对每条读取检查：文件存在、大小等于 `expected_bytes` 和 `bytes`、整文件 SHA-256 等于接收时哈希、主机重读哈希一致、每 MiB 分块哈希一致（`--no-chunks` 跳过最后一项）。

## SHA256SUMS

```sh
.venv/bin/python host/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-<时间戳>/SHA256SUMS
```

标准 `sha256sum` 格式，路径相对于 sums 文件解析。

## 分区切片

```sh
.venv/bin/python host/zve10_verify.py slices \
  --read1 backups/zve10-raw-emmc-<时间戳>/nflasha.read1.bin \
  --read2 backups/zve10-raw-emmc-<时间戳>/nflasha.read2.bin \
  --layout examples/partitions.sample.tsv \
  --json slice-report.json
```

布局文件每行 `name offset size`（十进制或 `0x` 十六进制）。工具对两遍分别计算切片哈希；对不一致的切片，报告差异字节数和每个不同的 512 字节扇区。差异是数据，不是工具失败；加 `--fail-on-difference` 可在有差异时返回非零。

## 通过校验能证明什么

- 镜像与 manifest 内部一致；
- 主机保存的正是它接收到的字节；
- 两遍一致的区域在采集窗口内没有变化。

不能证明镜像等于物理 eMMC 布局，也不能证明它可以恢复。
