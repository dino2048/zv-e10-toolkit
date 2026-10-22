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
void mira_logx(const char *msg, u64 value);

#endif /* ZVE10_LOG_H */
