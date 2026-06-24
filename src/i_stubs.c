/*-----------------------------------------------------------------------------
 *
 *  Genesis/SGDK ビルド用の libc スタブ。
 *  リンクは -nostdlib + libmd（newlib libc 非リンク）のため、Doom が使う
 *  数個の標準関数を自前で供給する。
 *
 *  GPL v2 or later.
 *-----------------------------------------------------------------------------*/

#include <stddef.h>
#include <stdint.h>
#include <genesis.h>


// Doom の起動メッセージ等。Genesis には標準出力が無いので no-op。
int printf(const char *fmt, ...)
{
	(void)fmt;
	return 0;
}


// 異常終了。Genesis では停止するだけ。
void exit(int code)
{
	(void)code;
	for (;;)
		SYS_doVBlankProcess();
}


// SGDK は memcmp を提供しないため自前実装（Doom の _fmemcmp）。
int memcmp(const void *s1, const void *s2, u16 n)
{
	const unsigned char *a = (const unsigned char*)s1;
	const unsigned char *b = (const unsigned char*)s2;
	while (n--)
	{
		int d = (int)*a++ - (int)*b++;
		if (d)
			return d;
	}
	return 0;
}


// r_draw.c が abs() を関数として参照する（移植可能ファイルは maths.h を読まない）。
// このファイルは genesis.h 経由で maths.h の abs マクロを得るため undef してから実体を定義。
#undef abs
int abs(int x)
{
	return (x < 0) ? -x : x;
}


long labs(long x)
{
	return (x < 0) ? -x : x;
}


void *memchr(const void *s, int c, u16 n)
{
	const unsigned char *p = (const unsigned char*)s;
	while (n--)
	{
		if (*p == (unsigned char)c)
			return (void*)p;
		p++;
	}
	return NULL;
}


int strcasecmp(const char *a, const char *b)
{
	for (;;)
	{
		unsigned char ca = (unsigned char)*a++;
		unsigned char cb = (unsigned char)*b++;
		if (ca >= 'A' && ca <= 'Z') ca += 'a' - 'A';
		if (cb >= 'A' && cb <= 'Z') cb += 'a' - 'A';
		if (ca != cb)
			return (int)ca - (int)cb;
		if (ca == 0)
			return 0;
	}
}
