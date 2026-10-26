#ifndef ZVE10_USB_LINK_H
#define ZVE10_USB_LINK_H

/*
 * Stage 1's exported entry points, pinned to ../../prebuilt/stage1.bin
 * (8028 B, SHA 4b63d41f...). tools/check_abi.py validates the full identity.
 *
 * These are called through function pointers with the Thumb bit set: absolute
 * untyped linker symbols in the old build produced an immediate BLX to
 * Arm state. Typed Thumb symbols would be another valid solution. A pointer call emits BLX r3, which
 * takes the state from bit0.
 */
#include "io.h"

#ifndef BULK_MAXPACKET
#define BULK_MAXPACKET 512
#endif


#define usb_bulk_recv          ((u32  (*)(void *, u32))       0xFE02188Du)
#define usb_bulk_send          ((u32  (*)(void *, u32))       0xFE0219B7u)
#define usb_event_pump          ((void (*)(void))              0xFE021485u)
#define usb_bulk_abort          ((void (*)(void))              0xFE021957u)
#define usb_bulk_recover        ((int  (*)(void))              0xFE021995u)
#define usb_bulk_enable_pending ((void (*)(void))              0xFE021837u)
#define dwc3_disconnect         ((void (*)(void))              0xFE020287u)
#define system_reset            ((void (*)(void))              0xFE021339u)
#define led_heartbeat           ((void (*)(void))              0xFE0211FBu)

#define usb_bulk_error          (*(volatile int *)0xFE021FB4u)

/* Keepalive state, for the read-only `oem ka` probe. */
#define ka_sent                 (*(volatile u32 *)0xFE021F8Cu)
#define ka_busy                 (*(volatile u32 *)0xFE021F90u)
#define ka_timer_ok             (*(volatile u32 *)0xFE021F7Cu)
#define ka_rx0                  (*(volatile u32 *)0xFE021F94u)
#define ka_rx13                 (*(volatile u32 *)0xFE021F98u)
#define ka_rx_ok                (*(volatile u32 *)0xFE021F9Cu)

/* Stage 1's download staging area (1 MiB). */
#define STAGE1_DL_BUF         0xFE101300u
#define STAGE1_DL_MAX   0x00100000u


#endif /* ZVE10_USB_LINK_H */
