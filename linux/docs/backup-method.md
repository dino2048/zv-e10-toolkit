# Backup method

## Scope

| Node | Bytes |
|---|---:|
| `/dev/nflasha` | 1,954,545,664 |
| `/dev/nflashaB0` | 4,194,304 |
| `/dev/nflashaB1` | 4,194,304 |

`nflasha` is the whole Linux-visible user area, including inter-partition gaps.
The two `B` nodes are boot areas. This is not a physical chip dump.

## Preconditions

1. `/version.txt` equals `30110_05.2025031501` (`--expect-version` overrides).
2. `/proc/partitions` reports the sizes above.
3. At least `2 * total + 1 GiB` free space.

The terminal is opened only to read `/proc/partitions`, `/proc/mounts`, and
`/sys/class/block/nflasha*`, then closed.

## Two passes

For each region and each pass:

1. Open a `.bin.part` file with mode `0600`.
2. Stream the FileControl response into a sink that writes to disk, updates a
   whole-file SHA-256, and records a SHA-256 per 1 MiB chunk.
3. Check response status and exact length.
4. `flush()` and `fsync()`.
5. Rename `.bin.part` to `.bin` only after the pass succeeds.
6. Re-open the file, re-read it from the host disk, and compare the SHA-256
   with the receive-time hash. Abort on mismatch.

Both passes are kept. Differences are reported, never overwritten.

## Manifest

`manifest.json` records:

- `scope`;
- one row per pass: device, iteration, bytes, response, duration, whole-file
  SHA-256, per-MiB hashes, host re-read hash, completion;
- raw `/proc/partitions`, `/proc/mounts`, and sysfs layout;
- per-device comparison: identical or not, and differing 1 MiB chunks;
- `completed`, `service_returned`, `terminal_closed`, and `error` if any.

`SHA256SUMS` is written separately for offline checking.

## Observed run

- user area: about 152 s and 155 s (roughly 12 MiB/s);
- boot areas: identical across passes;
- user area: 916 differing bytes in 8 sectors, confined to the settings
  partition and an active MPR region;
- every other partition slice matched between passes.

## Limits

- The camera is running: read-write partitions can change between passes.
- The image is what the driver exposes, not a verified physical layout.
- No RPMB, OTP/eFuse, or hidden area.
- No write-back or restore test; this is not a proven rescue image.
