# Related work

This project builds on public work. The mechanisms below are cited for
context; their code is not copied into this repository.

## Sony-PMCA-RE

[github.com/ma1co/Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) — MIT.

Provides the USB transport, the mass-storage-to-service-mode switch, the
Senser authentication implementation, packet framing, and the terminal
read/write primitives. This toolkit imports it rather than vendoring it.

## a7c2-service-preload

[github.com/YuuLuo/a7c2-service-preload](https://github.com/YuuLuo/a7c2-service-preload)

Public work that identified the path traversal in Sony's factory service
(Senser/Jiritsu) and the library-loading chain. Check the repository for its
license. This project does not include or copy that exploit chain.

## sony-a7iv-feature-research

[github.com/leogenot/sony-a7iv-feature-research](https://github.com/leogenot/sony-a7iv-feature-research)

Documents a read-only Jiritsu dump method on the A7 IV. The optional
`zve10_read_file_jiritsu.py` tool is an independent implementation of the
`GET_FILE` request described there, with the key derivation and path traversal
that the public documentation records. It is **not** used by the backup tools.

## Jiritsu read path, briefly

- AdjustControl block `0x1001`, command `0x4008` (`GET_FILE`).
- Payload: `[mode=1][area=0][f2=1] + "/.." + absolute path`.
- The response body is AES-128-CTR encrypted; the key is
  `MD5("jiritsu team" padded to 16 bytes)`, IV `00..0f`.
- Reading is a separate route from service-mode FileControl and does not need
  a root shell.

This toolkit keeps Jiritsu out of the backup path because FileControl reads
block-device nodes directly and is easier to constrain to fixed targets.

## What this project adds

- A fixed-target, two-pass raw backup with end-to-end hashing and an offline
  verifier.
- A file-level backup built on the service terminal.
- A read-only-by-default service terminal with an explicit owner-authorized
  write mode.
- Documentation of what the resulting images do and do not prove.

## Not included

No Sony firmware, firmware extracts, boot ROM dumps, camera binaries, service
software, certificates, Sony Senser authentication key tables, device data, or
backup images are part of this repository.
