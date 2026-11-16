# 服务模式

2.03 请使用 [Jiritsu 后端](jiritsu.zh-CN.md)。下文原有终端/FileControl 流程保留用于 2.02。

本工具通过 Sony 服务模式（“Senser”协议）与相机通信，传输层由 Sony-PMCA-RE 实现。

## 前提

- 相机处于 **USB 海量存储**模式（不是自动，也不是 MTP），枚举为 `054c:0d95`。
- macOS 上需要原始 USB 访问权限；启动脚本通过 `osascript` + `launchctl asuser` 触发一次管理员弹窗。
- Linux 上也需要原始 USB 访问权限；启动脚本优先通过 `pkexec` 提权，若 polkit 不可用则使用
  `sudo`。相机重新枚举为服务模式时，同一个提权进程会继续运行。
- Windows 上需要给相机的两个身份（`054c:0d95`、`054c:0336`）安装 `libusb-win32` 驱动（可用 Zadig）。已验证的只读会话在普通、非管理员 PowerShell 中运行；只有打开设备报 access denied 时才需要管理员。直接运行 `host/zve10_terminal_server.py`，`.sh` 启动器仅适用于 macOS/Linux。
- 需要 `libusb`。`zve10_common` 依次检查 `LIBUSB_PATH`、Homebrew 路径，最后回退到系统查找。

## 流程

1. **StartSenser** —— 向海量存储设备发送 Sony 私有 vendor request。
2. **重新枚举** —— 相机出现为 Senser 设备（`054c:0336`）。
3. **认证** —— PMCA-RE 的 `SonySenserAuthDevice.authenticate()` 执行 challenge/response。
4. **回调** —— 工具拿到 `SonySenserCamera`，发出固定的只读请求。
5. **StopSenser** —— 退出时 PMCA-RE 发送停止请求。相机回到海量存储模式；如果没有重新出现，拔插一次 USB。

## 副作用

服务认证本身可能更新相机上的 `/setting/.etools` 和 `/setting/.hasp`。本工具不执行这些写入，也不上传文件、不建立挂载、不写块设备；会话不是持久的。

## 边界

- 要求固件能启动到接受服务会话的程度。它不是 BootROM 路径。
- 协议未公开且依赖版本。只在 ZV-E10 固件 `30110_05.2025031501` 上实测。

## 持久会话与 Backup 属性

普通一次性回调返回后，服务连接随之结束；终端服务端则保持回调打开，直到关闭或空闲超时。结构化 Backup 属性写入仅在明确启用写模式时允许。读写接口及动作扩展见 [Backup 属性说明](backup-properties.md)。
