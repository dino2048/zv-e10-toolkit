# BootROM dump

通过服务终端对 ZV-E10 BootROM 做两遍只读转储。

## 方法

1. 主机校验固件基线，并确认 `/tmp_bt` 是 tmpfs。
2. 把 `payload/read_page.elf`（460 字节）上传到新建的 `/tmp_bt/br.XXXXXX` 目录，核对大小和 SHA-256。
3. 每个 4 KiB 页执行一次助手。助手以只读方式打开 `/dev/mem`，映射 `0xffff0000 + index * 0x1000`，把 4096 字节以十六进制输出后退出。
4. 所有页读两遍并比对，再写入 `dump.bin`。
5. 从相机删除助手和它的目录。

助手只读取映射页。相机端唯一的写入是 tmpfs 里的临时助手；不碰 eMMC、闪存、配置或内核模块。

## 已验证范围

`0xffff0000–0xffff5fff`（6 页，24 KiB），固件 `30110_05.2025031501`。两遍逐字节一致。

观察到的页结构：

| 页 | 内容 |
|---|---|
| 0 | ARM 向量表和启动代码 |
| 1 | Thumb 代码、字符串、数据 |
| 2 | Thumb 代码、十六进制表 |
| 3–4 | 全零 |
| 5 | 前 1 KiB 非零，其余全零 |

`0xffff6000` 及之后没有读取。助手只接受 0..5 的页索引，主机也会拒绝超出已验证范围的参数。

## 用法

```sh
./scripts/run_bootrom_dump.sh --owner-authorized-exec
```

选项：

- `--pages 1..6` —— 4 KiB 页数（默认 6）；
- `--passes 1|2` —— 2 表示已验证的双遍方法（默认 2）；
- `--keep-helper` —— 保留 `/tmp_bt` 里的助手，便于调试。

输出：

```
backups/zve10-bootrom-<时间戳>/
├── dump.bin
├── pages/pass1_seg0.bin ... pass2_seg5.bin
├── manifest.json
└── SHA256SUMS
```

## 要求与限制

- 相机处于 USB 海量存储模式；一次管理员弹窗；macOS 启动脚本。
- `/tmp_bt` 必须是 tmpfs 挂载；否则工具拒绝执行。
- 必须传 `--owner-authorized-exec`：这会在相机上执行代码。
- 已验证范围很小，助手也固定在这个范围。扩大范围需要重新构建并重新验证助手。
- 读取未验证地址可能让助手触发 SIGBUS/SIGSEGV。逐页读、失败即停，不要一次性映射大范围。
- 转储内容是 Sony 固件。请私密保存，不要提交，也不要放进本仓库。

## 替代路径：BootROM 串口注入

项目里还有一条已确认的 UART 注入路径（RP2040 → 相机 D−，GP27 复位，电池保持，**1 长 + 7 短** 表示 payload 在 SRAM 中执行）。这条路径在 Linux 启动之前就能用；见 [fastboot/README.zh-CN.md](../fastboot/README.zh-CN.md)。
