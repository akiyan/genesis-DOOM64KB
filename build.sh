#!/usr/bin/env bash
# Genesis64KBDoom ネイティブビルドスクリプト（Linux / Ubuntu 24.04 系）
#
# Doom64KB (https://github.com/FrenkelS/Doom64KB) を SGDK で Sega Genesis 用に移植。
# 同梱(symlink) vendor/sgdk からネイティブビルドした SGDK で ROM を作る（Docker/Wine 不使用）。
#
# 必要:
#   - m68k-elf-gcc (marsdev) : $HOME/toolchains/mars/m68k-elf/bin （MARSDEV で上書き可）
#   - default-jre-headless   : rescomp 用
#   - vendor/sgdk/bin に sjasm/bintos/convsym/xgmtool がビルド済みであること
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GDK="${ROOT}/vendor/sgdk"
cd "${ROOT}"

# marsdev m68k-elf ツールチェーン
MARSDEV="${MARSDEV:-$HOME/toolchains/mars}"
PREFIX="${PREFIX:-m68k-elf-}"
export PATH="${MARSDEV}/m68k-elf/bin:${GDK}/bin:${PATH}"

if ! command -v "${PREFIX}gcc" >/dev/null 2>&1; then
  echo "error: ${PREFIX}gcc が見つかりません（MARSDEV=${MARSDEV}）。" >&2
  exit 1
fi
if [ ! -f "${GDK}/lib/libmd.a" ]; then
  echo "error: ${GDK}/lib/libmd.a がありません。SGDK をネイティブビルドしてください。" >&2
  exit 1
fi

# doom64.wad を doom64ng.h から抽出（初回のみ）
if [ ! -f scripts/doom64.wad ]; then
  python3 scripts/wad_from_header.py
fi
# 68000 向けに lump を 4 バイト整列して再パックし src/doom64ng.h を再生成（必須）。
# 非整列 lump を WAD へ直接 far 参照すると 68000 で address error になるため。
python3 scripts/repack_wad.py
# PLAYPAL -> Genesis 64色パレット/LUT を生成
python3 scripts/genpal.py
# doom1.wad の DS* -> XGM PCM 用 SFX データ(src/gen_sfx.h)を生成（変更時のみ）
python3 scripts/gen_sfx.py

# LTO 無効化（冪等パッチ）: marsdev(13.1.0) の LTO バイトコードと SGDK libmd の版差を回避。
MK="${GDK}/makefile.gen"
if [ -f "${MK}" ]; then
  sed -i -e 's/ -flto=auto//g' -e 's/ -ffat-lto-objects//g' \
         -e 's/ -fuse-linker-plugin//g' -e 's/ -flto\b//g' "${MK}"
  grep -q -- '-fno-use-linker-plugin' "${MK}" || \
    sed -i '/md\.ld/ s/-m68000 -B/-m68000 -fno-lto -fno-use-linker-plugin -B/' "${MK}"
fi

# Doom64KB レンダ構成（Neo Geo 版 bneogeo.sh と同じ）:
#   FLAT_SPAN          : 床/天井をテクスチャ無しのベタ塗りに（タイルFB向け）
#   FLAT_NUKAGE1_COLOR : 毒沼の色 index
#   VIEWWINDOW* / MAPWIDTH : ビューを 38x28 セルに
#   LOW_MEMORY         : 省メモリ経路
RENDER_OPTIONS="-DFLAT_SPAN -DFLAT_NUKAGE1_COLOR=118 -DVIEWWINDOWWIDTH=38 -DVIEWWINDOWHEIGHT=28 -DMAPWIDTH=38 -DLOW_MEMORY"

# TIMEDEMO=1 で起動直後に DEMO3(E1M1) を再生するベンチ版（3Dレンダラ動作確認用）。
if [ "${TIMEDEMO:-0}" = "1" ]; then
  RENDER_OPTIONS="${RENDER_OPTIONS} -DTIMEDEMO"
fi
if [ "${PLAYTEST:-0}" = "1" ]; then
  RENDER_OPTIONS="${RENDER_OPTIONS} -DPLAYTEST"
fi
# MENU_TEST=1 で起動後に自動でメニューを開く（テキスト描画の検証用）。
if [ "${MENU_TEST:-0}" = "1" ]; then
  RENDER_OPTIONS="${RENDER_OPTIONS} -DMENU_TEST"
fi
# SFXDEBUG=1 で SFX 検証ビルド: デモ即開始＋無音BGM＋発砲音を強制発火。
# 録音すると BGM に邪魔されず SFX(PCM)が鳴っているかを分離判定できる。
if [ "${SFXDEBUG:-0}" = "1" ]; then
  RENDER_OPTIONS="${RENDER_OPTIONS} -DSFXDEBUG"
fi

# フラグ変更の検知: make は -D フラグの変更を検知できないため、TIMEDEMO/SFXDEBUG 等を
# 付けたビルドと通常ビルドを切り替えると、デバッグ付きの .o が残って混入する
# （例: 通常ビルドなのにタイトルで SFX が鳴り続ける）。前回ビルドと RENDER_OPTIONS が
# 変わっていたら強制的にクリーンビルドして再発を防ぐ。
STAMP="out/.render_options"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" != "${RENDER_OPTIONS}" ]; then
  echo "==> ビルドフラグ変更を検出 → クリーンビルド"
  rm -rf out
fi
mkdir -p out
printf '%s' "${RENDER_OPTIONS}" > "$STAMP"

# ビルド失敗時に古い ROM が残らないよう、毎ビルド前に削除する。
rm -f out/rom.bin

make GDK="${GDK}" PREFIX="${PREFIX}" \
  EXTRA_FLAGS="-std=gnu11 ${RENDER_OPTIONS}" \
  LIBGCC="${GDK}/lib/libgcc.a -lgcc" "$@"

if [ -f out/rom.bin ]; then
  echo "ROM: $(ls -l out/rom.bin | awk '{print $5}') bytes -> out/rom.bin"
fi
