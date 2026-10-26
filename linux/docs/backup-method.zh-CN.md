# 备份方法

## 范围

| 节点 | 字节数 |
|---|---:|
| `/dev/nflasha` | 1,954,545,664 |
| `/dev/nflashaB0` | 4,194,304 |
| `/dev/nflashaB1` | 4,194,304 |

`nflasha` 是 Linux 可见的整个用户区，包含分区间隙；两个 `B` 节点是启动区。这不是物理芯片转储。

## 前置条件

1. `/version.txt` 等于 `30110_05.2025031501`（可用 `--expect-version` 覆盖）。
2. `/proc/partitions` 报告上述容量。
3. 至少 `2 × 总量 + 1 GiB` 空闲空间。

终端只用于读取 `/proc/partitions`、`/proc/mounts` 和 `/sys/class/block/nflasha*`，随后关闭。

## 双遍读取

每个区域、每一遍：

1. 以 `0600` 创建 `.bin.part`。
2. 把 FileControl 响应流式写入 sink：写盘、更新整文件 SHA-256、每 1 MiB 记录一个哈希。
3. 检查响应状态和精确长度。
4. `flush()` 并 `fsync()`。
5. 成功后才把 `.bin.part` 改名为 `.bin`。
6. 重新打开文件，从主机磁盘独立重读，与接收时哈希比较；不一致立即中止。

两遍结果都保留，差异如实报告，不覆盖。

## manifest

`manifest.json` 记录：

- `scope`；
- 每遍一行：设备、遍次、字节数、响应、耗时、整文件 SHA-256、每 MiB 哈希、主机重读哈希、完成标志；
- 原始 `/proc/partitions`、`/proc/mounts`、sysfs 布局；
- 每个设备的对比结果，以及不同的 1 MiB 块；
- `completed`、`service_returned`、`terminal_closed`，以及出错时的 `error`。

`SHA256SUMS` 单独生成，用于离线核对。

## 实测结果

- 用户区约 152 秒和 155 秒（约 12 MiB/s）；
- 启动区两遍一致；
- 用户区 916 字节、8 个扇区不同，集中在设置分区和一个活跃 MPR 区域；
- 其余分区切片两遍一致。

## 限制

- 读取时相机在运行，rw 分区可能在两遍之间变化。
- 镜像是驱动暴露的内容，不是经过验证的物理布局。
- 不含 RPMB、OTP/eFuse 或隐藏区域。
- 尚未通过这条 Linux 路线验证镜像写回或分区恢复。
