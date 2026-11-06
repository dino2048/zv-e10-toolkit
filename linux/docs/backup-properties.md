# Backup properties / Backup 属性

Backup properties are Sony camera settings addressed by numeric IDs. They are **not** eMMC backup images. Linux root shell commands and Backup service requests are different interfaces. These actions reuse Sony-PMCA-RE's existing `readBackup`, `writeBackup` and `saveBackup`; no new protocol implementation or direct BK4-file editing is involved.

Start the existing persistent terminal server first, then wait for its `state.json` to say `ready`. Use one service connection at a time. All commands below run from `linux/`.

```sh
./scripts/run_terminal.sh
.venv/bin/python -B host/zve10_terminal_client.py --request-json '{"action":"backup-read","id":"0x01071C54"}'
```

The read reports the exact value as hex and saves a unique private snapshot in the session directory. Do not publish these snapshots: arbitrary properties may contain device secrets.

For an explicitly authorized write, start the server with `--owner-authorized-write`. Request `backup-write` with the property ID, **exact previously read original bytes** in `expected`, and the desired bytes in `value`. These strings are hex; original/new lengths must match and be 1–512 bytes. The tool saves/fsyncs the original privately **before** writing, invokes `saveBackup(id >> 16)`, and immediately rereads it. A mismatch or action error stops the session; never blindly retry after an uncertain USB result. Use the same guarded request to restore the exact saved original, not a whole old database.

This toolkit deliberately contains **no camera-feature-specific property list, unlock values, country selection, or patch offsets**. The caller is responsible for understanding the chosen property and compatibility. Authorization to open a root shell is not by itself a decision about which camera settings should change.

Project integrations can import the existing server, set its optional `REQUEST_HANDLER(camera, request, session, write_mode)` callable, and call `main()`. The hook receives non-shell/non-close actions on the **same authenticated connection**. The existing server still owns queue validation, ready/executing state, timeout, terminal teardown and StopSenser. With no hook, built-in `backup-read`/`backup-write` actions use `host/zve10_backup_properties.py`. A hook can narrow permitted properties and delegate to that same module. There is no second service connection or new server implementation.

This addition has offline fake-camera tests only, including read-only refusal, exact-old-value checks, private snapshot preservation, save/readback, existing queue dispatch, hook connection identity and normal/error teardown. The underlying methods have prior research use; this packaged toolkit integration is not newly camera-tested.

---

Backup 属性是按数字 ID 访问的相机设置，不是 eMMC 备份镜像。root shell 是 Linux 终端；属性读写走 Sony 服务协议，直接调用 Sony-PMCA-RE 已有方法。

先启动原有持久会话并确认 `ready`。只读会话可读属性，写入必须使用 `--owner-authorized-write`，请求中给出完整原值 `expected` 和新值 `value`（均为十六进制，长度相同）。工具先私密保存并落盘原值，再写入、调用 Sony 保存接口、立即读回。错误会结束会话；结果不确定时不要重复写。恢复时写回该相机的原始值，不整库覆盖。

通用 toolkit 不内置 Wi-Fi 解锁编号、地区配置或补丁偏移；这些规则归各功能项目。功能项目通过小型动作入口复用现有服务端和客户端，通用 Backup 读写只维护一份。新增集成仅完成离线测试，本轮未连接相机。
