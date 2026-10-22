# 服务模式

本工具通过 Sony 服务模式（“Senser”协议）与相机通信，传输层由 Sony-PMCA-RE 实现。本文说明主机做了什么，以及相机会经历什么。

## 前提

- 相机通过 USB 连接，并设置为 **海量存储**（不是自动，也不是 MTP）。
- 海量存储模式下相机枚举为 `054c:0d95`。
- macOS 上宿主进程需要原始 USB 访问权限：使用仓库提供的启动脚本，它们通过 `osascript` + `launchctl asuser` 触发一次管理员弹窗。
- 需要 `libusb`。`zve10_common` 会依次尝试 `LIBUSB_PATH`、Homebrew 路径，最后才回退到系统查找。

## 流程

1. **StartSenser** —— 向海量存储设备发送 Sony 私有 vendor request。
2. **重新枚举** —— 相机离开海量存储模式，出现为 Senser 设备（`054c:0336`）。
3. **认证** —— PMCA-RE 的 `SonySenserAuthDevice.authenticate()` 执行 challenge/response。
4. **回调** —— 工具拿到 `SonySenserCamera` 对象，发出固定的只读请求。
5. **StopSenser** —— 退出时 PMCA-RE 发送停止请求。相机回到海量存储模式，可能需要几秒。如果没有重新出现，拔插一次 USB。

## 副作用

- 服务认证本身可能更新相机上的 `/setting/.etools` 和 `/setting/.hasp`。本工具不执行这些写入，它们属于厂商认证流程。
- 本工具不上传文件、不建立挂载、不写任何块设备。
- 服务会话是临时的，不会在相机上安装持久内容。

## 认证后能做什么

认证后的会话会暴露 Sony 的服务功能：产品信息、调节控制、文件控制、内存转储和调试终端。本仓库只使用：

- FileControl READ（pFunc `0xff01`）读取 `/version.txt` 和块设备节点；
- 服务终端执行固定元数据命令，以及可选的机主授权 shell。

## 边界

- 服务模式要求相机固件能启动到接受会话的程度。它不是 BootROM 路径，无法帮助启动早期就失败的相机。
- 协议未公开且依赖版本。本仓库只在 ZV-E10 固件 `30110_05.2025031501` 上实测。
