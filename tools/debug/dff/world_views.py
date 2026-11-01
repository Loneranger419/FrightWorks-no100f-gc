"""Orthographic world-space views (X-Y and Z-Y) of selected draws' triangles.

Draws whose position matrix is the camera view matrix carry world-space vertices, so this shows true shape.
usage: world_views.py <draws.pkl|-> <out.png> <draw ids> [title]
"""
import pickle
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dff_decode import Draw  # noqa: F401
from render_dff import tris, PALETTE  # noqa: E402  (module guards below)


def load(path):
    return pickle.load(open(path, "rb"))


def draw_views(draws, ids, out, title="", bounds=None):
    pts = [draws[i].verts[idx] for i in ids for idx in draws[i].pos_idx]
    xs, ys, zs = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
    if bounds is None:
        bounds = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    x0, x1, y0, y1, z0, z1 = bounds
    S = 700
    span = max(x1 - x0, z1 - z0, y1 - y0) or 1
    sc = (S - 40) / span
    img = Image.new("RGB", (2 * S, S + 30), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    for panel, (a0, axis) in enumerate(((x0, 0), (z0, 2))):
        ox = panel * S + 20
        for k, i in enumerate(ids):
            d = draws[i]
            col = PALETTE[k % len(PALETTE)]
            for a, b, c in tris(d):
                tri = [d.verts[d.pos_idx[v]] for v in (a, b, c)]
                poly = [(ox + (p[axis] - a0) * sc, S - 20 - (p[1] - y0) * sc) for p in tri]
                dr.polygon(poly, outline=col)
        # floor reference y=0 and y grid every 2 units
        for gy in range(int(y0) - 1, int(y1) + 2):
            if gy % 2 == 0:
                yy = S - 20 - (gy - y0) * sc
                dr.line([(ox, yy), (ox + S - 40, yy)], fill=(40, 40, 40))
                dr.text((ox - 18, yy - 6), str(gy), fill=(160, 160, 160))
    dr.text((10, S + 8), f"{title}  left: X-Y   right: Z-Y   y-range {y0:.2f}..{y1:.2f}", fill=(255, 255, 255))
    img.save(out)


if __name__ == "__main__":
    draws = load(sys.argv[1])
    ids = [int(x) for x in sys.argv[3].split(",")]
    draw_views(draws, ids, sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else "")
