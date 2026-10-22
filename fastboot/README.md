# ZV-E10 fastboot payload（USB 传输层）

CXD90045（ZV-E10，ARMv7-A/Cortex-A9）裸机 fastboot。用 BootROM 串口启动注入，
跑起来后把 D−/D+ 交给 PC，PC 用 `fastboot` 访问。

**当前状态：已实机跑通（2026-10-22），并已通过 stage 2 在真机上读取 eMMC
（SDM2 分区表与分区数据，只读）。USB 以 `18d1:4ee0` 枚举，`getvar` 返回
`OKAY0.4`，`oem help/peek` 可用。镜像 7,908 B，在 8 KB 直接注入窗口内。**

不要把它和 `../zve10-led-payload` 搞混：那个只闪灯；这个初始化 USB 时钟/PHY/DWC3
并暴露 fastboot 传输层（`oem peek/poke/call/download/load`）。eMMC 驱动不在这
7.9 KB 里，而是运行时通过 USB 下发的 [stage2/](stage2/)（1,316 B）。

## 预期现象（v2 诊断版）

注入后相机（电池保持）先 **一次长闪（0.4 s）**表示 payload 活着，然后是一串
**短脉冲（120 ms）计数**，最后每 2 秒一次短脉冲表示“在等主机”：

| 短脉冲数 | 到达点 |
|---:|---|
| 1 | USB 时钟/PHY 初始化完成 |
| 2 | DWC3 核初始化完成（GSNPSID、软复位、事件缓冲） |
| 3 | `DEPSTARTCFG` 完成 |
| 4 | EP0 OUT 配置完成 |
| 5 | EP0 IN 配置完成 |
| 6 | EP0 使能、SETUP 已挂好 |
| 之后单脉冲/2 s | D+ 上拉已打开，在等 PC 枚举 |

**停在第 N 个短脉冲之后不动 = 下一步没返回**，这比上一版的“1 长 2 短后静默”
能定位得多。看到“每 2 秒一次短脉冲”就说明 payload 在正常等主机，问题在
PHY/主机侧而不是卡死。

等主机期间相机不会自己重启；PC 一插上就会看到 `18d1:4ee0`（Google fastboot）：

> 闪灯不再调用 ROM 的 `0xFFFF0D0B`：从本地 ROM dump 反汇编可见它在
> `0xFFFF0DB0` 有一条 `b 0xffff0d58`，**永不返回**，用它做进度提示会卡死。
> 现在按 ROM 自己的寄存器访问直接驱动 GPIO0 bit0（`0xF2910044/0x48`），
> 本版用 0.4 s 长闪 / 120 ms 短脉冲，便于计数。

```sh
# macOS 上的 Android fastboot CLI 认不到这个设备（设备级 class=0xff），
# 用仓库里的 pyusb 工具，协议完全相同：
python3 fastboot/host/zve10_fb.py getvar product       # -> ZVE10
python3 fastboot/host/zve10_fb.py oem help
python3 fastboot/host/zve10_fb.py oem peek:0xf020c120:4    # GSNPSID
python3 fastboot/host/zve10_fb.py oem peek:0xfe020000:16   # payload 自己的代码
python3 fastboot/host/zve10_fb.py reboot
```

地址必须是 8 位十六进制；`0xf02000c120` 这类多一位的输入会被设备端 64 位解析
拒绝（早期版本截断成 DRAM 地址后 AXI 挂死，整机 USB 不再响应）。

`oem` 命令：

```
peek:<addr>[:<len>]   dump memory, max 0x1000
poke:<addr>:<val>     32-bit write, reports readback
call:<addr>           call addr as u32 f(void)
load:<addr>           copy staged download to addr
```

`flash:`/`erase:` 明确返回 FAIL——这一版没有 eMMC。

## stage 2（eMMC 读取）

主 payload 只有 7.9 KB，放不下 eMMC 驱动，所以 eMMC 代码作为二级镜像在运行时
通过 USB 下发：

```sh
# 设备枚举后
python3 fastboot/host/run_stage2.py --block 0xe000 --count 1   # 读 nflasha3 的第一块
```

