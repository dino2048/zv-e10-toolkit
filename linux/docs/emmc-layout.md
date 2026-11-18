# eMMC capacity variants and read-only diagnostics

**English** | [简体中文](emmc-layout.zh-CN.md)

The user area and boot areas B0/B1 need not have the same capacities as the original test camera. Both backup paths now cross-check `/proc/partitions` (KiB) and sysfs (512-byte sectors), including device numbers. They require the known 16 ZV-E10 logical partitions to match the sample's offsets and sizes and fit inside the user area. Missing, duplicate, inconsistent or changed geometry stops backup.

The complete Linux-visible user area includes gaps and the tail beyond the last partition. Each boot area is read at its own confirmed size, without padding or truncation. The confirmed byte counts are saved in `manifest.json` under `regions`; free host space is calculated from them. Geometry is rechecked before each pass. Exact lengths, saved-file hashes and double-pass comparisons remain required. Boot-area differences stop completion; live user-area differences are retained for review. Successful reading is not proof that an image is safe to restore to another camera.

Current bounds are positive 4 KiB-aligned regions below 4 GiB, boot areas no larger than 32 MiB, and the unchanged sample logical layout. These are supported read-path bounds, not a claim that every eMMC has these sizes. No restore or WBI-write guard is relaxed. Capacity-variant support has offline tests, including the reported 1888 MiB user area and 2 MiB boot areas; it still needs hardware confirmation on that variant.

## Query through one existing ready session

Use the existing [session workflow](agent-workflow.md). On system 2.02 select the terminal backend; on 2.03 use the documented Jiritsu arguments. This action works through both backends, including a session started by the companion Wi-Fi tool. Do not open a second USB connection.

Windows example, from `linux/`, after the existing session is ready (replace the session path with yours):

```powershell
$python = '.\.venv\Scripts\python.exe'
$requestFile = 'session/emmc-info-request.json'
@{ action = 'emmc-info' } | ConvertTo-Json | Set-Content -LiteralPath $requestFile -Encoding UTF8
& $python -B .\host\zve10_terminal_client.py --session-dir session/backup-01 --request-file $requestFile
```

macOS/Linux:

```sh
.venv/bin/python -B host/zve10_terminal_client.py --session-dir session/backup-01 --request-json '{"action":"emmc-info"}'
```

`emmc-info` reads version, layout and available identity attributes such as CID/CSD, manufacturer and product name from sysfs. It does not write eMMC configuration, load kernel modules or run an `mmc` utility. Normal session setup still has its documented effects; Jiritsu uploads a temporary loader. Some Sony kernels do not expose chip identity: `identity_available: false` means unavailable, not a failed chip or proof of its model. Chip identity is optional and is not a prerequisite for geometry-validated backup.

The response is retained in the existing session's `responses/` directory. CID may include a device serial number: keep raw output private and redact serials/credentials before posting. Share the validated capacities, layout checks and available manufacturer/product name. Close normally and follow the backend's cleanup and power-removal instructions.

## Continue with a backup

For the existing system 2.03 Jiritsu session, use `raw-backup` with `passes: 2` as documented. System 2.02's terminal backend continues to use the original FileControl backup CLI: first finish/close the diagnostic session normally, then run `host/zve10_backup_raw.py` using the platform instructions. Do not run that standalone CLI while another server owns USB. Do not edit capacity constants or switch firmware to bypass a refusal. Preserve a failed manifest for review.

This change supports read-only backup, not cross-camera restoration. B0/B1 boot writing is not added; recovery must independently validate the target and the same camera's saved sizes. See [recovery scope](../../fastboot/docs/recovery.md).
