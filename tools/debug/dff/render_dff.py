"""Painter's-algorithm render of decoded indexed draws (one frame) to check which draws are curtains.

usage: render_dff.py <draws.pkl> <frame> <out.png> [highlight ids] [only ids]
"""
import math
import pickle
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dff_decode import Draw  # noqa: F401

W, H = 640, 528
PALETTE = [(255, 40, 40), (40, 255, 40), (60, 120, 255), (255, 230, 40), (255, 40, 255), (40, 255, 255),
           (255, 140, 0), (160, 80, 255), (255, 255, 255), (120, 255, 160)]


def mul(m, v):
    x, y, z = v
    return (m[0] * x + m[1] * y + m[2] * z + m[3], m[4] * x + m[5] * y + m[6] * z + m[7], m[8] * x + m[9] * y + m[10] * z + m[11])


def project(d, p):
    pr = d.proj
    x, y, z = p
    if pr[6] == 0:  # perspective
        cx = pr[0] * x + pr[1] * z
        cy = pr[2] * y + pr[3] * z
        cw = -z
    else:
        cx = pr[0] * x + pr[1]
        cy = pr[2] * y + pr[3]
        cw = 1.0
    if cw <= 1e-4:
        return None
    vp = d.viewport
    sx = cx / cw * vp[0] + vp[3] - 342
    sy = cy / cw * vp[1] + vp[4] - 342
    return sx, sy


def tris(d):
    n = d.n
    if d.prim == 0x90:
        for i in range(0, n - 2, 3):
            yield i, i + 1, i + 2
    elif d.prim == 0x98:
        for i in range(2, n):
            yield (i - 2, i - 1, i) if i % 2 == 0 else (i - 1, i - 2, i)
    elif d.prim == 0xA0:
        for i in range(2, n):
            yield 0, i - 1, i
    elif d.prim == 0x80:
        for i in range(0, n - 3, 4):
            yield i, i + 1, i + 2
            yield i, i + 2, i + 3


def render(draws, frame, out, highlight=(), only=None):
    highlight = sorted(highlight)
    img = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    polys = []
    for di, d in enumerate(draws):
        if d.frame != frame or d.proj[6] != 0 or d.viewport[0] < 200:
            continue
        if only is not None and di not in only:
            continue
        eye = []
        for v in range(d.n):
            idx = d.pos_idx[v]
            m = d.mtx_rows[d.pn_idx[v]] if d.pn_idx else d.mtx
            eye.append(mul(m, d.verts[idx]))
        for a, b, c in tris(d):
            pa, pb, pc = eye[a], eye[b], eye[c]
            sa, sb, sc = project(d, pa), project(d, pb), project(d, pc)
            if not (sa and sb and sc):
                continue
            u = [pb[k] - pa[k] for k in range(3)]
            w = [pc[k] - pa[k] for k in range(3)]
            nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            ln = math.sqrt(sum(t * t for t in nrm)) or 1
            shade = 0.35 + 0.65 * abs(nrm[2] / ln)
            depth = (pa[2] + pb[2] + pc[2]) / 3
            if di in highlight:
                base = PALETTE[highlight.index(di) % len(PALETTE)]
                col = tuple(int(c * shade) for c in base)
            else:
                col = (int(90 * shade),) * 3
            polys.append((depth, [sa, sb, sc], col))
    polys.sort(key=lambda t: t[0])
    for _, pts, col in polys:
        dr.polygon(pts, fill=col)
    img.save(out)
    return len(polys)


if __name__ == "__main__":
    draws = pickle.load(open(sys.argv[1], "rb"))
    hl = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 and sys.argv[4] else []
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 and sys.argv[5] else None
    print("tris", render(draws, int(sys.argv[2]), sys.argv[3], hl, only))
