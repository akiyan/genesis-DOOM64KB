/*-----------------------------------------------------------------------------
 *
 *  Sega Genesis / Mega Drive video code
 *  (Doom64KB の i_neogev.c をベースに ngdevkit -> SGDK へ置換)
 *
 *  方式: VDP プレーン A を 38x28 の「チャンキー・フレームバッファ」として使う。
 *  各セル = 8x8 ベタ塗りタイル 1 個。タイル 0..15 は単色(パレット内 index 0..15)。
 *  Doom の 256 色は 64 色(4 パレット x 16)へ量子化(scripts/genpal.py)。
 *  _s_screen は完成済み VDP タイルマップ語を直接保持し、I_FinishUpdate で一括 DMA。
 *
 *  Copyright (C) 2026 Frenkel Smeijers
 *  GPL v2 or later.
 *-----------------------------------------------------------------------------*/

#include <stddef.h>
#include <stdint.h>
#include <genesis.h>
#include <stdint.h>

#include "compiler.h"
#include "i_system.h"
#include "i_video.h"
#include "m_random.h"
#include "r_defs.h"
#include "v_video.h"
#include "w_wad.h"

#include "globdata.h"
#include "gen_pal.h"


extern const int16_t CENTERY;

// 16 個のベタ塗りタイルを置く VRAM 先頭 index
#define SOLID_TILE_INDEX  TILE_USER_INDEX

// チャンキー FB。各要素は完成済み VDP タイルマップ語。
static uint16_t _s_screen[VIEWWINDOWWIDTH * VIEWWINDOWHEIGHT];

// Doom 8bit 色 index -> VDP タイルマップ語
static uint16_t colorcell[256];

static int16_t palettelumpnum;


// ビュー slot(0..55) -> セル語。各パレットの index 1..14 がビュー色（0=黒, 15=テキスト色は予約）。
static inline uint16_t cell_for_color(uint8_t doomcolor)
{
	uint8_t slot = genpal_cell[doomcolor];               // 0..GENPAL_NVIEW-1
	uint8_t pal  = slot / GENPAL_VIEW_PER_PAL;           // 0..3
	uint8_t idx  = 1 + (slot % GENPAL_VIEW_PER_PAL);     // 1..14
	return TILE_ATTR_FULL(pal, 0, 0, 0, SOLID_TILE_INDEX + idx);
}

// 真の黒セル（全パレット index 0 = 黒。テキスト背景・画面クリア用）
#define BLACK_CELL  TILE_ATTR_FULL(0, 0, 0, 0, SOLID_TILE_INDEX + 0)

// Doom テキスト色(0..15) -> テキストパレット(0..3): PAL0=白 / PAL1=赤 / PAL2=黄 / PAL3=灰
// （i_neogev.c の colors[] の意図に合わせる: 4,12=赤 / 14=黄 / 7,8,9=灰 / 既定=白）
static const uint8_t textpal_for_color[16] = {
	0, 0, 0, 0, 1, 0, 0, 3, 3, 3, 0, 0, 1, 0, 2, 0
};

// テキスト1文字のセル語。SGDK 内蔵フォント(TILE_FONT_INDEX, ASCII 32..127, 前景=index15)を使う。
static inline uint16_t font_cell(uint8_t color, char c)
{
	uint8_t uc = (uint8_t)c;
	// メニューカーソルは CP437 のスカル(コード 1,2)。SGDK フォントに無いので '>' で代用。
	if (uc == 1 || uc == 2)
		uc = '>';
	else if (uc < 32 || uc > 127)
		uc = 32;
	uint8_t pal = textpal_for_color[color & 15];
	return TILE_ATTR_FULL(pal, 0, 0, 0, TILE_FONT_INDEX + (uc - 32));
}


//**************************************************************************************
//
// Palette
//

void I_ReloadPalette(void)
{
	char lumpName[8] = "PLAYPAL";
	if (_g_gamma != 0)
		lumpName[7] = '0' + _g_gamma;
	palettelumpnum = W_GetNumForName(lumpName);
}


static void I_UploadNewPalette(int8_t pal)
{
	if (pal < 0)
		pal = 0;
	if (pal >= GENPAL_NSUB)
		pal = GENPAL_NSUB - 1;
	PAL_setColors(0, genpal_cram[pal], 64, DMA);   // PAL0..3（ビュー色 + 予約テキスト色）
}


