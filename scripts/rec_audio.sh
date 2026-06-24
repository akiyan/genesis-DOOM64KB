#!/usr/bin/env bash
# rec_audio.sh — out/rom.bin を RetroArch+GenesisPlusGX でヘッドレス等速実行し、
# エミュ音声を録音(mkv)→ WAV 抽出 → 時間分解 RMS で「音が鳴っているか / SFXバーストの有無」を判定。
# demo-build-record スキル(genesis-novel)の retroarch 経路を音声解析用に流用したもの。
#
# 使い方: scripts/rec_audio.sh [seconds] [out_prefix]
#   seconds     録音する“エミュ内”秒数（既定 12）
#   out_prefix  出力プレフィックス（既定 tmp/rec）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
SECS="${1:-12}"; PFX="${2:-tmp/rec}"
mkdir -p tmp
GPGX=/usr/lib/x86_64-linux-gnu/libretro/genesis_plus_gx_libretro.so
test -f out/rom.bin || { echo "error: out/rom.bin が無い" >&2; exit 1; }
test -f "$GPGX"     || { echo "error: GPGX コアが無い" >&2; exit 1; }

# 1) snd-dummy（実時間シンク=等速録画用）を用意しデバイス開放（要 sudo 非対話）
awk '/Dummy/{exit 0} END{exit 1}' /proc/asound/cards 2>/dev/null || sudo -n modprobe snd-dummy 2>/dev/null || true
DCARD="$(awk '/Dummy/{gsub(/[][]/,"",$1); print $1; exit}' /proc/asound/cards 2>/dev/null || true)"
[ -n "$DCARD" ] || { echo "error: snd-dummy を用意できない" >&2; exit 1; }
sudo -n chmod 666 "/dev/snd/pcmC${DCARD}D0p" "/dev/snd/controlC${DCARD}" 2>/dev/null || true

# 2) Xvfb（空き番号に自前起動・無認証）
unset XAUTHORITY; DISP=""
for n in 99 121 122 123 124 125; do
  [ -e "/tmp/.X${n}-lock" ] && continue
  Xvfb ":${n}" -screen 0 640x480x24 -nolisten tcp >"/tmp/rec_xvfb_${n}.log" 2>&1 &
  XPID=$!
  for _ in $(seq 1 30); do DISPLAY=":${n}" xdotool getdisplaygeometry >/dev/null 2>&1 && { DISP=":${n}"; break; }; sleep 0.2; done
  [ -n "$DISP" ] && break
  kill "$XPID" 2>/dev/null || true
done
[ -n "$DISP" ] || { echo "error: Xvfb 確保失敗" >&2; exit 1; }
export DISPLAY="$DISP" SDL_VIDEODRIVER=x11
cleanup(){ pkill -x retroarch 2>/dev/null||true; kill "$XPID" 2>/dev/null||true; }
trap cleanup EXIT

# 3) RetroArch 設定（ALSA=snd-dummy / audio_sync で等速 / ffv1+flac lossless 録画）
REC_CFG="tmp/ra_rec_codec.cfg"
printf 'vcodec = ffv1\nacodec = flac\npix_fmt = yuv444p\n' > "$REC_CFG"
CFG="tmp/ra_demo.cfg"
cat > "$CFG" <<EOF
video_driver = "gl"
audio_driver = "alsa"
audio_device = "plughw:${DCARD},0"
audio_sync = "true"
audio_latency = "64"
menu_driver = "null"
video_fullscreen = "false"
video_threaded = "false"
video_record_quality = "0"
video_record_config = "$PWD/$REC_CFG"
EOF

MAXF=$(( SECS * 60 ))
RAW="${PFX}_raw.mkv"; WAV="${PFX}.wav"; rm -f "$RAW" "$WAV"
echo "==> 録音 ${SECS}s (max-frames=${MAXF}) display=${DISP} dummycard=${DCARD}"
timeout $(( SECS + 120 )) retroarch -L "$GPGX" out/rom.bin --config "$CFG" \
  --record "$RAW" --size 256x224 --max-frames "$MAXF" -v >/tmp/rec_retroarch.log 2>&1 || true
test -s "$RAW" || { echo "録音失敗"; tail -25 /tmp/rec_retroarch.log; exit 1; }

# 4) WAV 抽出（モノ 22050Hz で十分）
ffmpeg -hide_banner -loglevel error -y -i "$RAW" -ac 1 -ar 22050 "$WAV"

# 5) 全体音量 + 0.5秒刻みの RMS(dB) で時間分解。無音床より高いバーストが SFX 候補。
echo "=== 全体 volumedetect ==="
ffmpeg -hide_banner -nostats -i "$WAV" -af volumedetect -f null /dev/null 2>&1 \
  | grep -iE "mean_volume|max_volume"
echo "=== 0.5s 区間 RMS(dB) 時系列 ==="
ffmpeg -hide_banner -nostats -i "$WAV" -af astats=metadata=1:reset=1:length=0.5,ametadata=mode=print:key=lavfi.astats.Overall.RMS_level -f null /dev/null 2>&1 \
  | awk -F= '/RMS_level/{printf "%6.1f ", $2; n++; if(n%10==0)print ""} END{print ""}'
echo "出力: $WAV / $RAW"
