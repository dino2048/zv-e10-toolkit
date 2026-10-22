# ZV-E10 BootROM 串口启动协议（已验证）

2026-10-22 在本机实测成功。本文是与当前可用方案配套的协议摘要；
详细逆向来源见 [cokeenet/zve10-qemu](https://github.com/cokeenet/zve10-qemu) 的 UART boot 参考与本地 A7C UART boot 笔记。

## 1. 物理层

| 项 | 值 |
|---|---|
| 信号 | 相机 USB-C **D− (A7)**；本机实测**直连、无串阻**（参考用 470Ω 保护） |
| 电平 | **OPEN_DRAIN**（借相机侧上拉；不要 3.3V 推挽） |
| 链路 | **48000 baud，8O1**（start + 8 data LSB + odd parity + stop = 11 bit） |
| 位周期 | 20.83 µs（参考 B/4.032 MHz 组；21.0 µs 也可尝试） |
| carrier | 125 µs 半周期（约 4 kHz），**常开** |
| 同步慢块 | 250 µs（必须在 225.4–293.6 µs 窗口内） |
| 记录间隔 | 14.4 ms；组内不得有 >293.6 µs 静默 |
| 一组总时长 | 同族文档 `<1.45 s`；本机实测 8 KB/2.17 s 通过、10 KB/2.65 s 返回 `0x2004`，实际上限约 **8–10 KB** |

发送端实测：RP2040 Pico，PIO 位翻转 + DMA，open-drain；当前使用
`zve10_pico_od_reset`（v15）和 `inject_payload.py`，GP27 复位、电池保持。
v7 + `inject_fixed.py` 是旧的拔电池冷启动方法。

接线：USB-C 公头转 24pin 小板；GP28 → D−：A7（A 组，可选串 470Ω），
GP27 → 470Ω → D+：A6（A 组）；A6/A7 不行时整组换 B7/B6。
5V → VBUS（一根），GND（一根），CC1/CC2 并接后 5.1kΩ 下拉到 GND；
GP29 不接。详见 [../docs/hardware.zh-CN.md](../docs/hardware.zh-CN.md)。

## 2. 记录格式

```python
body   = struct.pack("<IHI", 10 + len(payload), rtype, value) + payload
record = body + struct.pack("<I", zlib.crc32(body) & 0xffffffff)
```

| 偏移 | 宽度 | 字段 |
|---|---|---|
| `+0x00` | u32 LE | `length = 10 + payload_len`（不含尾部 CRC） |
| `+0x04` | u16 LE | type |
| `+0x06` | u32 LE | value |
| `+0x0A` | length-10 | payload（仅“其他 type”读取） |
| `+length` | u32 LE | CRC32（zlib，poly `0xEDB88320`） |

## 3. 记录类型与组语义

| type | 含义 | 行为 |
|---|---|---|
| `0x0000` | `SET_UNLOCK` | value = 解锁 token；置内部 flag0 |
| `0x0001` | `MEM_WRITE` | value = 目标地址；payload 直接写入（无地址校验） |
| `0xFFFF` | `SET_ENTRY` | value = 入口地址；写 `[0xFE00500C]` 并置 flag1 |
| 其他 | 普通记录 | 按 payload 处理 |

**组规则（关键）**：

- 组首与组末必须是**同一 type**；ROM 收到与组首同类型的记录即关组。
- 必须用 **`SET_UNLOCK` 作为组首/组末**，不能用 `marker(0x0123)`；
  否则关组时 flag0=0，载荷不跳转（我们之前失败的根因）。
- 关组时 `flag0 | flag1` 必须非 0；`SET_ENTRY` 置 flag1。
- `MEM_WRITE` 记录 `length >= 0x0A`；任意记录 `length <= 0x1000`。

## 4. 解锁 token

ZV-E10 的 boot0（EXBL 头）偏移 `0x200` 处 8 字节：

```text
V = 0x8CB102DC
C = 0xA86DA25E
crc32(V || C) == 0xFFFFFFFF
```

`SET_UNLOCK` 的 value 必须等于 V，否则 ROM 报 `0x2002`（1 长 2 短）。
参考仓库的 `zve10-uart-boot/README.md` 与 `inject_a7c_exact.py` 使用同一值。

## 5. 完整序列

```text
SET_UNLOCK(0x8CB102DC)
MEM_WRITE(0xFE020000, payload)
SET_ENTRY(0xFE020001)          ; Thumb 入口
SET_UNLOCK(0x8CB102DC)
```

- 载波常开；每条记录后等 14.4 ms；整组反复重放。
- **整组重放**覆盖相机上电后的接收窗口；单次发送很容易错过。
- 参考的 `CMD_BLOB` 路径不追加 FF 尾字节；本机成功路径也未追加。
- 组总时长必须 <1.45 s。

## 6. 自证明 payload

```text
02 48        ldr r0, [pc, #8]    ; r0 = 0x2007
03 49        ldr r1, [pc, #12]   ; r1 = 0xFFFF0D0B
08 47        bx  r1               ; 调用 ROM 0xFFFF0D0A
00 bf ×3     nop
07 20 00 00  .word 0x00002007
0b 0d ff ff  .word 0xFFFF0D0B
```

- 加载地址 `0xFE020000`；Thumb 入口 `0xFE020001`。
- 期望灯码 **1 长 + 7 短**（`0x2007`），ROM 自身错误路径不可能产生。

## 7. 错误灯码

| 长 | 短 | code | 含义 |
|---|---|---|---|
| 0 | 13 | `0x100D` | 奇校验错（收到数据但解不对） |
| 1 | 2 | `0x2002` | token 不匹配 |
| 1 | 3 | `0x2003` | CRC 校验失败 |
| 1 | 4 | `0x2004` | 记录不完整 / 同步失败 / 字节超时 / `len > 0x1000` |
| 1 | 5 | `0x2005` | 跳转发生且入口返回 |
| 2 | 1 | `0x3001` | 接收超时 |
| 0 | 1 | `0x1001` | 只有 flag0，未置 entry |

## 8. 与其他机型的关系

- **A7C / A7M4 家族**：相同的记录格式、`SET_UNLOCK` / `MEM_WRITE` /
  `SET_ENTRY`、组关语义、入口槽和 `bx` 跳转；ZV-E10 这次的实际行为与它们
  一致，而不是候选 ROM 推断的“无 token Path A”。
- **A6700**：另一代机型；开漏 / 48 kbaud 的发送方法可借鉴，但记录内容和
  时序不能直接照搬。
- 机型差异主要在 ROM 内部地址/flag/定时描述符；**发送端记录协议相同**。

## 9. 边界

- payload 在 SRAM，易失；断电清除，相机恢复正常启动。
- 写入只到 SRAM；eMMC/SD/OTP 未触碰。
- 更大载荷需要二级 loader（参考仓库的 `stage_a.py` / `stage_b.py` 路线）。
- 不是运行时漏洞；需要专用接线与上电时序。
