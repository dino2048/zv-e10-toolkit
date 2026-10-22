#include "io.h"
#include "fastboot.h"
#include "usb.h"
#include "dwc3.h"
#include "reset.h"
#include "timer.h"

/*
 * Minimal fastboot protocol on top of usb.c's bulk endpoints.
 *
 * Two forward slashes are not a thing here: this payload only exists to prove
 * the USB path and to give the host a memory window. Partition/flash commands
 * are acknowledged as unsupported; eMMC comes later, over `oem load`/`oem
 * call` if it does not fit in the serial-boot budget.
 *
 * Wire format (fastboot 0.4):
 *   host -> device   ASCII command, no terminator, one bulk packet
 *   device -> host   "OKAY" | "FAIL<text>" | "INFO<text>" | "DATA<8 hex>"
 */

#define FB_COMMAND_MAX   128
#define FB_RESPONSE_MAX  256
#define DOWNLOAD_MAX     0x100000u          /* 1 MiB, fits the .usbdma arena */

#define DMA_SECTION __attribute__((section(".usbdma"), aligned(64)))

static u8  cmd_buf[FB_COMMAND_MAX]        DMA_SECTION;
static u8  resp_buf[FB_RESPONSE_MAX]      DMA_SECTION;
static u8  download_buf[DOWNLOAD_MAX]     DMA_SECTION;

static u32 download_len;

static const char hexdigits[] = "0123456789abcdef";

/* ---- string helpers ----------------------------------------------------- */

static int str_eq(const char *a, const char *b)
{
    while (*a && *a == *b) {
        a++;
        b++;
    }
    return *a == *b;
}

static const char *str_after(const char *s, const char *prefix)
{
    while (*prefix) {
        if (*s++ != *prefix++)
            return 0;
    }
    return s;
}

static u32 str_copy(char *dst, const char *src, u32 max)
{
    u32 n = 0;

    while (*src && n < max)
        dst[n++] = *src++;
    return n;
}

static u32 str_append(char *dst, u32 n, u32 size, const char *src)
{
    while (*src && n + 1 < size)
        dst[n++] = *src++;
    return n;
}

static u32 hex_format(char *dst, u32 value, u32 digits)
{
    u32 i;

    for (i = 0; i < digits; i++)
        dst[i] = hexdigits[(value >> ((digits - 1 - i) * 4)) & 0xf];
    return digits;
}

static u64 hex_parse(const char *s, const char **end)
{
    u64 v = 0;

    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X'))
        s += 2;

    for (;;) {
        char c = *s;
        u32 d;

        if (c >= '0' && c <= '9')       d = (u32)(c - '0');
        else if (c >= 'a' && c <= 'f')  d = (u32)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F')  d = (u32)(c - 'A' + 10);
        else break;

        v = (v << 4) | d;
        s++;
    }

    if (end)
        *end = s;
    return v;
}

/*
 * A read of an address whose bus has no target does not abort here, it stalls
 * the AXI and wedges the whole payload -- DRAM is not trained in this context,
 * so an address that silently truncates into DRAM (a typo, or a >32-bit value
 * parsed as u32) kills the session. Only the peripheral and eSRAM windows are
 * exposed.
 */
static int addr_ok(u64 addr, u32 len)
{
    u64 end = addr + len;

    if (addr > 0xffffffffull)
        return 0;
    if (addr >= 0xf0000000ull && end <= 0xf4000000ull)
        return 1;
    if (addr >= 0xfe000000ull && end <= 0xff000000ull)
        return 1;
    return 0;
}

/* ---- responses ---------------------------------------------------------- */

static void fb_reply(const char *tag, const char *msg)
{
    u32 n = str_copy((char *)resp_buf, tag, 4);
    n = str_append((char *)resp_buf, n, sizeof(resp_buf), msg ? msg : "");
    usb_bulk_send(resp_buf, n);
}

static void fb_okay(const char *msg) { fb_reply("OKAY", msg); }
static void fb_fail(const char *msg) { fb_reply("FAIL", msg); }
static void fb_info(const char *msg) { fb_reply("INFO", msg); }

static void fb_result(const char *msg)
{
    fb_info(msg);
    fb_okay("");
}

