#include "io.h"
#include "optlog.h"
#include "sdhci.h"
#include "partitions.h"
#include "usb_link.h"
#include "diag.h"
#include "timer.h"


/* Read-only diagnostic command loop. Stage 1 owns USB TRBs and event memory;
 * every passed buffer lives in eSRAM, not untrained DRAM. */
static u8 cmd_buf[512] __attribute__((aligned(64)));
static u8 resp_buf[64] __attribute__((aligned(64)));
static u32 read_buf[128] __attribute__((aligned(64)));
static u32 up_buf[64 * 128] __attribute__((aligned(64)));   /* 32 KB upload staging */
static const char digits[] = "0123456789abcdef";
static u32 last_usb_error;

/* Exported so the host can read the expected identity from this exact ELF. */
const char stage2_build_id[] = "stage2-flash-20261026";

/* Stage 1's 1 MiB DMA staging area is idle once stage 2 is running; reuse it
 * instead of a 16 KiB .bss buffer, so `max-download-size` matches stage 1 and
 * the CLI needs far fewer download/flash round trips.
 *
 * DL_BUF_ADDR exists only so the host tests can point it at a real buffer. */
#define DL_MAX    STAGE1_DL_MAX
#define DL_SECTION
#ifndef DL_BUF_ADDR
#define DL_BUF_ADDR STAGE1_DL_BUF
#endif
#define dl_buf ((u8 *)(DL_BUF_ADDR))


static int eq(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}
static const char *after(const char *s, const char *prefix)
{
    while (*prefix) if (*s++ != *prefix++) return 0;
    return s;
}
static int reply(const char *tag, const char *msg)
{
    u32 n=0;
    while (*tag && n<4) resp_buf[n++]=*tag++;
    while (*msg && n<sizeof(resp_buf)) resp_buf[n++]=*msg++;
    return usb_bulk_send(resp_buf,n)==n;
}
static void okay(const char *s) { (void)reply("OKAY",s); }
static void fail(const char *s) { (void)reply("FAIL",s); }
static int parse_hex(const char *s, u32 *out)
{
    u32 v = 0; int any = 0;
    for (;;) {
        u32 d;
        if (*s >= '0' && *s <= '9') d = (u32)(*s - '0');
        else if (*s >= 'a' && *s <= 'f') d = (u32)(*s - 'a') + 10u;
        else break;
        v = (v << 4) | d; any = 1; s++;
    }
    *out = v;
    return any;
}

static void hex8(char *out, u32 n)
{
    for (u32 i=0;i<8;i++) out[i]=digits[(n>>((7-i)*4))&15];
}
static void value(u32 n)
{
    char line[11]={'0','x'};
    hex8(line+2,n); line[10]=0; okay(line);
}

/* The standard CLI never issues `oem emmc-init`; bring the card and the
 * partition table up on first use. `fastboot flash` asks for
 * `getvar:partition-size:<name>` before it downloads anything, so this has to
 * work from getvar as well as from flash/fetch.
 *
 * Stage 2 only: the single-stage image has ~20 bytes of headroom under the
 * 8168-byte injection limit, so it keeps the explicit `oem emmc-init` path. */
static u8 left_user;

/*
 * Coming back from a boot area: CMD6 with PARTITION_ACCESS=0 is accepted
 * (R1b clears) but does not actually take effect on this card -- measured on
 * hardware: after fetching boot0, LBA0 still read boot0's "EXBL" header. A
 * full mmc_init() does return to the user area, verified in the same session.
 */
static void leave_boot_area(void)
{
    if (left_user && mmc_init() == MMC_OK)
        left_user = 0;
}

/* Every raw-LBA / user-area command goes through this. */
static int ensure_user_area(void)
{
    if (!left_user && mmc_select_partition(0) == MMC_OK)
        return 0;
    if (mmc_init() != MMC_OK)
        return -1;
    left_user = 0;
    return 0;
}

static int emmc_ready(void)
{
    if (!mmc_ready && mmc_init() != MMC_OK)
        return -1;
    if (!part_count()) {
        if (ensure_user_area() != 0)
            return -1;
        part_reset();
        if (part_load() != MMC_OK)
            return -1;
    }
    return 0;
}

/* Select the area a partition lives in. The first switch needs EXT_CSD; if
 * that read fails on a card we never moved off the user area, keep the old
 * behaviour rather than failing every command. */
