# Memory and eMMC partition reads

[Bare-metal guide](../README.md) · [Linux route](../../linux/README.md)

Stage1 exposes USB memory access; stage2 provides eMMC and fastboot operations.

## Read memory

After injecting stage1 and moving camera USB to the host, before loading stage2:

```sh
fastboot oem peek:fe020000:100
```

Addresses and lengths are hexadecimal; this reads the first 256 bytes of stage1.
Reads are limited to 4 KiB with four-byte alignment. Allowed ranges are
`0xf0000000–0xf3ffffff` and `0xfe000000–0xfeffffff`. Choose addresses using the
hardware memory map; peripheral-register reads can have side effects.

`oem call` and `oem load` support program loading and execution.
`host/bootstrap.py` handles the complete stage2 handoff, including
fingerprinting the running stage1.

## Read eMMC

Load stage2, list partitions with `fastboot oem partition`, then export
one with `fastboot fetch <partition> <output>`. To compare with your backup:

```sh
.venv/bin/python host/backup_compare.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7
```

The backup needs `offline-verification.json`; see [recovery](recovery.md) to
create it. The four-minute session limit applies to reads too; plan batches for
large partitions.

## Read BootROM

The published bare-metal peek allow-list excludes ROM addresses, and stage2
has no ROM-copy command. Use the [Linux BootROM reader](../../linux/docs/bootrom-dump.md)
for extraction. Historical bare-metal extraction evidence remains in the research
project and is not presented as a ready-to-run command in this repository.
