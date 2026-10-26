/*
 * Keep-alive for the power MCU.
 *
 * The power side counts down and cuts the system at ~240 s unless something
 * talks to it. Nothing in BootROM context does, which is why every payload
 * died at about four minutes.
 *
 * The message and the transport were recovered from the camera's own boot0
 * loader (base 0xFE060000):
 *
 *   SIO channel 0  registers 0xF2405000, data 0xF2405100, stride 0x200
 *   setup          CTRL=0xD8000000, CTRL2=0x68000000, CFG=0x01000000,
 *                  RATE_LO=0x04000000, RATE_HI=0
 *   transfer       LEN(+0x0C) = (len-1)<<24, copy to data, REG08(+0x08)=0,
 *                  CTRL |= 0x20000000 (GO), poll CTRL bit29 (BUSY)
 *   message        28 bytes, byte[0] = 0xB0, rest zero
 *
 * Verified on hardware: a payload sending this every 5 s ran past 341 s
 * without the reset that used to arrive at ~240 s.
 *
 * Called from usb_event_pump(), so every loop that waits for the host or for
 * configuration feeds the power MCU -- including the `while (!configured)`
 * paths that never reach a bulk transfer.
 */
#include "io.h"
#include "timer.h"

#define SIO_REG   0xF2405000u
#define SIO_DATA  0xF2405100u
#define SIO_CTRL  (SIO_REG + 0x00)
#define SIO_CTRL2 (SIO_REG + 0x04)
#define SIO_R08   (SIO_REG + 0x08)
#define SIO_LEN   (SIO_REG + 0x0C)
#define SIO_CFG   (SIO_REG + 0x10)
#define SIO_RL    (SIO_REG + 0x14)
#define SIO_RH    (SIO_REG + 0x18)

#define PKT_LEN   28
#define PERIOD_US 5000000u

static u32 ka_init_done;
static u32 ka_armed;
static u32 ka_last;
static u32 ka_spins;

/* Diagnostic counters, read by stage 2 through the pinned addresses in
 * usb_link.h. BSS only: they cost nothing in the injected image. */
volatile u32 ka_sent;
volatile u32 ka_busy;
volatile u32 ka_timer_ok;
volatile u32 ka_rx0;
volatile u32 ka_rx13;
volatile u32 ka_rx_ok;

void keepalive_tick(void)
{
    volatile u8 *p = (volatile u8 *)SIO_DATA;
    u32 now;

    if (!ka_init_done) {
        ka_init_done = 1;
        ka_timer_ok = timer_running ? 1u : 0u;
        write32(SIO_CFG, 0x01000000u);
        write32(SIO_RL, 0x04000000u);
        write32(SIO_RH, 0);
        write32(SIO_CTRL2, 0x68000000u);
        write32(SIO_CTRL, 0xD8000000u);
    }

    if (timer_running) {
        now = timer_ticks();
        /* A separate flag, not "ka_last != 0": the counter can legitimately
         * read zero here, and testing it would send on every pump call and
         * starve USB completely. */
        if (ka_armed && (now - ka_last) < PERIOD_US)
            return;
        ka_last = now;
    } else {
        /* No usable clock. A call-count gate keeps the send out of the
         * per-event path without depending on the frozen timer. */
        if (ka_armed && ++ka_spins < 100000u)
            return;
        ka_spins = 0;
    }
    ka_armed = 1;

    write32(SIO_LEN, (PKT_LEN - 1) << 24);
    p[0] = 0xB0;
    for (u32 i = 1; i < PKT_LEN; i++)
        p[i] = 0;
    write32(SIO_R08, 0);
    write32(SIO_CTRL, read32(SIO_CTRL) | 0x20000000u);
    ka_sent++;

    /* Time-based first, with an iteration guard so a frozen counter cannot
     * hang the event pump. 20 ms is far past a 28-byte transfer. */
    {
        u32 start = timer_ticks();
        u32 guard = 20000;

        while (read32(SIO_CTRL) & 0x20000000u) {
            if (!--guard || (timer_running && timer_ticks() - start > 20000u)) {
                ka_busy++;
                break;
            }
        }
    }

    /*
     * The boot0 transaction is a write *and a read back*: after BUSY clears it
     * copies len bytes out of the same data buffer and the heartbeat caller
     * checks byte 13 == 1. Sending without this read may be why the power MCU
     * never accepted our message. Stage 2 only for now: the single-stage image
     * is 12 bytes over the 8168 limit with it.
     */
    {
        volatile u8 *rx = (volatile u8 *)SIO_DATA;
        u8 b0 = 0, b13 = 0;

        for (u32 i = 0; i < PKT_LEN; i++) {
            u8 v = rx[i];
            if (i == 0)
                b0 = v;
            if (i == 13)
                b13 = v;
        }
        ka_rx0 = b0;
        ka_rx13 = b13;
        if (b13 == 1u)
            ka_rx_ok++;
    }
}
