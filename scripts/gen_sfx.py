#!/usr/bin/env python3
"""doom1.wad の DMX 効果音(DS*)を SGDK XGM(classic) PCM 用データへ変換し
src/gen_sfx.h を生成する。

classic XGM ドライバの PCM は「8bit 符号付き・固定14kHz・256バイト整列」。
doom64.wad には DS* が無いため、音名が 1:1 一致する doom1.wad を音源にする。

各 DS ランプの処理:
  - DMX ヘッダ 8B (u16 fmt=3, u16 rate, u32 nsamples) を除去
  - 符号なし(0..255) -> 符号付き(-128..127): sample-128
  - 元レート -> 14000Hz へ線形補間リサンプル（ピッチ維持）
  - 長さを 256 の倍数へ 0(=符号付き無音) パディング

出力 gen_sfx.h:
  GENSFX_PCM_ID_BASE  : XGM PCM id の基点(64。0..63 は音楽予約)
  GENSFX_COUNT        : SFX 数
  gensfx[1..COUNT]    : {データ, 長さ, XGM優先度(0..15)}  index は sfxenum_t に一致
"""
import struct, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAD  = os.path.join(ROOT, "scripts", "doom1.wad")
if not os.path.exists(WAD):
    alt = "/home/akiyan/genesis-doom/wad/doom1.wad"
    if os.path.exists(alt):
        WAD = alt
OUT  = os.path.join(ROOT, "src", "gen_sfx.h")

XGM_RATE    = 14000   # classic XGM ドライバの固定 PCM レート
PCM_ID_BASE = 64      # 0..63 は音楽用に予約。SFX は 64 以上

# sounds.h の sfx_*(sfx_None を除く)順。DS ランプ名は大文字化で導出。
# 末尾の Doom priority(S_sfx[]: 小さいほど重要) は XGM 優先度(0..15)へ反転変換。
SFX = [
    ("pistol",  64), ("shotgn",  64), ("sgcock",  64), ("sawup",   64),
    ("sawidl", 118), ("sawful",  64), ("sawhit",  64), ("rlaunc",  64),
    ("rxplod",  70), ("firsht",  70), ("firxpl",  70), ("pstart", 100),
    ("pstop",  100), ("doropn", 100), ("dorcls", 100), ("stnmov", 119),
    ("swtchn",  78), ("swtchx",  78), ("plpain",  96), ("dmpain",  96),
    ("popain",  96), ("slop",    78), ("itemup",  78), ("wpnup",   78),
    ("oof",     96), ("telept",  32), ("posit1",  98), ("posit2",  98),
    ("posit3",  98), ("bgsit1",  98), ("bgsit2",  98), ("sgtsit",  98),
    ("brssit",  94), ("sgtatk",  70), ("claw",    70), ("pldeth",  32),
    ("pdiehi",  32), ("podth1",  70), ("podth2",  70), ("podth3",  70),
    ("bgdth1",  70), ("bgdth2",  70), ("sgtdth",  70), ("brsdth",  32),
    ("posact", 120), ("bgact",  120), ("dmact",  120), ("noway",   78),
    ("barexp",  60), ("punch",   64), ("tink",    60), ("getpow",  60),
]

def read_lumps():
    b = open(WAD, "rb").read()
    n = struct.unpack_from('<i', b, 4)[0]
    o = struct.unpack_from('<i', b, 8)[0]
    d = {}
    for i in range(n):
        e = o + i*16
        fp, sz = struct.unpack_from('<ii', b, e)
        name = b[e+8:e+16].split(b'\x00')[0].decode('latin1')
        if name.startswith("DS"):
            d[name] = b[fp:fp+sz]
    return d