`run_stage2.py` 会 `download → oem load:0xfe300000 → poke 参数 → oem call →
peek`。参数区 `0xFE320000`：`[0]`=起始块（512 B 扇区），`[1]`=块数（≤64）。
结果在 `0xFE308000`，数据在 `0xFE310000`。

源码在 [stage2/](stage2/)，1,316 B，寄存器序列移植自 CXD90057 的
`sdhci.c`，基址换成 ZV-E10 的 `0xF0304000`。详见
[docs/emmc-success.md](docs/emmc-success.md)。

## 硬件与流程

接线、电池和换线步骤见 [docs/hardware.zh-CN.md](docs/hardware.zh-CN.md)。摘要：
GP28 → D−：A7（A 组）直连，可选串 470Ω；GP27 → 470Ω → D+：A6（A 组）。
A6/A7 不行时整组换 B7/B6。5V → VBUS（一根），GND（一根）；
CC1/CC2 连在一起后经 5.1kΩ 下拉到 GND。注入时相机不接电脑；
电池插着，GP27 复位，不需要拔电池。如果不行，翻转 USB-C 方向再试。

```sh
# 以下命令在仓库根目录执行。

# 1. 编译
make -C fastboot
make -C fastboot/stage2

# 2. 注入（Pico 已连、相机已开机、电池在）
python3 fastboot/pico/inject_payload.py \
    --port /dev/cu.usbmodemXXXX \
    --file fastboot/build/fastboot.bin --duration 90

# 3. 看到 0x2003 后，把相机 USB-C 从 Pico 拔下，插到 PC
python fastboot/host/zve10_fb.py getvar product
```

`inject_payload.py` 使用与 v15 注入流程相同的记录组：`SET_UNLOCK →
MEM_WRITE(0xFE020000…) → SET_ENTRY(0xFE020001) → SET_UNLOCK`，13.3 ms
和 50 ms 的间隔不变；7,908 B 落在 8 KB 已验证窗口内。

## 源码来源与地址