static int select_area(const struct partition *p)
{
    int ret = mmc_select_partition(p->dev);

    if (ret == MMC_OK) {
        left_user = p->dev != 0;
        return 0;
    }
    if (!p->dev && left_user && mmc_init() == MMC_OK) {
        left_user = 0;
        return 0;
    }
    return (!p->dev && !left_user) ? 0 : -1;
}
static void getvar(const char *name)
{
    const char *rest;
    if ((rest=after(name,"partition-size:"))) {
        const struct partition *p;
        if (emmc_ready() != 0) { fail("emmc"); return; }
        p = part_find(rest);
        if (p) value(p->size_bytes); else fail("no partition");
    }
    else if ((rest=after(name,"partition-type:"))) {
        if (part_find(rest)) okay("raw"); else fail("no partition");
    }
    else if (eq(name,"version-bootloader")) okay(stage2_build_id);
    else if (eq(name,"version")) okay("0.4");
    else if (eq(name,"product")) okay("ZVE10");
    else if (eq(name,"serialno")) okay("ZVE10-stage2");
    else if (eq(name,"read-only")) {
        okay("no");
    }
    else if (eq(name,"optical-debug")) {
        okay("no");
    }
    else if (eq(name,"emmc-status")) value(mmc_ready);
    else if (eq(name,"emmc-init-rc")) value((u32)emmc_init_rc);
    else if (eq(name,"part-load-rc")) value((u32)part_load_rc);
    else if (eq(name,"part-count")) value(part_count());
    else if (eq(name,"mmc-last-cmd")) value(mmc_last_cmd);
    else if (eq(name,"mmc-last-error")) value(mmc_last_error);
    else if (eq(name,"mmc-last-r1")) value(mmc_last_r1);
    else if (eq(name,"mmc-ocr")) value(mmc_ocr);
    else if (eq(name,"entry-stack-sp")) value(boot_stack_sp);
    else if (eq(name,"usb-last-error")) value(last_usb_error);
    else if (eq(name,"max-download-size")) value(DL_MAX);
    /* Old clients ask for this name instead of max-download-size. */
    else if (eq(name,"downloadsize")) value(DL_MAX);
    /* The CLI asks for this before it will issue `fetch:` at all. */
    else if (eq(name,"max-fetch-size")) value(0x10000);
    else if (eq(name,"block0-head")) {
        char line[33];
        for(u32 i=0;i<4;i++) hex8(line+i*8,part_block0_word(i));
        line[32]=0; okay(line);
    }
    /* Unknown variables must answer OKAY with an empty value: `fastboot
     * getvar all` walks the list and a FAIL aborts the walk. */
    else okay("");
}

static void read_block(const char *s)
{
    u32 lba=0;
    for (u32 i=0;i<8;i++) {
        u32 d;
        if (s[i]>='0' && s[i]<='9') d=s[i]-'0';
        else if(s[i]>='a' && s[i]<='f') d=s[i]-'a'+10;
        else if(s[i]>='A' && s[i]<='F') d=s[i]-'A'+10;
        else { fail("need 8 hex digits"); return; }
        lba=(lba<<4)|d;
    }
    if(s[8]) { fail("need 8 hex digits"); return; }
    if(!mmc_ready) { fail("emmc-init first"); return; }
    /* Raw LBAs mean the user area, even if a boot-area fetch ran before. */
    if (ensure_user_area() != 0) { fail("part area"); return; }
    int rc=mmc_read_blocks(lba,read_buf,1);
    if(rc) { fail("read failed"); return; }
    for(u32 off=0;off<512;off+=16) {
        char line[42];
        hex8(line,off); line[8]=':';
        const u8 *bytes=(const u8 *)read_buf;
        for(u32 i=0;i<16;i++) {
            line[9+i*2]=digits[bytes[off+i]>>4];
            line[10+i*2]=digits[bytes[off+i]&15];
        }
        line[41]=0;
        if(!reply("INFO",line)) return;
    }
    okay("");
}

