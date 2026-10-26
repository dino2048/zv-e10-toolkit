#include "sdhci.h"
#include "io.h"
#include "timer.h"
#include "usb_link.h"
#include "led.h"
#include "led.h"
#include "optlog.h"

/* First bring-up stays at <=400 kHz, 1-bit legacy, without CMD6.
 * SDHCI host completion and card R1 status are checked independently. */
u16 mmc_last_error;
u32 mmc_ocr, mmc_rca;
int mmc_ready;
u32 mmc_last_cmd, mmc_last_r1;
u32 mmc_step;

/* Cached EXT_CSD[179] so selecting an area does not rewrite the boot-enable
 * bits from a stale copy. Invalidated whenever the card is re-initialised. */
static u8 part_cfg;
static u8 part_cfg_valid;

#define CMD_TIMEOUT_TICKS   (TIMER0_HZ / 2)     /* 500 ms */
#define BUSY_TIMEOUT_TICKS  (TIMER0_HZ)         /* 1 s    */

/*
 * Iteration bound also handles a frozen timer.
 *
 * Deliberately does NOT pump stage 1's USB events here: stage 1's reset
 * handling disables the bulk endpoints, and a spurious RESET/DISCONNECT event
 * during a card wait therefore kills the reply we are about to send. Nothing
 * arrives on the bus while the host is waiting for this command's reply.
 */
static int expired(u32 start, u32 limit, u32 *guard)
{
    led_tick();
    if (!--*guard) return 1;
    return timer_ticks() - start > limit;
}

static int sdhci_reset(u8 mask)
{
    u32 start = timer_ticks(), guard = 2000000;

    write8(SDHCI_SOFTWARE_RESET, mask);
    while (read8(SDHCI_SOFTWARE_RESET) & mask) {
        if (expired(start, CMD_TIMEOUT_TICKS, &guard))
            return MMC_ERR_RESET;
    }
    return MMC_OK;
}

static void sdhci_recover(void)
{
    sdhci_reset(SDHCI_RESET_CMD | SDHCI_RESET_DATA);
    write16(SDHCI_INT_STATUS, read16(SDHCI_INT_STATUS));
    write16(SDHCI_ERR_INT_STATUS, read16(SDHCI_ERR_INT_STATUS));
}

static int wait_inhibit(u32 mask)
{
    u32 start = timer_ticks(), guard = 2000000;

    while (read32(SDHCI_PRESENT_STATE) & mask) {
        if (expired(start, CMD_TIMEOUT_TICKS, &guard))
            return MMC_ERR_INHIBIT;
    }
    return MMC_OK;
}

static int wait_int(u16 mask, u32 timeout, int err)
{
    u32 start = timer_ticks(), guard = 2000000;
    u16 sts;

    for (;;) {
        sts = read16(SDHCI_INT_STATUS);

        if (sts & SDHCI_INT_ERROR) {
            mmc_last_error = read16(SDHCI_ERR_INT_STATUS);
            write16(SDHCI_ERR_INT_STATUS, mmc_last_error);
            write16(SDHCI_INT_STATUS, sts);
            sdhci_recover();
            return MMC_ERR_CMD_ERROR;
        }
        if (sts & mask) {
            write16(SDHCI_INT_STATUS, mask);
            return MMC_OK;
        }
        if (expired(start, timeout, &guard)) {
            sdhci_recover();
            return err;
        }
    }
}

