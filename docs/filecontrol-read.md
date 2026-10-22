# FileControl read path

The backup tools read bytes through Sony's FileControl function, pFunc
`0xff01`. This path is useful because it reads a **path**, not a shell command,
so it does not require opening the camera terminal or obtaining a root shell.

## Request format

The Senser packet payload is:

```
struct.pack("<HH", cmd, filenameSize) + filename
```

- `cmd = 2` means READ. Command 1 is WRITE and command 3 is DELETE; this
  toolkit only sends READ.
- `filename` is ASCII, NUL-padded to a 4-byte boundary.
- There is no offset or length field. The camera decides what the path refers
  to and returns the whole object; the host streams the response.

Example: reading `/version.txt` sends `cmd=2`, `filenameSize=12`, and
`/version.txt\0`.

## Response

- `response` 0 or 1 is treated as success; both are observed in practice.
- The body is the raw bytes of the object.
- The host receive callback writes bytes directly to disk and updates a
  SHA-256, so a 1.9 GB region does not need to fit in memory.

## What can be read

Observed successfully on the tested firmware:

- `/version.txt` (19 bytes);
- `/bin/busybox`;
- block-device nodes such as `/dev/nflasha7`;
- the whole `/dev/nflasha` node (1,954,545,664 bytes);
- `/dev/nflashaB0` and `/dev/nflashaB1` (4,194,304 bytes each).

Reading a block-device node returns the bytes the running kernel exposes for
that node. It does **not** imply access to RPMB, OTP/eFuse, or controller
hidden areas.

## Why this matters for backups

- No shell command entry is needed for the data path.
- The host can enforce a fixed target list.
- The same channel can be validated twice and hashed end to end.
- It does not depend on the camera's userland permissions: the service
  firmware performs the read.

## Boundaries

- The channel requires a successfully authenticated service session, which in
  turn requires the camera to boot.
- A node's existence and size do not prove every address is readable; the tool
  checks the returned length and response status and aborts on mismatch.
- The camera-side implementation may read a live, changing block device. Two
  passes are used to detect changes, not to freeze the device.
