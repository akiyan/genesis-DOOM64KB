#!/usr/bin/env bash
# demo_build_record.sh
#
# アトラクト（自動プレイ）を録画する: タイトル画面(TITLE_DEMO_SECONDS秒) + DEMO3(E1M1)。
# RetroArch + Genesis Plus GX をヘッドレス(Xvfb)で起動し、音声付きで録画して mp4 に変換する。
# 録画尺は scripts/demo_duration.py が DEMO3 の tic 数から自動算出する。
#
# 使い方（プロジェクトルートで）:
#   scripts/demo_build_record.sh [--title-seconds N] [--no-build] [--build-only]
#                                [--margin SEC] [--width W] [--height H]
#                                [--display :N] [--out FILE]
#
#   --title-seconds N : タイトル表示秒（既定 10）。-DTITLE_DEMO_SECONDS でビルドに反映。
#   --no-build        : ビルドせず既存 out/rom.bin を使う（--title-seconds はビルドに無効）。
#   --build-only      : ビルドと録画尺の算出だけで止める（録画しない）。
#   --margin SEC      : 末尾マージン秒（既定 3）。
#   --width/--height  : 出力解像度（既定 960x672 = 320x224 の 3 倍 neighbor）。
#   --display :N      : 使う X ディスプレイ（既定 :99 に Xvfb を自前起動）。
#   --out FILE        : 出力 mp4（既定 tmp/demo_doom.mp4）。
#
# env:
#   CORE  : libretro コア .so（既定 genesis_plus_gx）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TITLE_SECONDS=10
DO_BUILD=1
BUILD_ONLY=0
MARGIN=3
SCALE=5          # 描画内容(304x224)の neighbor 整数拡大率
PAD=40           # 外周 padding(px)
PADCOL="0x181818"
CRF=0            # 最終 mp4 の x264 CRF（0=ロスレス）。yuv444p でクロマ間引きせず赤滲みを防ぐ
DISPLAY_NUM=":99"
OUT="out/doom_megadrive.mp4"
CORE="${CORE:-/usr/lib/x86_64-linux-gnu/libretro/genesis_plus_gx_libretro.so}"

# ビューは 38x28 セル = 304x224。録画(320x224)の右 16px は黒なのでクロップして中央化する。
CONTENT_W=304
CONTENT_H=224

while [ $# -gt 0 ]; do
  case "$1" in
    --title-seconds) TITLE_SECONDS="$2"; shift 2;;
    --no-build) DO_BUILD=0; shift;;
    --build-only) BUILD_ONLY=1; shift;;
    --margin) MARGIN="$2"; shift 2;;
    --scale) SCALE="$2"; shift 2;;
    --pad) PAD="$2"; shift 2;;
    --pad-color) PADCOL="$2"; shift 2;;
    --crf) CRF="$2"; shift 2;;
    --display) DISPLAY_NUM="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    -h|--help) sed -n '2,30p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

mkdir -p tmp out

# --- ビルド ---
if [ "$DO_BUILD" -eq 1 ]; then
  echo "==> build (TITLE_DEMO_SECONDS=${TITLE_SECONDS})"
  TITLE_DEMO_SECONDS="$TITLE_SECONDS" ./build.sh >tmp/demo_build.log 2>&1 || {
    echo "build failed; see tmp/demo_build.log" >&2; tail -20 tmp/demo_build.log; exit 1; }
fi
[ -f out/rom.bin ] || { echo "out/rom.bin がありません" >&2; exit 1; }

# --- 録画尺の算出（boot 余白 + タイトル + DEMO3 + 末尾マージン） ---
DEMO_SECONDS="$(python3 scripts/demo_duration.py --demo-seconds)"
BOOT_PAD=2
TOTAL_SECONDS="$(python3 - "$TITLE_SECONDS" "$DEMO_SECONDS" "$BOOT_PAD" "$MARGIN" <<'PY'
import sys, math
title, demo, boot, margin = (float(x) for x in sys.argv[1:5])
print(int(math.ceil(boot + title + demo + margin)))
PY
)"
MAX_FRAMES=$(( TOTAL_SECONDS * 60 ))   # NTSC 60fps
echo "==> 録画尺: タイトル ${TITLE_SECONDS}s + DEMO3 ${DEMO_SECONDS}s (+boot ${BOOT_PAD}s +margin ${MARGIN}s) = ${TOTAL_SECONDS}s / ${MAX_FRAMES} frames"

