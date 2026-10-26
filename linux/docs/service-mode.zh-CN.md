# 服务模式

本工具通过 Sony 服务模式（“Senser”协议）与相机通信，传输层由 Sony-PMCA-RE 实现。

## 前提

- 相机处于 **USB 海量存储**模式（不是自动，也不是 MTP），枚举为 `054c:0d95`。
- macOS 上需要原始 USB 访问权限；启动脚本通过 `osascript` + `launchctl asuser` 触发一次管理员弹窗。
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
