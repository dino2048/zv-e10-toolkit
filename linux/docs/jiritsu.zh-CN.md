# Jiritsu 持续会话与慢速原始备份

**简体中文** | [English](jiritsu.md)

Jiritsu 是相机 Linux 内的临时执行后端，用于 2.03 的服务终端和原始备份。它临时上传加载程序，不安装开机自启。连接与清理规则见[会话操作规范](agent-workflow.zh-CN.md)，平台范围和备份耗时见[兼容性与验证](validation.zh-CN.md)。

| 系统 | 路线 | 实测范围 |
|---|---|---|
| 2.02 `30110_05.2025031501` | 原终端 / FileControl | 已有完整双遍备份，约 12 MiB/s |
| 2.03 `30110_06.2026060501` | Jiritsu | 持续 root shell；4 MiB 分块完整用户区+B0/B1 单遍，940.956 秒 / 1.989 MiB/s |
| 2.02 | 可选 Jiritsu | 此后端尚未完成该版本实机验证 |

本机 2.03 的旧终端命令通道失败，启用终端前后 FileControl 都返回 `0x80`、0 字节。这是该设备/会话的结果，不能扩大成所有 2.03 都删除了该协议。

## 建立唯一连接

在 `linux/` 完成环境准备后：

```sh
./scripts/run_terminal.sh --backend jiritsu --firmware 2.03 --owner-authorized-exec --idle-timeout 3600
.venv/bin/python -B host/zve10_terminal_client.py
```

等待 `state.json` 为 `ready`。默认仍限制为只读命令；经机主授权的写操作还需给服务端加 `--owner-authorized-write`。命令在同一个 shell 执行，保留工作目录及变量，但不是完整 PTY，单条输出限 64 KiB。不要用结构化命令中的 `exit/exec/kill/trap/return` 结束或替换子 shell；客户端输入 `exit` 会关闭服务。

建立后端需要**临时向相机服务工作区上传自有的 440 字节载荷及脚本**，所以不能把整个流程称为“相机端零写入”。载荷在 `helpers/jiritsu-shell/` 有汇编源码和构建脚本，构建哈希与实测二进制一致。命令、结果及数据块放在唯一的、已验证为 tmpfs 的 `/tmp_network` 内存目录；不会安装开机自启 root。

启动时先完成两次精确固件版本核对，再发送相机自带的 MOUNT 命令（编号 `2`，参数 `00 00`），然后才检查旧载荷文件和上传。由相机固件在需要时创建 `/tmp/jiritsu`，再挂载维修工作区。初始化失败立即停止并报告命令及状态码，不重试上传。正常清理删除上传的文件，保留挂载点目录；这个目录可能在断电后仍然存在。

旧版 toolkit 缺少这项初始化。已有 2.03 代码证据表明，SET_FILE2 返回 `0x10000004` 表示打开目标文件之前挂载工作区失败；缺少挂载点只是可能原因，不能据此诊断所有相机。若初始化也失败，应保留完整错误，不格式化工作区。这次启动流程修改已有离线回归测试，尚未在社区报告故障的相机上验证。

## 慢速原始备份

另一终端复用同一会话：

```sh
.venv/bin/python -B host/zve10_terminal_client.py --timeout 3600 --request-json '{"action":"raw-backup","passes":1}'
# 安装前建议：独立双遍读取，使用专用 RAM 缓冲。
.venv/bin/python -B host/zve10_terminal_client.py --timeout 7200 --request-json '{"action":"raw-backup","passes":2,"chunk_kib":4096}'
# 单遍选项：独立 8 MiB RAM 缓冲，4 MiB 分块。
.venv/bin/python -B host/zve10_terminal_client.py --timeout 3600 --request-json '{"action":"raw-backup","passes":1,"chunk_kib":4096}'
# 可选 passes=2，执行独立双遍完整读取；客户端 --timeout 建议 7200。
```

范围为 Linux 暴露的整个 `/dev/nflasha`（1,954,545,664 字节，含间隙及尾部），以及 B0/B1 启动区各 4 MiB；每个设备都核对实时容量。不含 RPMB、OTP/eFuse 或隐藏区域，不提供镜像恢复。

root 默认每次读取 512 KiB 到内存；设置 `chunk_kib=4096` 时，先检查主机磁盘与相机内存，建立独立 8 MiB tmpfs，完成或取消后自动卸载并删除挂载点。分块通过同一个 Jiritsu 连接回传，逐块核对相机与主机 SHA-256，保存后再从电脑磁盘独立重读校验。结果位于私密会话目录的 `raw-backup-*`。只有精确长度和保存文件验证通过后，`.part` 才改为正式文件；不把部分数据标成完整。

4 MiB 分块使用专用缓冲，默认 512 KiB 使用共享缓冲；完整备份耗时见[测量说明](validation.zh-CN.md)。双遍读取时运行中的可写数据可能变化，保留两份镜像并审阅差异。

取消时不要强杀进程：

```sh
.venv/bin/python -B host/zve10_terminal_client.py --cancel-backup
```

取消在完整数据块之间处理，保留 `.part` 和未完成/已取消清单，连接继续用于清理。SIGINT/SIGTERM 也请求在边界停止。短读取消已实机验证：保留 8,912,896 字节和未完成清单，主机重读一致，取消后连接可继续。

## Windows 服务响应读取

Windows 默认使用 `host/zve10_senser.py`，按响应头声明的长度读取，核对序号与功能码，交换失败后停止使用该通道。macOS/Linux 保留原读取器。排查兼容性时可用 `ZVE10_SENSER_FRAMING=stock` 或 `length` 强制选择；一般使用无需设置。

## 结束和断电

客户端输入 `exit` 或提交 `close`。先删除并确认 `run.sh/libJit.so/out.txt` 不存在，再退出服务；等待 `state=closed`、`service_returned=true`、`loader_files_removed=true`。随后关机、拔 USB、取电池约 30 秒，结束剩余的内存进程。

实测先结束子 shell 再访问服务会导致 GET_FILE 超时；“先清理文件、关闭服务、再断电”的顺序成功。内部原因未确定，不能宣传任意子进程退出均可靠。发生超时可能留下临时文件，应保留状态并核查，不盲目覆盖旧载荷。