/* ---- oem peek / poke / call / load -------------------------------------- */

static void cmd_peek(const char *args)
{
    const char *p;
    u32 addr;
    u32 len, off;
    char line[FB_RESPONSE_MAX];

    u64 addr64 = hex_parse(args, &p);

    len = 4;
    if (*p == ':')
        len = (u32)hex_parse(p + 1, 0);

    if (len == 0 || len > 0x1000) {
        fb_fail("bad length (max 0x1000)");
        return;
    }

    addr64 &= ~3ull;
    len = (len + 3) & ~3u;

    if (!addr_ok(addr64, len)) {
        fb_fail("address outside 0xf0000000-0xf3ffffff / 0xfe000000-0xfeffffff");
        return;
    }
    addr = (u32)addr64;

    for (off = 0; off < len; off += 16) {
        u32 n = 0;
        u32 i;

        n += hex_format(line + n, addr + off, 8);
        line[n++] = ':';

        for (i = 0; i < 16 && off + i < len; i += 4) {
            u32 word = read32(addr + off + i);
            line[n++] = ' ';
            n += hex_format(line + n, word, 8);
        }
        line[n] = 0;
        fb_info(line);
    }

    fb_okay("");
}

static void cmd_poke(const char *args)
{
    const char *p;
    u64 addr64;
    u32 addr, value;
    char line[FB_RESPONSE_MAX];
    u32 n = 0;

    addr64 = hex_parse(args, &p);
    if (*p != ':') {
        fb_fail("usage: oem poke:<addr>:<value>");
        return;
    }
    value = (u32)hex_parse(p + 1, 0);

    addr64 &= ~3ull;
    if (!addr_ok(addr64, 4)) {
        fb_fail("address outside the allowed windows");
        return;
    }
    addr = (u32)addr64;
    write32(addr, value);
    dsb();

    n = str_append(line, n, sizeof(line), "wrote ");
    n += hex_format(line + n, value, 8);
    n = str_append(line, n, sizeof(line), " -> ");
    n += hex_format(line + n, addr, 8);
    n = str_append(line, n, sizeof(line), " readback ");
    n += hex_format(line + n, read32(addr), 8);
    line[n] = 0;
    fb_result(line);
}

/* `oem call:<addr>` -- call the address as u32 f(void), report the result. */
static void cmd_call(const char *args)
{
    u64 addr64 = hex_parse(args, 0);
    u32 addr;
    u32 (*fn)(void);

    if (!addr_ok(addr64, 4)) {
        fb_fail("address outside the allowed windows");
        return;
    }
    addr = (u32)addr64;
    fn = (u32 (*)(void))addr;
    u32 ret;
    char line[FB_RESPONSE_MAX];
    u32 n;

    if (!addr) {
        fb_fail("usage: oem call:<addr>");
        return;
    }

    ret = fn();

    n = str_append(line, 0, sizeof(line), "call ");
    n += hex_format(line + n, addr, 8);
    n = str_append(line, n, sizeof(line), " -> ");
    n += hex_format(line + n, ret, 8);
    line[n] = 0;
    fb_result(line);
}

/* `oem load:<addr>` -- copy the staged download to addr and report the length. */
static void cmd_load(const char *args)
{
    u64 addr64 = hex_parse(args, 0);
    u32 addr;
    char line[FB_RESPONSE_MAX];
    u32 n = 0;
    u32 i;

    addr = (u32)addr64;

    if (!download_len) {
        fb_fail("nothing staged; download first");
        return;
    }
    if (!addr || !addr_ok(addr64, download_len)) {
        fb_fail("usage: oem load:<addr> (in an allowed window)");
        return;
    }

    for (i = 0; i < download_len; i++)
        ((u8 *)addr)[i] = download_buf[i];
    dsb();

    n = str_append(line, n, sizeof(line), "loaded ");
    n += hex_format(line + n, download_len, 8);
    n = str_append(line, n, sizeof(line), " bytes -> ");
    n += hex_format(line + n, addr, 8);
    line[n] = 0;
    fb_result(line);
}

static void cmd_oem_help(void)
{
    fb_info("peek:<addr>[:<len>]   dump memory, max 0x1000");
    fb_info("poke:<addr>:<val>     32-bit write, reports readback");
    fb_info("call:<addr>           call addr as u32 f(void)");
    fb_info("load:<addr>           copy staged download to addr");
    fb_okay("");
}

