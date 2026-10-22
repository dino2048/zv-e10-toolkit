# Backup method

## Scope

The raw backup targets exactly three block-device nodes:

| Node | Bytes |
|---|---:|
| `/dev/nflasha` | 1,954,545,664 |
| `/dev/nflashaB0` | 4,194,304 |
| `/dev/nflashaB1` | 4,194,304 |

`nflasha` is the whole Linux-visible user area, including inter-partition
gaps. The two `B` nodes are boot areas. This is the complete read-only scope of
the current channel on the tested firmware; it is not a physical chip dump.

## Preconditions

Before any read:

1. `/version.txt` must equal `30110_05.2025031501` (configurable with
   `--expect-version`).
2. The camera terminal is opened only to read `/proc/partitions`,
   `/proc/mounts`, and `/sys/class/block/nflasha*` metadata, then closed.
3. The live sizes reported by `/proc/partitions` must match the table above.
4. The host must have at least `2 * total + 1 GiB` free space.

## Two passes

Every region is read twice, sequentially. For each pass:

1. Open a `.bin.part` file with mode `0600`.
2. Stream the FileControl response into a sink that:
   - writes bytes to disk;
   - updates a whole-file SHA-256;
   - records a SHA-256 for every 1 MiB chunk (the final partial chunk is also
     recorded);
   - prints progress every 10 seconds.
3. Check the response status and the exact expected length.
4. `flush()` and `fsync()` the file.
5. Rename `.bin.part` to `.bin` only after the pass succeeds.
6. Re-open the finished file, re-read it from the host disk, and compare the
   SHA-256 with the receive-time hash. Abort on mismatch.

The two reads are never overwritten. If they differ, both files and the
per-MiB comparison stay in the manifest.

## Manifest

`manifest.json` contains:

- `scope` — a one-line description of what was and was not done;
- `reads` — one row per pass: device, iteration, expected/actual bytes,
  response code, duration, whole-file SHA-256, per-MiB hashes, host re-read
  hash, completion flag;
- `metadata` — raw `/proc/partitions`, `/proc/mounts`, and sysfs layout output;
- `comparisons` — per device: identical or not, and which 1 MiB chunks differ;
- `completed`, `service_returned`, `terminal_closed`, and `error` if any.

`SHA256SUMS` is generated separately for easy offline checking.

## Observed result

On the reference run:

- user area passes took about 152 s and 155 s (roughly 12 MiB/s);
- boot areas were identical across passes;
- the user area differed in 916 bytes across 8 sectors, confined to the
  settings partition and an active MPR region (see the project notes);
- every other partition slice matched between passes.

## Limits

- The camera is running while the read happens. Partitions mounted read-write
  can change. The two-pass diff makes this visible; it does not eliminate it.
- The image is what the driver exposes, not a verified physical layout.
- No RPMB, OTP/eFuse, or hidden area is included.
- There is no write-back or restore test. A backup is not a proven rescue
  image.
