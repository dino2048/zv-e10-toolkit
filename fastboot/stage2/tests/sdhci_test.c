#include <assert.h>
#include <stdio.h>
#include "host_io.h"
#include "../src/sdhci.c"
static u32 tick, response=0x900, command, pumped;
static int frozen, stuck_reset, bad_clock, bad_r1, byte_addressed;
u32 read32(u32 addr) {
    if(addr==TIMER0_COUNT) return frozen ? tick : tick++;
    if(addr==SDHCI_CAPABILITIES) return 0x64eec000;
    if(addr==SDHCI_RESPONSE) {
        if(command==1) return byte_addressed ? 0x80ff8080 : 0xc0ff8080;
        return bad_r1 ? BIT(22) : response;
    }
    return 0;
}
u16 read16(u32 addr) {
    if(addr==SDHCI_CLOCK_CONTROL) return bad_clock ? 0 : SDHCI_CLK_INT_STABLE;
    if(addr==SDHCI_INT_STATUS) return SDHCI_INT_CMD_COMPLETE|SDHCI_INT_XFER_COMPLETE|SDHCI_INT_BUF_READ_RDY;
    return 0;
}
u8 read8(u32 addr) { return addr==SDHCI_SOFTWARE_RESET && stuck_reset ? 6 : 0; }
void write32(u32 a,u32 v) {}
void write16(u32 a,u16 v) { if(a==SDHCI_COMMAND) command=v>>8; }
void write8(u32 a,u8 v) {}
void usb_event_pump(void) { pumped++; }
void udelay(u32 n) {}
void mdelay(u32 n) {}
int main(void) {
    assert(mmc_init()==MMC_OK && mmc_ready && mmc_last_cmd==13 && mmc_last_r1==0x900);
    byte_addressed=1; assert(mmc_init()==MMC_ERR_ADDRESSING && !mmc_ready); byte_addressed=0;
    bad_r1=1; assert(mmc_init()==MMC_ERR_CARD_STATUS && !mmc_ready); bad_r1=0;
    response=0x700; assert(mmc_init()==MMC_ERR_CARD_STATUS && !mmc_ready); response=0x900;
    frozen=1; stuck_reset=1;
    /* mmc_init now treats host reset as best effort. Test the bounded reset
     * primitive itself, including when the timer no longer advances. */
    assert(sdhci_reset(SDHCI_RESET_CMD|SDHCI_RESET_DATA)==MMC_ERR_RESET); stuck_reset=0;
    bad_clock=1; assert(mmc_init()==MMC_ERR_CLOCK && !mmc_ready);
    puts("PASS: card status/addressing, frozen-timer reset/clock timeout");
}
