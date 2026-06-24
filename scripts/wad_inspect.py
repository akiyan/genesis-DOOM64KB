#!/usr/bin/env python3
import struct
b = open("scripts/doom64.wad","rb").read()
numlumps = struct.unpack_from('>h', b, 4)[0]
infoofs  = struct.unpack_from('>i', b, 8)[0]
print("numlumps",numlumps,"infoofs",infoofs,"total",len(b))
lumps=[]
for i in range(numlumps):
    o=infoofs+i*16
    filepos=struct.unpack_from('>i',b,o)[0]
    size=struct.unpack_from('>H',b,o+4)[0]
    name=b[o+8:o+16].split(b'\x00')[0].decode('latin1')
    lumps.append((name,filepos,size))
# show first 20 and find PLAYPAL
for n,fp,sz in lumps[:18]:
    print(f"  {n:10s} pos={fp:8d} size={sz}")
print("...")
for n,fp,sz in lumps:
    if n in ("PLAYPAL","COLORMAP","PALPAL"):
        print(f">>{n:10s} pos={fp:8d} size={sz}  size/256={sz/256}")
        if n=="PLAYPAL":
            pp=b[fp:fp+min(sz,32)]
            print("   first16bytes:", " ".join(f"{x:02x}" for x in pp))
