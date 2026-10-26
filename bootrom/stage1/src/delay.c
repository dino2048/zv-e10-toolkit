#include "timer.h"
#include "io.h"

/*
 * Timer0 at 0xF2403000 is the one the kernel driver uses. Whether its clock
 * is ungated at the point the ROM hands us control is not known, so probe it
 * and fall back to a busy loop. The fallback is only order-of-magnitude
 * accurate; every use here is a timeout or a PHY settling delay.
 */

int timer_running;

void timer_init(void)
{
    u32 a, b;
    volatile u32 i;

    write32(TIMER0_CTRL, TIMER0_CTRL_FREERUN_1MHZ);
    write32(TIMER0_CLR, 0x10);          /* TMCLR */

    a = timer_ticks();
    for (i = 0; i < 1000; i++)
        __asm__ volatile("nop");
    b = timer_ticks();

    timer_running = (a != b);
}

/* ~200 loop iterations per microsecond on a ~500 MHz A9; deliberately long. */
#define FALLBACK_LOOPS_PER_US 200u

static void busy_wait_us(u32 usec)
{
    volatile u32 n = usec * FALLBACK_LOOPS_PER_US;

    while (n--)
        __asm__ volatile("nop");
}

void udelay(u32 usec)
{
    u32 start, ticks;
    u32 guard;

    if (!timer_running) {
        busy_wait_us(usec);
        return;
    }

    start = timer_ticks();
    ticks = usec * TIMER0_TICKS_PER_US;

    /*
     * The guard makes this terminate even if the counter freezes or is
     * cleared by something else: a delay that never returns is
     * indistinguishable from a crashed payload when the LED is the only
     * output.
     */
    guard = usec * 2000u + 10000u;
    while ((timer_ticks() - start) < ticks && --guard)
        __asm__ volatile("nop");

    if (!guard)
        timer_running = 0;
}

void mdelay(u32 msec)
{
    while (msec--)
        udelay(1000);
}
