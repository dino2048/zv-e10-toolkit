# USB 串流

[English](usb-streaming.md)

初代 ZV-E10 的 USB 串流不在 **USB 连接**设置中。USB 连接只有 Auto、Mass Storage
和 MTP 三项。

## 启动官方模式

1. 断开 USB 线。
2. 将相机切换到视频模式，并先设定所需的对焦和曝光。
3. 选择 **MENU → Camera Settings2 → USB Streaming**。
4. 屏幕显示 `USB Streaming: Not Connect` 后重新连接 USB 线。

Sony 规定的格式为 1280×720 MJPEG、30 或 25 fps，以及 48 kHz、16 bit 双声道
PCM 音频。串流期间不能录像、操作菜单、进入回放、使用 PC Remote 或连接手机。详见
[Sony ZV-E10 官方帮助指南](https://helpguide.sony.net/ilc/2070/v1/en/contents/TP1000201566.html)。

## 不泄露序列号的主机验证

在 Linux 上运行：

```sh
./scripts/probe_usb_streaming.sh --duration 10
```

探针依赖 `lsusb`、`v4l2-ctl`、`arecord` 和 `ffmpeg`。它确认串流 USB 身份、选择
MJPEG 采集节点、将视频与音频采集到空目标，并报告收到的帧数。它不会输出相机序列号，
也不会保存视频帧或音频。不要公开未经筛选的 `v4l2-ctl --all`、`pactl` 或 udev
输出，因为这些输出可能包含序列号。

## 已验证的 Linux 结果

固件 `30110_05.2025031501` 使用与服务访问相同的普通 USB-C 线完成验证：

- USB 身份为 `054c:0de3`，连接速度为 USB 2 high-speed；
- UVC MJPEG，1280×720，30 fps；
- 10 秒空目标测试收到 299 帧，无传输错误；
- USB Audio PCM，signed 16-bit little-endian，双声道，48 kHz；
- 主机检测到 OBS Studio 33；UVC 和 ALSA 设备可直接用作 Video Capture Device
  与 Audio Input Capture 来源。

此测试只证明主机端持续接收，不能证明端到端延迟。测量延迟需要让相机拍摄持续变化的
参考时钟，再将参考时钟与收到的画面比较。
