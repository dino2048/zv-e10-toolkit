#ifndef ZVE10_OPTLOG_H
#define ZVE10_OPTLOG_H

#include "io.h"

/*
 * Optical log on the tally LED (GPIO0 bit3, active low), 1200 baud 8N1,
 * light-inverted. Same frame format as the receiver firmware:
 *   AA AA | TYPE | SEQ | LEN | payload | CRC8(poly 0x07, init 0)
 *
 * Blocking: roughly 100 ms per short line. Use only around command
 * boundaries, never inside the SDHCI wait loops.
 */
/* Normal firmware does not touch the optical GPIO or restart timer0. */
static inline void opt_init(void) {}
static inline int opt_ok(void) { return 0; }
static inline void opt_str(const char *s) { (void)s; }
static inline void opt_val(const char *tag, u32 v) { (void)tag; (void)v; }
static inline void opt_dec(const char *tag, u32 v) { (void)tag; (void)v; }

#endif