static int send_cmd(u8 index, u32 arg, u16 flags, u32 data_blocks)
{
    int ret;
    mmc_last_cmd = index;

    ret = wait_inhibit(data_blocks ? (SDHCI_CMD_INHIBIT | SDHCI_DATA_INHIBIT)
                                   : SDHCI_CMD_INHIBIT);
    if (ret) {
        sdhci_recover();
        ret = wait_inhibit(SDHCI_CMD_INHIBIT);
        if (ret)
            return ret;
    }

    write16(SDHCI_INT_STATUS, read16(SDHCI_INT_STATUS));
    write16(SDHCI_ERR_INT_STATUS, read16(SDHCI_ERR_INT_STATUS));
    mmc_last_error = 0;

    write32(SDHCI_ARGUMENT, arg);
    dsb();
    write16(SDHCI_COMMAND, SDHCI_MAKE_CMD(index, flags));
    dsb();

    ret = wait_int(SDHCI_INT_CMD_COMPLETE, CMD_TIMEOUT_TICKS, MMC_ERR_CMD_TIMEOUT);

    /*
     * Card-status error check applies only to commands that answer with R1/R1b.
     *
     * CMD1 is polled until the busy bit clears, so its response is not a final
     * status. CMD3 answers with R6, not R1: R6 packs the RCA in bits 31:16 and
     * only the low 16 status bits below it. Applying the R1 mask to R6 makes
     * CMD3 fail unconditionally - with RCA = 1, RESPONSE0 = 0x00010000 and the
     * mask (0xFDFFA080) has bit 16 set.
     */
    if (!ret && index != MMC_CMD_SEND_OP_COND && index != MMC_CMD_SET_RELATIVE_ADDR &&
        ((flags & 3) == SDHCI_CMD_RESP_SHORT || (flags & 3) == SDHCI_CMD_RESP_BUSY)) {
        mmc_last_r1 = read32(SDHCI_RESPONSE);
        if (mmc_last_r1 & MMC_R1_ERROR_MASK) ret = MMC_ERR_CARD_STATUS;
    }
    return ret;
}

static int mmc_raw_cmd(u8 index, u32 arg, u16 flags, u32 *resp)
{
    int ret = send_cmd(index, arg, flags, 0);

    if (resp)
        *resp = read32(SDHCI_RESPONSE);

    if (ret == MMC_OK && (flags & 0x3) == SDHCI_CMD_RESP_BUSY)
        ret = wait_int(SDHCI_INT_XFER_COMPLETE, BUSY_TIMEOUT_TICKS,
                       MMC_ERR_XFER);
    return ret;
}

static int sdhci_set_clock(u32 div)
{
    u32 start, guard = 2000000;
    u16 clk;

    clk = read16(SDHCI_CLOCK_CONTROL);
    write16(SDHCI_CLOCK_CONTROL, clk & (u16)~SDHCI_CLK_SD_EN);

    clk = (u16)(((div & 0xff) << SDHCI_CLK_DIV_SHIFT) |
                (((div >> 8) & 0x3) << SDHCI_CLK_DIV_HI_SHIFT) |
                SDHCI_CLK_INT_EN);
    write16(SDHCI_CLOCK_CONTROL, clk);

    start = timer_ticks();
    while (!(read16(SDHCI_CLOCK_CONTROL) & SDHCI_CLK_INT_STABLE)) {
        if (expired(start, CMD_TIMEOUT_TICKS, &guard))
            return MMC_ERR_CLOCK;
    }

    write16(SDHCI_CLOCK_CONTROL, (u16)(clk | SDHCI_CLK_SD_EN));
    udelay(100);
    return MMC_OK;
}

/* CMD6 SWITCH: arg = 0b11<<26 | 1<<24 | index<<16 | value<<8 */
static int mmc_switch(u32 index, u32 value)
{
    u32 arg = (3u << 26) | (1u << 24) | (index << 16) | (value << 8);
    return mmc_raw_cmd(6, arg,
                       SDHCI_CMD_RESP_BUSY | SDHCI_CMD_CRC_CHECK |
                       SDHCI_CMD_INDEX_CHECK, 0);
}

