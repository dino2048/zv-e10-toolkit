# AI agent session and failure workflow

**English** | [简体中文](agent-workflow.zh-CN.md)

Read [AGENTS.md](../../AGENTS.md) before device access and [Jiritsu instructions](jiritsu.md) for that backend. These rules address observed mistakes; they do not establish every USB failure's internal cause.

## Prepare once, keep one connection

Check interpreter, imports, dependency paths and CLI help as the normal user before requesting administrator access. Reuse one server and request queue. Check state.json; wait for ready before the next request or owner menu interaction. The default idle timeout is 600 seconds after completion; --idle-timeout 3600 allows one idle hour. Active backup time does not consume this budget. Do not open competing probes against an existing server.

Run these camera commands through the existing read-only client:

```sh
busybox --list
busybox cat /proc/mounts
busybox cat /proc/meminfo
busybox cat /proc/self/status
```

Check the applet list before using commands. The tested camera has no id/df; do not assume desktop utilities such as stat or free exist. /proc/self/status identifies the cat process; verifying the persistent shell PID requires an explicit shell-PID status read within the backend.

GET_FILE handles ordinary files and may return empty proc/sys pseudo-file content. Read /proc and /sys using shell cat. Empty GET_FILE results do not establish loss of root or process death; the Jiritsu session reader rejects direct pseudo-file reads.

## RAM buffers

Mounts, not directory names, determine storage. The tested /tmp_network tmpfs is limited to 1 MiB; /tmp is eMMC-backed. Commands/results also occupy the small tmpfs, so a full 1 MiB data chunk does not fit. The public backup CLI defaults to 512 KiB.

Larger chunks were tested in a separate 8 MiB tmpfs, with commands staying in the original directory. Check free/reclaimable memory, exact mount identity, capacity and contents; unmount it and remove its mountpoint afterwards. Do not enlarge shared mounts, spill chunks into flash or touch another session's files.

A complete user+B0+B1 single pass with 4 MiB chunks took 940.956 seconds (1.989 MiB/s), with chunk and saved-file host checks passing. The public raw-backup action now accepts chunk_kib=4096 and manages the mount lifecycle automatically. Its integration has offline failure tests; the underlying RAM/read sequence has hardware validation. The default remains 512 KiB.

## Handle failures by cause

| Observation | Required response |
|---|---|
| Missing host dependency/path | Fix before privilege/USB startup |
| Refused command/missing applet | Review response and session state; this alone is not USB failure |
| Empty GET_FILE proc/sys content | Use shell cat; do not infer permission/process loss |
| Shared tmpfs too small | Stop increasing chunks; do not bypass checks or use flash |
| USB timeout, short read, hash mismatch, uncertain write | Stop further mutations, preserve evidence, no blind retry |
| Cable attached but no USB enumeration | Check host inventory once (macOS: ioreg -p IOUSB -w 0; Windows: Get-PnpDevice -PresentOnly, then filter InstanceId on VID_054C); ask for a replug if needed. The RAM shell may still exist |

Preflight predictable read-only failures before transactions. Research diagnostics can return reviewable failures instead of aborting the entire service. The public server may fail closed on structured-handler exceptions; do not claim every error preserves USB. Never broadly swallow exceptions and force ready after uncertain USB, writes or cleanup.

Cancel with the supplied --cancel-backup request, wait for a block boundary and result, preserve .part and incomplete metadata. Do not SIGKILL or mark interrupted output complete.

## Finish all work before cleanup

Complete operations and verification; remove owned temporary data/helpers; unmount only this session's dedicated tmpfs and remove its mountpoint; close service normally; then let owner power removal end the RAM shell. Restore /usr read-only first if remounted.

Jiritsu cleanup removes/verifies run.sh, libJit.so and out.txt while the child shell remains alive. Stopping that shell first and then doing GET_FILE cleanup repeatedly timed out. The internal cause remains unresolved.

A close response means accepted, not cleanup finished. Wait for state=closed, service_returned=true, loader_files_removed=true and any dedicated mount cleanup. Legacy terminal uses terminal_closed=true. Ask the owner to switch off, wait for the access lamp, unplug USB and remove the battery for about 30 seconds.

On failure, preserve this session's state; prior cleanup flags are not current evidence. Never overwrite existing loader files blindly. Distinguish complete single-pass reads, independent double passes, atomic snapshots and restoration. Complete 2.03 single pass is validated; double pass and restoration are not.