/* oem upload:<lba>:<count> - DATA<len> then raw bytes, then OKAY. */
/* fetch: covers multi-block reads, so the single-stage image drops this. */
static void upload(const char *s)
{
    u32 lba = 0, cnt = 0;
    const char *colon = s;

    while (*colon && *colon != ':') colon++;
    if (!parse_hex(s, &lba) || *colon != ':') { fail("usage: oem upload:lba:count"); return; }
    if (!parse_hex(colon + 1, &cnt)) { fail("bad count"); return; }
    if (!cnt || cnt > 64) { fail("count 1..64"); return; }
    if (!mmc_ready) { fail("emmc-init first"); return; }
    if (ensure_user_area() != 0) { fail("part area"); return; }

    int rc = mmc_read_blocks(lba, up_buf, cnt);
    if (rc) { fail("block read failed"); return; }

    u32 n = cnt * 512u;
    char len[9];
    hex8(len, n); len[8] = 0;
    if (!reply("DATA", len)) return;
    usb_bulk_send((void *)up_buf, n);
    okay("");
}


/*
 * Standard `fastboot download:` + `flash:`.
 *
 * The host sends the image *before* it names the target partition, so the
 * bytes have to be parked somewhere. The DWC3's DMA arena at 0xFE100000 is
 * NOLOAD and already permanently mapped for the controller's AXI master, so
 * the staging buffer costs nothing in the image.
 */
static u32 dl_size, dl_got;

/* Returns 1 when the whole image is in, 0 on any failure. */
static void single_download(const char *args)
{
    u32 size;
    char line[9];

    if (!parse_hex(args, &size) || size == 0 || size > DL_MAX) {
        fail("bad size");
        return;
    }
    dl_size = size;
    dl_got = 0;
    hex8(line, size);
    line[8] = 0;
    if (!reply("DATA", line))
        return;

    while (dl_got < dl_size) {
        u32 want = dl_size - dl_got;
        u32 n;
        if (want > 0x10000u)
            want = 0x10000u;
        n = usb_bulk_recv(dl_buf + dl_got, want);
        if (!n)
            break;
        dl_got += n;
    }
    if (dl_got != dl_size) {
        fail("dl short");
        return;
    }
    okay("");
}

/*
 * Sparse images (libsparse): the standard way to flash more than one
 * max-download-size, and what A7M4's payload does for the same reason.
 * `fastboot` splits an oversized sparse file into several download/flash
 * pairs; each split after the first starts with a DONT_CARE chunk covering
 * what is already written, which is how the offset is conveyed. So the device
 * needs no write cursor: every split describes its own placement.
 */
#ifndef NO_SPARSE
#define SPARSE_MAGIC     0xED26FF3Au
#define SPARSE_HDR       28
#define SPARSE_CHUNK_HDR 12
#define CHUNK_RAW        0xCAC1
#define CHUNK_FILL       0xCAC2
#define CHUNK_SKIP       0xCAC3
#define CHUNK_CRC32      0xCAC4
#define WRITE_SECTORS    64          /* 32 KB, one up_buf */

static u32 rd32(const u8 *p)
{
    return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
}

static u32 rd16(const u8 *p)
{
    return (u32)p[0] | ((u32)p[1] << 8);
}

/* Writes `nsec` sectors at `sector`, from `src` or from a repeated 32-bit
 * pattern. Chunked so no single eMMC command holds the bus too long.
 *
 * `write_limit` is the first sector past the resolved partition. Sparse is
 * already validated before anything is written, so this is belt and braces for
 * a future caller. Stage 2 only: the single-stage image has 20 bytes of
 * headroom under the 8168-byte injection limit and keeps validation alone. */
static u32 write_limit;

static int write_range(u32 sector, const u8 *src, u32 nsec, u32 pattern, int fill)
{
    if (sector > write_limit || nsec > write_limit - sector)
        return -1;

    while (nsec) {
        u32 n = nsec > WRITE_SECTORS ? WRITE_SECTORS : nsec;

        if (fill) {
            u32 *w = up_buf;
            for (u32 i = 0; i < n * 128u; i++)
                w[i] = pattern;
            src = (const u8 *)up_buf;
        }
        if (mmc_write_blocks(sector, src, n) != MMC_OK)
            return -1;
        sector += n;
        nsec -= n;
        if (!fill)
            src += n * 512u;
    }
    return 0;
}

/* Validates the whole image without touching eMMC. A chunk table that turns
 * bad halfway through must be rejected before the first sector is written:
 * checking as we write leaves a half-flashed partition behind.
 *
 * `chunk_blks` is bounded by the blocks the header still owes, so the running
 * total can never pass `total_blks`, and `total_blks * blk_sz` is checked
 * against the partition by division. Both keep the products from wrapping. */
