# Sony ZV-E10 service-interface and BootROM tools

**English** | [简体中文](README.zh-CN.md)

This repository contains two sets of tools for the Sony ZV-E10. `linux/` reads files, eMMC and BootROM through the USB service interface after the camera starts Linux. `bootrom/` uses Pico serial injection to provide memory access, eMMC partition reads and writes, and partition recovery from backups before Linux starts. Some data can be read through either route.

| Route | Entry | Capabilities | Start here |
|---|---|---|---|
| `linux/` | USB service connection after the camera boots Linux | Root terminal, file extraction, raw eMMC backup, BootROM extraction, offline verification | [Linux guide](linux/README.md) |
| `bootrom/` | Pico serial injection of stage1, then USB loading of stage2 | Bare-metal memory access, fastboot partition reads, raw/sparse writes and partition recovery | [Bare-metal guide](bootrom/README.md) |

## Operating conditions and tasks

- When the camera starts and accepts a USB service connection, use the [Linux tools](linux/README.md) for terminal access, file reads or backups.
- To prepare backups for comparison or later partition recovery, read eMMC twice and run [offline verification](linux/docs/verification.md).
- If Linux cannot start but BootROM injection and payload USB communication work, follow the [partition recovery guide](bootrom/docs/recovery.md) to restore supported user partitions from an existing backup.

## Layout

```text
linux/
  host/                     Computer-side terminal, extraction, backup and checks
  scripts/                  Setup and launchers
  helpers/bootrom-reader/   BootROM helper running under camera Linux
  docs/                     Service-mode and operation guides
  examples/                 Manifest and partition-layout examples
  requirements.txt          Python dependencies for this route
bootrom/
  stage1/                   First stage: USB transport and memory access
  stage2/                   Second stage: eMMC / fastboot and offline tests
  host/                     Computer-side loading, backup comparison and recovery
  pico/                     Pico firmware, protocol and injection tools
  tools/                    ABI checks and sparse-image generation
  prebuilt/                 Approved paired payloads and full SHA-256 hashes
  docs/                     Wiring, memory reads and partition recovery
  Makefile                  Build, check and test entry point
  requirements.txt          Python dependencies for this route
```

Run commands from the relevant route directory. The Linux environment, vendor
checkout, backup and session directories are rooted in `linux/`. Published payloads live in `bootrom/prebuilt/`; intermediate build outputs are excluded.
See [development and validation](CONTRIBUTING.md) for building and testing.

## Current scope

- Existing hardware validation covers ZV-E10 firmware `30110_05.2025031501` with macOS hosts.
- Bare-metal reads, writes, sparse images, readback and partition recovery have hardware validation records. An approximately four-minute external reset requires batching longer operations.
- The recovery script supports 16 user partitions; it does not handle boot0/boot1, the partition table or hardware faults.
- The Linux route reads a 24 KiB BootROM range. See [memory read documentation](bootrom/docs/exploration.md) for the permitted bare-metal `peek` ranges.
- No Sony firmware, BootROM dumps, service key tables or device backups are included. Research history and raw evidence live outside this publication repository.

## Sources and acknowledgements

- [ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) (MIT): USB service transport; the Linux setup script fetches it separately.
- [DavidBuchanan314/ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE): parts of the BootROM stage1/stage2 DWC3, USB, SDHCI, register and I/O code are ported or adapted from its `payloads/fastboot` implementation. The upstream repository does not currently state a redistribution license.
- [cokeenet/zve10-qemu](https://github.com/cokeenet/zve10-qemu) (MIT): UART boot protocol, partition map and hardware reference.
- [YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload) and [leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research) (MIT): Jiritsu and service-mode research.
- [xyzhangxin/sony-a6700-powerful](https://github.com/xyzhangxin/sony-a6700-powerful) (GPL-3.0): Pico/CC method reference.
- [ma1co/OpenMemories-Platform](https://github.com/ma1co/OpenMemories-Platform) (MIT): BootROM base address reference.
- [ma1co/fwtool.py](https://github.com/ma1co/fwtool.py) (MIT) and [DavidBuchanan314/fwtool.py](https://github.com/DavidBuchanan314/fwtool.py): firmware-unpacking research; not bundled.

Use only on devices you own or are authorized to service. Not affiliated with or
endorsed by Sony. See [LICENSE](LICENSE) for the repository's MIT license;
upstream code retains its own rights.