def convert(lump):
    fmt, rate, ns = struct.unpack_from('<HHI', lump, 0)
    pcm = lump[8:8+ns]                       # 8bit 符号なし
    out_n = max(1, (ns * XGM_RATE) // rate)  # 14kHz へ
    res = bytearray(out_n)
    step = rate / XGM_RATE
    for i in range(out_n):
        src = i * step
        i0 = int(src); frac = src - i0
        s0 = pcm[i0] if i0 < ns else pcm[ns-1]
        s1 = pcm[i0+1] if i0+1 < ns else s0
        u = s0 + (s1 - s0) * frac            # 線形補間 (0..255)
        res[i] = (int(u + 0.5) - 128) & 0xFF # 符号付きを 2 の補数バイトで格納
    res += b'\x00' * ((-len(res)) % 256)     # 256 倍数へ無音パディング
    return res

def xgm_prio(doom_prio):
    # Doom: 小さいほど重要(32..120) -> XGM: 大きいほど優先(0..15)
    p = (128 - doom_prio) // 8
    return max(0, min(15, p))

def fresh():
    # gen_sfx.h が WAD・本スクリプトより新しければ再生成不要
    if not os.path.exists(OUT):
        return False
    t = os.path.getmtime(OUT)
    for dep in (WAD, os.path.abspath(__file__)):
        if os.path.exists(dep) and os.path.getmtime(dep) > t:
            return False
    return True

def write_stub():
    # doom1.wad 不在環境(リポジトリに WAD を含めない方針)でもビルドが通るよう、
    # SFX を無効化したスタブを出力する。DMX_Init/DMX_Play は GENSFX_COUNT=0 で no-op になる。
    with open(OUT, "w") as f:
        f.write("// 自動生成 (scripts/gen_sfx.py) — doom1.wad 不在のため SFX 無効スタブ\n")
        f.write("#ifndef __GEN_SFX_H__\n#define __GEN_SFX_H__\n#include <stdint.h>\n\n")
        f.write("#define GENSFX_PCM_ID_BASE %d\n#define GENSFX_COUNT 0\n\n" % PCM_ID_BASE)
        f.write("typedef struct { const uint8_t *data; uint32_t len; uint8_t prio; } gensfx_t;\n")
        f.write("static const gensfx_t gensfx[1] = { { 0, 0, 0 } };\n\n#endif\n")
    print("warning: doom1.wad が無いため SFX 無効スタブを生成。"
          "SFX を有効化するには scripts/doom1.wad を配置して再ビルド。")

def main():
    if "--force" not in sys.argv and fresh():
        print("gen_sfx.h は最新。スキップ")
        return
    if not os.path.exists(WAD):
        write_stub()
        return
    lumps = read_lumps()

    arrays = []
    total = 0
    for name, dprio in SFX:
        ln = "DS" + name.upper()
        if ln not in lumps:
            sys.exit("error: %s が doom1.wad に無い" % ln)
        data = convert(lumps[ln])
        total += len(data)
        arrays.append((name, data, xgm_prio(dprio)))

    with open(OUT, "w") as f:
        f.write("// 自動生成 (scripts/gen_sfx.py) — 編集禁止\n")
        f.write("// doom1.wad の DS* を 8bit 符号付き/14kHz/256整列へ変換\n")
        f.write("#ifndef __GEN_SFX_H__\n#define __GEN_SFX_H__\n#include <stdint.h>\n\n")
        f.write("#define GENSFX_PCM_ID_BASE %d\n" % PCM_ID_BASE)
        f.write("#define GENSFX_COUNT %d\n\n" % len(arrays))
        for name, data, _ in arrays:
            f.write("static const uint8_t pcm_%s[] __attribute__((aligned(256))) = {\n" % name)
            for i in range(0, len(data), 32):
                f.write("  " + ",".join("%d" % (b if b < 128 else b-256) for b in data[i:i+32]) + ",\n")
            f.write("};\n")
        f.write("\ntypedef struct { const uint8_t *data; uint32_t len; uint8_t prio; } gensfx_t;\n")
        f.write("// sfxenum_t(1..%d) に一致。index 0(sfx_None) はダミー。\n" % len(arrays))
        f.write("static const gensfx_t gensfx[GENSFX_COUNT + 1] = {\n")
        f.write("  { 0, 0, 0 },\n")
        for name, data, prio in arrays:
            f.write("  { pcm_%s, sizeof(pcm_%s), %d },\n" % (name, name, prio))
        f.write("};\n\n#endif\n")
    print("wrote %s  SFX=%d  PCM合計=%d bytes (%.0f KB)" % (OUT, len(arrays), total, total/1024))

if __name__ == "__main__":
    main()
