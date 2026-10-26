# Verification

All checks are offline; they never connect to the camera.

## Manifest

```sh
.venv/bin/python host/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-<stamp>/manifest.json
```

For each read: file exists, size matches `expected_bytes` and `bytes`, the
whole-file SHA-256 matches the receive-time hash, the host re-read hash matches,
and the per-MiB chunk hashes match (`--no-chunks` skips the last check).

## SHA256SUMS

```sh
.venv/bin/python host/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-<stamp>/SHA256SUMS
```

Standard `sha256sum` format, resolved relative to the sums file.

## Partition slices

```sh
.venv/bin/python host/zve10_verify.py slices \
  --read1 backups/zve10-raw-emmc-<stamp>/nflasha.read1.bin \
  --read2 backups/zve10-raw-emmc-<stamp>/nflasha.read2.bin \
  --layout examples/partitions.sample.tsv \
  --json slice-report.json
```

Layout lines are `name offset size` (decimal or `0x` hex). The tool hashes each
slice in both reads and, for differing slices, reports the differing byte count
and every differing 512-byte sector. Differences are data, not a tool failure;
add `--fail-on-difference` for a non-zero exit.

## What a pass proves

- The images are consistent with the manifest.
- The host saved exactly the bytes it received.
- If two reads agree, those regions did not change during capture.

It does not prove the image matches the physical eMMC layout, or that it can be
restored.
