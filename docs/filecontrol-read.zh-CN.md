# FileControl 读取路径

备份工具通过 Sony 的 FileControl 功能（pFunc `0xff01`）读取字节。它的价值在于读取的是**路径**而不是 shell 命令，因此不需要打开相机终端，也不需要拿到 root shell。

## 请求格式

Senser 包 payload：

```
struct.pack("<HH", cmd, filenameSize) + filename
```

- `cmd = 2` 表示 READ。1 是 WRITE，3 是 DELETE；本工具只发送 READ。
- `filename` 为 ASCII，按 4 字节边界补 NUL。
- 没有 offset 或 length 字段。由相机决定路径指向什么，并返回整个对象；主机流式接收。

例如读取 `/version.txt` 时发送 `cmd=2`、`filenameSize=12` 和 `/version.txt\0`。

## 响应

- `response` 为 0 或 1 都按成功处理；两种都在实测中出现过。
- body 是对象的原始字节。
- 主机接收回调直接写盘并增量计算 SHA-256，因此 1.9 GB 的区域不需要一次性放进内存。

## 能读什么

在实测固件上已成功读取：

- `/version.txt`（19 字节）；
- `/bin/busybox`；
- 块设备节点，如 `/dev/nflasha7`；
- 整个 `/dev/nflasha` 节点（1,954,545,664 字节）；
- `/dev/nflashaB0` 和 `/dev/nflashaB1`（各 4,194,304 字节）。

读取块设备节点返回的是当前内核为该节点暴露的字节。它**不**意味着能访问 RPMB、OTP/eFuse 或控制器隐藏区域。

## 对备份的意义

- 数据路径不需要 shell 命令入口。
- 主机可以强制固定目标列表。
- 同一通道可以双读校验并做端到端哈希。
- 不依赖相机用户态权限：读取由服务固件执行。

## 边界

- 通道需要成功认证的服务会话，也就要求相机能启动。
- 节点存在且容量明确，不代表每个地址都可读；工具会检查返回长度和状态，不匹配就中止。
- 相机端读取的是活的、可能变化的块设备。两遍读取用于发现变化，不是冻结设备。
