#!/usr/bin/env python3
"""アトラクト（自動プレイ）の録画尺を算出する。

Doom64KB のアトラクト順序:
  タイトル画面 (TITLE_DEMO_SECONDS 秒) -> DEMO3(E1M1) 再生 -> ループ

DEMO3 の長さは WAD のデモデータ（1 tic = 4 バイト、終端 0x80=DEMOMARKER）から求める。
TICRATE=35。タイトル秒数はビルド時 -DTITLE_DEMO_SECONDS で決まるので引数で渡す。

使い方:
  python3 scripts/demo_duration.py [TITLE_SECONDS]      # 人間向けサマリ
  python3 scripts/demo_duration.py [TITLE_SECONDS] --total-seconds   # 合計秒だけ出力
  python3 scripts/demo_duration.py --demo-seconds       # DEMO3 の秒だけ出力
"""
import struct, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAD  = os.path.join(ROOT, "scripts", "doom64_aligned.wad")
if not os.path.exists(WAD):
    WAD = os.path.join(ROOT, "scripts", "doom64.wad")

TICRATE   = 35
DEMO_HDR  = 13      # G_ReadDemoHeader が読むヘッダ長（version1 + 8 + maxplayers 4）
DEMOMARK  = 0x80

def demo_tics(name="DEMO3"):
    b = open(WAD, "rb").read()
    n = struct.unpack_from('>h', b, 4)[0]
    o = struct.unpack_from('>i', b, 8)[0]
    for i in range(n):
        e = o + i*16
        nm = b[e+8:e+16].split(b'\x00')[0].decode('latin1')
        if nm == name:
            fp = struct.unpack_from('>i', b, e)[0]
            sz = struct.unpack_from('>H', b, e+4)[0]
            d  = b[fp:fp+sz]
            p, t = DEMO_HDR, 0
            while p < len(d) and d[p] != DEMOMARK:
                p += 4; t += 1
            return t
    raise SystemExit(f"{name} not found in {WAD}")

def main():
    args  = sys.argv[1:]
    title = 30
    for a in args:
        if a.isdigit():
            title = int(a)
    tics = demo_tics()
    demo = tics / TICRATE
    total = title + demo
    if "--demo-seconds" in args:
        print(f"{demo:.1f}")
    elif "--total-seconds" in args:
        print(f"{total:.1f}")
    else:
        print(f"title       : {title}s")
        print(f"demo (DEMO3): {tics} tics = {demo:.1f}s")
        print(f"total       : {total:.1f}s")

if __name__ == "__main__":
    main()
