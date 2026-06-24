#!/usr/bin/env python3
import re, sys, struct
src = sys.argv[1] if len(sys.argv)>1 else "/tmp/claude-1000/-home-akiyan-Genesis64KBDoom/d3eac2b0-c29e-48e9-a668-d1d5c6f8f697/scratchpad/Doom64KB/doom64ng.h"
data = open(src,'rb').read().decode('latin1')
# grab between first '{' and last '}'
body = data[data.index('{')+1: data.rindex('}')]
b = bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{1,2})', body))
out = sys.argv[2] if len(sys.argv)>2 else "/home/akiyan/Genesis64KBDoom/scripts/doom64.wad"
open(out,'wb').write(b)
print("wad bytes:", len(b))
ident = b[0:4]; numlumps = struct.unpack_from('<i', b, 4)[0]; infoofs = struct.unpack_from('<i', b, 8)[0]
print("ident", ident, "numlumps", numlumps, "infoofs", infoofs)
# but big-endian baked? try BE
numl_be = struct.unpack_from('>i', b, 4)[0]; info_be = struct.unpack_from('>i', b, 8)[0]
print("BE numlumps", numl_be, "infoofs", info_be)