static void cmd_oem(const char *args)
{
    const char *rest;

    if ((rest = str_after(args, "peek:")) != 0) {
        cmd_peek(rest);
        return;
    }
    if ((rest = str_after(args, "poke:")) != 0) {
        cmd_poke(rest);
        return;
    }
    if ((rest = str_after(args, "call:")) != 0) {
        cmd_call(rest);
        return;
    }
    if ((rest = str_after(args, "load:")) != 0) {
        cmd_load(rest);
        return;
    }
    if (str_eq(args, "help")) {
        cmd_oem_help();
        return;
    }
    fb_fail("unknown oem command (try: oem help)");
}

/* ---- getvar ------------------------------------------------------------- */

static void cmd_getvar(const char *name)
{
    char line[FB_RESPONSE_MAX];
    u32 n;

    if (str_eq(name, "version")) {
        fb_okay("0.4");
    } else if (str_eq(name, "product")) {
        fb_okay("ZVE10");
    } else if (str_eq(name, "serialno")) {
        fb_okay("ZVE10-fastboot");
    } else if (str_eq(name, "max-download-size") ||
               str_eq(name, "downloadsize")) {
        n = str_append(line, 0, sizeof(line), "0x");
        n += hex_format(line + n, DOWNLOAD_MAX, 8);
        line[n] = 0;
        fb_okay(line);
    } else {
        /* Unknown variables must answer OKAY with an empty value. */
        fb_okay("");
    }
}

/* ---- download ----------------------------------------------------------- */

static void cmd_download(const char *args)
{
    char line[16];
    u32 want = (u32)hex_parse(args, 0);
    u32 got = 0;
    u32 n;

    if (want == 0 || want > DOWNLOAD_MAX) {
        fb_fail("data too large");
        return;
    }

    n = str_append(line, 0, sizeof(line), "DATA");
    n += hex_format(line + n, want, 8);
    usb_bulk_send(line, n);

    while (got < want) {
        u32 chunk = want - got;
        u32 got_now;

        if (chunk > BULK_MAXPACKET * 8)
            chunk = BULK_MAXPACKET * 8;

        got_now = usb_bulk_recv(download_buf + got, chunk);
        if (got_now == 0)
            break;
        got += got_now;
    }

    if (got != want) {
        download_len = 0;
        fb_fail("short read");
        return;
    }

    download_len = want;
    fb_okay("");
}

/* ---- reboot ------------------------------------------------------------- */

static void cmd_reboot(void)
{
    fb_okay("");
    mdelay(50);
    dwc3_disconnect();
    mdelay(10);
    system_reset();
}

/* ---- dispatch ----------------------------------------------------------- */

static void fastboot_command(const char *cmd)
{
    const char *rest;

    if ((rest = str_after(cmd, "getvar:")) != 0) {
        cmd_getvar(rest);
    } else if ((rest = str_after(cmd, "download:")) != 0) {
        cmd_download(rest);
    } else if ((rest = str_after(cmd, "oem ")) != 0) {
        cmd_oem(rest);
    } else if (str_after(cmd, "flash:") != 0) {
        fb_fail("flash not implemented in the transport payload");
    } else if (str_after(cmd, "erase:") != 0) {
        fb_fail("erase not implemented in the transport payload");
    } else if (str_eq(cmd, "reboot")) {
        cmd_reboot();
    } else if (str_after(cmd, "reboot-") != 0) {
        fb_fail("only plain `reboot` is supported");
    } else {
        fb_fail("unknown command");
    }
}

void fastboot_loop(void)
{
    for (;;) {
        u32 n;

        usb_bulk_enable_pending();

        if (usb_bulk_error && usb_bulk_recover() != 0) {
            usb_event_pump();
            continue;
        }

        n = usb_bulk_recv(cmd_buf, FB_COMMAND_MAX);
        if (n == 0)
            continue;
        if (n >= sizeof(cmd_buf))
            n = sizeof(cmd_buf) - 1;
        cmd_buf[n] = 0;

        fastboot_command((const char *)cmd_buf);
    }
}