大部分 USB 栈移植自 [ILCE-7M4-RE](https://github.com/DavidBuchanan314/ILCE-7M4-RE) 的 fastboot payload（CXD90057，
AArch64），本机只改有明确依据的部分：

| 项 | A7M4（CXD90057） | ZV-E10（CXD90045） | 依据 |
|---|---|---|---|
| DWC3 | `0xF10C0000` | **`0xF0200000`** | `platform.h:191 CXD900X0_USB_DRD_BASE` |
| 全局/设备寄存器 | `+0xC100/+0xC700` | 相同 | ZV-E10 GPL `drivers/usb/dwc3/core.h` |
| DWC3 IP 族 | DWC_usb31 | **DWC_usb3（0x5533）** | ZV-E10 GPL 驱动 |
| DEPCMD 状态位 | bit12-15 | **bit15** | ZV-E10 `core.h` |
| 时钟/复位 | SCU `0xF1388000` | **CLKRST3 `0xF2900000`** | `platform.h:111`、`usb_otg_reg.h` |
| IPCLKEN1 | — | `+0x34` 置 bit14（USB30DRD_ACLK） | `usb_otg.c:311` |
| IPRESET2 | — | `+0xC4` 置 bit9、bit10 | `usb_otg.c:309,317` |
| OTG / REFCLK | — | `0xF2920000` `+0x100` 置 bit16 | `usb_otg.c:307` |
| PHY 调节块 | `phy_cr 0xF10A0000` | **`0xF0220000`**（DRD+0x20000） | `platform.c:414` |
| TXVREFTUNE | U2PHY_CFGR1 | `0xF0220000+0` 低 4 位 = 3 | `usb_otg.c:313-315` |
| ADPADDR/ADPDATA | — | `+0x11080` / `+0x11084` | `usb_otg.c:323-324` |
| TCA | `0xF10D0000` | **不存在**，不访问 | ZV-E10 GPL 无 TCA 代码 |
| 定时器 | `0xF1042000` 4 MHz | `0xF2403000` 1 MHz | `platform.h:60`、`regs-timer.h` |
| 复位 | GPIO XRESET_REQ | MISC `0xF2915044` = 0x011 | `core.c:245`、`regs-misc.h` |
| LED | GPIO ch18 | ROM `0xFFFF0D0B(code)` | 本机实测 |

ZV-E10 侧的初始化序列直接来自 Sony 自己的 `drivers/usb/f_usb/usb_otg.c`：
REFCLK → 释放 USB30 → 使能 ACLK → TXVREFTUNE → 释放 PHY → `GUSB3PIPECTL
= 0x11080002` → ADPADDR/ADPDATA。`GUSB2PHYCFG` 保持复位值（Sony 驱动也不写
PHYIF/USBTRDTIM），只清 suspend 位。

## 与 A7M4 版有意不同的地方

- `start.S` 改为 ARMv7/Thumb：关 IRQ/FIQ、关 I/D cache、设自己的 SP、清 .bss。
  关 cache 是因为 DWC3 通过 AXI 读 TRB/事件缓冲，cache 开着会读到旧数据。
- `usb_phy.c` 整份重写（ZV-E10 的时钟/复位/PHY 布局与 CXD90057 完全不同）。
- `dwc3.c` 去掉 `PWRDNSCALE(2)` 与 `DSBLCLKGTNG`（ZV-E10 驱动明确说后者是保留位）、
  去掉 UTMI 8-bit 覆写。
- `led.c`/`log.c` 换成 ROM 闪灯与 PL011 UART0（`0xF2000000`）。
- `fastboot_min.c` 是新写的精简协议层（`fastboot.c` 里 2,000 行是 A7M4 的
  eMMC/CP/NOR 命令，这一版不需要）。

## 实测结果（2026-10-22）

- 枚举：`18d1:4ee0`，480 Mb/s，序列号 `ZVE10-fastboot`
- `getvar:version` → `OKAY0.4`；`oem help/peek/poke/call/download/load` 全部可用
- GSNPSID `0x5533290A`（DWC_usb3 2.90a），PHY/时钟/复位寄存器读回与写入值一致
- stage 2：eMMC 识别 + SDM2 分区表 + 分区数据（nflasha3 = FAT），只读
- 证据：[docs/usb-success.md](docs/usb-success.md)、
  [docs/emmc-success.md](docs/emmc-success.md)

## 已知问题与限制

- **payload 约 15–20 分钟后自行复位**，原因未查明。ROM dump 里没有
  `0xF2402000`（WDT）的引用，可能是 PMIC 侧。每次会话要一次做完。
- macOS 的 Android `fastboot` CLI 认不到这个设备（设备级 class=0xff），
  用 `host/zve10_fb.py` / `host/run_stage2.py`。
- **重复 SET_CONFIGURATION 会挂死 EP0**：macOS 枚举时配置一次、libusb 再配置
  一次，第二次在 bulk 传输已排队时重跑端点命令就会卡住。`src/usb.c` 已改成
  只有第一次生效；旧固件仍有这个风险。
- **非法地址会卡死 AXI**：`oem peek` 的地址若被截断进未初始化的 DRAM，读不会
  abort 而是挂住总线，连 EP0 都不再响应，只能断电。payload 与主机工具都已加
  白名单（`0xf0000000-0xf3ffffff`、`0xfe000000-0xfeffffff`）。
- `oem peek:<addr>:<len>` 的 `len` 按**十六进制**解析：要 64 字节写 `:40`。
- 闪灯用 GPIO0 bit0 直接驱动（`0xF2910044/0x48`），不再调用 ROM 的
  `0xFFFF0D0B`（它在 `0xFFFF0DB0` 有 `b 0xffff0d58`，永不返回）。
- 写入边界不变：主 payload 与 stage2 只读内存和 eMMC；没有任何写卡路径。

## 下一步

1. **device→host 批量上传通道**：现在一次 `oem peek` 只能回 4 KB，
   整分区 dump 需要加一个 bulk IN 上传命令。
2. **写路径**（CMD6/CMD24/25）：逐次授权后再做，先写 RAM 镜像验证。
3. **查清 15–20 分钟复位来源**：PMIC / 其他看门狗。
