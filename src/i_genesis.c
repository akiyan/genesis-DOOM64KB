/*-----------------------------------------------------------------------------
 *
 *  Sega Genesis / Mega Drive implementation of i_system.h
 *  (Doom64KB の i_neogeo.c をベースに ngdevkit -> SGDK へ置換)
 *
 *  Copyright (C) 2026 Frenkel Smeijers
 *  GPL v2 or later.
 *-----------------------------------------------------------------------------*/

#include <stddef.h>
#include <stdint.h>
#include <genesis.h>

#include "doomdef.h"
#include "doomtype.h"
#include "compiler.h"
#include "d_main.h"
#include "i_system.h"
#if defined PLAYTEST
#include "g_game.h"
#endif

#include "globdata.h"


void I_InitGraphicsHardwareSpecificCode(void);
void I_ShutdownGraphics(void);


static boolean isGraphicsModeSet = false;


//**************************************************************************************
//
// Screen
//

void I_InitGraphics(void)
{
	I_InitGraphicsHardwareSpecificCode();
	isGraphicsModeSet = true;
}


//**************************************************************************************
//
// Keyboard / joypad
//

static boolean isKeyboardIsrSet = false;


void I_InitKeyboard(void)
{
	JOY_init();
	isKeyboardIsrSet = true;
}


static void I_PostEvent(boolean keyup, int16_t data1)
{
	event_t ev;
	ev.type  = keyup ? ev_keyup : ev_keydown;
	ev.data1 = data1;
	D_PostEvent(&ev);
}


// Genesis ボタン -> Doom KEYD_* の対応表（上流 Neo Geo 版に合わせる）。
//   方向キー : 移動 / メニュー上下左右
//   A        : KEYD_A  (Use / Sprint / メニュー決定)
//   B        : KEYD_B  (Fire)
//   C        : KEYD_R  (Strafe 右)
//   X / Z    : KEYD_L  (Strafe 左 / 6ボタン時)
//   Start    : KEYD_START (Menu 開閉 / 戻る)
typedef struct { uint16_t mask; int16_t key; } joymap_t;

static const joymap_t joymap[] = {
	{ BUTTON_UP,    KEYD_UP    },
	{ BUTTON_DOWN,  KEYD_DOWN  },
	{ BUTTON_LEFT,  KEYD_LEFT  },
	{ BUTTON_RIGHT, KEYD_RIGHT },
	{ BUTTON_A,     KEYD_A     },
	{ BUTTON_B,     KEYD_B     },
	{ BUTTON_C,     KEYD_R     },
	{ BUTTON_X,     KEYD_L     },
	{ BUTTON_Z,     KEYD_L     },
	{ BUTTON_START, KEYD_START },
};
#define NJOYMAP (sizeof(joymap)/sizeof(joymap[0]))


void I_StartTic(void)
{
#if defined MENU_TEST
	// 検証用: START でメニューを開き、A で "New Game" を選択して進む様子を自動再現
	static uint16_t bootframes = 0;
	if (bootframes < 400)
	{
		bootframes++;
		if (bootframes == 120) I_PostEvent(false, KEYD_START); // メニューを開く
		if (bootframes == 124) I_PostEvent(true,  KEYD_START);
		if (bootframes == 200) I_PostEvent(false, KEYD_A);     // New Game 決定
		if (bootframes == 204) I_PostEvent(true,  KEYD_A);
		if (bootframes == 280) I_PostEvent(false, KEYD_A);     // 難易度決定（あれば）
		if (bootframes == 284) I_PostEvent(true,  KEYD_A);
		if (bootframes == 360) I_PostEvent(false, KEYD_UP);    // 前進（押しっぱ＝離さない）
	}
#endif
#if defined PLAYTEST
	// 検証用: メニュー経路を経ずに E1M1 を直接開始する
	static uint16_t pf = 0;
	if (++pf == 30) G_DeferedInitNew(sk_medium);
#endif
	// SGDK のジョイパッド状態更新。SYS_doVBlankProcess() の中でしか呼ばれないため、
	// VDP_waitVSync() しか使わない本ループでは毎 tic ここで明示的に更新する。
	// これを呼ばないと JOY_readJoypad() が常に無入力を返し、実機の操作が一切効かない。
	JOY_update();

	static uint16_t prev = 0;
	uint16_t cur = JOY_readJoypad(JOY_1);
	uint16_t diff = cur ^ prev;
	prev = cur;

	for (uint16_t i = 0; i < NJOYMAP; i++)
	{
		if (diff & joymap[i].mask)
			I_PostEvent((cur & joymap[i].mask) == 0, joymap[i].key);
	}
}


