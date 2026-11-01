"""Cleaned copy of the HD pack for leak suspects: alpha -> 0 inside the original's fully clear area (eroded by one original
pixel), and alpha < 16 -> 0 in the one-pixel band around it (keeps real soft edges). Everything else is a hardlink to the
real pack (never written). Output: autotest/texhunt/cleanpack/ + cleaned.txt (id, file, pixels changed)."""
import csv, os, pickle, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import gxtex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")  # repo root
DATA = os.path.join(ROOT, "autotest", "texhunt")  # git-ignored work data and output
PACK = os.path.join(ROOT, "texture_pack", "ScoobyHD")
OUT = os.path.join(DATA, "cleanpack")
allt = pickle.load(open(os.path.join(DATA, "disc.pkl"), "rb"))

def erode(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out &= np.roll(np.roll(m, dy, 0), dx, 1)
    return out

# Per-suspect extras, added after the human checked v1 in game:
# ORIG_ALPHA: the HD file has no alpha at all, so take the original's alpha, bilinear-upscaled (T001: boards it must hide).
# BLEED: Topaz darkened the colour of faint edge pixels, which draws a dark rim; give them the colour of the nearest
# solid pixel (T005 web). Alpha (the shape) is unchanged.
# RAMP (lo, hi): alpha <= lo -> 0, >= hi -> 255, linear between. The game seems to write depth for any alpha > 0, so a
# faint skirt round each strand hides what is drawn behind it later and shows as a dark rim (T005 web). Making the skirt
# solid keeps the strands thick; cutting it (v3, alpha < 96 -> 0) made them too thin.
ORIG_ALPHA = {"T001"}
BLEED = {"T005"}
RAMP = {"T005": (60, 110)}  # v4 (24, 80) was too thick; (60, 110) = strand width of the T006 web

def bleed(hd, solid=128):
    rgb = hd[..., :3].astype(float); ok = hd[..., 3] >= solid
    for _ in range(64):
        if ok.all(): break
        s = np.zeros_like(rgb); n = np.zeros(ok.shape)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            m = np.roll(np.roll(ok, dy, 0), dx, 1)
            s += np.roll(np.roll(rgb, dy, 0), dx, 1) * m[..., None]; n += m
        grow = ~ok & (n > 0)
        rgb[grow] = s[grow] / n[grow, None]; ok = ok | grow
    changed = int((np.abs(rgb.round() - hd[..., :3]).max(2) > 0).sum())
    hd[..., :3] = rgb.round().astype(np.uint8)
    return changed

def clean(id_, key):
    o = gxtex.decode(allt[key]); hd = np.array(Image.open(f"{PACK}/{key}.png").convert("RGBA"))
    k = hd.shape[0] // o.shape[0]
    a = hd[..., 3]
    if id_ in ORIG_ALPHA:
        up = np.array(Image.fromarray(o[..., 3]).resize(a.shape[::-1], Image.BILINEAR))
        n = int((a != up).sum()); a[:] = up
    else:
        clear = o[..., 3] == 0
        inner = np.kron(erode(clear, 1), np.ones((k, k), bool))
        band = np.kron(clear, np.ones((k, k), bool)) & ~inner
        change = (inner & (a > 0)) | (band & (a > 0) & (a < 16))
        a[change] = 0; n = int(change.sum())
    if id_ in BLEED: n += bleed(hd)
    if id_ in RAMP:
        lo, hi = RAMP[id_]
        new = (np.clip((a.astype(float) - lo) / (hi - lo), 0, 1) * 255).round().astype(np.uint8)
        n += int((new != a).sum()); a[:] = new
    return hd, n

rows = list(csv.DictReader(open(os.path.join(DATA, "suspects.csv"))))
leak = [r for r in rows if "alpha (" in r["findings"] and "clear area" in r["findings"]]
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
done = {}
with open(os.path.join(DATA, "cleaned.txt"), "w") as log:
    for r in leak:
        hd, n = clean(r["id"], r["texture"])
        Image.fromarray(hd, "RGBA").save(f"{OUT}/{r['texture']}.png")
        done[r["texture"]] = n
        log.write(f"{r['id']}\t{r['texture']}\t{n}\n")
for f in os.listdir(PACK):
    if f[:-4] not in done: os.link(f"{PACK}/{f}", f"{OUT}/{f}")
print(f"cleaned {len(done)} files ({', '.join(r['id'] for r in leak)}); {len(os.listdir(OUT))} files in {OUT}")