int mmc_init(void)
{
    u16 saved_clk = read16(SDHCI_CLOCK_CONTROL);
    u8  saved_host = read8(SDHCI_HOST_CONTROL);
    u16 r1 = SDHCI_CMD_RESP_SHORT | SDHCI_CMD_CRC_CHECK | SDHCI_CMD_INDEX_CHECK;
    u32 base_khz, div, start, resp, guard;
    int ret;

    mmc_ocr = mmc_rca = mmc_last_cmd = mmc_last_r1 = mmc_last_error = 0;
    mmc_ready = 0;
    part_cfg_valid = 0;

    base_khz = ((read32(SDHCI_CAPABILITIES) >> 8) & 0xff) * 1000;
    if (base_khz == 0)
        base_khz = 192000;

    /* Identification at <= 400 kHz. */
    div = (base_khz + 799) / 800;
    if (div == 0)
        div = 1;

    write16(SDHCI_INT_ENABLE, SDHCI_INT_CMD_COMPLETE |
                              SDHCI_INT_XFER_COMPLETE |
                              SDHCI_INT_BUF_WRITE_RDY |
                              SDHCI_INT_BUF_READ_RDY);
    write16(SDHCI_ERR_INT_ENABLE, 0xffff);

    mmc_step = 2; led_set(2);
    /* Best effort: the controller may still hold a transfer from an earlier
     * payload run and never clear the reset bit. CMD0 resets the card anyway,
     * so a failed host reset is not fatal here. */
    (void)sdhci_reset(SDHCI_RESET_CMD | SDHCI_RESET_DATA);
    write8(SDHCI_HOST_CONTROL, (u8)(saved_host & ~0x26));
    mmc_step = 3; led_set(3);
    ret = sdhci_set_clock(div);
    if (ret) goto out;

    mmc_step = 4; led_set(4);
    ret = send_cmd(MMC_CMD_GO_IDLE_STATE, 0, SDHCI_CMD_RESP_NONE, 0);
    if (ret)
        goto out;
    mdelay(2);

    start = timer_ticks();
    guard = 200; /* CMD1 attempts also bounded when the timer freezes. */
    for (;;) {
        ret = mmc_raw_cmd(MMC_CMD_SEND_OP_COND, 0x40FF8080,
                          SDHCI_CMD_RESP_SHORT, &resp);
        if (ret)
            goto out;
        mmc_ocr = resp;
        if (resp & 0x80000000u)
            break;
        if (expired(start, TIMER0_HZ, &guard)) {
            ret = MMC_ERR_CMD_TIMEOUT;
            goto out;
        }
        mdelay(5);
    }

    mmc_step = 5; led_set(5);
    if (!(mmc_ocr & BIT(30))) { ret = MMC_ERR_ADDRESSING; goto out; }

    mmc_step = 6; led_set(6);
    ret = mmc_raw_cmd(MMC_CMD_ALL_SEND_CID, 0,
                      SDHCI_CMD_RESP_LONG | SDHCI_CMD_CRC_CHECK, 0);
    if (ret)
        goto out;

    mmc_rca = 1;
    mmc_step = 7; led_set(7);
    ret = mmc_raw_cmd(MMC_CMD_SET_RELATIVE_ADDR, mmc_rca << 16, r1, 0);
    if (ret)
        goto out;

    mmc_step = 8; led_set(8);
    ret = mmc_raw_cmd(MMC_CMD_SELECT_CARD, mmc_rca << 16,
                      SDHCI_CMD_RESP_BUSY | SDHCI_CMD_CRC_CHECK |
                      SDHCI_CMD_INDEX_CHECK, 0);
    if (ret)
        goto out;

    /*
     * Conservative: stay at 400 kHz / 1-bit. The CMD6 bus-width and 48 MHz
     * switch used by the monolithic build has not been verified on this
     * hardware and wedges the SDHCI before the USB command loop is reachable.
     */

    mmc_step = 9; led_set(9);
    ret = mmc_raw_cmd(MMC_CMD_SEND_STATUS, mmc_rca << 16, r1, &resp);
    if (ret) goto out;
    if (!(resp & MMC_R1_READY_FOR_DATA) || MMC_R1_STATE(resp) != MMC_STATE_TRAN) {
        ret = MMC_ERR_CARD_STATUS; goto out;
    }

    /*
     * Speed-up, best effort. Measured on 2026-10-26: 1-bit/400 kHz is
     * 12 KB/s, 8-bit at 50 MHz high-speed timing is 9.7 MB/s.
     * A refusal at either step leaves the card on the slower setting.
     */
    mmc_step = 10; led_set(10);
    opt_str("SP");
    ret = mmc_switch(183, 2);                 /* BUS_WIDTH = 8-bit */
    opt_dec("BW", (u32)ret);
    if (ret == MMC_OK) {
        u8 hc = read8(SDHCI_HOST_CONTROL);
        write8(SDHCI_HOST_CONTROL, (u8)((hc & (u8)~0x02) | 0x20));
        udelay(100);
    }
    ret = mmc_switch(185, 1);                 /* HS_TIMING = high speed */
    opt_dec("HS", (u32)ret);
    if (ret == MMC_OK) {
        write8(SDHCI_HOST_CONTROL, (u8)(read8(SDHCI_HOST_CONTROL) | 0x04));
        ret = sdhci_set_clock(2);             /* 192 MHz / (2*2) = 48 MHz */
        opt_dec("CK", (u32)ret);
    }
    /* The card must still answer at the new width/clock. */
    ret = mmc_raw_cmd(MMC_CMD_SEND_STATUS, mmc_rca << 16, r1, &resp);
    opt_dec("VFY", (u32)ret);
    if (ret) goto out;

    mmc_ready = 1;
    return MMC_OK;

out:
    write8(SDHCI_HOST_CONTROL, saved_host);
    write16(SDHCI_CLOCK_CONTROL, saved_clk);
    udelay(100);
    return ret;
}

