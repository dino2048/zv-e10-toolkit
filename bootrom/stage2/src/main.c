#include "io.h"
#include "sdhci.h"
#include "partitions.h"
#include "diag.h"
#include "optlog.h"

void fb_loop(void) __attribute__((noreturn));
int emmc_init_rc = DIAG_NOT_RUN;
int part_load_rc = DIAG_NOT_RUN;
u32 boot_stack_sp;

void diag_emmc_init(void)
{
    /* Explicit command: USB/version checks can run even when eMMC is broken. */
    opt_str("PR");
    part_reset();
    part_load_rc = DIAG_NOT_RUN;
    opt_str("MI");
    emmc_init_rc = mmc_init();
    opt_dec("RC",(u32)emmc_init_rc);
    if (emmc_init_rc == MMC_OK) {
        opt_str("PL");
        part_load_rc = part_load();
        opt_dec("PT",(u32)part_load_rc);
    }
}

void stage2_main(void)
{
    __asm__ volatile("mov %0, sp" : "=r"(boot_stack_sp));
    opt_init();
    opt_str("S2");
    fb_loop(); /* One-way handoff; retain stage 1 USB state and inherited stack. */
}
