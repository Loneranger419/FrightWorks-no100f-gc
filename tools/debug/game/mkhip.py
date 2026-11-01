"""Build a modded level HIP for the zz-manual boot mod (local only, never commit game data).

mkhip.py <level> [--npc all|none|NAME,NAME] [--pos X Y Z] [--yaw R] [--spot NAME]
  --npc   move these NPC assets' start positions far outside the map (default all).
          Clearing baseFlags & 1 does not work: the NPC code ignores the enabled bit.
  --pos   move the PLYR start position; --yaw sets PLYR +0x10 (radians)
  --spot  pos + yaw from an F9 save (postool in vi.cpp) in tools/debug/game/spots.txt or Play/postool/spots.txt.
          F9 saves the model matrix (feet); the asset start sits 0.27 higher, so 0.3 is added to Y.
Writes Play/UserData/mods/zz-manual/files/<dir>/<level>.HIP from Disc/DATA/files.
"""
import argparse, os, struct, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def assets(data):
    out = []
    def walk(off, end):
        while off + 8 <= end:
            tag = data[off:off+4].decode("latin1"); size = struct.unpack(">I", data[off+4:off+8])[0]
            body = off + 8
            if tag == "HIPA":
                off = body; continue
            if tag == "AHDR":
                aid, typ, aoff, asz = struct.unpack(">I4sII", data[body:body+16])
                name = ""
                if data[body+24:body+28] == b"ADBG":
                    dsz = struct.unpack(">I", data[body+28:body+32])[0]
                    name = data[body+36:body+32+dsz].split(b"\0")[0].decode("latin1")
                out.append((aid, typ.decode("latin1"), aoff, asz, name.strip()))
            elif tag in ("PACK", "DICT", "ATOC", "LTOC", "STRM", "LHDR"):
                walk(body + (4 if tag == "LHDR" else 0), body + size)
            off = body + size
    walk(0, len(data))
    return out

ap = argparse.ArgumentParser()
ap.add_argument("level")
ap.add_argument("--npc", default="all")
ap.add_argument("--pos", nargs=3, type=float)
ap.add_argument("--yaw", type=float)
ap.add_argument("--spot")
a = ap.parse_args()
if a.spot:
    for f in (os.path.join(ROOT, "tools", "debug", "game", "spots.txt"), os.path.join(ROOT, "Play", "postool", "spots.txt")):
        if os.path.exists(f):
            for line in open(f):
                t = line.split()
                if t and t[0] == a.spot:
                    a.pos = [float(t[2]), float(t[3]) + 0.3, float(t[4])]; a.yaw = float(t[6])
            if a.pos: break
    if not a.pos: sys.exit(f"spot {a.spot} not found")

sub = a.level[0].upper() + "0"
src = os.path.join(ROOT, "Disc", "DATA", "files", sub, a.level + ".HIP")
dst = os.path.join(ROOT, "Play", "UserData", "mods", "zz-manual", "files", sub, a.level + ".HIP")
data = bytearray(open(src, "rb").read())
lst = assets(data)

want = None if a.npc == "all" else set() if a.npc == "none" else {n.upper() for n in a.npc.split(",")}
moved = 0
for aid, typ, off, sz, name in lst:
    if typ == "NPC " and (want is None or name.upper() in want):
        old = struct.unpack(">3f", data[off+0x1C:off+0x28])
        new = (2000.0 + 50 * moved, -500.0, 2000.0)
        struct.pack_into(">3f", data, off + 0x1C, *new)
        moved += 1
        print("NPC %-10s pos %.1f %.1f %.1f -> %.0f %.0f %.0f" % ((name,) + old + new))

plyr = [x for x in lst if x[1] == "PLYR"]
if (a.pos or a.yaw is not None) and len(plyr) != 1:
    sys.exit(f"expected one PLYR asset, found {len(plyr)}")
if plyr:
    off = plyr[0][2]
    if a.pos:
        struct.pack_into(">3f", data, off + 0x1C, *a.pos)
    if a.yaw is not None:
        struct.pack_into(">f", data, off + 0x10, a.yaw)
    print("PLYR yaw %.3f pos %.3f %.3f %.3f" % (struct.unpack(">f", data[off+0x10:off+0x14])
                                              + struct.unpack(">3f", data[off+0x1C:off+0x28])))

os.makedirs(os.path.dirname(dst), exist_ok=True)
open(dst, "wb").write(data)
print("wrote", dst)
