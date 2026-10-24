import math
import pickle
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dff_decode import Draw  # noqa: F401

draws = pickle.load(open(sys.argv[1], "rb"))
frame = int(sys.argv[2]) if len(sys.argv) > 2 else 0
lo = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0xB80000
hi = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0xC00000

print(Counter(hex(d.pos_base) for d in draws if d.frame == frame).most_common(12))


def xf(m, v):
    x, y, z = v
    return (
        m[0] * x + m[1] * y + m[2] * z + m[3],
        m[4] * x + m[5] * y + m[6] * z + m[7],
        m[8] * x + m[9] * y + m[10] * z + m[11],
    )


for i, d in enumerate(draws):
    if d.frame != frame or not (lo <= d.pos_base < hi):
        continue
    vs = list(d.verts.values())
    ys = [v[1] for v in vs]
    w = [xf(d.mtx, v) for v in vs]
    sc = [math.sqrt(d.mtx[c] ** 2 + d.mtx[4 + c] ** 2 + d.mtx[8 + c] ** 2) for c in range(3)]
    print(
        f"#{i} off={d.off} prim=0x{d.prim:02X} vat={d.vat} n={d.n} vsz={d.vsz} base=0x{d.pos_base:X} "
        f"stride={d.pos_stride} fmt={d.pos_fmt} pn={'direct' if d.pnmtx_direct else d.cur_mtx} "
        f"idx={min(d.pos_idx)}..{max(d.pos_idx)} uniq={len(d.verts)} modelY={min(ys):.2f}..{max(ys):.2f} "
        f"scale=({sc[0]:.3f},{sc[1]:.3f},{sc[2]:.3f}) viewZ={min(p[2] for p in w):.1f}..{max(p[2] for p in w):.1f}"
    )
