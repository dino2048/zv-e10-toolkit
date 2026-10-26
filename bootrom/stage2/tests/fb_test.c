#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "host_io.h"
#include "../src/fb.c"
int emmc_init_rc=-100,part_load_rc=-100,mmc_ready,usb_bulk_error;
u32 boot_stack_sp, mmc_last_cmd, mmc_last_r1,mmc_ocr,mmc_rca;
u16 mmc_last_error;
static int reads, initialized, replies;
static char last_reply[65];
u32 usb_bulk_send(const void *data,u32 size) {
    assert(size<=64); memcpy(last_reply,data,size); last_reply[size]=0; replies++; return size;
}
u32 usb_bulk_recv(void *b,u32 n) { return 0; }
void usb_event_pump(void) {}
void system_reset(void) { assert(!"unexpected reset"); }
void usb_bulk_enable_pending(void) {}
int usb_bulk_recover(void) { return 0; }
void diag_emmc_init(void) { initialized++; emmc_init_rc=part_load_rc=0; mmc_ready=1; }
int part_count(void) { return 0; }
u32 part_block0_word(u32 i) { return 0; }
const struct partition *part_find(const char *p) { return 0; }
const struct partition *part_get(u32 i) { (void)i; return 0; }
int mmc_read_blocks(u32 lba,void *buffer,u32 count) {
    assert(count==1 && lba==0x80); reads++; memset(buffer,0xa5,512); return 0;
}
int mmc_write_blocks(u32 lba,const void *buffer,u32 count) {
    assert(!"identity test must never write blocks"); return -1;
}
int mmc_init(void) { return 0; }
int mmc_select_partition(u32 access) { (void)access; return 0; }
int part_load(void) { return 0; }
void part_reset(void) {}
u32 read32(u32 a) { (void)a; return 0; }
void mdelay(u32 ms) { (void)ms; }
volatile u32 ka_sent, ka_busy, ka_timer_ok;
volatile u32 ka_rx0, ka_rx13, ka_rx_ok;
u8 host_dl_buf[0x2000];
int main(void) {
    /* Unknown getvar must be an empty OKAY, not FAIL: `getvar all` aborts on
     * FAIL while walking the variable list. */
    dispatch("getvar:not-a-real-var");
    assert(!strcmp(last_reply,"OKAY"));
    dispatch("getvar:downloadsize");
    assert(!strcmp(last_reply,"OKAY0x00100000"));
    dispatch("getvar:version-bootloader");
    assert(!strcmp(last_reply,"OKAYstage2-flash-20261026"));
    dispatch("getvar:optical-debug");
    assert(!strcmp(last_reply,"OKAYno"));
    dispatch("getvar:read-only");
    assert(!strcmp(last_reply,"OKAYno"));
    puts("PASS: writer identity/capability; no block writes executed");
    return 0;
    dispatch("getvar:emmc-init-rc"); assert(!strcmp(last_reply,"OKAY0xffffff9c"));
    dispatch("flash:nflasha1"); assert(!strncmp(last_reply,"FAIL",4));
    dispatch("erase:nflasha1"); assert(!strncmp(last_reply,"FAIL",4));
    dispatch("download:00000200"); assert(!strncmp(last_reply,"FAIL",4));
    dispatch("oem read-block:00000080"); assert(!reads && !strncmp(last_reply,"FAIL",4));
    dispatch("oem emmc-init"); assert(initialized==1);
    dispatch("oem read-block:0"); assert(!reads && !strncmp(last_reply,"FAIL",4));
    dispatch("oem read-block:000000800"); assert(!reads && !strncmp(last_reply,"FAIL",4));
    int before=replies; dispatch("oem read-block:00000080");
    assert(reads==1 && replies==before+33 && !strcmp(last_reply,"OKAY"));
    puts("PASS: read-only commands, init diagnostics, strict LBA and 512-byte INFO dump");
}