static int8_t newpal;
#define NO_PALETTE_CHANGE 100


void I_SetPalette(int8_t p)
{
	newpal = p;
}


void V_SetSTPalette(void)
{
	// Do nothing
}


//**************************************************************************************
//
// Init / shutdown
//

static void I_BuildSolidTiles(void)
{
	// 各タイル i は全 64 ピクセルが index i のベタ塗り
	uint32_t tile[8];
	for (uint16_t i = 0; i < 16; i++)
	{
		uint32_t row = i * 0x11111111UL;   // 8 ピクセル分の nibble
		for (uint16_t j = 0; j < 8; j++)
			tile[j] = row;
		VDP_loadTileData(tile, SOLID_TILE_INDEX + i, 1, CPU);
	}
}


void I_InitGraphicsHardwareSpecificCode(void)
{
	VDP_setScreenWidth320();
	VDP_setPlaneSize(64, 32, TRUE);

	I_BuildSolidTiles();

	// 256 色 -> セル語 LUT を構築
	for (uint16_t i = 0; i < 256; i++)
		colorcell[i] = cell_for_color((uint8_t)i);

	I_ReloadPalette();
	I_UploadNewPalette(0);
	newpal = NO_PALETTE_CHANGE;

	// 画面を黒で埋める
	for (int i = 0; i < VIEWWINDOWWIDTH * VIEWWINDOWHEIGHT; i++)
		_s_screen[i] = BLACK_CELL;
}


void I_ShutdownGraphics(void)
{
	// Do nothing
}


void I_FinishUpdate(void)
{
	VDP_waitVSync();

	if (newpal != NO_PALETTE_CHANGE)
	{
		I_UploadNewPalette(newpal);
		newpal = NO_PALETTE_CHANGE;
	}

	VDP_setTileMapDataRect(BG_A, _s_screen, 0, 0,
	                       VIEWWINDOWWIDTH, VIEWWINDOWHEIGHT,
	                       VIEWWINDOWWIDTH, DMA);
}


//**************************************************************************************
//
// Column / span rendering （ハード非依存。i_neogev.c とほぼ同一だが uint16 stride=W）
//

#define COLEXTRABITS (8 - 1)
#define COLBITS (8 + 1)


void R_DrawColumnSprite(const draw_column_vars_t *dcvars)
{
	int16_t count = (dcvars->yh - dcvars->yl) + 1;
	if (count <= 0)
		return;

	const uint8_t *source   = dcvars->source;
	const uint8_t *colormap = dcvars->colormap;

	uint16_t *dest = &_s_screen[dcvars->yl * VIEWWINDOWWIDTH + dcvars->x];

	const uint16_t fracstep = dcvars->fracstep;
	uint16_t frac = (dcvars->texturemid >> COLEXTRABITS) + (dcvars->yl - CENTERY) * fracstep;
	const uint8_t colbits = COLBITS;

	do
	{
		*dest = colorcell[colormap[source[frac >> colbits]]];
		dest += VIEWWINDOWWIDTH;
		frac += fracstep;
	} while (--count);
}


void R_DrawColumnWall(const draw_column_vars_t *dcvars)
{
	R_DrawColumnSprite(dcvars);
}


void R_DrawColumnFlat(uint8_t color, const draw_column_vars_t *dcvars)
{
	int16_t count = (dcvars->yh - dcvars->yl) + 1;
	if (count <= 0)
		return;

	uint16_t cell = colorcell[color];
	uint16_t *dest = &_s_screen[dcvars->yl * VIEWWINDOWWIDTH + dcvars->x];

	do
	{
		*dest = cell;
		dest += VIEWWINDOWWIDTH;
	} while (--count);
}


void R_DrawFuzzColumn(const draw_column_vars_t *dcvars)
{
	// TODO: ファジー(不可視)描画。とりあえずスプライトと同じ。
	R_DrawColumnSprite(dcvars);
}


//**************************************************************************************
//
// Full-screen / background images
//