int mmc_read_blocks(u32 start_block, void *buf, u32 nblocks)
{
    u32 *out = (u32 *)buf;
    u16 mode, flags;
    u32 b, w;
    int ret, multi = (nblocks > 1);

    if (!mmc_ready)
        return MMC_ERR_INHIBIT;
    if (nblocks == 0)
        return MMC_OK;

    ret = wait_inhibit(SDHCI_CMD_INHIBIT | SDHCI_DATA_INHIBIT);
    if (ret)
        return ret;

    write16(SDHCI_BLOCK_SIZE, 512);
    write16(SDHCI_BLOCK_COUNT, (u16)nblocks);

    mode = SDHCI_TRNS_READ | SDHCI_TRNS_BLK_CNT_EN;
    if (multi)
        mode |= SDHCI_TRNS_MULTI | SDHCI_TRNS_AUTO_CMD12;
    write16(SDHCI_TRANSFER_MODE, mode);
    dsb();

    flags = SDHCI_CMD_RESP_SHORT | SDHCI_CMD_CRC_CHECK |
            SDHCI_CMD_INDEX_CHECK | SDHCI_CMD_DATA_PRESENT;

    ret = send_cmd(multi ? MMC_CMD_READ_MULTIPLE_BLOCK
                         : MMC_CMD_READ_SINGLE_BLOCK,
                   start_block, flags, nblocks);
    if (ret)
        return ret;

    for (b = 0; b < nblocks; b++) {
        ret = wait_int(SDHCI_INT_BUF_READ_RDY, CMD_TIMEOUT_TICKS,
                       MMC_ERR_DATA_TIMEOUT);
        if (ret)
            return ret;
        for (w = 0; w < 512 / 4; w++)
            *out++ = read32(SDHCI_BUFFER);
    }

    return wait_int(SDHCI_INT_XFER_COMPLETE, CMD_TIMEOUT_TICKS, MMC_ERR_XFER);
}

