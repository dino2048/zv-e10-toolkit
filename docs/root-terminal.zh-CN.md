# root 终端

服务认证之后，相机可以暴露一个调试终端。在实测的 ZV-E10 固件上，shell 的 Uid/Gid 为 0。

## 打开与关闭

- `camera.setTerminalEnable(True)` 打开终端。
- `dev.readTerminal()` 读取输出，`dev.writeTerminal(...)` 写入输入。
- `setTerminalEnable(False)` 关闭；服务端始终在 `finally` 中执行。

每条命令都带唯一的开始/结束标记，即使输出分片也能可靠归属。

## root 身份

`/proc/$$/status` 报告 `Uid: 0 0 0 0` 和 `Gid: 0 0 0 0`。相机的 busybox 可能没有编入 `id` applet，这不改变权限级别。

## 默认模式：只读

不传 `--owner-authorized-write` 时，只接受一小份白名单：
`cat`、`ls`、`find`、`ps`、`du`、`df`、`grep`、`head`、`tail`、`wc`、
`sha256sum`、`md5sum`、`stat`、`readlink`、`pwd`、`uptime`、`date`、`uname`、
`free`、`echo`、`id`、`dmesg`（可带 `busybox` 前缀）。

只读模式下还会拒绝：

- 单引号之外的 shell 元字符；
- `/dev/` 访问；
- `find` 的 `-exec`、`-delete`、`-fprint` 等动作参数。

命令必须单行 ASCII，最多 200 字符。空闲 10 分钟自动结束。

## 完整 shell

`--owner-authorized-write` 在该会话中解除白名单。灾难性命令黑名单仍然生效：文件系统/分区工具、块设备写入、递归删除、挂载操作、内核模块、关机重启。`--allow-module-swap` 额外允许 `insmod`/`rmmod`，且必须先开启写模式。

这些检查是护栏，不是安全边界。完整 shell 仍然可以损坏相机，仅面向设备机主。
