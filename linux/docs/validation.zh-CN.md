# 兼容性与验证

**简体中文** | [English](validation.md)

## 平台与固件

| 路线 | 平台 / 系统 | 覆盖范围 |
| --- | --- | --- |
| USB 服务 | macOS、ZV-E10 2.02 | 终端、文件读取、双遍原始备份、BootROM 读取 |
| USB 服务 / Jiritsu | macOS、ZV-E10 2.03 | 持久 shell、完整原始备份、取消备份 |
| USB 服务 / Jiritsu | Windows 10、ZV-E10 2.03 | 环境安装、持久 shell、完整原始备份、完整库读取、Backup 属性写入 |
| Fastboot | macOS | 分区读取、raw/sparse 写入、读回校验、恢复 |

配套 Wi-Fi 项目还验证了 Windows 2.03 下的属性修改和库恢复/补丁操作。Windows 当前覆盖 USB 服务路线；BootROM 提取、文件备份及 Fastboot 需分别确认平台适用性。

## 备份测量

使用 4 MiB 分块和独立 8 MiB RAM 缓冲，用户区与 B0/B1 共 1,962,934,272 字节，相机/主机逐块哈希及保存文件的独立重读哈希一致。完整一遍在 macOS 耗时 940.956 秒（1.989 MiB/s），Windows 耗时 916.141 秒（约 2.04 MiB/s）。这是测试相机上包含备份处理的一遍耗时，不是保证速度或纯 USB 速率。

性能测量各执行一遍。修改前使用时建议独立读取两遍，再[校验保存文件并比较差异](verification.zh-CN.md)。运行中可写数据可能变化；备份完整性校验不等于恢复测试。

## 开发检查

构建与回归测试命令见[开发说明](../../CONTRIBUTING.md)。缓冲配置见 [Jiritsu 指南](jiritsu.zh-CN.md)，清理及异常处理见[会话操作规范](agent-workflow.zh-CN.md)。
