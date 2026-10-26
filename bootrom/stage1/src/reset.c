#include "reset.h"
#include "io.h"

/*
 * cxd900x0_reset() in arch/arm/mach-cxd900x0/core.c:245 asserts XRESET_REQ by
 * writing MISC_RSTREQ_EN | MISC_RSTREQ_ASSERT to VA_MISC_RSTREQ_SET.
 *
 *   MISC base        = CXD900X0_MACRO_BASE + 0x5000 = 0xF2915000
 *                      (include/mach/platform.h:87)
 *   MISC_RSTREQ_SET  = 0x0044   (regs-misc.h:63)
 *   MISC_RSTREQ_EN   = 0x010    (regs-misc.h:61)
 *   MISC_RSTREQ_ASSERT = 0x001  (regs-misc.h:62)
 */
#define MISC_RSTREQ_SET  0xF2915044u
#define MISC_RSTREQ_EN   0x010u
#define MISC_RSTREQ_ASSERT 0x001u

void system_reset(void)
{
    __asm__ volatile("cpsid aif" ::: "memory");

    write32(MISC_RSTREQ_SET, MISC_RSTREQ_EN | MISC_RSTREQ_ASSERT);
    dsb();

    for (;;)
        __asm__ volatile("wfi");
}
