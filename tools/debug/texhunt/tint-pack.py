"""tint-pack.py --out DIR (--from DIR | --hip H.HIP) [--match S ...] [--color R,G,B]: tinted copies of textures, to see
where in the game a texture is drawn (link DIR with look.ps1 -Extra DIR, then look for the colour).

--from DIR   tint the replacement PNGs in DIR (an HD pack, or frames you made) whose file name contains a --match
--hip H.HIP  tint the originals decoded from one HIP; --match is tested on the asset/texture name and on the key
The copy keeps the texture's shading (luminance) and alpha and paints it in --color (default red). Example that found
the dormer roof and sill sampling the Creeper frames: tint-pack.py --hip Disc/DATA/files/H0/h001.HIP --match crprwndw
--out autotest/texhunt/tint-creeper.
"""
import argparse, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gxtex

def tint(rgba, color):
    a = np.asarray(rgba, np.float64)
    lum = a[..., :3] @ [0.299, 0.587, 0.114] / 255.0
    out = np.empty_like(a)
    out[..., :3] = (0.35 + 0.65 * lum)[..., None] * np.asarray(color, np.float64)
    out[..., 3] = a[..., 3]
    return Image.fromarray(np.clip(out, 0, 255).round().astype(np.uint8), "RGBA")

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from", dest="src")
    src.add_argument("--hip")
    ap.add_argument("--match", nargs="*", default=[])
    ap.add_argument("--color", default="255,0,0")
    a = ap.parse_args()
    color = [int(c) for c in a.color.split(",")]
    hit = lambda *names: not a.match or any(m.lower() in n.lower() for m in a.match for n in names)
    os.makedirs(a.out, exist_ok=True)
    n = 0
    if a.src:
        for f in sorted(os.listdir(a.src)):
            if f.lower().endswith(".png") and f.startswith("tex1_") and hit(f):
                tint(Image.open(os.path.join(a.src, f)).convert("RGBA"), color).save(os.path.join(a.out, f))
                n += 1
    else:
        data = open(a.hip, "rb").read()
        done = set()
        for aid, typ, aoff, asz, name in gxtex.hip_assets(data):
            if typ != "RWTX":
                continue
            for t in gxtex.rwtx_textures(data[aoff:aoff + asz]):
                k = gxtex.tex_key(t)
                if k in done or not hit(name, t["name"], k):
                    continue
                tint(gxtex.decode(t), color).save(os.path.join(a.out, k + ".png"))
                done.add(k)
                print(f"{k}  {name}")
                n += 1
    print(f"{n} tinted -> {a.out}")
    if not n:
        sys.exit(1)

if __name__ == "__main__":
    main()
