#ifndef ZVE10_IO_H
#define ZVE10_IO_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int32_t s32;
#define BIT(n) (1u << (n))
u32 read32(u32);
u16 read16(u32);
u8 read8(u32);
void write32(u32,u32);
void write16(u32,u16);
void write8(u32,u8);
static inline void dsb(void) {}
void udelay(u32);
void mdelay(u32);
#endif
