# FileControl 读取路径

备份工具通过 Sony 的 FileControl 功能（pFunc `0xff01`）读取字节。它接收的是**路径**而不是 shell 命令，因此不需要相机终端或 root shell。

## 请求格式

```
struct.pack("<HH", cmd, filenameSize) + filename
```

- `cmd = 2` 表示 READ。1 是 WRITE，3 是 DELETE；本工具只发送 READ。
- `filename` 为 ASCII，按 4 字节边界补 NUL。
- 没有 offset 或 length 字段。相机返回整个对象，主机流式接收。

读取 `/version.txt` 时发送 `cmd=2`、`filenameSize=12` 和 `/version.txt\0`。

## 响应

- `response` 为 0 或 1 都按成功处理；两种都出现过。
- body 是对象的原始字节。
- 接收回调直接写盘并增量计算 SHA-256，因此 1.9 GB 的区域不需要一次性放进内存。

## 已验证目标

- `/version.txt`（19 字节）；
- `/bin/busybox`；
- 块设备节点 `/dev/nflasha7`、`/dev/nflasha`（1,954,545,664 字节）、`/dev/nflashaB0` 和 `/dev/nflashaB1`（各 4,194,304 字节）。

读取块设备节点返回的是当前内核为该节点暴露的字节。它不意味着能访问 RPMB、OTP/eFuse 或控制器隐藏区域。

## Jiritsu GET_FILE（可选替代路径）

另一条只读路径，实现在 `host/zve10_read_file_jiritsu.py`：

- AdjustControl block `0x1001`，command `0x4008`（`GET_FILE`）；
- payload `[mode=1][area=0][f2=1] + "/.." + 绝对路径`；
- 响应体用 AES-128-CTR 解密：密钥 `MD5("jiritsu team" 补零到 16 字节)`，IV `00..0f`。

备份工具**不**使用 Jiritsu。FileControl 可以直接读块设备节点，且更容易限制在固定目标上。

## 边界

- 通道需要成功认证的服务会话，也就要求相机能启动。
- 节点存在且容量明确，不代表每个地址都可读。工具会检查状态和精确长度，不匹配就中止。
- 两遍读取用于发现变化，不是冻结设备。
