#ifndef ZVE10_LED_H
#define ZVE10_LED_H

#include "io.h"

/*
 * Non-blocking status blinker: code N = N fast pulses (120 ms on/off), then a
 * 1.5 s gap, repeated. Driven from the card wait loops, so a hang still shows
 * the step it is stuck in.
 */
void led_init(void);
void led_set(u32 code);     /* 0 = off */
void led_tick(void);        /* call from every polling loop */
u32  led_code(void);

__attribute__((noreturn)) void led_hang(u32 code);

#endif /* ZVE10_LED_H */
