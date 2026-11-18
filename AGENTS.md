# Agent entry point

## Public publication content

This is an independent public release repository under `publish/`. README pages are for users: title, language switch, purpose, platform support and usage links. Keep Agent instructions here, build/test instructions in CONTRIBUTING.md, and validation evidence in technical documentation. Keep local handoffs, session histories, deleted-file narratives and pending-commit notes outside the publication repository. Recommend two-pass backup verification without repeating the test body's pass count in user introductions. Preserve accurate support boundaries in the validation page; never claim unperformed validation. Keep Chinese and English navigation consistent.

Read README.md and [the session workflow](linux/docs/agent-workflow.md) ([中文](linux/docs/agent-workflow.zh-CN.md)) before camera access. For Jiritsu, also read linux/docs/jiritsu.md. For fastboot writes, use fastboot/docs/recovery.md. The owner's current instructions take precedence; documentation work does not authorize device access.

## One connection, complete preflight

- Prepare imports, dependencies, interpreter, paths and CLI help before requesting administrator access. Respect the owner's interpreter choice. Do not repeatedly launch privileged processes to discover host configuration errors.
- Reuse one persistent server/request queue for the entire task. Confirm state.json is ready before requests or owner menu interaction. An existing server owns USB even if a second probe cannot open it. Never open competing connections or launch one-shot probes to check a healthy session. Submit close only after all work, verification and cleanup are finished. The default idle timeout is 600 seconds after the last completed action; --idle-timeout 3600 allows an hour of idle time. Long active backups do not consume the idle budget.
- Check the exact system version twice. Known 2.02 and 2.03 versions have different supported paths. Do not silently override firmware guards or equate a package version with the installed camera system.
- Use the client for fixed read-only preflight commands: `busybox --list`, `busybox cat /proc/mounts`, `busybox cat /proc/meminfo`, and `busybox cat /proc/self/status`. Do not assume id, df, stat, free or other desktop commands exist. Use only applets listed by the camera. Read shell identity from /proc through a running shell; the `self` status belongs to the command process. Do not claim it proves a persistent shell PID; that needs an explicit shell-PID check within the authorized backend.
- Jiritsu GET_FILE is for ordinary files. It may return empty content for proc/sys pseudo-files. Read /proc and /sys using shell cat; empty GET_FILE content is not evidence of root loss, process death or an absent device.

## Windows hosts

- Use client --request-file for structured requests on Windows, especially commands, paths and confirmation text with spaces. Save a UTF-8 JSON object with ConvertTo-Json and Set-Content -Encoding UTF8. Inline JSON escaping in PowerShell 5.1 is not reliable for these values. Request-file input does not grant write authorization or supply owner consent.

- `linux/scripts/setup-windows.ps1` creates `.venv/Scripts/python.exe`, installs the pinned dependencies and Sony-PMCA-RE, and runs the server self-test. Add `-Proxy <url>` when downloads need a proxy (pip ignores `HTTP_PROXY`/`HTTPS_PROXY`); if pip reports an SSL error through a proxy, upgrade pip in the new environment first.
- Service mode needs the `libusb-win32` driver (Zadig) for both camera identities. The validated read-only session ran without administrator rights; use an elevated PowerShell only if opening the device reports access denied.
- Run `host/zve10_terminal_server.py` directly. The `.sh` launchers and `--client-uid` are macOS/Linux-only; the server sets the session directory ACL to the current user's SID.
- Windows uses `host/zve10_senser.py` (length-delimited replies); macOS/Linux keep the vendor reader. The libusb 1.0 DLL from `libusb-package` is opt-in (`ZVE10_LIBUSB1=1`); otherwise PyUSB would prefer it over the libusb0 backend and lose the camera.
- Validated on Windows system 2.03: read-only `inspect`, `boot-check`, a single-pass `raw-backup`, Backup-property writes, and the byte-patch plus `/usr` round trip. Not validated: WBI writing, 2.02, `fastboot/`, BootROM dump, and the file-backup route.

## RAM, backup and errors

- Raw backups discover user/B0/B1 capacities from matching proc/sysfs metadata and retain the known 16-partition layout guard. Do not replace this with fixed test-unit sizes, pad boot images, truncate the user tail, or accept conflicting geometry. The original 1864 MiB / 4 MiB values are evidence, not universal requirements. WBI capacity/write and restore guards remain independent. Use emmc-info on one ready session for optional sysfs identity; keep CID private and do not install helpers or write chip configuration to identify a device.

- Confirm mounts, not names. On the tested device /tmp_network is tmpfs limited to 1 MiB; /tmp is eMMC-backed. A full 1 MiB data chunk cannot coexist with command/result files in the original mount. Do not put backup chunks in flash directories or change shared mount limits.
- The public backup CLI defaults to 512 KiB. Larger chunks require an independently verified, dedicated tmpfs with checked capacity/content and sufficient free/reclaimable memory. A separately mounted 8 MiB tmpfs with 4 MiB chunks completed one full 2.03 backup in 940.956 seconds (1.989 MiB/s). The public raw-backup action now accepts chunk_kib=4096 and manages this lifecycle automatically. The default remains 512 KiB. Use the documented action rather than reconstructing a research launcher.
- Prefer existing structured actions and fixed commands. Preflight known limitations before starting a transaction. A refused/unsupported diagnostic is not by itself USB failure. Review response and state before reconnecting. The server may fail closed on a structured handler exception; do not claim every error preserves its connection.
- Do not make a broad catch-all that forces ready after errors. Unknown USB state, hash/size mismatch, uncertain writes and failed cleanup require stopping further mutations and retaining evidence. Never blindly retry injection, patching or WBI invalidation.
- Cancel raw backups with the supplied cancellation request; wait for a completed-block boundary and incomplete manifest. Do not SIGKILL the host process, discard partial evidence or mark an interrupted backup complete. Report full lengths, camera/host hashes, independent saved-file verification, pass count, timing scope and cleanup status. A live Linux image is not an atomic snapshot; single pass is not double-pass or restore validation.

## Cleanup order and handoff

1. Finish all reads/writes and their verification while shell and service remain alive.
2. Remove owned chunk/helpers, unmount only this session's dedicated tmpfs and remove its mountpoint. Verify /usr read-only if it was remounted. Never remove other sessions' files or unmount shared camera mounts.
3. Use normal close. Jiritsu removes/verifies run.sh, libJit.so and out.txt while its RAM child remains alive. Wait for state=closed, service_returned=true and loader_files_removed=true; separately verify any dedicated mount cleanup. Legacy terminal uses terminal_closed=true.
4. Ask the owner to switch off, wait for access lamp, unplug USB and remove the battery for about 30 seconds. This ends the remaining RAM shell. Do not terminate it first and then attempt GET_FILE cleanup: that ordering repeatedly timed out on the tested device; the internal cause is unresolved.

A physically connected cable does not prove USB enumeration. Inspect host state once (on macOS, `ioreg -p IOUSB -w 0`) and distinguish absent enumeration, service authentication failure, unsupported commands and transfer failure. If absent after session exit, a USB replug may be needed; a RAM shell may still exist. Do not infer a lost root from absent USB. Inspect preserved state before any new loader upload. State cleanup flags are per session, not evidence from a prior run.

Keep firmware, raw backups, device identity, credentials, keys and runtime logs private. Do not push or publish without the owner's instruction. State what was actually validated and what remains unknown.
