/*
 * Entry for the CXD90045 (ARMv7-A / Cortex-A9) after the boot ROM's serial
 * boot hands control to 0xFE020000.
 *
 * Ported from the ILCE-7M4-RE AArch64 payload. Two deliberate changes:
 *   - caches are turned off. The DWC3 reads its TRBs and event buffer through
 *     AXI; with caches on, writes can sit in L1/L2 and the controller sees
 *     stale memory. The ROM's MMU state is left untouched.
 *   - secondaries are parked only after reading MPIDR, which is always
 *     available on A9.
 */

    .syntax unified
    .arch armv7-a
    .thumb

    .section .text.start, "ax", %progbits
    .balign 4
    .global _start
    .type _start, %function
    .thumb_func
_start:
    /* The ROM may have left IRQ/FIQ enabled with its own vectors. */
    cpsid   aif

    /*
     * Do not park the other cores by MPIDR: which core the ROM hands control
     * to is not known here, and parking "everything except core 0" would park
     * the core we are actually running on.
     */

1:  ldr     sp, =__stack_top

    /* SCTLR: clear I (bit 12) and C (bit 2). */
    mrc     p15, 0, r0, c1, c0, 0
    bic     r0, r0, #(1 << 12)
    bic     r0, r0, #(1 << 2)
    mcr     p15, 0, r0, c1, c0, 0
    dsb
    isb

    /* Zero .bss. */
    ldr     r0, =__bss_start
    ldr     r1, =__bss_end
    movs    r2, #0
2:  cmp     r0, r1
    bhs     3f
    str     r2, [r0], #4
    b       2b

3:  bl      main

    bl      led_panic
4:  b       4b

    .ltorg
    .size _start, .-_start

    .section .note.GNU-stack, "", %progbits
