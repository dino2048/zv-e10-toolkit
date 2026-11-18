# eMMC 容量差异与只读诊断

**简体中文** | [English](emmc-layout.md)

用户区和 B0/B1 启动区不必与最初测试机容量相同。两条备份路径现在都会交叉核对 `/proc/partitions`（KiB）与 sysfs（512 字节扇区），并核对设备号。16 个已知 ZV-E10 逻辑分区的起点、长度仍须与样表一致，且全部落在用户区内；缺失、重复、矛盾或发生变化的布局都会停止备份。

完整读取 Linux 暴露的用户区，包括分区间隙和最后一个分区之后的尾部。B0、B1 各按本机确认的实际容量读取，不补齐、不截短。确认的字节数保存在 `manifest.json` 的 `regions` 中，主机剩余空间也按它计算。每遍读取前重新核对布局，保留精确长度、保存文件哈希和双遍比较。启动区两遍不同会停止完成流程；活动用户区的差异保留供审阅。备份成功不代表可以将镜像恢复到另一台相机。

当前读取范围要求：容量为正、4 KiB 对齐、小于 4 GiB，启动区各不超过 32 MiB，逻辑布局与样表相同。这是现有读取路径的支持边界，不表示所有 eMMC 都是这些容量。恢复和 WBI 写入保护不放宽。容量适配已有离线测试，包含报告中的 1888 MiB 用户区和各 2 MiB 启动区；该变体仍待实机确认。

## 通过已有的唯一 ready 会话查询

沿用[会话操作规范](agent-workflow.zh-CN.md)。2.02 使用 terminal 后端，2.03 使用文档规定的 Jiritsu 参数。本动作可复用两个后端，也可复用 Wi-Fi 工具启动的会话；不要另开第二个 USB 连接。

Windows 在 `linux/` 目录执行，先确认已有会话为 `ready`，把路径替换为自己的会话：

```powershell
$python = '.\.venv\Scripts\python.exe'
$requestFile = 'session/emmc-info-request.json'
@{ action = 'emmc-info' } | ConvertTo-Json | Set-Content -LiteralPath $requestFile -Encoding UTF8
& $python -B .\host\zve10_terminal_client.py --session-dir session/backup-01 --request-file $requestFile
```

macOS/Linux：

```sh
.venv/bin/python -B host/zve10_terminal_client.py --session-dir session/backup-01 --request-json '{"action":"emmc-info"}'
```

`emmc-info` 读取版本、布局，以及内核通过 sysfs 提供的 CID/CSD、厂商、产品名等属性；不写芯片配置、不加载驱动模块、不执行 `mmc` 工具。建立会话仍有原文档说明的影响，Jiritsu 会临时上传载荷。部分 Sony 内核不提供芯片身份，`identity_available: false` 仅表示无法取得，不代表芯片故障，也不能据此猜型号。芯片身份是补充信息，不是通过容量及布局检查后进行备份的前提。

结果保存在当前会话的 `responses/` 内。CID 可能包含设备序列号，原始输出应私密保留，发布前删除序列号和凭据；可提供确认的容量、布局检查结果及能取得的厂商/产品名。结束后正常关闭，并按后端要求清理和断电。

## 接着进行备份

2.03 的已有 Jiritsu 会话按文档发送 `raw-backup`、`passes: 2`。2.02 terminal 后端继续使用原有 FileControl 备份 CLI：先完成并正常关闭诊断会话，再按本平台说明运行 `host/zve10_backup_raw.py`。其他服务端占用 USB 时不要启动独立备份 CLI。不要修改容量常量或切换固件绕过拒绝，保留失败清单供复核。

本次适配用于只读备份，不支持跨机恢复。没有新增 B0/B1 写入功能；恢复仍须独立检查目标与同一机身保存的实际容量。见[恢复范围](../../fastboot/docs/recovery.zh-CN.md)。
