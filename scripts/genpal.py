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

def dist2(a, b):
    return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2

def gen_to_rgb(w):
    # gen_color() で作った Genesis 9bit 語を表示時の RGB888 へ戻す（各3bit -> 8bit）
    r = (w >> 1) & 7; g = (w >> 5) & 7; b = (w >> 9) & 7
    e = lambda v: (v << 5) | (v << 2) | (v >> 1)
    return (e(r), e(g), e(b))

def main():
    pp = load_playpal()
    cols = decode_subpal(pp, 0)        # Doom idx -> RGB888（量子化の基準）

    def centroid(idxs):
        n = len(idxs)
        return (sum(cols[i][0] for i in idxs)/n,
                sum(cols[i][1] for i in idxs)/n,
                sum(cols[i][2] for i in idxs)/n)

    # --- 初期クラスタ: median cut。箱数調整は「最近傍の箱へ合流」させ、
    #     旧コードのように1箱へ雪だるま式に集約しないようにする。
    items = [(i, cols[i]) for i in range(NCOL)]
    boxes = [[c[0] for c in b] for b in median_cut(items, 6) if b]   # 箱 = Doom idx のリスト
    while len(boxes) > NVIEW:
        boxes.sort(key=len)
        small = boxes.pop(0)
        sc = centroid(small)
        j = min(range(len(boxes)), key=lambda k: dist2(sc, centroid(boxes[k])))
        boxes[j] = boxes[j] + small
    while len(boxes) < NVIEW:
        big = max(boxes, key=len); boxes.remove(big)
        rng = [max(cols[i][ch] for i in big) - min(cols[i][ch] for i in big) for ch in range(3)]
        ax = rng.index(max(rng))
        big = sorted(big, key=lambda i: cols[i][ax]); m = len(big)//2
        boxes.append(big[:m]); boxes.append(big[m:])

    centroids = [centroid(b) for b in boxes]

    # --- Lloyd 反復 (k-means) で代表色を最適化（決定論的）---
    for _ in range(30):
        groups = [[] for _ in range(NVIEW)]
        for i in range(NCOL):
            j = min(range(NVIEW), key=lambda k: dist2(cols[i], centroids[k]))
            groups[j].append(i)
        for k in range(NVIEW):              # 空クラスタ救済: 最も誤差の大きい点を奪う
            if groups[k]:
                continue
            assign = [min(range(NVIEW), key=lambda kk: dist2(cols[i], centroids[kk])) for i in range(NCOL)]
            worst = max(range(NCOL), key=lambda i: dist2(cols[i], centroids[assign[i]]))
            groups[assign[worst]].remove(worst); groups[k] = [worst]
        new = [centroid(g) for g in groups]
        if new == centroids:
            break
        centroids = new

    # --- 各クラスタの代表 Doom index を選ぶ。表示色(Genesis 9bit)が重複しないよう調整し、
    #     実効色数を NVIEW に近づける。大きいクラスタから distinct 色を確保。---
    groups = [[] for _ in range(NVIEW)]
    for i in range(NCOL):
        j = min(range(NVIEW), key=lambda k: dist2(cols[i], centroids[k]))
        groups[j].append(i)
    used_gen = set()
    repr_idx = [0]*NVIEW
    for k in sorted(range(NVIEW), key=lambda k: -len(groups[k])):
        cen = centroids[k]
        g = groups[k] if groups[k] else [min(range(NCOL), key=lambda i: dist2(cols[i], cen))]
        cand = sorted(g, key=lambda i: dist2(cols[i], cen))           # まずクラスタ内
        chosen = next((i for i in cand if gen_color(cols[i]) not in used_gen), None)
        if chosen is None:                                           # 全色から未使用 Genesis 色を探す
            allc = sorted(range(NCOL), key=lambda i: dist2(cols[i], cen))
            chosen = next((i for i in allc if gen_color(cols[i]) not in used_gen), cand[0])
        repr_idx[k] = chosen
        used_gen.add(gen_color(cols[chosen]))

    # --- 各 Doom 色を「最も近い代表“表示色”」へ割り当て直す（箱の所属ではなく）。
    #     これでグレーが緑代表へ混入するような誤割当てが消える。---
    repr_disp = [gen_to_rgb(gen_color(cols[repr_idx[k]])) for k in range(NVIEW)]
    slot_of = [min(range(NVIEW), key=lambda k: dist2(cols[i], repr_disp[k])) for i in range(NCOL)]

    print("実効色数(distinct Genesis):", len(used_gen), "/", NVIEW)

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
