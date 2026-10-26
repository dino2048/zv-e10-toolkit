#ifndef ZVE10_DIAG_H
#define ZVE10_DIAG_H
#include "io.h"
#define DIAG_NOT_RUN (-100)
extern int emmc_init_rc, part_load_rc;
extern u32 boot_stack_sp;
void diag_emmc_init(void);
#endif