static int sparse_validate(const struct partition *p, u32 *chunks_off)
{
    u32 hdr_sz, chunk_hdr_sz, blk_sz, total_blks, total_chunks, spb, off, done, i;

    if (dl_size < SPARSE_HDR || rd16(dl_buf + 4) != 1)
        return -1;
    hdr_sz       = rd16(dl_buf + 8);
    chunk_hdr_sz = rd16(dl_buf + 10);
    blk_sz       = rd32(dl_buf + 12);
    total_blks   = rd32(dl_buf + 16);
    total_chunks = rd32(dl_buf + 20);

    if (hdr_sz < SPARSE_HDR || hdr_sz > dl_size ||
        chunk_hdr_sz < SPARSE_CHUNK_HDR ||
        !blk_sz || (blk_sz & 511u))
        return -1;

    spb = blk_sz / 512u;
    if (total_blks > p->size_bytes / blk_sz)
        return -1;

    off = hdr_sz;
    done = 0;

    for (i = 0; i < total_chunks; i++) {
        u32 type, chunk_blks, total_sz, data_len;

        if (off > dl_size || chunk_hdr_sz > dl_size - off)
            return -1;
        type       = rd16(dl_buf + off);
        chunk_blks = rd32(dl_buf + off + 4);
        total_sz   = rd32(dl_buf + off + 8);
        if (total_sz < chunk_hdr_sz || total_sz > dl_size - off)
            return -1;

        if (chunk_blks > total_blks - done)
            return -1;
        data_len = total_sz - chunk_hdr_sz;

        switch (type) {
        case CHUNK_RAW:
            if (data_len != chunk_blks * spb * 512u)
                return -1;
            break;
        case CHUNK_FILL:
        case CHUNK_CRC32:
            if (data_len != 4u)
                return -1;
            break;
        case CHUNK_SKIP:
            if (data_len != 0)
                return -1;
            break;
        default:
            return -1;
        }
        done += chunk_blks;
        off += total_sz;
    }

    /* A split sparse image carries the whole image's total_blks but only the
     * chunks for its own range, so `done` may legitimately be smaller here.
     * Every chunk is bounded by the header above; the host verifies the final
     * readback. */
    (void)done;

    *chunks_off = hdr_sz;
    return 0;
}

/* Returns 0, or -1 with a reason the caller turns into a FAIL. */
static int flash_sparse(const struct partition *p)
{
    u32 chunk_hdr_sz, blk_sz, spb, off, sector, i;

    if (sparse_validate(p, &off) != 0)
        return -1;

    chunk_hdr_sz = rd16(dl_buf + 10);
    blk_sz       = rd32(dl_buf + 12);
    spb          = blk_sz / 512u;
    sector       = p->start_bytes / 512u;
    write_limit  = sector + p->size_bytes / 512u;

    for (i = 0; i < rd32(dl_buf + 20); i++) {
        u32 type       = rd16(dl_buf + off);
        u32 chunk_blks = rd32(dl_buf + off + 4);
        u32 total_sz   = rd32(dl_buf + off + 8);
        const u8 *data = dl_buf + off + chunk_hdr_sz;
        u32 nsec       = chunk_blks * spb;

        switch (type) {
        case CHUNK_RAW:
            if (write_range(sector, data, nsec, 0, 0))
                return -1;
            break;
        case CHUNK_FILL:
            if (write_range(sector, 0, nsec, rd32(data), 1))
                return -1;
            break;
        default:                    /* SKIP / CRC32: leave those sectors alone */
            break;
        }
        sector += nsec;
        off += total_sz;
    }
    return 0;
}

#endif /* !NO_SPARSE */

