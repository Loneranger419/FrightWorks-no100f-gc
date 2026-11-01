"""creeper-frames.py [--hip H] [--pack P] [--out O]: HD Creeper window frames (h001, anim_crprwndw01..18) in the ScoobyHD
pack's style -> O/tex1_64x64_<key>_14.png (384x384 RGB, 6x like ScoobyHD) + O/sheet.png. Needs numpy, Pillow and SciPy.

Defaults: H = Disc/DATA/files/H0/h001.HIP (originals are decoded from it), P = texture_pack/ScoobyHD (needs its
owih0001 window), O = autotest/texhunt/creeper-hd/out. The frames posted in upstream issue #24 (CreeperHD.zip) came from
this method (first written in the separate HD-4X repo, 2026-10-31).

The empty frame (01) is the static window owih0001 with other colours: same art, bars at the same place. So the base
is ScoobyHD's owih0001, in its own colours (TINT 0) or pulled toward frame 01's paler ones at low frequency. Each
frame = that base darkened by its silhouette: the originals darken evenly in R, G and B (frame / frame 01 about
0.78), so the shade is a mask (smoothed, cubic-magnified, clean edge with a SOFT px ramp) times the frame's own
darkness. Every frame shares the identical base, so the window doesn't shimmer during the animation.
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gxtex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")  # repo root
Z = 6          # ScoobyHD's scale
SIG = 1.0      # texels: smoothing of the colour offset between ScoobyHD's window and frame 01
TINT = 0.0     # share of that offset applied: 1 = frame 01's (paler) colours, 0 = ScoobyHD's owih0001 colours.
               # 1 first; human: "lets make the window color match ScoobyHD more" (2026-10-31) -> 0
SHADE = 0.92   # a texel is in the silhouette below this luminance ratio to frame 01
SMOOTH = 0.6   # texels: smoothing of the silhouette mask before its edge is drawn (rounds texel steps)
SOFT = 1.5     # HD px: edge ramp of the silhouette

def mag(a, order=3):
    """Z x magnification of a 64px grid at HD pixel centres, wrapping."""
    h, w = a.shape
    c = (np.arange(h * Z) + 0.5) / Z - 0.5
    yy, xx = np.meshgrid(c, (np.arange(w * Z) + 0.5) / Z - 0.5, indexing="ij")
    return ndimage.map_coordinates(a.astype(np.float64), [yy, xx], order=order, mode="grid-wrap")

def originals(hip):
    """{asset name: (key, RGB float array)} for the Creeper frames and the static window owih0001."""
    data = open(hip, "rb").read()
    out = {}
    for aid, typ, aoff, asz, name in gxtex.hip_assets(data):
        if typ != "RWTX" or not name.startswith(("anim_crprwndw", "owih0001")):
            continue
        for t in gxtex.rwtx_textures(data[aoff:aoff + asz]):
            out[name] = (gxtex.tex_key(t), gxtex.decode(t)[..., :3].astype(np.float64))
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hip", default=os.path.join(ROOT, "Disc", "DATA", "files", "H0", "h001.HIP"))
    ap.add_argument("--pack", default=os.path.join(ROOT, "texture_pack", "ScoobyHD"))
    ap.add_argument("--out", default=os.path.join(ROOT, "autotest", "texhunt", "creeper-hd", "out"))
    a = ap.parse_args()
    org = originals(a.hip)
    frames = sorted(k for k in org if k.startswith("anim_crprwndw"))
    win = next(k for k in org if k.startswith("owih0001"))
    if len(frames) != 18:
        sys.exit(f"expected 18 Creeper frames in {a.hip}, found {len(frames)}")
    f01 = org[frames[0]][1]
    shH = np.array(Image.open(os.path.join(a.pack, org[win][0] + ".png")).convert("RGB")).astype(np.float64)
    sh = np.array(Image.fromarray(shH.astype(np.uint8)).resize((64, 64), Image.BOX)).astype(np.float64)
    off = np.stack([mag(ndimage.gaussian_filter(f01[..., c] - sh[..., c], SIG, mode="wrap")) for c in range(3)], -1)
    base = np.clip(shH + TINT * off, 0, 255)
    lum = lambda x: x.mean(-1) + 1
    os.makedirs(a.out, exist_ok=True)
    done, imgs = set(), []
    for name in frames:
        k, o = org[name]
        r = np.clip(lum(o) / lum(f01), 0, 1)
        core = r < SHADE
        dark = float(np.median(r[core])) if core.sum() >= 4 else 1.0
        m = mag(ndimage.gaussian_filter(np.clip((1 - r) / max(1 - dark, 1e-3), 0, 1), SMOOTH, mode="wrap"))
        gy, gx = np.gradient(m)
        al = np.clip(0.5 + (m - 0.5) / (np.hypot(gx, gy) + 1e-6) / SOFT, 0, 1)
        img = np.clip(base * (1 - al * (1 - dark))[..., None], 0, 255).round().astype(np.uint8)
        imgs.append((name, img, dark, int(core.sum())))
        if k not in done:  # frames 01, 09 and 10 share one texture
            Image.fromarray(img, "RGB").save(os.path.join(a.out, k + ".png"))
            done.add(k)
    T = 192
    sheet = Image.new("RGB", (T * 6, (T + 14) * 3), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (name, img, dark, n) in enumerate(imgs):
        x, y = (i % 6) * T, (i // 6) * (T + 14)
        sheet.paste(Image.fromarray(img).resize((T, T), Image.LANCZOS), (x, y + 14))
        d.text((x + 3, y + 1), f"{name[-2:]}: x{dark:.2f}, {n} texels", fill=(255, 220, 80))
    sheet.save(os.path.join(a.out, "sheet.png"))
    print(f"{len(frames)} frames, {len(done)} files -> {a.out}")

if __name__ == "__main__":
    main()
