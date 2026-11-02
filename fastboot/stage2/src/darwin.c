#include "io.h"

/*
 * One-shot Darwin (power MCU) 0x16 keepalive read, run once at stage 2 entry.
 *
 * ZV-E10 hardware parameters (from Backup: 0xF900D4/B1/6D and boot0):
 *   SIO channel 3, base 0xF2405600, data 0xF2405700
 *   chip select GPIO port 5 bit 14, SIO lines port 5 bits 15/13/12
 *   CTRL2=0x70000000, RATE_LO=0x03000000, CTRL setup 0xD8000000 + GO
 *
 * Frame format follows the A7C reference document (its porting rules supplied
 * the SIO constants above, re-verified on ZV-E10):
 *   0x80-byte frame, command 0x16, address little-endian, length,
 *   CRC-16/CCITT-FALSE at 0x7E..0x7F, 8 retries, stop/ack before load,
 *   CS low 150 us, fixed 2000 us after start (do not poll), CS high,
 *   1200 us, read back; success needs CRC and header echo.
 *
 * This is read-only; it never writes Darwin memory or eMMC.
 */

#define SIO_REG   0xF2405600u
#define SIO_DATA  0xF2405700u
#define SIO_CTRL  (SIO_REG + 0x00u)
#define SIO_CTRL2 (SIO_REG + 0x04u)
#define SIO_R08   (SIO_REG + 0x08u)
#define SIO_LEN   (SIO_REG + 0x0Cu)
#define SIO_CFG   (SIO_REG + 0x10u)
#define SIO_RL    (SIO_REG + 0x14u)
#define SIO_RH    (SIO_REG + 0x18u)

#define GPIO5     0xF2910500u
#define AUX5      0xF2912500u
#define CS_BIT    (1u << 14)
#define LINE15    (1u << 15)
#define LINE13    (1u << 13)
#define LINE12    (1u << 12)

#define CTRL_STOP  0xC0000000u
#define CTRL_SETUP 0xD8000000u
#define CTRL_GO    0x20000000u
#define CTRL_BUSY  0x20000000u

#define FRAME_LEN  0x80u
#define READ_ADDR  0x200026FCu
#define READ_SIZE  4u
#define RETRIES    8

static void gpio_init(void)
{
    write32(GPIO5 + 0x44u, CS_BIT);
    write32(GPIO5 + 0x04u, CS_BIT);
    write32(AUX5 + 0x04u, CS_BIT);

    write32(GPIO5 + 0x04u, LINE15);
    write32(AUX5 + 0x04u, LINE15);
    write32(GPIO5 + 0x04u, LINE13);
    write32(AUX5 + 0x04u, LINE13);
    write32(GPIO5 + 0x08u, LINE12);
    write32(GPIO5 + 0x24u, LINE12);
    write32(AUX5 + 0x14u, LINE12);
    write32(GPIO5 + 0x38u, LINE15);
    write32(GPIO5 + 0x38u, LINE13);
    write32(GPIO5 + 0x38u, LINE12);
}

static u16 crc16_ccitt_false(const u8 *p, u32 n)
{
    u16 crc = 0xFFFF;

    while (n--) {
        crc ^= (u16)(*p++) << 8;
        for (int i = 0; i < 8; i++)
            crc = (crc & 0x8000) ? (u16)((crc << 1) ^ 0x1021) : (u16)(crc << 1);
    }
    return crc;
}

static int darwin_read_once(u32 addr, u8 len)
{
    u8 tx[FRAME_LEN], rx[FRAME_LEN];
    u32 i;
    u16 crc;

    write32(SIO_CTRL, CTRL_STOP);
    write32(SIO_CFG, 0);
    if (read32(SIO_CTRL) & CTRL_BUSY)
        return -1;

    write32(GPIO5 + 0x48u, CS_BIT);
    udelay(150);

    for (i = 0; i < FRAME_LEN; i++)
        tx[i] = 0;
    tx[0] = 0x16;
    tx[1] = (u8)(addr >> 0);
    tx[2] = (u8)(addr >> 8);
    tx[3] = (u8)(addr >> 16);
    tx[4] = (u8)(addr >> 24);
    tx[5] = len;
    crc = crc16_ccitt_false(tx, 0x7E);
    tx[0x7E] = (u8)crc;
    tx[0x7F] = (u8)(crc >> 8);

    for (i = 0; i < FRAME_LEN; i++)
        write8(SIO_DATA + i, tx[i]);
    write32(SIO_R08, 0);
    write32(SIO_LEN, 0x7F000000u);
    write32(SIO_CFG, 0x01000000u);
    write32(SIO_CTRL2, 0x70000000u);
    write32(SIO_RL, 0x03000000u);
    write32(SIO_RH, 0);
    write32(SIO_CTRL, CTRL_SETUP);
    write32(SIO_CTRL, read32(SIO_CTRL) | CTRL_GO);

    /* Protocol requires a fixed delay; do not poll CTRL after start. */
    udelay(2000);
    write32(GPIO5 + 0x44u, CS_BIT);
    udelay(1200);

    for (i = 0; i < FRAME_LEN; i++)
        rx[i] = read8(SIO_DATA + i);

    write32(SIO_CTRL, CTRL_STOP);
    write32(SIO_CFG, 0);

    crc = (u16)rx[0x7E] | ((u16)rx[0x7F] << 8);
    if (crc16_ccitt_false(rx, 0x7E) != crc)
        return -2;
    for (i = 0; i < 6; i++)
        if (rx[i] != tx[i])
            return -3;
    return 0;
}

int darwin_kick(void)
{
    gpio_init();
    for (int i = 0; i < RETRIES; i++) {
        if (darwin_read_once(READ_ADDR, READ_SIZE) == 0)
            return 0;
    }
    return -1;
}
