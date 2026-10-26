#include "led.h"
#include "io.h"
#include "timer.h"

#define LED_WDATA_SET   (0xF2910000u + 0x44)
#define LED_WDATA_CLR   (0xF2910000u + 0x48)
#define LED_INEN_CLR    (0xF2910000u + 0x28)
#define LED_DIR_SET     (0xF2910000u + 0x04)
#define LED_OCTRL0      (0xF2910000u + 0x2000)

#define MARK_ON_MS   500u
#define MARK_OFF_MS  300u
#define ON_MS        120u
#define OFF_MS       120u
#define GAP_MS       1500u

static u32 code, phase, done, t0;

static void on(void)  { write32(LED_WDATA_CLR, 1); }   /* active low */
static void off(void) { write32(LED_WDATA_SET, 1); }

void led_init(void)
{
    write32(LED_WDATA_SET, 1);
    write32(LED_INEN_CLR, 1);
    write32(LED_WDATA_SET, 1);
    write32(LED_OCTRL0 + 0x24, 1);
    write32(LED_OCTRL0 + 0x34, 1);
    write32(LED_OCTRL0 + 0x44, 1);
    write32(LED_DIR_SET, 1);
    off();
}

void led_set(u32 c)
{
    code = c;
    done = 0;
    phase = 0;
    t0 = timer_ticks();
    if (c == 0)
        off();
    else
        on();
}

u32 led_code(void) { return code; }

void led_tick(void)
{
    u32 now, el;

    if (!code)
        return;

    now = timer_ticks();
    el = now - t0;

    switch (phase) {
    case 0:                         /* long marker on */
        if (el >= MARK_ON_MS) { off(); phase = 1; t0 = now; }
        break;
    case 1:                         /* long marker off */
        if (el >= MARK_OFF_MS) { on(); phase = 2; t0 = now; }
        break;
    case 2:                         /* short pulse on */
        if (el >= ON_MS) { off(); phase = 3; t0 = now; }
        break;
    case 3:                         /* short pulse off */
        if (el >= OFF_MS) {
            done++;
            if (done >= code) { phase = 4; t0 = now; }
            else { on(); phase = 2; t0 = now; }
        }
        break;
    default:                        /* gap between cycles */
        if (el >= GAP_MS) { done = 0; on(); phase = 0; t0 = now; }
        break;
    }
}

void led_hang(u32 c)
{
    led_set(c);
    for (;;)
        led_tick();
}
