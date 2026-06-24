#!/usr/bin/env python3
"""WAD を 68000 向けに再パックする。

Doom64KB は level/render データ(segs/sidedefs/nodes 等)を W_GetLumpByNum の戻り値で
WAD バイト配列へ直接 far 参照し、int16/int32 フィールドを読む。元 WAD には奇数 filepos の
lump が多数あり、Sega Genesis(68000) では非整列アクセスで address error になる。

各 lump の filepos を 4 バイト境界へ揃えて再パックし、ディレクトリを更新する。
出力 WAD を doom_iwad[] として doom64ng.h(aligned(4)) に焼き直す。

入力 : scripts/doom64.wad  (doom64ng.h から wad_from_header.py で抽出)
出力 : scripts/doom64_aligned.wad, src/doom64ng.h
"""
import struct, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "scripts", "doom64.wad")
WOUT = os.path.join(ROOT, "scripts", "doom64_aligned.wad")
HOUT = os.path.join(ROOT, "src", "doom64ng.h")
ALIGN = 4

def main():
    b = open(SRC, "rb").read()
    ident    = b[0:4]
    numlumps = struct.unpack_from('>h', b, 4)[0]
    infoofs  = struct.unpack_from('>i', b, 8)[0]

    lumps = []
    for i in range(numlumps):
        e = infoofs + i*16
        fp   = struct.unpack_from('>i', b, e)[0]
        sz   = struct.unpack_from('>H', b, e+4)[0]
        name = b[e+8:e+16]
        data = b[fp:fp+sz] if sz else b''
        lumps.append([name, sz, data])

    # 新 WAD を構築: ヘッダ(12) -> lump データ(4整列) -> ディレクトリ
    out = bytearray()
    out += ident
    out += struct.pack('>h', numlumps)
    out += struct.pack('>h', 0)
    out += struct.pack('>i', 0)   # infotableofs は後で埋める

    positions = []
    for name, sz, data in lumps:
        while len(out) % ALIGN != 0:
            out += b'\x00'
        positions.append(len(out) if sz else 0)
        out += data

    while len(out) % ALIGN != 0:
        out += b'\x00'
    infotableofs = len(out)
    for (name, sz, data), pos in zip(lumps, positions):
        out += struct.pack('>i', pos)
        out += struct.pack('>H', sz)
        out += struct.pack('>h', 0)
        out += name
    struct.pack_into('>i', out, 8, infotableofs)

    open(WOUT, "wb").write(out)

    # 整列検証
    bad = 0
    for (name, sz, data), pos in zip(lumps, positions):
        if sz and (pos % ALIGN):
            bad += 1
    print(f"repacked: {len(out)} bytes, lumps={numlumps}, misaligned={bad}, infoofs={infotableofs}")

    # doom64ng.h を生成（aligned(4)）
    with open(HOUT, "w") as f:
        f.write("// 自動生成 (scripts/repack_wad.py) — 68000 向けに 4 バイト整列した WAD を埋め込む。\n")
        f.write("static const unsigned char __attribute__((aligned(4))) doom_iwad[%d] = {\n" % len(out))
        for i in range(0, len(out), 20):
            chunk = out[i:i+20]
            f.write("".join("0x%02x," % x for x in chunk) + "\n")
        f.write("};\n")
    print("wrote", HOUT)

if __name__ == "__main__":
    main()
