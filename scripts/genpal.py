#!/usr/bin/env python3
"""Doom64KB(Neo Geo WAD) の PLAYPAL を Genesis パレットへ量子化し src/gen_pal.h を生成。

Genesis は 4 パレット x 16 色。テキスト描画(SGDK 内蔵フォント, 前景=index15/背景=index0)と
3D ビューを両立させるため、各パレットの以下を予約する:
  index 0  = 黒（テキスト背景・ビューの黒）
  index 15 = テキスト色（PAL0=白 / PAL1=赤 / PAL2=黄 / PAL3=ライトグレー）
残り index 1..14 を 3D ビュー用に使う → ビューは 4 x 14 = 56 色。

出力 gen_pal.h:
  GENPAL_NVIEW         : ビュー色数(56)
  genpal_cell[256]     : Doom 色index -> ビュー slot(0..55)
                         （cell 語は実機側で pal=slot/14, tile index=1+slot%14 として組む）
  genpal_cram[14][64]  : 各サブパレットの Genesis CRAM 語(64=PAL0..3 連結)
"""
import struct, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAD  = os.path.join(ROOT, "scripts", "doom64_aligned.wad")
if not os.path.exists(WAD):
    WAD = os.path.join(ROOT, "scripts", "doom64.wad")
OUT  = os.path.join(ROOT, "src", "gen_pal.h")

NSUB  = 14            # PLAYPAL サブパレット数
NCOL  = 256
NPAL  = 4
VIEW_PER_PAL = 14     # 各パレットの index 1..14
NVIEW = NPAL * VIEW_PER_PAL   # 56

# テキスト色（各パレットの index 15）。サブパレットに依らず固定。
TEXT_FG = [
    (255, 255, 255),   # PAL0 白
    (255,  40,  40),   # PAL1 赤
    (255, 235,  60),   # PAL2 黄
    (200, 200, 200),   # PAL3 ライトグレー
]

def load_playpal():
    b = open(WAD, "rb").read()
    n = struct.unpack_from('>h', b, 4)[0]
    o = struct.unpack_from('>i', b, 8)[0]
    for i in range(n):
        e = o + i*16
        name = b[e+8:e+16].split(b'\x00')[0].decode('latin1')
        if name == "PLAYPAL":
            fp = struct.unpack_from('>i', b, e)[0]
            sz = struct.unpack_from('>H', b, e+4)[0]
            return b[fp:fp+sz]
    raise SystemExit("PLAYPAL not found")

def ng16_to_rgb(c):
    dark = (c >> 15) & 1
    r = ((c >> 8) & 0xF); r0 = (c >> 14) & 1
    g = ((c >> 4) & 0xF); g0 = (c >> 13) & 1
    b = ((c >> 0) & 0xF); b0 = (c >> 12) & 1
    R6 = (r << 2) | (r0 << 1) | dark
    G6 = (g << 2) | (g0 << 1) | dark
    B6 = (b << 2) | (b0 << 1) | dark
    to8 = lambda v: (v << 2) | (v >> 4)
    return (to8(R6), to8(G6), to8(B6))

def gen_color(rgb):
    r, g, b = rgb
    return ((b >> 5) << 9) | ((g >> 5) << 5) | ((r >> 5) << 1)

def decode_subpal(pp, pal):
    base = pal * NCOL * 2
    return [ng16_to_rgb(struct.unpack_from('>H', pp, base + i*2)[0]) for i in range(NCOL)]

def median_cut(items, depth):
    boxes = [items]
    for _ in range(depth):
        nb = []
        for box in boxes:
            if len(box) <= 1:
                nb.append(box); continue
            rng = [max(c[1][ch] for c in box) - min(c[1][ch] for c in box) for ch in range(3)]
            ax = rng.index(max(rng))
            box = sorted(box, key=lambda c: c[1][ax])
            m = len(box)//2
            nb.append(box[:m]); nb.append(box[m:])
        boxes = nb
    return boxes

def main():
    pp = load_playpal()
    base_rgb = decode_subpal(pp, 0)

    # 256 色を NVIEW(56) クラスタへ。2^6=64 分割の先頭 56 box を使う。
    items = [(i, base_rgb[i]) for i in range(NCOL)]
    boxes = [b for b in median_cut(items, 6) if b]      # 空 box を除去
    # box 数を NVIEW へ調整（多ければ小さい box を併合）
    boxes.sort(key=len, reverse=True)
    while len(boxes) > NVIEW:
        small = boxes.pop()
        boxes[-1] = boxes[-1] + small
    while len(boxes) < NVIEW:
        big = max(boxes, key=len)
        boxes.remove(big)
        big = sorted(big, key=lambda c: c[1][0])
        m = len(big)//2
        boxes.append(big[:m]); boxes.append(big[m:])

    repr_idx = [0]*NVIEW
    slot_of  = [0]*NCOL
    for s, box in enumerate(boxes):
        cr = sum(c[1][0] for c in box)/len(box)
        cg = sum(c[1][1] for c in box)/len(box)
        cb = sum(c[1][2] for c in box)/len(box)
        best = min(box, key=lambda c: (c[1][0]-cr)**2 + (c[1][1]-cg)**2 + (c[1][2]-cb)**2)
        repr_idx[s] = best[0]
        for c in box:
            slot_of[c[0]] = s

    def cram_pos(slot):
        # ビュー slot -> CRAM 位置（pal*16 + index）。index は 1..14。
        pal = slot // VIEW_PER_PAL
        idx = 1 + (slot % VIEW_PER_PAL)
        return pal*16 + idx

    cram = []
    for sub in range(NSUB):
        rgb = decode_subpal(pp, sub)
        words = [0]*64
        for p in range(NPAL):
            words[p*16 + 0]  = 0x0000                       # 黒（テキスト背景）
            words[p*16 + 15] = gen_color(TEXT_FG[p])        # テキスト色
        for slot in range(NVIEW):
            words[cram_pos(slot)] = gen_color(rgb[repr_idx[slot]])
        cram.append(words)

    with open(OUT, "w") as f:
        f.write("// 自動生成 (scripts/genpal.py) — 編集禁止\n")
        f.write("#ifndef __GEN_PAL_H__\n#define __GEN_PAL_H__\n#include <stdint.h>\n\n")
        f.write("#define GENPAL_NSUB %d\n#define GENPAL_NVIEW %d\n" % (NSUB, NVIEW))
        f.write("#define GENPAL_VIEW_PER_PAL %d\n\n" % VIEW_PER_PAL)
        f.write("static const uint8_t genpal_cell[256] = {\n")
        for i in range(0, NCOL, 16):
            f.write("  " + ",".join("%d" % slot_of[j] for j in range(i, i+16)) + ",\n")
        f.write("};\n\n")
        f.write("static const uint16_t genpal_cram[GENPAL_NSUB][64] = {\n")
        for sub in range(NSUB):
            f.write("  {" + ",".join("0x%04x" % w for w in cram[sub]) + "},\n")
        f.write("};\n\n#endif\n")
    print("wrote", OUT, " view slots:", len(set(slot_of)), "/", NVIEW)

if __name__ == "__main__":
    main()
