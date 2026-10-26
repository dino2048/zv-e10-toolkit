# 校验

所有校验都是离线的，不连接相机。

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
