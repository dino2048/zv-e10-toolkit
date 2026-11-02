#ifndef ZVE10_RESET_H
#define ZVE10_RESET_H

#include "io.h"

/* Assert XRESET_REQ through the MISC block. Nothing after the call runs. */
__attribute__((noreturn)) void system_reset(void);

#endif /* ZVE10_RESET_H */