//**************************************************************************************
//
// Audio (no sound, like the Neo Geo edition)
//

void DMX_Play(sfxenum_t id)  { (void)id; }
void DMX_Init(void)          { }
void DMX_Init2(void)         { }
void DMX_Shutdown(void)      { }
// I_ShutdownSound は i_audio.c が定義する


//**************************************************************************************
//
// Timer : 1/35 秒 tic を返す（VBlank 60Hz を数える）
//

static volatile int32_t ticcount;
static boolean isTimerSet;


static void I_VBlankCallback(void)
{
	ticcount++;
}


int32_t I_GetTime(void)
{
	return ticcount * TICRATE / 60;
}


void I_InitTimer(void)
{
	SYS_setVIntCallback(I_VBlankCallback);
	isTimerSet = true;
}


static void I_ShutdownTimer(void)
{
	SYS_setVIntCallback(NULL);
}


//**************************************************************************************
//
// Memory : Doom の zone ヒープ。Genesis は RAM 64KB なので SGDK 使用分を除いた静的配列。
//

// 調整可能。リンク時 RAM 使用量を見て増減する。
#ifndef HEAP_SIZE
#define HEAP_SIZE (43 * 1024)
#endif


uint8_t __far* I_ZoneBase(uint32_t *heapSize)
{
	static uint8_t heap[HEAP_SIZE];
	uint32_t paragraphs = HEAP_SIZE / PARAGRAPH_SIZE;
	uint8_t *ptr = heap;

	uint32_t m = (uint32_t) ptr;
	if ((m & (PARAGRAPH_SIZE - 1)) != 0)
	{
		paragraphs--;
		while ((m & (PARAGRAPH_SIZE - 1)) != 0)
			m = (uint32_t) ++ptr;
	}

	*heapSize = paragraphs * PARAGRAPH_SIZE;
	return ptr;
}


//**************************************************************************************
//
// Exit
//

static void I_Shutdown(void)
{
	if (isGraphicsModeSet)
		I_ShutdownGraphics();

	I_ShutdownSound();

	if (isTimerSet)
		I_ShutdownTimer();
}


void I_Quit(void)
{
	I_Shutdown();
	for (;;) { SYS_doVBlankProcess(); }
}


void I_Error(const char *error, ...)
{
	va_list argptr;
	char buffer[80];

	I_Shutdown();

	va_start(argptr, error);
	vsprintf(buffer, error, argptr);
	va_end(argptr);

	VDP_init();
	VDP_setTextPalette(PAL0);
	PAL_setColor(15, 0x0EEE);
	VDP_drawText(buffer, 1, 1);

	for (;;) { SYS_doVBlankProcess(); }
}


//**************************************************************************************
//
// Entry point (SGDK が main を呼ぶ)
//

int main(bool hardReset)
{
	(void)hardReset;

#if defined TIMEDEMO
	int argc = 3;
	const char * const argv[] = {"Doom64KB", "-timedemo", "demo3"};
#else
	int argc = 1;
	const char * const argv[] = {"Doom64KB"};
#endif
	D_DoomMain(argc, argv);

	return 0;
}