if [ "$BUILD_ONLY" -eq 1 ]; then
  echo "build-only: 録画はしません。"
  exit 0
fi

for t in Xvfb retroarch ffmpeg; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing tool: $t" >&2; exit 1; }
done
[ -f "$CORE" ] || { echo "core not found: $CORE (set CORE=)" >&2; exit 1; }

# --- RetroArch 設定 ---
CFG="tmp/demo_ra.cfg"
cat > "$CFG" <<EOF
video_driver = "gl"
video_context_driver = "x"
input_driver = "x"
joystick_driver = "null"
audio_driver = "null"
audio_enable = "true"
menu_driver = "null"
config_save_on_exit = "false"
video_fullscreen = "false"
EOF
RECCFG="tmp/demo_rec.cfg"
# RAW は ffv1 + bgr0(RGB) の完全ロスレス。yuv420p はクロマ間引き(4:2:0)で赤が滲むため使わない。
cat > "$RECCFG" <<EOF
format = matroska
vcodec = ffv1
acodec = flac
pix_fmt = bgr0
sample_rate = 44100
EOF

RAW="tmp/demo_raw.mkv"; rm -f "$RAW"

# --- 録画（Xvfb 上で全速録画。--max-frames で自動終了） ---
pkill -9 -x retroarch 2>/dev/null || true; pkill -9 -x Xvfb 2>/dev/null || true; sleep 1
Xvfb "$DISPLAY_NUM" -screen 0 640x480x24 >tmp/demo_xvfb.log 2>&1 &
XVFB_PID=$!
sleep 2
echo "==> RetroArch+GPGX 録画 (size 320x224, max-frames ${MAX_FRAMES})"
DISPLAY="$DISPLAY_NUM" LIBGL_ALWAYS_SOFTWARE=1 \
  timeout $(( TOTAL_SECONDS + 120 )) \
  retroarch -c "$CFG" -L "$CORE" --record "$RAW" --recordconfig "$RECCFG" \
  --size 320x224 --max-frames "$MAX_FRAMES" out/rom.bin >tmp/demo_ra.log 2>&1 || true
kill "$XVFB_PID" 2>/dev/null || true; pkill -9 -x Xvfb 2>/dev/null || true

[ -s "$RAW" ] || { echo "録画失敗（$RAW が空）。tmp/demo_ra.log を確認:" >&2; tail -20 tmp/demo_ra.log; exit 1; }

# --- mp4 へ変換（右黒線をクロップして中央化 → neighbor 拡大 → 外周 padding → AAC） ---
SCALED_W=$(( CONTENT_W * SCALE ))
SCALED_H=$(( CONTENT_H * SCALE ))
CANVAS_W=$(( SCALED_W + PAD * 2 ))
CANVAS_H=$(( SCALED_H + PAD * 2 ))
VF="crop=${CONTENT_W}:${CONTENT_H}:0:0,scale=${SCALED_W}:${SCALED_H}:flags=neighbor,pad=${CANVAS_W}:${CANVAS_H}:${PAD}:${PAD}:color=${PADCOL}"
echo "==> mp4 変換 -> $OUT (${CANVAS_W}x${CANVAS_H}, 60fps, yuv444p crf=${CRF}, AAC)"
# yuv444p でクロマ間引きせず（赤の滲み防止）、crf=0 でロスレス。RGB から直接 444 へ変換。
ffmpeg -hide_banner -loglevel error -y -i "$RAW" \
  -vf "$VF" \
  -r 60 -c:v libx264 -preset medium -crf "$CRF" -pix_fmt yuv444p \
  -c:a aac -b:a 256k -movflags +faststart "$OUT"

DUR="$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "$OUT" 2>/dev/null || echo '?')"
echo "完了: $OUT  (長さ ${DUR}s, ${CANVAS_W}x${CANVAS_H})"
echo "      raw: $RAW"
