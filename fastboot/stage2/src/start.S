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
    bl      stage2_main
    pop     {r4-r11, pc}
    .ltorg
    .size _start, .-_start

    .section .note.GNU-stack, "", %progbits