static void single_flash(const char *args)
{
    const struct partition *p;

    if (!dl_size || dl_got != dl_size) { fail("nothing"); return; }
    if (emmc_ready() != 0) { fail("emmc"); return; }
    p = part_find(args);
    if (!p) { fail("no partition"); return; }
    if (select_area(p) != 0) { fail("part area"); return; }

#ifndef NO_SPARSE
    if (rd32(dl_buf) == SPARSE_MAGIC) {
        if (flash_sparse(p) != 0) { fail("sparse"); return; }
        dl_size = 0;
        dl_got = 0;
        leave_boot_area();
        okay("");
        return;
    }
#endif
    {
        u32 blocks = (dl_size + 511u) / 512u;

        if (dl_size > p->size_bytes) { fail("too large"); return; }
        if (mmc_write_blocks(p->start_bytes / 512u, dl_buf, blocks) != MMC_OK) {
            fail("wr failed");
            return;
        }
    }
    dl_size = 0;
    dl_got = 0;
    leave_boot_area();
    okay("");
}

/* One hex field, terminated by ':' or NUL. Returns 0 if the field is empty or
 * has no hex digit. */
static int hex_field(const char **sp, u32 *out)
{
    const char *s = *sp;
    u32 v = 0;
    int any = 0;

    /* The CLI writes the fields as 0x00000000; bare hex is accepted too. */
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X'))
        s += 2;

    while (*s && *s != ':') {
        u32 d;
        if (*s >= '0' && *s <= '9') d = (u32)(*s - '0');
        else if (*s >= 'a' && *s <= 'f') d = (u32)(*s - 'a') + 10u;
        else if (*s >= 'A' && *s <= 'F') d = (u32)(*s - 'A') + 10u;
        else return 0;
        v = (v << 4) | d;
        any = 1;
        s++;
    }
    if (*s == ':') s++;
    *sp = s;
    *out = v;
    return any;
}

/*
 * Standard `fastboot fetch <partition> <file>`: fetch:<name>:<off>:<size>.
 * Answers DATA<8 hex> then the bytes, so a backup needs no custom host code.
 */
static void single_fetch(const char *args)
{
    const char *s = args;
    char name[PART_NAME_LEN];
    u32 n = 0, off, size, lba, sent = 0;
    const struct partition *p;
    char len[9];

    while (*s && *s != ':' && n < sizeof(name) - 1) name[n++] = *s++;
    name[n] = 0;
    if (*s == ':') s++;

    if (!hex_field(&s, &off) || !hex_field(&s, &size)) {
        fail("fetch fmt");
        return;
    }
    if (!size) { fail("zero size"); return; }
    if (emmc_ready() != 0) { fail("emmc"); return; }
    p = part_find(name);
    if (!p) { fail("no partition"); return; }
    if (off > p->size_bytes || size > p->size_bytes - off) {
        fail("outside");
        return;
    }
    if (select_area(p) != 0) { fail("part area"); return; }

    hex8(len, size);
    len[8] = 0;
    if (!reply("DATA", len))
        return;

    lba = (p->start_bytes + off) / 512u;
    while (sent < size) {
        u32 want = size - sent;
        u32 blocks;

        if (want > 0x8000u) want = 0x8000u;      /* 64 blocks into up_buf */
        blocks = (want + 511u) / 512u;
        if (mmc_read_blocks(lba, up_buf, blocks) != MMC_OK) {
            fail("read failed");
            return;
        }
        if (!usb_bulk_send((void *)up_buf, want))
            return;
        lba += blocks;
        sent += want;
    }
    /* A boot-area read leaves the card on that area; CMD6 back to 0 does not
     * take effect, so re-init before returning to the host. */
    leave_boot_area();
    okay("");
}

/* Read-only keepalive probe. The 270 s test only proved that the camera died
 * at ~241 s; this reports whether keepalive ever ran, whether the SIO channel
 * accepted the message, and whether Timer0 is advancing. */
static char *ka_field(char *p, const char *tag, u32 v)
{
    while (*tag)
        *p++ = *tag++;
    hex8(p, v);
    p += 8;
    *p++ = ' ';
    return p;
}

static void cmd_ka_probe(void)
{
    char line[64];
    char *p;
    u32 t0 = timer_ticks(), t1, ctrl, len, d0;
    volatile u32 spin;

    /* Self-contained delay: calling mdelay() would pull the whole timer-aware
     * delay path back into the image. */
    for (spin = 0; spin < 200000u; spin++)
        ;
    t1 = timer_ticks();
    ctrl = read32(0xF2405000u);
    len  = read32(0xF240500Cu);
    d0   = read32(0xF2405100u) & 0xffu;

    p = line;
    p = ka_field(p, "t0=", t0);
    p = ka_field(p, "t1=", t1);
    p = ka_field(p, "ctrl=", ctrl);
    *p = 0;
    reply("INFO", line);

    p = line;
    p = ka_field(p, "len=", len);
    p = ka_field(p, "d0=", d0);
    p = ka_field(p, "sent=", ka_sent);
    p = ka_field(p, "busy=", ka_busy);
    *p = 0;
    reply("INFO", line);

    p = line;
    p = ka_field(p, "rx0=", ka_rx0);
    p = ka_field(p, "rx13=", ka_rx13);
    p = ka_field(p, "ok=", ka_rx_ok);
    *p = 0;
    reply("INFO", line);
    okay("");
}

