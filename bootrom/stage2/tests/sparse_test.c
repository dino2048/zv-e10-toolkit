/* Host-only sparse validation test. Writes are counted; no device I/O.
 * Every rejected image must also leave the write counter at zero: the parser
 * has to refuse before it starts flashing. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "host_io.h"
#include "../src/fb.c"

int emmc_init_rc=-100, part_load_rc=-100, mmc_ready, usb_bulk_error;
u32 boot_stack_sp, mmc_last_cmd, mmc_last_r1, mmc_ocr, mmc_rca;
u16 mmc_last_error;
static u32 writes, sectors, last_lba;
static int write_rc;

u32 usb_bulk_send(const void *p, u32 n) { return n; }
u32 usb_bulk_recv(void *p, u32 n) { return 0; }
void usb_event_pump(void) {}
void usb_bulk_enable_pending(void) {}
int usb_bulk_recover(void) { return 0; }
void system_reset(void) { assert(!"unexpected reset"); }
void diag_emmc_init(void) {}
int part_count(void) { return 0; }
u32 part_block0_word(u32 i) { return 0; }
const struct partition *part_find(const char *n) { return 0; }
const struct partition *part_get(u32 i) { (void)i; return 0; }
int mmc_read_blocks(u32 lba, void *buf, u32 n) { return 0; }
int mmc_write_blocks(u32 lba, const void *buf, u32 n) {
    writes++; sectors += n; last_lba = lba;
    return write_rc;
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

static void put16(u32 o, u32 v) { dl_buf[o]=(u8)v; dl_buf[o+1]=(u8)(v>>8); }
static void put32(u32 o, u32 v) {
    for (u32 i=0; i<4; i++) dl_buf[o+i]=(u8)(v>>(8*i));
}

static u32 hdr(u32 blk_sz, u32 total_blks, u32 chunks) {
    memset(dl_buf, 0, 28);
    put32(0, SPARSE_MAGIC);
    put32(4, 1);
    put16(8, 28);
    put16(10, 12);
    put32(12, blk_sz);
    put32(16, total_blks);
    put32(20, chunks);
    return 28;
}
static u32 chunk(u32 off, u32 type, u32 blocks, u32 data_len) {
    put16(off, type);
    put32(off+4, blocks);
    put32(off+8, 12 + data_len);
    return off + 12 + data_len;
}
static void begin(void) { writes=0; sectors=0; last_lba=0; write_rc=0; }

#define REJECT(p, n) do { begin(); dl_size=(n); assert(flash_sparse(p) == -1); \
                          assert(writes == 0 && sectors == 0); } while (0)

int main(void) {
    struct partition p = {.start_bytes = 0x56000, .size_bytes = 4096};

    /* RAW with two 512-byte blocks. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 2, 1);
        o = chunk(o, CHUNK_RAW, 2, 1024);
        memset(dl_buf + 28 + 12, 0x5a, 1024);
        begin(); dl_size = o;
        assert(flash_sparse(&p) == 0);
        assert(writes == 1 && sectors == 2 && last_lba == 0x56000 / 512);
    }

    /* FILL + SKIP + RAW; skipped blocks are never written. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 4, 3);
        o = chunk(o, CHUNK_FILL, 1, 4); put32(o-4, 0x11223344);
        o = chunk(o, CHUNK_SKIP, 1, 0);
        o = chunk(o, CHUNK_RAW, 2, 1024);
        begin(); dl_size = o;
        assert(flash_sparse(&p) == 0);
        assert(writes == 2 && sectors == 3);
    }

    /* 4 KiB blocks: one sparse block is eight 512-byte sectors. */
    {
        p.size_bytes = 8192;
        u32 o = hdr(4096, 1, 1);
        o = chunk(o, CHUNK_FILL, 1, 4);
        begin(); dl_size = o;
        assert(flash_sparse(&p) == 0);
        assert(writes == 1 && sectors == 8);
    }

    /* The audit's case: header promises one block, the chunk writes two.
     * Rejecting at parse time is the point; nothing may reach eMMC. */
    {
        struct partition small = {.start_bytes = 51200, .size_bytes = 512};
        u32 o = hdr(512, 1, 1);
        o = chunk(o, CHUNK_FILL, 2, 4);
        REJECT(&small, o);
    }

    /* Chunks fit the partition but not the header's own block count. */
    {
        p.size_bytes = 65536;
        u32 o = hdr(512, 1, 2);
        o = chunk(o, CHUNK_FILL, 1, 4);
        o = chunk(o, CHUNK_FILL, 1, 4);
        REJECT(&p, o);
    }

    /* A split sparse image carries the whole total_blks but only its own
     * chunks; writing fewer blocks than the header is legitimate here, and
     * the host verifies the final readback. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 2, 1);
        o = chunk(o, CHUNK_FILL, 1, 4);
        begin(); dl_size = o;
        assert(flash_sparse(&p) == 0);
        assert(writes == 1 && sectors == 1);
    }

    /* RAW payload length does not match its block count. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 1, 1);
        o = chunk(o, CHUNK_RAW, 1, 516);
        REJECT(&p, o);
    }

    /* A bogus block count must not wrap into a small sector count. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 2, 1);
        o = chunk(o, CHUNK_RAW, 0xffffffffu, 0);
        REJECT(&p, o);
    }

    /* Image larger than the partition. */
    {
        struct partition one = {.start_bytes = 0, .size_bytes = 512};
        u32 o = hdr(512, 2, 1);
        o = chunk(o, CHUNK_FILL, 2, 4);
        REJECT(&one, o);
    }

    /* Chunk body cut short. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 2, 1);
        o = chunk(o, CHUNK_RAW, 2, 1024);
        REJECT(&p, o - 100);
    }

    /* SKIP chunk carrying payload. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 1, 1);
        o = chunk(o, CHUNK_SKIP, 1, 4);
        REJECT(&p, o);
    }

    /* Block size not a multiple of 512 (and zero). */
    {
        u32 o = hdr(1000, 1, 1);
        o = chunk(o, CHUNK_FILL, 1, 4);
        REJECT(&p, o);
        o = hdr(0, 1, 1);
        o = chunk(o, CHUNK_FILL, 1, 4);
        REJECT(&p, o);
    }

    /* Valid image, but eMMC refuses the write: the error must propagate. */
    {
        p.size_bytes = 4096;
        u32 o = hdr(512, 1, 1);
        o = chunk(o, CHUNK_FILL, 1, 4);
        begin(); write_rc = -1; dl_size = o;
        assert(flash_sparse(&p) == -1);
    }

    puts("PASS: sparse bounds, block accounting, payload lengths; no partial writes on reject");
    return 0;
}
