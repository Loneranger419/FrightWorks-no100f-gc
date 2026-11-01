# skipintro.py <mods dir>: h001.HIP without the hub intro cutscene, for hunt.ps1 (local only, never commit game data).
# On scene start (event 87) INTRODISPATCHER sends INTRO (CSNM) event 190 = play the cutscene; when it ends INTRO sends
# H001D1 event 1 (starts the crickets/howl/wind ambience) and SCOOBY event 9. The rewrite points that first link straight
# at H001D1 event 1, so the cutscene never starts. Writes <mods dir>/files/H0/h001.HIP.
import os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import gxtex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")  # repo root
INTRO, DISPATCHER, AMBIENCE = 0x0BF2CB8C, 0xCC92D483, 0x0E42EC4E

data = bytearray(open(os.path.join(ROOT, "Disc", "DATA", "files", "H0", "h001.HIP"), "rb").read())
aid, typ, off, size, name = next(a for a in gxtex.hip_assets(bytes(data)) if a[0] == DISPATCHER)
links = data[off + 5]
for i in range(links):  # xBase links: 0x20 bytes each at the end (u16 srcEvent, u16 dstEvent, u32 dstAsset, ...)
    lo = off + size - 0x20 * (links - i)
    src, dst_ev, dst = struct.unpack_from(">HHI", data, lo)
    if (dst_ev, dst) == (190, INTRO):
        struct.pack_into(">HHI", data, lo, src, 1, AMBIENCE)
        break
else:
    sys.exit("INTRODISPATCHER link to INTRO not found")
out = os.path.join(sys.argv[1], "files", "H0", "h001.HIP")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "wb").write(data)
print("wrote", out)
