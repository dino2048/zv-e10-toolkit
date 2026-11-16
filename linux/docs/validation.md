# Compatibility and validation

**English** | [简体中文](validation.zh-CN.md)

## Platforms and firmware

| Route | Platform / system | Coverage |
| --- | --- | --- |
| USB service | macOS, ZV-E10 2.02 | Terminal, file reads, double-pass raw backup and BootROM reads |
| USB service / Jiritsu | macOS, ZV-E10 2.03 | Persistent shell, complete raw backup and cancellation |
| USB service / Jiritsu | Windows 10, ZV-E10 2.03 | Setup, persistent shell, complete raw backup, full library reads and Backup-property writes |
| Fastboot | macOS | Partition reads, raw/sparse writes, readback and recovery |

The companion Wi-Fi project also verified its property and library restore/patch actions on Windows 2.03. Windows coverage currently applies to the USB service route; BootROM extraction, file backup and Fastboot require separate platform qualification.

## Backup measurements

With 4 MiB chunks and a dedicated 8 MiB RAM buffer, the user area and B0/B1 totaled 1,962,934,272 bytes. Camera/host chunk hashes and independently reread saved-file hashes matched. Measured complete-pass times were 940.956 seconds on macOS (1.989 MiB/s) and 916.141 seconds on Windows (about 2.04 MiB/s). These are measurements from the tested camera, including backup processing, not guaranteed USB rates.

The performance runs each measured one pass. For use before modification, select two independent passes and [verify the saved files and comparisons](verification.md). Live writable data can change between passes; backup integrity checks do not constitute restoration testing.

## Developer checks

Build and regression-test commands are in [CONTRIBUTING.md](../../CONTRIBUTING.md). The [Jiritsu guide](jiritsu.md) describes buffer configuration and the [session workflow](agent-workflow.md) describes cleanup and error handling.
