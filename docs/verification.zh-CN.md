# 校验

所有校验都是离线的，只读取备份文件，不连接相机。

## manifest 校验

```sh
.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-<时间戳>/manifest.json
```

对每条已完成的读取检查：

- 文件存在于 `manifest.json` 同级目录；
- 大小同时等于 `expected_bytes` 和记录的 `bytes`；
- 整文件 SHA-256 等于接收时哈希；
- 主机重读哈希等于同一值；
- 每 MiB 分块哈希一致（可用 `--no-chunks` 跳过）。

只有全部通过时退出码才是 0。

## SHA256SUMS

```sh
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-<时间戳>/SHA256SUMS
```

哈希行使用标准 `sha256sum` 格式，路径相对于 sums 文件解析。

## 分区切片

```sh
.venv/bin/python tools/zve10_verify.py slices \
  --read1 backups/zve10-raw-emmc-<时间戳>/nflasha.read1.bin \
  --read2 backups/zve10-raw-emmc-<时间戳>/nflasha.read2.bin \
  --layout examples/partitions.sample.tsv \
  --json slice-report.json
```

布局文件每行一个分区：

```
name offset size
```

`offset` 和 `size` 支持十进制或 `0x` 十六进制。空行和 `#` 注释会被忽略。

工具对两遍读取分别计算每个切片哈希；对不一致的切片，报告差异字节数和每个不同的 512 字节扇区。差异是**数据，不是工具失败**：采集时相机在运行。若希望有差异时返回非零，加 `--fail-on-difference`。

## 通过校验能证明什么

- 保存的镜像与 manifest 内部一致；
- 主机保存的正是它接收到的字节；
- 如果两遍一致，这些区域在采集窗口内没有变化。

## 不能证明什么

- 字节等于物理 eMMC 布局；
- 镜像可恢复，或能让相机退出砖状态；
- 发生变化的区域不重要——差异需要人来解释。