void V_DrawRawFullScreen(int16_t num)
{
	const uint8_t *lump = W_GetLumpByNum(num);

	static const fixed_t DXI = ((fixed_t)SCREENWIDTH  << FRACBITS) / VIEWWINDOWWIDTH;
	static const fixed_t DYI = ((fixed_t)SCREENHEIGHT << FRACBITS) / VIEWWINDOWHEIGHT;

	uint16_t *dst = &_s_screen[0];
	fixed_t y = 0;
	for (int h = 0; h < VIEWWINDOWHEIGHT; h++)
	{
		fixed_t x = 0;
		for (int w = 0; w < VIEWWINDOWWIDTH; w++)
		{
			*dst++ = colorcell[lump[(y >> FRACBITS) * SCREENWIDTH + (x >> FRACBITS)]];
			x += DXI;
		}
		y += DYI;
	}
}


void V_DrawBackground(int16_t backgroundnum)
{
	// メニュー/ヘルプ背景。チャンキー FB では黒で塗ってテキストを読みやすくする。
	(void)backgroundnum;
	for (int i = 0; i < VIEWWINDOWWIDTH * VIEWWINDOWHEIGHT; i++)
		_s_screen[i] = BLACK_CELL;
}


void V_ClearViewWindow(void)
{
	for (int i = 0; i < VIEWWINDOWWIDTH * VIEWWINDOWHEIGHT; i++)
		_s_screen[i] = BLACK_CELL;
}


//**************************************************************************************
//
// Text / HUD （各セルに SGDK 内蔵フォントのグリフタイルを書き込む）
//

void V_DrawCharacter(int16_t x, int16_t y, uint8_t color, char c)
{
	if ((uint16_t)x < VIEWWINDOWWIDTH && (uint16_t)y < VIEWWINDOWHEIGHT)
		_s_screen[y * VIEWWINDOWWIDTH + x] = font_cell(color, c);
}

void V_DrawSTCharacter(int16_t x, int16_t y, uint8_t color, char c)
{
	V_DrawCharacter(x, y, color, c);
}

void V_DrawCharacterForeground(int16_t x, int16_t y, uint8_t color, char c)
{
	V_DrawCharacter(x, y, color, c);
}

void V_DrawString(int16_t x, int16_t y, uint8_t color, const char* s)
{
	if ((uint16_t)y >= VIEWWINDOWHEIGHT)
		return;
	while (*s)
	{
		if ((uint16_t)x < VIEWWINDOWWIDTH)
			_s_screen[y * VIEWWINDOWWIDTH + x] = font_cell(color, *s);
		s++;
		x++;
	}
}

void V_DrawSTString(int16_t x, int16_t y, uint8_t color, const char* s)
{
	V_DrawString(x, y, color, s);
}

void V_ClearString(int16_t y, size_t len)
{
	if ((uint16_t)y >= VIEWWINDOWHEIGHT)
		return;
	uint16_t *d = &_s_screen[y * VIEWWINDOWWIDTH];
	for (size_t i = 0; i < len && i < VIEWWINDOWWIDTH; i++)
		d[i] = BLACK_CELL;
}


//**************************************************************************************
//
// Lines (automap) / screen pages / wipe
//

void V_InitDrawLine(void)      { }
void V_ShutdownDrawLine(void)  { }

void V_DrawLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint8_t color)
{
	uint16_t cell = colorcell[color];
	int dx =  abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
	int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
	int err = dx + dy;
	for (;;)
	{
		if ((uint16_t)x0 < VIEWWINDOWWIDTH && (uint16_t)y0 < VIEWWINDOWHEIGHT)
			_s_screen[y0 * VIEWWINDOWWIDTH + x0] = cell;
		if (x0 == x1 && y0 == y1)
			break;
		int e2 = 2 * err;
		if (e2 >= dy) { err += dy; x0 += sx; }
		if (e2 <= dx) { err += dx; y0 += sy; }
	}
}


void I_InitScreenPage(void)
{
	V_ClearViewWindow();
}


void I_InitScreenPages(void)
{
	V_ClearViewWindow();
}


void wipe_StartScreen(void)
{
	I_InitScreenPages();
}


void D_Wipe(void)
{
	// TODO: 画面ワイプ。今は即時更新。
	I_FinishUpdate();
}
