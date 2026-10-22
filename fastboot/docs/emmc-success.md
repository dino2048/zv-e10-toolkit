# 真机 eMMC 读取打通（2026-10-22）

结论：通过 BootROM 串口注入 + USB fastboot 传输层 + 二级 payload（stage 2），
在 ZV-E10 真机上完成了 **eMMC 卡识别与分区数据读取**，全程只读。

## 链路

```
Pico 串口注入 (7,908 B payload, 0xFE020000)
  → DWC3 device + fastboot 协议 (18d1:4ee0)
  → oem download stage2.bin
  → oem load:0xfe300000
  → oem poke 参数 (0xFE320000 = block, 0xFE320004 = count)
  → oem call:0xfe300001
  → oem peek 结果/数据
```

stage 2 大小 1,316 B，链接地址 `0xFE300000`，结果块 `0xFE308000`，
数据块 `0xFE310000`。

## SDHCI

基址 `0xF0304000`（GPL `udif/platform.c:258 EMMC0_IO_BASE`，4 KB 窗口）。

```
CAPABILITIES   0x64EEC000   base clock 192 MHz, slot type = embedded
HOST_VERSION   0x0102       SD Host 3.0
PRESENT_STATE  0x01FF0000   CARD_INSERTED=1, 无 inhibit
HOST_CONTROL   0x34         4-bit, high-speed
POWER_CONTROL  0x0B         电源已开
```

## 卡识别（CMD0/1/2/3/9/7/13）

```
OCR   0xC0FF8080    ready=1, CCS=1（扇区寻址）
CID   f1b6986a 345201da 34465445 00150100
CSD   ef8e4040 fff6dbff 320f5903 00d02701
RCA   1
R1    0x00000900    state=TRAN(4), READY_FOR_DATA=1
status 0
```

读取时把控制器降到 400 kHz、1-bit、PIO，读完恢复原寄存器值。

## block 0 = SDM2 分区表

```
00000000: 36343238 30302e31 0000001e 00000001   "642800.1", 30 项, 1
00000020: 00010000 007f0000 00000001 ffffffff   nflasha1 start=0x10000 size=0x7f0000
00000030: 00800000 01400000 00000001 ffffffff   nflasha2
...
```

与外部 zve10-qemu 参考的分区表完全一致（start 字段是**字节**
偏移，不是扇区；CMD17 要除以 512）。

## 分区数据是明文

nflasha3（start 0x01C00000 = block 57344）第一块：

```
EB 3C 90 "mkfs.fat" ... "This is not a bootable disk. Please insert..." ... 55AA
```

即标准 FAT 引导扇区，**没有分区级加密**（至少 user area 的 SDM2 槽位如此）。

## 限制与注意

- 每次 `oem call` 都重新 CMD0→CMD13，约 1–2 秒；单次最多读 64 块（32 KB），
  但 `oem peek` 一次只能回 0x1000 字节。
- 尚未实现 device→host 的批量上传通道；要整分区 dump 需要加一个。
- 尚未实现写（CMD6/CMD24/25）。按约定，写操作逐次授权。
- payload 在真机上约 15–20 分钟后会自行复位（原因未查明，ROM dump 中没有
  WDT 引用），所以每次会话要一次做完。
- `oem peek` 的地址参数与长度都按**十六进制**解析；写成 `:64` 会被当成 0x64。
- 越界地址（如误写 0xf02000c120 被截断成 DRAM）会卡死 AXI，只有断电可恢复；
  payload 与主机工具都已加范围校验。
