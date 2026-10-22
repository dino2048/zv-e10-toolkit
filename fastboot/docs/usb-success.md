# USB fastboot 枚举成功（2026-10-22）

> 本日志记录了两个构建：第一次 7,452 B（`08f0df4a…`），修复版 7,908 B（`0fdc8d9c…`）。最终构建以后者为准。

## 结果

ZV-E10（CXD90045）注入 `fastboot/build/fastboot.bin` 后，USB 设备首次枚举：

```
ZV-E10   VID 0x18d1  PID 0x4ee0  Serial ZVE10-fastboot  Speed 480 Mb/s
bDeviceClass 0xff, bNumConfigurations 1, EP0 64 B
接口 0: class 0xff / subclass 0x42 / protocol 0x03, 2 个 bulk 端点 512 B
```

`set_configuration()` 成功，EP 0x01 写入 `getvar:version`，EP 0x81 读回：

```
OKAY0.4
```

`oem help` 返回四行 INFO 后 `OKAY`。这证明 PHY、时钟/复位、DWC3 device 模式、
EP0 控制传输、bulk 端点与 fastboot 帧全部工作。

## 关键条件

- payload：7,452 B（含换线等待），SHA-256 `08f0df4a…`
- v15 复位注入，重放 90 秒；payload 起来后先长闪，再等 VBUS 低→高
- 看到长闪后把相机 USB-C 从 Pico 移到 Mac，payload 在 25 秒窗口内检测到换线
- 移动线后 Pico 从 Mac 掉线（Pico 5V 与 Mac 5V 经相机 VBUS 顶在一起），
  不影响已经在跑的 payload

## 事故：地址打错导致 AXI 挂死

`oem peek:0xf02000c120:4` 多写了一个 `00`（正确是 `0xf020c120`）。
`hex_parse` 当时返回 `u32`，40 位的输入被静默截断成 `0x2000C120`——未初始化的
DRAM。该读没有返回 abort，而是把 AXI 卡住，payload 停在读指令上：

- bulk IN/OUT 全部超时
- 连 EP0 字符串描述符请求也超时（事件循环不再运行）
- 设备仍留在总线上（旧描述符），但没有任何响应

只有断电/取电池能恢复。

## 修复

- `hex_parse` 改为 `u64`；
- `oem peek/poke/call/load` 只接受
  `0xf0000000-0xf3ffffff`（外设）与 `0xfe000000-0xfeffffff`（eSRAM），
  其余一律 `FAIL`；
- 主机工具 `host/zve10_fb.py` 在发送前同样校验地址宽度和窗口。

## 复现命令

```sh
python3 fastboot/pico/inject_payload.py \
  --port /dev/cu.usbmodemXXXX \
  --file fastboot/build/fastboot.bin --duration 90
# 看到长闪 → 相机线移到 PC

P=python3
$P fastboot/host/zve10_fb.py getvar product
$P fastboot/host/zve10_fb.py oem peek:0xf020c120:4
```

## 复测（修复版，7,908 B）

第二次注入后设备再次枚举，读取全部成功：

```
getvar:version            -> OKAY 0.4
oem peek:0xf020c120:4     -> 5533290a    GSNPSID: DWC_usb3 2.90a
oem peek:0xfe020000:16    -> f8dfb677 ee11d034 ...   自己的代码
oem peek:0xf020c140:16    -> 4020404a 0160c93b 00000001 06a4d085   GHWPARAMS0-3
oem peek:0xf240300c:4     -> 08ca096e   定时器在跑
oem peek:0xf2920010:4     -> 00000003   VBUS=1, ID=1
oem peek:0xf2900030:4     -> 11de56fc   IPCLKEN1, bit14=1
oem peek:0xf29000c0:4     -> 007e1f03   IPRESET2, bit9/10 已释放
oem peek:0xf020c2c0:4     -> 11080002   GUSB3PIPECTL
oem peek:0xf0220000:4     -> 00000403   PCNTL1, TXVREFTUNE=3
oem peek:0xf020c110:4     -> 2ee12004   GCTL, PrtCapDir=2 (device)
oem peek:0xf020c704:4     -> 80f00000   DCTL, RUN_STOP=1
```

GHWPARAMS3 = `0x06A4D085`：设备端点数 = (>>8)&0x3f = 16，两套 PHY 配置与
U3 核一致。

另一个实际发现：`OTG_USB_ID_EXT` 在 payload 初始化 PHY 之后可正常读，
所以“等 VBUS 低→高再初始化 USB”的换线检测是可行的（本次 25 秒窗口超时后
它按计划继续，之后物理换线仍然枚举成功）。