int mmc_write_blocks(u32 start_block, const void *buf, u32 nblocks)
{
    const u32 *in = (const u32 *)buf;
    u16 mode, flags;
    u32 b, w;
    int ret, multi = (nblocks > 1);

    if (!mmc_ready)
        return MMC_ERR_INHIBIT;
    if (nblocks == 0)
        return MMC_OK;

    ret = wait_inhibit(SDHCI_CMD_INHIBIT | SDHCI_DATA_INHIBIT);
    if (ret)
        return ret;

    write16(SDHCI_BLOCK_SIZE, 512);
    write16(SDHCI_BLOCK_COUNT, (u16)nblocks);

    mode = SDHCI_TRNS_BLK_CNT_EN;
    if (multi)
        mode |= SDHCI_TRNS_MULTI | SDHCI_TRNS_AUTO_CMD12;
    write16(SDHCI_TRANSFER_MODE, mode);
    dsb();

    flags = SDHCI_CMD_RESP_SHORT | SDHCI_CMD_CRC_CHECK |
            SDHCI_CMD_INDEX_CHECK | SDHCI_CMD_DATA_PRESENT;

    ret = send_cmd(multi ? MMC_CMD_WRITE_MULTIPLE_BLOCK
                         : MMC_CMD_WRITE_BLOCK,
                   start_block, flags, nblocks);
    if (ret)
        return ret;

    for (b = 0; b < nblocks; b++) {
        ret = wait_int(SDHCI_INT_BUF_WRITE_RDY, CMD_TIMEOUT_TICKS,
                       MMC_ERR_WRITE_TIMEOUT);
        if (ret)
            return ret;
        for (w = 0; w < 512 / 4; w++)
            write32(SDHCI_BUFFER, *in++);
    }

    return wait_int(SDHCI_INT_XFER_COMPLETE, BUSY_TIMEOUT_TICKS, MMC_ERR_XFER);
}

/* CMD8 SEND_EXT_CSD: one 512-byte block, readable from any selected area. */
int mmc_read_ext_csd(u8 *buf)
{
    u32 *out = (u32 *)buf;
    u16 flags;
    int ret;

    if (!mmc_ready)
        return MMC_ERR_INHIBIT;

    ret = wait_inhibit(SDHCI_CMD_INHIBIT | SDHCI_DATA_INHIBIT);
    if (ret)
        return ret;

    write16(SDHCI_BLOCK_SIZE, 512);
    write16(SDHCI_BLOCK_COUNT, 1);
    write16(SDHCI_TRANSFER_MODE, SDHCI_TRNS_READ | SDHCI_TRNS_BLK_CNT_EN);
    dsb();

    flags = SDHCI_CMD_RESP_SHORT | SDHCI_CMD_CRC_CHECK |
            SDHCI_CMD_INDEX_CHECK | SDHCI_CMD_DATA_PRESENT;

    ret = send_cmd(MMC_CMD_SEND_EXT_CSD, 0, flags, 1);
    if (ret)
        return ret;

    ret = wait_int(SDHCI_INT_BUF_READ_RDY, CMD_TIMEOUT_TICKS,
                   MMC_ERR_DATA_TIMEOUT);
    if (ret)
        return ret;
    for (u32 w = 0; w < 512 / 4; w++)
        *out++ = read32(SDHCI_BUFFER);

    return wait_int(SDHCI_INT_XFER_COMPLETE, CMD_TIMEOUT_TICKS, MMC_ERR_XFER);
}

u32 mmc_boot_partition_sectors(void)
{
    u8 csd[512] __attribute__((aligned(4)));

    if (mmc_read_ext_csd(csd) != MMC_OK)
        return 0;
    /* BOOT_SIZE_MULT counts 128 KiB units: 128 KiB / 512 B = 256 sectors. */
    return (u32)csd[EXT_CSD_BOOT_SIZE_MULT] * 256u;
}

int mmc_select_partition(u32 access)
{
    u8 csd[512] __attribute__((aligned(4)));
    u32 value;
    int ret;

    if (!mmc_ready)
        return MMC_ERR_INHIBIT;

    access &= 7u;
    if (!part_cfg_valid) {
        ret = mmc_read_ext_csd(csd);
        if (ret)
            return ret;
        part_cfg = csd[EXT_CSD_PARTITION_CONFIG];
        part_cfg_valid = 1;
    }

    value = ((u32)part_cfg & 0xF8u) | access;
    if (value == part_cfg)
        return MMC_OK;

    /* CMD6 write-byte. mmc_raw_cmd() waits for the R1b busy window. */
    ret = mmc_switch(EXT_CSD_PARTITION_CONFIG, value);
    if (ret)
        return ret;
    part_cfg = (u8)value;
    return MMC_OK;
}
