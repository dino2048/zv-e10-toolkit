#ifndef ZVE10_TIMER_H
#define ZVE10_TIMER_H

#include "io.h"

/*
 * CXD90045 hardware timer 0 at 0xF2403000 (arch/arm/mach-cxd900x0/
 * include/mach/platform.h:60 CXD900X0_TIMER_BASE(x) = 0xf2403000 + 0x100*x).
 *
 * Register map from arch/arm/mach-cxd900x0/include/mach/regs-timer.h:
 *   0x00 CTRL, 0x04 CLR, 0x08 CMP, 0x0c READ, 0x10 LOAD
 * CTRL = TMST | TMCS_FREERUN | TMCK_DIV4; hwtimer.c uses 1 MHz
 * (TMCK_1MHZ = TMCK_DIV4), so one tick is one microsecond.
 *
 * The kernel driver may not have run and the clock gate state at the ROM
 * hand-off is unknown, so delay.c probes whether the counter actually moves
 * and falls back to a calibrated busy loop if it does not.
 */
#define TIMER0_BASE     0xF2403000u
#define TIMER0_CTRL     (TIMER0_BASE + 0x00)
#define TIMER0_CLR      (TIMER0_BASE + 0x04)
#define TIMER0_COUNT    (TIMER0_BASE + 0x0C)

#define TIMER0_CTRL_FREERUN_1MHZ  (0x1000u | 0x0030u | 0x0002u)  /* 0x1032 */

#define TIMER0_HZ       1000000u
#define TIMER0_TICKS_PER_US 1u

void timer_init(void);

/* Non-zero once timer_init() has confirmed the counter is running. */
extern int timer_running;

static inline u32 timer_ticks(void)
{
    return read32(TIMER0_COUNT);
}

#endif /* ZVE10_TIMER_H */
