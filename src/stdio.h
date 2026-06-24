// Genesis/SGDK 用 <stdio.h> 最小シム。
// newlib stdio.h を避け、Doom が使う printf のみ宣言する。
// sprintf / vsprintf は SGDK string.h（compiler.h 経由）が提供する。
#ifndef _STDIO_SHIM_H_
#define _STDIO_SHIM_H_

#include <stddef.h>

int printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif
