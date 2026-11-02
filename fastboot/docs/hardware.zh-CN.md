[English](hardware.md) | **简体中文**

# 硬件与接线

## 接线图

```
相机 USB-C 母座
      ↑ 插上
USB-C 公头（24pin 小板，A/B 两面都引出）
      │
      ├─ A7  D− ──[可选 470Ω]── GP28   Pico 串口 TX（open-drain）
      ├─ A6  D+ ── 470Ω ────── GP27   复位
      ├─ A5  CC1 ─┐
      ├─ B5  CC2 ─┴─ 5.1kΩ ── GND
      ├─ VBUS（A4/A9/B4/B9 任一根）── Pico 5V
      └─ GND（A1/A12/B1/B12 任一根）── Pico GND
```

备注：**A6/A7 不行的话，尝试 B6/B7。**

## 说明

- 相机侧是 USB-C 母座，必须用公头 24pin 小板才能接触引脚；
- 注入期间相机 USB-C 接 24pin 小板，不接电脑；
- D− 使用 open-drain，不要 3.3V 推挽；
- GP28 和 GP27 不能互换；
- GP29（MULTI_RX）当前不接；
- 470Ω：GP27 → D+ 必需；GP28 → D− 可选；
- VBUS、GND 各接一根即可，相机内部已经并联。

## 电池与复位

- 电池插着，相机正常开机；
- 脚本先开载波，再发 GP27 10 µs 低脉冲复位相机，然后整组重放；
- **有复位后不需要拔电池**；拔电池冷启动是旧的 v7 方法，当前不用。

## 换线到电脑

- payload 检测 VBUS 低 → 高；看到长闪后把 24pin 小板从相机拔下，换普通 USB-C 线接到电脑；
- Pico 5V 和 Mac 5V 会在相机 VBUS 上顶在一起，Pico 可能从 Mac 掉线，不影响已经在运行的 payload。

## LED

- 一次长闪（0.4 s）：payload 活着；
- 短脉冲计数：USB 时钟/PHY → DWC3 → EP0 配置 → 等主机；
- 之后每 2 秒一次短脉冲：在等主机枚举；
- 停在第 N 个短脉冲：对应步骤没有返回。

## 停止 / 恢复正常启动

从仓库根目录：

```sh
python3 fastboot/pico/reset_only.py --port /dev/cu.usbmodemXXXX
```

发一次 GP27 复位、关闭载波，相机回到正常启动，不用拆电池。也可以直接断电/取电池：
payload 在 SRAM，易失。

## 边界

- 这是 BootROM 串口启动，不是运行时漏洞；需要专用接线和复位时序。
- 只写 SRAM；不写 eMMC、SD 或 OTP。
