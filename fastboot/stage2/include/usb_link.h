#ifndef ZVE10_USB_LINK_H
#define ZVE10_USB_LINK_H

/*
 * Stage 1's exported entry points, pinned to ../../prebuilt/stage1.bin
 * (7636 B, SHA 8573b5d1...). tools/check_abi.py validates the full identity.
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


#define usb_bulk_recv          ((u32  (*)(void *, u32))       0xFE021705u)
#define usb_bulk_send          ((u32  (*)(void *, u32))       0xFE02182Fu)
#define usb_event_pump          ((void (*)(void))              0xFE021301u)
#define usb_bulk_abort          ((void (*)(void))              0xFE0217CFu)
#define usb_bulk_recover        ((int  (*)(void))              0xFE02180Du)
#define usb_bulk_enable_pending ((void (*)(void))              0xFE0216AFu)
#define dwc3_disconnect         ((void (*)(void))              0xFE020287u)
#define system_reset            ((void (*)(void))              0xFE0211B5u)
#define led_heartbeat           ((void (*)(void))              0xFE02107Du)

#define usb_bulk_error          (*(volatile int *)0xFE021E0Cu)

/* Stage 1's download staging area (1 MiB). */
#define STAGE1_DL_BUF         0xFE101300u
#define STAGE1_DL_MAX   0x00100000u


#endif /* ZVE10_USB_LINK_H */
