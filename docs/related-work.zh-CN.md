# 相关工作

本项目建立在公开工作的基础上。下文引用这些机制作为背景；它们的代码没有复制进本仓库。

## Sony-PMCA-RE

[github.com/ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) —— MIT。

提供 USB 传输、海量存储到服务模式的切换、Senser 认证实现、包 framing，以及终端读写原语。本工具通过依赖引用它，而不是把代码搬进来。

## a7c2-service-preload

[github.com/YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload)

公开工作，指出 Sony 工厂服务（Senser/Jiritsu）中的路径穿越和库加载链。许可证请查看该仓库。本项目不包含也不复制那条利用链。

## sony-a7iv-feature-research

[github.com/leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)

记录了 A7 IV 上的只读 Jiritsu dump 方法。可选的 `zve10_read_file_jiritsu.py` 是对公开文档中 `GET_FILE` 请求的独立实现，包含公开资料记录的密钥推导和路径穿越写法。它**不**被备份工具使用。

## Jiritsu 读取路径简述

- AdjustControl block `0x1001`，command `0x4008`（`GET_FILE`）。
- payload：`[mode=1][area=0][f2=1] + "/.." + 绝对路径`。
- 响应体为 AES-128-CTR 加密；密钥为 `MD5("jiritsu team" 补零到 16 字节)`，IV 为 `00..0f`。
- 读取路径与服务模式的 FileControl 是两条独立通道，不需要 root shell。

本工具把 Jiritsu 排除在备份主路径之外，因为 FileControl 可以直接读块设备节点，且更容易限制在固定目标上。

## 本项目增加了什么

- 固定目标、双遍读取、端到端哈希的原始备份，以及离线校验器。
- 基于服务终端的文件级备份。
- 默认只读、写模式需机主显式授权的服务终端。
- 说明这些镜像能证明什么、不能证明什么。

## 不包含

本仓库不包含任何 Sony 固件、固件解包、BootROM 转储、相机二进制、服务软件、证书、Sony Senser 认证密钥表、设备数据或备份镜像。
