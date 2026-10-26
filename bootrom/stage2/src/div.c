/*
 * ARM EABI division helpers for the flash build.
 *
 * Linking with -nostdlib means no libgcc, and the sparse/download path divides
 * by values that are not compile-time constants. A shift-and-subtract loop is
 * a few dozen bytes, against pulling in libgcc's whole integer core.
 * --gc-sections drops this from builds that never divide.
 */
#include "io.h"

static u32 udivmod(u32 n, u32 d, u32 *rem)
{
    u32 q = 0, r = 0;

    if (!d) {
        *rem = 0;
        return 0;
    }
    for (int i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1u);
        if (r >= d) {
            r -= d;
            q |= 1u << i;
        }
    }
    *rem = r;
    return q;
}

u32 __aeabi_uidiv(u32 n, u32 d);
u32 __aeabi_uidiv(u32 n, u32 d)
{
    u32 rem;
    return udivmod(n, d, &rem);
}

u64 __aeabi_uidivmod(u32 n, u32 d);
u64 __aeabi_uidivmod(u32 n, u32 d)
{
    u32 rem;
    u32 q = udivmod(n, d, &rem);
    return ((u64)rem << 32) | q;
}
