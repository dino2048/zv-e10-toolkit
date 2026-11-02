#ifndef ZVE10_LED_H
#define ZVE10_LED_H

#include "io.h"

/*
 * Status is reported through the mask ROM's blink routine; see led.c.
 * Codes: 0x2001 alive, 0x2002 USB core up, 0x2003 fastboot ready,
 * 0x2004 timeout, 0x2005 bus error, 0x2006 no PHY.
 */

void led_init(void);
void led_on(void);
void led_off(void);

/* One short pattern. The only sign of life before USB is up. */
void led_blip(void);

/* Marker pattern. */
void led_marker(void);

/* N short flashes, once (n is clamped to 12). */
void led_count(u32 n);

/* N quick flashes, no leading long pulse: breadcrumb for each init step. */
void led_step(u32 n);

/* One short pulse: "still alive, waiting". */
void led_heartbeat(void);

__attribute__((noreturn)) void led_fail(u32 code);

void led_activity(void);
void led_activity_tick(void);

__attribute__((noreturn)) void led_panic(void);

/* Milestone patterns. */
void led_usb_up(void);
void led_ready(void);
void led_timeout(void);
void led_bus_error(void);
void led_no_phy(void);

#endif /* ZVE10_LED_H */
