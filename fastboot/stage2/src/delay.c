#include "timer.h"
#include "io.h"

/*
 * The main payload has already started timer0 at 1 MHz and confirmed it
 * counts, so stage 2 just consumes it. The guard keeps a frozen counter from
 * turning a timeout into a hang.
 */
int timer_running = 1;

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
