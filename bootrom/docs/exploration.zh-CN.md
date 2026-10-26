# 内存与 eMMC 分区读取

[裸机入口](../README.zh-CN.md) · [Linux 路线](../../linux/README.zh-CN.md)

stage1 提供 USB 内存访问；stage2 提供 eMMC 与 fastboot 分区操作。

## 读取内存

注入 stage1 并将相机 USB 换到电脑后，在加载 stage2 之前，可以执行：

```sh
fastboot oem peek:fe020000:100
```

地址与长度均为十六进制，示例读取 stage1 开头的 256 字节。
每次最多读取 4 KiB，地址按 4 字节对齐；允许范围为
`0xf0000000–0xf3ffffff`、`0xfe000000–0xfeffffff`。
具体地址需要结合芯片和寄存器含义判断，读取外设寄存器可能有副作用。

`oem call`、`oem load` 供程序加载与执行使用，加载 stage2 的完整流程由
`host/bootstrap.py` 处理，包括正在运行的 stage1 指纹校验。

## 读取 eMMC

加载 stage2 后，用 `fastboot oem partition` 列出分区，
再用 `fastboot fetch <分区名> <输出文件>` 导出原始分区内容。
需与已有备份比较时：

```sh
.venv/bin/python host/backup_compare.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7
```

备份目录应包含 `offline-verification.json`，生成方法见 [恢复说明](recovery.zh-CN.md)。
约 4 分钟会话限制同样适用于只读操作，大分区需规划分批读取。

## BootROM 读取

当前发布的裸机 `peek` 白名单不包含 ROM 地址，stage2 也未提供 ROM 复制命令。
需要提取 BootROM 时，使用 [Linux BootROM 读取工具](../../linux/docs/bootrom-dump.zh-CN.md)。
裸机提取方法的历史验证材料保留在研究项目中，不作为本仓库现成的操作入口。
