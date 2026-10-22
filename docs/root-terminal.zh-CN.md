# root 终端

服务认证之后，相机可以暴露一个调试终端。在实测的 ZV-E10 固件上，该 shell 的 Uid/Gid 为 0。它是 root shell，但本质是厂商调试设施，不是内存破坏漏洞。

## 终端如何打开

- `camera.setTerminalEnable(True)` 打开终端。
- `dev.readTerminal()` 读取输出，`dev.writeTerminal(...)` 写入输入。
- `setTerminalEnable(False)` 关闭。服务端始终在 `finally` 中关闭，包括出错时。

工具会给每条命令加上唯一的开始/结束标记，这样即使输出分片或延迟，也能可靠归属。

## root 身份

服务 shell 在 `/proc/$$/status` 中报告 `Uid: 0 0 0 0` 和 `Gid: 0 0 0 0`。相机的 busybox 可能没有编入 `id` applet，这不代表 shell 没有特权。

## 默认模式：只读

除非机主传入 `--owner-authorized-write`，终端服务默认只读。只读模式下：

- 只接受一小份白名单：`cat`、`ls`、`find`、`ps`、`du`、`df`、`grep`、`head`、`tail`、`wc`、`sha256sum`、`md5sum`、`stat`、`readlink`、`pwd`、`uptime`、`date`、`uname`、`free`、`echo`、`id`、`dmesg`（可带 `busybox` 前缀）；
- 单引号之外的 shell 元字符一律拒绝；
- 拒绝 `/dev/` 访问；
- 拒绝 `find` 的 `-exec`、`-delete`、`-fprint` 等动作参数。

命令必须单行、ASCII、不超过 200 字符。空闲 10 分钟自动结束。

## 完整 shell

`--owner-authorized-write` 会在该会话中解除白名单。灾难性命令黑名单仍然生效：文件系统/分区工具、块设备写入、递归删除、挂载操作、内核模块、关机重启都会被拒绝。`--allow-module-swap` 额外允许 `insmod`/`rmmod`，且必须先开启写模式。

这些检查是**护栏，不是安全边界**。拥有完整 shell 的用户仍然可以损坏相机。这个服务面向设备机主，不是给不可信用户用的沙箱。

## 这个工具不做什么

- 不读取 eMMC 镜像；那用 `zve10_backup_raw.py`。
- 不写块设备、不恢复备份。
- 本身不会让任何东西跨重启持久化。
