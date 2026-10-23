# ZV-E10 BootROM serial-boot protocol (verified)

[**English**](PROTOCOL.md) | [简体中文](PROTOCOL.zh-CN.md)

Verified on hardware on 2026-10-22. This is the protocol summary for the current
working flow. Reverse-engineering references:
[cokeenet/zve10-qemu](https://github.com/cokeenet/zve10-qemu) UART boot and the
local A7C UART boot notes.

## 1. Physical layer

| Item | Value |
|---|---|
| Signal | Camera USB-C **D− (A7)**; measured **direct, no series resistor** (the reference uses 470Ω for protection) |
| Level | **OPEN_DRAIN** (uses the camera-side pull-up; do not push 3.3V) |
| Link | **48000 baud, 8O1** (start + 8 data LSB + odd parity + stop = 11 bits) |
| Bit period | 20.83 µs (reference B/4.032 MHz group; 21.0 µs also worth trying) |
| Carrier | 125 µs half-period (~4 kHz), **always on** |
| Slow sync block | 250 µs (must be inside the 225.4–293.6 µs window) |
| Record interval | 14.4 ms; no gap >293.6 µs inside a group |
| Group duration | family docs say `<1.45 s`; measured 8 KB/2.17 s passes, 10 KB/2.65 s returns `0x2004`; practical limit about **8–10 KB** |

Sender verified: RP2040 Pico, PIO bit-banging + DMA, open-drain. The current
flow uses `zve10_pico_od_reset` (v15) and `inject_payload.py`, with GP27 reset
and the battery left in. v7 + `inject_fixed.py` is the legacy battery-removal
cold-boot method.

Wiring: USB-C male to 24-pin breakout; GP28 → D−: A7 (A pair, optional 470Ω),
GP27 → 470Ω → D+: A6 (A pair); if A6/A7 do not work, switch the whole pair to
B7/B6. 5V → VBUS (one wire), GND (one wire), CC1/CC2 tied with 5.1kΩ to GND;
GP29 is not connected. See [../docs/hardware.md](../docs/hardware.md).

## 2. Record format

```python
body   = struct.pack("<IHI", 10 + len(payload), rtype, value) + payload
record = body + struct.pack("<I", zlib.crc32(body) & 0xffffffff)
```

| Offset | Width | Field |
|---|---|---|
| `+0x00` | u32 LE | `length = 10 + payload_len` (excluding the trailing CRC) |
| `+0x04` | u16 LE | type |
| `+0x06` | u32 LE | value |
| `+0x0A` | length-10 | payload (read only for "other" types) |
| `+length` | u32 LE | CRC32 (zlib, poly `0xEDB88320`) |

## 3. Record types and group semantics

| type | Meaning | Behaviour |
|---|---|---|
| `0x0000` | `SET_UNLOCK` | value = unlock token; sets internal flag0 |
| `0x0001` | `MEM_WRITE` | value = target address; payload is written directly (no address check) |
| `0xFFFF` | `SET_ENTRY` | value = entry address; writes `[0xFE00500C]` and sets flag1 |
| other | ordinary record | handled as payload |

**Group rules (critical):**

- The first and last records must have the **same type**; the ROM closes the
  group when it receives a record of the same type as the first.
- Use **`SET_UNLOCK` as both the first and last record**, not `marker(0x0123)`;
  otherwise flag0 is 0 when the group closes and the payload does not jump
  (this was the root cause of earlier failures).
- When the group closes, `flag0 | flag1` must be non-zero; `SET_ENTRY` sets
  flag1.
- `MEM_WRITE` records need `length >= 0x0A`; any record needs `length <= 0x1000`.

## 4. Unlock token

At offset `0x200` of the ZV-E10 boot0 (EXBL header), 8 bytes:

```text
V = 0x8CB102DC
C = 0xA86DA25E
crc32(V || C) == 0xFFFFFFFF
```

`SET_UNLOCK`'s value must equal V; otherwise the ROM reports `0x2002`
(1 long, 2 short). The reference repository's `zve10-uart-boot/README.md` and
`inject_a7c_exact.py` use the same value.

## 5. Full sequence

```text
SET_UNLOCK(0x8CB102DC)
MEM_WRITE(0xFE020000, payload)
SET_ENTRY(0xFE020001)          ; Thumb entry
SET_UNLOCK(0x8CB102DC)
```

- Carrier stays on; wait 14.4 ms after each record; replay the whole group.
- **Replaying the group** covers the camera's receive window after power-up;
  a single send is easily missed.
- The reference `CMD_BLOB` path does not append an FF tail byte; the working
  path here does not either.
- Total group duration must be <1.45 s.

## 6. Self-proof payload

```text
02 48        ldr r0, [pc, #8]    ; r0 = 0x2007
03 49        ldr r1, [pc, #12]   ; r1 = 0xFFFF0D0B
08 47        bx  r1               ; call ROM 0xFFFF0D0A
00 bf ×3     nop
07 20 00 00  .word 0x00002007
0b 0d ff ff  .word 0xFFFF0D0B
```

- Load address `0xFE020000`; Thumb entry `0xFE020001`.
- Expected LED code **1 long + 7 short** (`0x2007`), which the ROM's own error
  paths cannot produce.

## 7. Error LED codes

| Long | Short | Code | Meaning |
|---|---|---|---|
| 0 | 13 | `0x100D` | odd-parity error (data received but decoded wrong) |
| 1 | 2 | `0x2002` | token mismatch |
| 1 | 3 | `0x2003` | CRC failure |
| 1 | 4 | `0x2004` | incomplete record / sync failure / byte timeout / `len > 0x1000` |
| 1 | 5 | `0x2005` | jump happened and the entry returned |
| 2 | 1 | `0x3001` | receive timeout |
| 0 | 1 | `0x1001` | only flag0, entry not set |

## 8. Relation to other models

- **A7C / A7M4 family**: same record format, `SET_UNLOCK` / `MEM_WRITE` /
  `SET_ENTRY`, group-close semantics, entry slot and `bx` jump. ZV-E10's
  observed behaviour matches them, not the candidate ROM's "no-token Path A".
- **A6700**: another generation; the open-drain / 48 kbaud sender method is
  reusable, but record content and timing cannot be copied directly.
- Model differences are mostly ROM-internal addresses, flags, and timer
  descriptors; the **sender record protocol is the same**.

## 9. Boundaries

- The payload lives in SRAM and is volatile; power loss clears it and the
  camera boots normally.
- Writes reach SRAM only; eMMC, SD, and OTP are untouched.
- Larger payloads need a second-stage loader (the reference repository's
  `stage_a.py` / `stage_b.py` route).
- Not a runtime exploit; it needs dedicated wiring and reset timing.
