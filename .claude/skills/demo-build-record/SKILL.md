---
name: demo-build-record
description: Genesis64KBDoom のアトラクト（自動プレイ）を録画する。タイトル画面(TITLE_DEMO_SECONDS秒)＋DEMO3(E1M1)を RetroArch + Genesis Plus GX のヘッドレス(Xvfb)で音声付き録画し、neighbor 拡大の mp4 に変換するまでを 1 本で行う。「デモ動画を録って」「自動プレイを録画」「タイトルとデモを録画」「録画用ビルド」等のときに使う。録画尺は DEMO3 の tic 数から自動算出。録画せずビルドと尺だけ欲しいときは --build-only。成果物は大きいので Telegram には送らず tmp/ にパス提示する。
---

# demo-build-record

Genesis64KBDoom の**アトラクト（自動プレイ）**を録画する。順序は

```
タイトル画面 (TITLE_DEMO_SECONDS 秒) -> DEMO3(E1M1) 再生(約61秒) -> ループ
```

なので **タイトル秒 + DEMO3 秒** を録画する。RetroArch + Genesis Plus GX を
ヘッドレス(Xvfb)で起動し、**音声付き**で録画して mp4 に変換するまでを 1 本で行う。
実体は `scripts/demo_build_record.sh`（録画尺の算出は `scripts/demo_duration.py`）。
出力は**プロジェクト内 `tmp/`**。

## 使い方

プロジェクトルートで:

```sh
scripts/demo_build_record.sh [--title-seconds N] [--no-build] [--build-only] \
                             [--margin SEC] [--width W] [--height H] \
                             [--display :N] [--out FILE]
```

- `--title-seconds N` … タイトル表示秒（既定 10）。`-DTITLE_DEMO_SECONDS` でビルドに反映する。
- `--no-build` … ビルドせず既存 `out/rom.bin` を使う（タイトル秒は ROM のビルド時設定のまま）。
- `--build-only` … ビルドと録画尺の算出までで止める（録画しない）。
- `--margin SEC` … 末尾マージン秒（既定 3）。
- `--width/--height` … 出力解像度（既定 960x672 ＝ 320x224 の整数3倍 neighbor）。
- `--display :N` … 使う X ディスプレイ（既定 `:99` に Xvfb を自前起動）。
- `--out FILE` … 出力 mp4（既定 `tmp/demo_doom.mp4`）。
- `CORE`（env）… libretro コア .so（既定 `genesis_plus_gx`）。

例:
```sh
scripts/demo_build_record.sh                       # ビルド(タイトル10s)→録画→mp4
scripts/demo_build_record.sh --title-seconds 5     # タイトル5秒でビルドして録画
scripts/demo_build_record.sh --no-build            # 既存 ROM を録画
scripts/demo_build_record.sh --build-only          # 録画尺だけ算出（録画しない）
```

## 録画尺の算出

`scripts/demo_duration.py` が WAD のデモデータ（DEMO3、1 tic = 4 バイト、終端 0x80）から
DEMO3 の tic 数を数え、秒数(= tics/35)を出す。録画尺は

```
boot余白(2s) + タイトル秒 + DEMO3秒 + 末尾マージン
```

を 60fps(NTSC) でフレーム化し、RetroArch の `--max-frames` に渡して**ぴったり録って自動終了**する。

## 仕組み（RetroArch + Genesis Plus GX）

- ヘッドレス(Xvfb)で起動。`video_context_driver=x` / `input_driver=x`、`LIBGL_ALWAYS_SOFTWARE=1`。
- RetroArch の ffmpeg 内蔵録画（`--record` + `--recordconfig`、libx264+flac の mkv）で映像＋音声を
  1 ファイルに。音声(YM2612 BGM / XGM PCM SFX)は**エミュレータの A/V を per-frame でサンプル**するため、
  ヘッドレスが全速で回っても出力内で同期する（壁時計は実時間より短く済む）。
- `--size 320x224` でネイティブ等倍記録（GPGX の起動直後の可変 geometry で潰れるのを防ぐ）。
- 最終 mp4 は **neighbor 拡大(既定 960x672) + 60fps + AAC**。素材 `tmp/demo_raw.mkv` は再変換用に残す。

## 注意

- **成果物は大きいので Telegram には送らない**。`tmp/` のパスを伝え、ユーザーが取りに行く。
- `--no-build` で録るときは、既存 `out/rom.bin` のタイトル秒（ビルド時の `TITLE_DEMO_SECONDS`、
  既定 30）と `--title-seconds` がズレると尺が合わない。タイトル秒を変えたいときはビルドから行う。
- DEMO3 は E1M1 を約61秒プレイする記録 1 本のみ。アトラクトはこれをループする。
- ヘッドレスで RetroArch 窓に実機入力は注入できない（WM 不在）。本スキルは**録画専用**。
