/*
 * Entry for the CXD90045 (ARMv7-A / Cortex-A9) after the boot ROM's serial
 * boot hands control to 0xFE020000.
 *
 * Caches are turned off so the DWC3 sees updates to its TRBs and event buffer
 * through AXI. The ROM's MMU state is left untouched.
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
