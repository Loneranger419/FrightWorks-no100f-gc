# ogexport.py [--stats] [IDs or name patterns...]: original disc textures next to their HD replacement, as PNGs to look at.
# Local only (decoded disc textures: never put them on the public site). Writes og-view\<ID>-<asset>.png per suspect:
#   original | HD | HD cut on/off at alpha 128 | cleanpack (if cleaned) over a checkerboard (top row), alpha as
#   greyscale (bottom row); the original is upscaled (nearest) to the HD size. Plus <ID>-<asset>-og.png / -hd.png.
# Why on/off matters: the game draws these with alpha compare GREATER 0 + blending + depth write, so any alpha > 0
# writes depth: a faint HD halo is invisible but hides whatever is drawn behind it later (the hub fountain).
# --stats: per suspect, how much of each texture's alpha is neither 0 nor 255 (semi-transparent).
import csv, os, pickle, re, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import gxtex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")  # repo root
HERE = os.path.join(ROOT, "autotest", "texhunt")  # git-ignored work data and output
PACK = os.path.join(ROOT, "texture_pack", "ScoobyHD")
OUT = os.path.join(HERE, "og-view")

def checker(h, w, cell=16):
    y, x = np.mgrid[0:h, 0:w]
    return np.where(((y // cell + x // cell) % 2)[..., None] == 0, 200, 120).astype(np.float32).repeat(3, -1)

def over(rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3] * a + checker(*rgba.shape[:2]) * (1 - a)).astype(np.uint8)

def semi(a):
    return float(((a > 0) & (a < 255)).mean())

def levels(a):
    v = np.unique(a)
    return " ".join(map(str, v)) if len(v) <= 10 else f"{len(v)} levels"

rows = list(csv.DictReader(open(os.path.join(HERE, "suspects.csv"), encoding="utf-8")))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
pick = [r for r in rows if not args or r["id"] in args or any(re.search(a, r["asset"], re.I) for a in args)]
disc = pickle.load(open(os.path.join(HERE, "disc.pkl"), "rb"))
os.makedirs(OUT, exist_ok=True)
for r in pick:
    key = r["texture"]
    hd_path = os.path.join(PACK, key + ".png")
    if key not in disc or not os.path.exists(hd_path):
        print(f"{r['id']} {key}: missing"); continue
    og = gxtex.decode(disc[key])
    hd = np.array(Image.open(hd_path).convert("RGBA"))
    if "--stats" in sys.argv:
        print(f"{r['id']} {r['asset']:<24} {r['status']:<10} original semi {semi(og[..., 3]):6.1%} ({levels(og[..., 3])})"
              f"  HD semi {semi(hd[..., 3]):6.1%}")
        continue
    name = f"{r['id']}-{re.sub(r'[^A-Za-z0-9_]+', '_', r['asset'])}"
    Image.fromarray(og).save(os.path.join(OUT, name + "-og.png"))
    Image.fromarray(hd).save(os.path.join(OUT, name + "-hd.png"))
    h, w = hd.shape[:2]
    big = np.array(Image.fromarray(og).resize((w, h), Image.NEAREST))
    onoff = hd.copy()
    onoff[..., 3] = np.where(hd[..., 3] >= 128, 255, 0)
    cols = [big, hd, onoff]
    clean_path = os.path.join(HERE, "cleanpack", key + ".png")
    if os.path.exists(clean_path) and not os.path.samefile(clean_path, hd_path):  # cleanpack: hardlink = not cleaned
        cols.append(np.array(Image.open(clean_path).convert("RGBA")))
    gap = 8
    sheet = np.full((2 * h + gap, len(cols) * (w + gap) - gap, 3), 40, np.uint8)
    for c, img in enumerate(cols):
        x = c * (w + gap)
        sheet[:h, x:x + w] = over(img)
        sheet[h + gap:, x:x + w] = img[..., 3:4].repeat(3, -1)
    scale = max(1, 512 // w)  # small textures: blow up so they're easy to see
    Image.fromarray(sheet).resize((sheet.shape[1] * scale, sheet.shape[0] * scale), Image.NEAREST).save(
        os.path.join(OUT, name + ".png"))
    print(f"{name}.png  original {og.shape[1]}x{og.shape[0]} alpha {levels(og[..., 3])}; HD {w}x{h} semi {semi(hd[..., 3]):.1%}")
