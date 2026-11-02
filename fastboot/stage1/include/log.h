#ifndef ZVE10_LOG_H
#define ZVE10_LOG_H

#include "io.h"

/*
 * PL011 UART0 at 0xF2000000 (arch/arm/mach-cxd900x0/include/mach/platform.h:55
 * CXD900X0_UART(x) = 0xf2000000 + 0x1000*x). Whether the pins are brought out
 * on a given body is not known; the writes are harmless either way and give a
 * second channel if a test point is found.
 */
void log_init(void);
void mira_log(const char *msg);

#if 1  /* the PL011 UART is not brought out; drop the strings everywhere */
/* These builds have to stay inside the ROM's ~2.2 s receive window, so drop the
 * assertion strings entirely rather than leave them in .rodata pointing at a
 * no-op. */
#define mira_logx(msg, value) ((void)0)
#else
void mira_logx(const char *msg, u64 value);
#endif

#endif /* ZVE10_LOG_H */
