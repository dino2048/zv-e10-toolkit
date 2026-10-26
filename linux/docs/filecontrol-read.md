# FileControl read path

The backup tools read bytes through Sony's FileControl function, pFunc
`0xff01`. It takes a **path**, not a shell command, so it does not require the
camera terminal or a root shell.

## Request format

```
struct.pack("<HH", cmd, filenameSize) + filename
```

- `cmd = 2` means READ. Command 1 is WRITE and 3 is DELETE; this toolkit only
  sends READ.
- `filename` is ASCII, NUL-padded to a 4-byte boundary.
- There is no offset or length field. The camera returns the whole object and
  the host streams the response.

Reading `/version.txt` sends `cmd=2`, `filenameSize=12`, and
`/version.txt\0`.

## Response

- `response` 0 or 1 is treated as success; both are observed.
- The body is the raw bytes of the object.
- The receive callback writes to disk and updates a SHA-256 incrementally, so
  a 1.9 GB region does not need to fit in memory.

## Verified targets

- `/version.txt` (19 bytes);
- `/bin/busybox`;
- block nodes `/dev/nflasha7`, `/dev/nflasha` (1,954,545,664 bytes),
  `/dev/nflashaB0` and `/dev/nflashaB1` (4,194,304 bytes each).

Reading a block node returns the bytes the running kernel exposes for it. It
does not imply access to RPMB, OTP/eFuse, or controller hidden areas.

## Jiritsu GET_FILE (optional alternative)

A separate read-only route, implemented in `host/zve10_read_file_jiritsu.py`:

- AdjustControl block `0x1001`, command `0x4008` (`GET_FILE`);
- payload `[mode=1][area=0][f2=1] + "/.." + absolute path`;
- response body decrypted with AES-128-CTR: key
  `MD5("jiritsu team" padded to 16 bytes)`, IV `00..0f`.

The backup tools do **not** use Jiritsu. FileControl reads block nodes directly
and is easier to constrain to a fixed target list.

## Boundaries

- The channel requires an authenticated service session, which requires the
  camera to boot.
- A node's existence and size do not prove every address is readable. The tools
  check status and exact length and abort on mismatch.
- Two passes detect changes; they do not freeze the device.
