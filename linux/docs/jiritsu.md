# Jiritsu shell and slow raw backup

**English** | [简体中文](jiritsu.zh-CN.md)

Jiritsu is a temporary execution backend for the service shell and raw backups on camera system 2.03. It uploads a temporary loader without installing a boot service. See the [session workflow](agent-workflow.md) for connection/cleanup and [compatibility and validation](validation.md) for platforms and backup timings.

| System | Backend | Evidence |
|---|---|---|
| 2.02 `30110_05.2025031501` | existing terminal / FileControl | Full double raw backup previously tested, about 12 MiB/s |
| 2.03 `30110_06.2026060501` | Jiritsu | Persistent shell; complete user+B0/B1 single pass with 4 MiB chunks, 940.956 seconds / 1.989 MiB/s |
| 2.02 | optional Jiritsu | Not yet camera-tested as this backend |

The old terminal command path failed on the tested 2.03 device. FileControl returned `0x80` with zero data even after terminal enable. This is a result on that device/session, not proof of a universal firmware protocol removal.

## Start one connection

From `linux/`, after setup:

```sh
./scripts/run_terminal.sh --backend jiritsu --firmware 2.03 --owner-authorized-exec --idle-timeout 3600
.venv/bin/python -B host/zve10_terminal_client.py
```

Wait for `state.json` to say `ready`. Default command restrictions still apply. Add `--owner-authorized-write` to the server only for owner-approved write operations. Commands use one persistent shell; this is not a PTY. Replies are limited to 64 KiB. Do not terminate or replace the shell with `exit`, `exec`, `kill`, `trap` or `return`; the client's `exit` closes the service instead.

Starting this backend **temporarily writes our 440-byte loader and script to the camera service workspace**. The loader has assembly source and a reproducible build in `helpers/jiritsu-shell/`; its hash matches the camera-tested binary. Commands/results/chunks live in a unique verified `/tmp_network` tmpfs directory. There is no boot-time installation. This is not a zero-camera-write backup method.

## Slow raw backup

In a second terminal on the same session:

```sh
.venv/bin/python -B host/zve10_terminal_client.py --timeout 3600 --request-json '{"action":"raw-backup","passes":1}'
# Recommended before installation: two independent reads, dedicated RAM buffer.
.venv/bin/python -B host/zve10_terminal_client.py --timeout 7200 --request-json '{"action":"raw-backup","passes":2,"chunk_kib":4096}'
# Single-pass alternative: dedicated 8 MiB RAM buffer, 4 MiB chunks.
.venv/bin/python -B host/zve10_terminal_client.py --timeout 3600 --request-json '{"action":"raw-backup","passes":1,"chunk_kib":4096}'
# Optional: passes=2 for two independent full reads; use client --timeout 7200.
```

Scope: entire Linux-visible `/dev/nflasha` (1,954,545,664 bytes, including gaps/tail) and `/dev/nflashaB0`, `/dev/nflashaB1` (4 MiB each). Each live capacity is checked. No RPMB, OTP/eFuse or hidden chip areas. This does not implement image restoration.

The default is 512 KiB chunks. With `chunk_kib=4096`, host disk and camera memory are checked, a dedicated 8 MiB tmpfs is mounted, and it is unmounted/removed on success or cancellation. Jiritsu transfers each chunk; camera and host SHA-256 must match. Saved files are independently reread on the host. Output and metadata stay under the private session's `raw-backup-*` directory. `.part` is renamed only after exact length and saved-file verification; incomplete output is never marked complete.

4 MiB chunks use the dedicated buffer; the default 512 KiB uses the shared workspace. See [measurements](validation.md) for full-backup timings. Live writable data may change between passes; preserve both images and review their differences.

Cancel without killing the process:

```sh
.venv/bin/python -B host/zve10_terminal_client.py --cancel-backup
```

Cancellation is checked between completed blocks, preserves `.part` and a cancelled/incomplete manifest, and keeps USB available for cleanup. SIGINT/SIGTERM request the same boundary-safe stop. Short-read cancellation was hardware-tested: incomplete metadata and 8,912,896 bytes were retained, host reread matched, and the connection remained usable.

## Windows service-reply framing

Windows uses `host/zve10_senser.py` to read the declared reply length, check sequence/function identifiers and stop using a failed channel. macOS/Linux keep the vendor reader. `ZVE10_SENSER_FRAMING=stock` or `length` overrides this for compatibility diagnosis; normal use needs no override.

## Close and remove power

Use the client `exit` or a structured `close`. The backend removes and verifies removal of `run.sh`, `libJit.so` and `out.txt` **before** ending the service. Wait for `state: closed`, `service_returned: true`, `loader_files_removed: true`. Then switch off, unplug USB and remove the battery for about 30 seconds. The remaining RAM process ends with power removal.

Stopping the child shell before its service connection repeatedly caused GET_FILE timeouts on the tested camera. The cleanup-first/service-close/power-removal handoff succeeded. Its internal cause is not established; this release does not claim arbitrary child-process termination is reliable. A timeout may leave temporary files: preserve state and inspect, never blindly re-upload over existing loader files.
