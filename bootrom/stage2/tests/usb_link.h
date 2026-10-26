#ifndef ZVE10_USB_LINK_H
#define ZVE10_USB_LINK_H
#include "io.h"
u32 usb_bulk_recv(void *,u32);
u32 usb_bulk_send(const void *,u32);
void usb_event_pump(void);
void usb_bulk_enable_pending(void);
int usb_bulk_recover(void);
void system_reset(void);
extern int usb_bulk_error;
extern volatile u32 ka_sent, ka_busy, ka_timer_ok;
extern volatile u32 ka_rx0, ka_rx13, ka_rx_ok;
#define STAGE1_DL_BUF 0xFE101300u
#define STAGE1_DL_MAX 0x00100000u
extern u8 host_dl_buf[];
#endif
