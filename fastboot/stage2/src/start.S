/*
 * Stage 2 entry, called from the main payload's `oem call:<addr>`.
 *
 * The caller uses the ARM AAPCS: r0-r3, r12 and the flags may be clobbered,
 * r4-r11 must survive, and the return address is in lr. `pop {..., pc}` using
 * the saved lr returns to the payload's fastboot loop.
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
    push    {r4-r11, lr}
    /* Nine saved registers are 36 B; pad to keep SP mod 8 == 0 at BL. */
    sub     sp, #4

    /* .bss lives in eSRAM that previous stage-2 runs have used; clear it. */
    ldr     r0, =__bss_start
    ldr     r1, =__bss_end
    movs    r2, #0
1:  cmp     r0, r1
    bhs     2f
    str     r2, [r0], #4
    b       1b
2:
    bl      stage2_main
    add     sp, #4
    pop     {r4-r11, pc}
    .ltorg
    .size _start, .-_start

    .section .note.GNU-stack, "", %progbits