/* `oem partition`: name, start, size, device. Same purpose as A7M4's listing. */
static void pt_line(const char *name, const struct partition *p)
{
    char line[64];
    char *q = line;

    while (*name && q < line + 16)
        *q++ = *name++;
    *q++ = ' ';
    q = ka_field(q, "start=", p->start_bytes);
    q = ka_field(q, "size=", p->size_bytes);
    q = ka_field(q, "dev=", p->dev);
    *q = 0;
    reply("INFO", line);
}

static void cmd_oem_partition(void)
{
    u32 i;

    if (emmc_ready() != 0) { fail("emmc"); return; }

    /* part_find() returns one shared static entry for the virtual partitions,
     * so resolve and print each one before asking for the next. */
    {
        const struct partition *b = part_find("nflashaB0");
        if (b) pt_line("nflashaB0", b);
    }
    {
        const struct partition *b = part_find("nflashaB1");
        if (b) pt_line("nflashaB1", b);
    }
    for (i = 0; i < (u32)part_count(); i++) {
        const struct partition *p = part_get(i);

        if (p && p->size_bytes)
            pt_line(p->name, p);
    }
    {
        const struct partition *w = part_find("nflasha");

        if (w) pt_line("nflasha", w);
    }
    okay("");
}

static void do_reboot(void)
{
    okay("");
    /* Let the reply reach the host before the device leaves the bus. The
     * size-bound single-stage image skips this and resets immediately. */
    u32 t0 = timer_ticks();
    for (u32 i = 0; i < 5000000u; i++) {
        if (timer_ticks() - t0 > 50000u)
            break;
    }
    system_reset();
}

static void dispatch(const char *cmd)
{
    const char *rest;
    if((rest=after(cmd,"getvar:"))) getvar(rest);
    else if(eq(cmd,"oem emmc-init")) {
        opt_str("DI");
        diag_emmc_init();
        opt_dec("RC",(u32)emmc_init_rc);
        opt_dec("PT",(u32)part_load_rc);
        opt_str("DR");
        if(!emmc_init_rc && !part_load_rc) { opt_str("TX OK"); okay("card ready"); }
        else { opt_str("TX FAIL"); fail("init failed"); }
    }
    else if(eq(cmd,"oem ka")) cmd_ka_probe();
    else if(eq(cmd,"oem partition")) cmd_oem_partition();
    else if((rest=after(cmd,"oem read-block:"))) read_block(rest);
    else if((rest=after(cmd,"oem upload:"))) upload(rest);
    else if((rest=after(cmd,"fetch:"))) single_fetch(rest);
    /* reboot is a standard command in every build, including read-only. */
    else if(eq(cmd,"reboot")) do_reboot();
    else if((rest=after(cmd,"download:"))) single_download(rest);
    else if((rest=after(cmd,"flash:"))) single_flash(rest);
    else if((rest=after(cmd,"erase:"))) fail("no erase");
    else fail("unknown cmd");
}

void fb_loop(void)
{
    for (;;) {
        usb_bulk_enable_pending();
        if(usb_bulk_error) {
            last_usb_error=(u32)usb_bulk_error;
            if(usb_bulk_recover()) { usb_event_pump(); continue; }
        }
        u32 n=usb_bulk_recv(cmd_buf,sizeof(cmd_buf));
        if(!n) continue;
        if(n>=sizeof(cmd_buf)) { fail("cmd too long"); continue; }
        cmd_buf[n]=0;
        /* Every optical frame blocks ~150 ms; bulk uploads would dominate. */
        if (!after((const char *)cmd_buf, "oem upload:"))
            opt_str((const char *)cmd_buf);
        dispatch((const char *)cmd_buf);
    }
}
