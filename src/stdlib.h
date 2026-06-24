// Genesis/SGDK 用 <stdlib.h> 最小シム。
// newlib の stdlib.h は SGDK の maths.h(abs マクロ) / tools.h(qsort 宣言) と衝突する。
// SGDK には stdlib.h が無いため -I$(SRC) によりこのファイルが先に見つかる。
// Doom が使うのは exit / abs のみ（malloc/free/calloc は z_zone へ。compiler.h で undef 済み）。
#ifndef _STDLIB_SHIM_H_
#define _STDLIB_SHIM_H_

#include <stddef.h>

void exit(int code);

// abs: SGDK ビルドで genesis.h を読むファイルでは maths.h がマクロ定義する。
// それ以外（移植可能ファイル）では関数として宣言（実体は i_stubs.c）。
#ifndef abs
int abs(int x);
#endif

#endif
