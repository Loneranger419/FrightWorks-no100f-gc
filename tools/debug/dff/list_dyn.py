"""List draws whose POS array is rewritten every frame (memory updates in frames >= 1)."""
import math
import pickle
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dff_decode import Draw  # noqa: F401

dff = open(sys.argv[2], "rb").read()
frame = int(sys.argv[3]) if len(sys.argv) > 3 else 1
frames_off, frame_count, _ = struct.unpack_from("<QII", dff, 60)
o = frames_off + frame * 64
mem_off, mem_n = struct.unpack_from("<QI", dff, o + 20)
dyn = set()
for i in range(mem_n):
    _fp, addr, _do, _ds, typ = struct.unpack_from("<IIQIB", dff, mem_off + i * 24)
    if typ == 4:
        dyn.add(addr & 0x01FFFFFF)

D = pickle.load(open(sys.argv[1], "rb"))
for i, d in enumerate(D):
    if d.frame != frame or d.pos_base not in dyn:
        continue
    vs = list(d.verts.values())
    xs, ys, zs = [v[0] for v in vs], [v[1] for v in vs], [v[2] for v in vs]
    sc = [math.sqrt(d.mtx[c] ** 2 + d.mtx[4 + c] ** 2 + d.mtx[8 + c] ** 2) for c in range(3)]
    pn = "direct" if d.pnmtx_direct else str(d.cur_mtx)
    print(
        f"#{i} prim=0x{d.prim:02X} n={d.n} base=0x{d.pos_base:X} pn={pn} idx={min(d.pos_idx)}..{max(d.pos_idx)} "
        f"X={min(xs):.2f}..{max(xs):.2f} Y={min(ys):.2f}..{max(ys):.2f} Z={min(zs):.2f}..{max(zs):.2f} "
        f"sc={sc[0]:.2f},{sc[1]:.2f},{sc[2]:.2f} vp={d.viewport[0]:.0f}"
    )
