.syntax unified
.arch armv7-a
.arm
.text
.global _start
_start:
    ldr r0, [sp]
    cmp r0, #2
    blt bad_arg
    ldr r0, [sp, #8]
    ldrb r1, [r0]
    ldrb r2, [r0, #1]
    cmp r2, #0
    bne bad_arg
    cmp r1, #0x30
    blt bad_arg
    cmp r1, #0x35
    bgt bad_arg
    sub r6, r1, #0x30

    adr r0, path
    mov r1, #0x1000
    mov r2, #0
    mov r7, #5
    svc #0
    cmp r0, #0
    blt failure
    mov r4, r0

    mov r0, #0
    mov r1, #4096
    mov r2, #1
    mov r3, #1
    ldr r5, page_base
    add r5, r5, r6
    mov r7, #192
    svc #0
    cmn r0, #4096
    bhi failure
    cmp r0, #0
    beq failure
    mov r8, r0

    mov r0, #2
    adr r1, mapped
    mov r2, #7
    mov r7, #4
    svc #0

    sub sp, sp, #520
    adr r11, digits
    mov r9, #16
    mov r10, r8

chunk_loop:
    mov r12, sp
    mov r5, #256
hex_loop:
    ldrb r0, [r10], #1
    lsr r2, r0, #4
    ldrb r2, [r11, r2]
    strb r2, [r12], #1
    and r0, r0, #0xf
    ldrb r0, [r11, r0]
    strb r0, [r12], #1
    subs r5, r5, #1
    bne hex_loop
    mov r0, #10
    strb r0, [r12]

    mov r1, sp
    movw r2, #513
    mov r7, #4
write_loop:
    mov r0, #1
    svc #0
    cmp r0, #0
    bgt write_advance
    cmn r0, #4
    beq write_loop
    b write_fail
write_advance:
    cmp r0, r2
    bhi write_fail
    add r1, r1, r0
    subs r2, r2, r0
    bne write_loop
    subs r9, r9, #1
    bne chunk_loop
    mov r0, #0
    b exit

bad_arg:
    mov r0, #2
    b exit
write_fail:
    mov r0, #125
    b exit
failure:
    rsb r0, r0, #0
    and r0, r0, #0xff
    cmp r0, #0
    moveq r0, #125
exit:
    mov r7, #1
    svc #0

.balign 4
page_base: .word 0xffff0
path: .asciz "/dev/mem"
mapped: .ascii "MAPPED\n"
digits: .ascii "0123456789abcdef"
