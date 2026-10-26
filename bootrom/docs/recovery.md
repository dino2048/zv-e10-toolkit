# User-partition recovery

[Bare-metal guide](../README.md) · [Wiring](hardware.md)

Restore user partitions from trusted backups when Linux cannot boot. BootROM
injection, stage1 USB communication and eMMC access must still work. Partition
recovery has hardware validation records; the current script does not handle
boot0/boot1, partition tables or physical hardware faults.

## Preparation

1. While the camera boots, make and verify raw backups using the [Linux route](../../linux/README.md). Keep both reads and hashes.
2. Generate `offline-verification.json` from both user-area reads and a checked partition layout using the commands below. It contains partition names, offsets, sizes and `read1_sha256`.
3. Install this route's Python dependencies and Android platform-tools. Put `fastboot` on PATH or pass `--fastboot /path/to/fastboot`.
4. Use the published `prebuilt/` pair. Host tools check full payload hashes and fingerprint the running stage1 before handoff.

## Generate the recovery report from Linux backups

Run from `linux/`. Check the sample layout against your camera's
`/proc/partitions` and `/sys/class/block` before using it; do not apply it to
other models or firmware without verifying offsets and capacities.

```sh
BACKUP=/path/to/backup
.venv/bin/python tools/zve10_verify.py manifest --manifest "$BACKUP/manifest.json"
.venv/bin/python tools/zve10_verify.py sums --sums "$BACKUP/SHA256SUMS"
.venv/bin/python tools/zve10_verify.py slices \
  --read1 "$BACKUP/nflasha.read1.bin" --read2 "$BACKUP/nflasha.read2.bin" \
  --layout examples/partitions.sample.tsv --json "$BACKUP/offline-verification.json"
```

The first two checks should pass. The slice report records differences between
reads; decide which content is appropriate before restoring a changing writable
partition. Recovery defaults to read1 and checks its slice hashes. The manifest
and partition report serve different purposes and are not interchangeable.

## Prepare offline first

Run from `bootrom/`, using this route's `.venv/` interpreter.
Replace the backup path and choose partitions appropriate to the fault and backup.

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7 \
  --prepare-only --out-dir /tmp/zve10-recovery-prep
```

This slices the backup, creates sparse images and checks hashes without connecting
to a camera. It uses the included `tools/make_sparse.py`. Invalid ranges, lengths or hashes stop execution before any device access.

## Flash and read back

Wire the hardware and inject stage1, then run:

```sh
.venv/bin/python host/restore_rescue.py \
  --backup-dir /path/to/backup --partitions nflasha3,nflasha7
```

The script loads writable stage2, flashes the named partitions as sparse images,
and verifies readback. Check the results before rebooting. An approximately
four-minute external reset requires batching longer restores and reinjecting
stage1 for each session. The tool writes only explicitly named user partitions and does not automatically reboot.
