#include "led.h"
#include "io.h"
#include "timer.h"

/*
 * The front LED is GPIO0 bit 0, active as driven by the mask ROM's own error
 * blink routine at 0xFFFF0D0A. That routine never returns (it ends in
 * `b 0xffff0d58`), so it cannot be used for progress reporting. Its register
 * accesses are replicated here instead, taken from the local ROM dump:
 *
 *   0xF2910044  GPIO0 WDATA_SET   drive high
 *   0xF2910048  GPIO0 WDATA_CLR   drive low
 *   0xF2910028  GPIO0 INEN_CLR    input buffer off
 *   0xF2910004  GPIO0 DIR_SET     output
 *   0xF2912024 / 0x34 / 0x44      OCTRL0 pad config, all 1
 *
 * (regs-gpio.h: DIR 0x00/SET 0x04, INEN 0x20/CLR 0x28, WDATA 0x40/SET 0x44/
 * CLR 0x48; platform.h:77 CXD900X0_GPIO(ch,reg) = 0xF2910000 + (ch<<8) + reg.)
 *
 * The ROM's timing, for reference: long = 2,000,000 timer ticks, short =
 * 1,000,000, gap = 8,000,000; at the 4 MHz ROM timer that is 0.5 s / 0.25 s /
 * 2 s. This driver uses the same proportions at millisecond resolution.
 */

#define LED_WDATA_SET   (0xF2910000u + 0x44)
#define LED_WDATA_CLR   (0xF2910000u + 0x48)
#define LED_INEN_CLR    (0xF2910000u + 0x28)
#define LED_DIR_SET     (0xF2910000u + 0x04)
#define LED_OCTRL0      (0xF2910000u + 0x2000)

#define LONG_ON_MS   500
#define LONG_OFF_MS  500
#define SHORT_ON_MS  250
#define SHORT_OFF_MS 250
#define GAP_MS       2000

void led_init(void)
{
    write32(LED_WDATA_SET, 1);
    write32(LED_INEN_CLR, 1);
    write32(LED_WDATA_SET, 1);
    write32(LED_OCTRL0 + 0x24, 1);
    write32(LED_OCTRL0 + 0x34, 1);
    write32(LED_OCTRL0 + 0x44, 1);
    write32(LED_DIR_SET, 1);
}

/* Active low, as on the CXD90057: the ROM's first blink half drives 0x48
 * (clear) and that is the lit half. */
void led_on(void)
{
    write32(LED_WDATA_CLR, 1);
}

void led_off(void)
{
    write32(LED_WDATA_SET, 1);
}

static void pulse(u32 on_ms, u32 off_ms)
{
    led_on();
    mdelay(on_ms);
    led_off();
    mdelay(off_ms);
}

/* Long and unmistakable: the short step pulses below are 120 ms. */
void led_blip(void)
{
    pulse(400, 400);
}

void led_marker(void)
{
    pulse(LONG_ON_MS, LONG_OFF_MS);
}

void led_count(u32 n)
{
    u32 i;

    if (n > 12)
        n = 12;

    pulse(LONG_ON_MS, LONG_OFF_MS);
    for (i = 0; i < n; i++)
        pulse(SHORT_ON_MS, SHORT_OFF_MS);
    mdelay(GAP_MS);
}

void led_step(u32 n)
{
    u32 i;

    if (n > 12)
        n = 12;

    for (i = 0; i < n; i++)
        pulse(120, 180);
    mdelay(300);
}

void led_heartbeat(void)
{
    pulse(60, 0);
}

__attribute__((noreturn)) void led_fail(u32 code)
{
    for (;;) {
        led_init();
        led_count(code & 0xfu);
    }
}

void led_activity(void)
{
}

void led_activity_tick(void)
{
}

__attribute__((noreturn)) void led_panic(void)
{
    for (;;) {
        led_init();
        pulse(100, 100);
    }
}

void led_usb_up(void)   { led_init(); led_count(2); }
void led_ready(void)    { led_init(); led_count(3); }
void led_timeout(void)  { led_init(); led_count(4); }
void led_bus_error(void){ led_init(); led_count(5); }
void led_no_phy(void)   { led_init(); led_count(6); }
