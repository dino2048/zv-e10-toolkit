# Verification

All verification is offline. It reads backup files and never connects to the
camera.

## Manifest checks

```sh
.venv/bin/python tools/zve10_verify.py manifest \
  --manifest backups/zve10-raw-emmc-<stamp>/manifest.json
```

For each completed read this checks:

- the file exists next to `manifest.json`;
- size equals both `expected_bytes` and the recorded `bytes`;
- the whole-file SHA-256 equals the receive-time hash;
- the host re-read hash equals the same value;
- the per-MiB chunk hashes match (disable with `--no-chunks`).

Exit code is 0 only when every check passes.

## SHA256SUMS

```sh
.venv/bin/python tools/zve10_verify.py sums \
  --sums backups/zve10-raw-emmc-<stamp>/SHA256SUMS
```

Hash lines use the standard `sha256sum` format and are resolved relative to
the sums file.

## Partition slices

```sh
.venv/bin/python tools/zve10_verify.py slices \
  --read1 backups/zve10-raw-emmc-<stamp>/nflasha.read1.bin \
  --read2 backups/zve10-raw-emmc-<stamp>/nflasha.read2.bin \
  --layout examples/partitions.sample.tsv \
  --json slice-report.json
```

The layout file has one line per partition:

```
name offset size
```

`offset` and `size` accept decimal or `0x` hex. Blank lines and `#` comments
are ignored.

The tool hashes each slice in both reads and, for differing slices, reports
the differing byte count and every differing 512-byte sector. Differences are
**data, not a tool failure**: the camera is live during capture. Use
`--fail-on-difference` if you want a non-zero exit for differences.

## What a passing check proves

- The saved images are internally consistent with the manifest.
- The host saved exactly the bytes it received.
- If two reads agree, those regions did not change during the capture window.

## What it does not prove

- That the bytes match the physical eMMC layout.
- That the image is restorable or that the camera can be unbooted with it.
- That a region which changed is unimportant; the operator must interpret
  differences.
