// Genesis/SGDK 用 <ctype.h> シム。
// SGDK には ctype.h が無く、newlib の ctype.h は SGDK string.h の isdigit マクロと衝突する。
// -I$(SRC) により標準 <ctype.h> よりこのファイルが先に見つかる。Doom が使う最小限のみ定義。
#ifndef _CTYPE_SHIM_H_
#define _CTYPE_SHIM_H_

#ifndef isdigit
#define isdigit(c)  ((c) >= '0' && (c) <= '9')
#endif
#ifndef isspace
#define isspace(c)  ((c) == ' ' || ((c) >= '\t' && (c) <= '\r'))
#endif
#ifndef isalpha
#define isalpha(c)  (((c) >= 'a' && (c) <= 'z') || ((c) >= 'A' && (c) <= 'Z'))
#endif
#ifndef isupper
#define isupper(c)  ((c) >= 'A' && (c) <= 'Z')
#endif
#ifndef islower
#define islower(c)  ((c) >= 'a' && (c) <= 'z')
#endif
#ifndef toupper
#define toupper(c)  (islower(c) ? ((c) - 'a' + 'A') : (c))
#endif
#ifndef tolower
#define tolower(c)  (isupper(c) ? ((c) - 'A' + 'a') : (c))
#endif

#endif
