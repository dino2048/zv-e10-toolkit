#include "io.h"
#include "log.h"

/* The header maps mira_logx to a no-op for every build; this file is where
 * it is actually implemented (for a host that wires up the UART). */
#undef mira_logx

/* PL011 UART0. */
#define UART0_BASE  0xF2000000u
#define UART_DR     (UART0_BASE + 0x00)
#define UART_FR     (UART0_BASE + 0x18)
#define UART_CR     (UART0_BASE + 0x30)

#define FR_TXFF     BIT(5)
#define CR_UARTEN   BIT(0)
#define CR_TXE      BIT(8)

#define LOG_MAX 64

static const char hexdigits[] = "0123456789abcdef";

void log_init(void)
{
    u32 cr = read32(UART_CR);
    write32(UART_CR, cr | CR_UARTEN | CR_TXE);
}

static void uart_putc(char c)
{
    u32 guard = 100000;

    while ((read32(UART_FR) & FR_TXFF) && --guard)
        ;
    if (!guard)
        return;                 /* UART not clocked; drop the line */
    write32(UART_DR, (u32)(u8)c);
}

static void uart_puts(const char *s)
{
    while (*s)
        uart_putc(*s++);
}

static u32 append(char *dst, u32 n, u32 size, const char *src)
{
    while (*src && n + 1 < size)
        dst[n++] = *src++;
    return n;
}

void mira_log(const char *msg)
{
    uart_puts("[zve10] ");
    uart_puts(msg);
    uart_putc('\r');
    uart_putc('\n');
}

void mira_logx(const char *msg, u64 value)
{
    char line[LOG_MAX];
    u32 n;
    int i;

    n = append(line, 0, sizeof(line), msg);
    n = append(line, n, sizeof(line), " 0x");
    for (i = 7; i >= 0 && n + 1 < sizeof(line); i--)
        line[n++] = hexdigits[(value >> (i * 4)) & 0xF];
    line[n] = 0;

    uart_puts("[zve10] ");
    uart_puts(line);
    uart_putc('\r');
    uart_putc('\n');
}
