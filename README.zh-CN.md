# Sony ZV-E10 服务接口与 BootROM 工具

**简体中文** | [English](README.md)

本仓库包含两组适用于 Sony ZV-E10 的工具。`linux/` 通过相机启动后的 USB 服务接口读取文件、eMMC 和 BootROM；`bootrom/` 通过 Pico 串口注入程序，在 Linux 启动前提供内存访问、eMMC 分区读写和基于备份的分区恢复。两组工具对部分数据提供不同的读取方式。

| 路线 | 进入方式 | 主要能力 | 从这里开始 |
|---|---|---|---|
| `linux/`：Linux 系统内操作 | 相机启动 Linux 后，通过 USB 服务接口连接 | root 终端、文件提取、原始 eMMC 备份、BootROM 提取、离线校验 | [Linux 使用说明](linux/README.zh-CN.md) |
| `bootrom/`：BootROM 注入与裸机操作 | Pico 串口注入 stage1，USB 加载 stage2 | 裸机内存访问、fastboot 分区读取、raw/sparse 写入、分区恢复 | [裸机使用说明](bootrom/README.zh-CN.md) |

## 使用条件与操作

- 相机可启动并接受 USB 服务连接时，使用 [Linux 工具](linux/README.zh-CN.md)访问终端、读取文件或制作备份。
- 制作可供后续比对或分区恢复的备份时，读取两遍 eMMC 镜像并执行[离线校验](linux/docs/verification.zh-CN.md)。
- Linux 无法启动但 BootROM 注入及裸机 USB 通信正常时，可按[分区恢复说明](bootrom/docs/recovery.zh-CN.md)从已有备份恢复受支持的用户分区。

## 内容布局

```text
linux/                      Linux 系统内操作
  host/                     电脑端：终端、提取、备份与离线校验
  scripts/                  环境安装和启动入口
  helpers/bootrom-reader/   相机端：Linux BootROM 读取助手
  docs/                     服务模式与各项操作说明
  examples/                 备份清单与分区表示例
  requirements.txt          Linux 路线 Python 依赖
bootrom/                    BootROM 注入与裸机操作
  stage1/                   第一级：USB 传输与内存访问
  stage2/                   第二级：eMMC / fastboot；含离线测试
  host/                     电脑端：加载、备份比较与恢复
  pico/                     Pico 固件、协议和注入工具
  tools/                    ABI 校验与 sparse 生成
  prebuilt/                 正式配套镜像与完整 SHA-256
  docs/                     接线、内存读取和分区恢复说明
  Makefile                  统一构建、检查、测试入口
  requirements.txt          裸机路线 Python 依赖
```

每条路线的命令从各自目录执行；Linux 环境、依赖仓库、备份和会话输出也以 `linux/` 为根。
正式镜像集中在 `bootrom/prebuilt/`，不包含本地构建中间文件。构建和测试见 [开发说明](CONTRIBUTING.md)。

## 当前范围

- 现有文档的实机验证对象是 ZV-E10、固件 `30110_05.2025031501`，主机为 macOS。
- 裸机分区读写、sparse、回读校验和恢复已有实机记录；约 4 分钟外部复位限制仍存在，需要分批操作。
- 恢复脚本支持 16 个用户分区，不处理 boot0/boot1、分区表或硬件故障。
- Linux 路线读取的 BootROM 范围为 24 KiB；裸机 `peek` 允许的地址范围见[内存读取说明](bootrom/docs/exploration.zh-CN.md)。
- 本仓库不包含 Sony 固件、BootROM 镜像、服务密钥表或设备备份。研究历史与原始证据保留在发布仓库之外。

## 来源与致谢

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE)（MIT）：USB 服务模式传输；Linux 安装脚本单独下载。
- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE)：BootROM 两级程序中部分 DWC3、USB、SDHCI、寄存器定义和 I/O 代码移植或改编自其 `payloads/fastboot` 实现。上游仓库目前未声明再发布许可证。
- [cokeenet/zve10-qemu](https://github.com/cokeenet/zve10-qemu)（MIT）：UART 启动协议、分区表及硬件参考。
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload) 与 [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)（MIT）：Jiritsu 与服务模式研究参考。
- [xyzhangxin/sony-a6700-powerful](https://github.com/xyzhangxin/sony-a6700-powerful)（GPL-3.0）：Pico/CC 方法参考。
- [ma1co/OpenMemories-Platform](https://github.com/ma1co/OpenMemories-Platform)（MIT）：BootROM 基址参考。
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py)（MIT）与 [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py)：固件解包研究参考，未收入本仓库。

仅用于拥有或获授权维修的设备。项目与 Sony 无关，也未获 Sony 认可。
仓库的 MIT 许可见 [LICENSE](LICENSE)；上游代码仍保留其原有权利。
