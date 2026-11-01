"""onoff.py [--dry]: HD pack with cut-out textures made on/off (alpha >= 128 -> 255, else 0) -> autotest/texhunt/onoffpack/.

Why: the game draws them with alpha compare GREATER 0 + blending + depth write (dev menu Find log, 2026-10-25), so any
alpha > 0 writes depth. The HD pack's faint halos (alpha 1-15) and not-quite-solid bodies (alpha 240-250) are invisible
or see-through but still hide whatever is drawn behind them later (hub fountain behind the leaves and grass).

Cut-out = the original has fully clear and fully solid pixels and less than SOFT of it is semi-transparent (real soft
effects such as glows, smoke and shadows are left alone: their originals are soft on purpose; see SOFT_NAMES for the
rest that is left alone). The whole pack is checked, not only the suspects. An HD file without alpha where the original has some (T001) gets the original's alpha, bilinear-upscaled,
before the cut. Textures not cut here but fixed by clean.py (T005/T006 webs) use the cleanpack file. Everything else is
a hardlink to the real pack (never written). Log: onoff.txt. Play it: hunt.ps1 -Pack onoffpack.
"""
import csv, os, pickle, re, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import gxtex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")  # repo root
HERE = os.path.join(ROOT, "autotest", "texhunt")  # git-ignored work data and output
PACK = os.path.join(ROOT, "texture_pack", "ScoobyHD")
OUT = os.path.join(HERE, "onoffpack")
SOFT = 0.35
CUT = 128

# Left alone until their draw state is checked (Find logs it): lights/glows/flames/shadows are soft on purpose even when
# their originals happen to be mostly 0/255, and menu (mn*) / boot textures are UI and effect sprites that may not write
# depth at all (cutting them would only make their edges jagged).
SOFT_NAMES = re.compile(r"light|glow|beam|flame|shadow|moon|spray|splash|sparkle|spec\d", re.I)
# Soft by the rules above but checked in game: the soft strand edges still hid the pot behind the T006 web. Cut the
# cleanpack file (T005 keeps its colour bleed) at a lower line so strands stay as thick as the approved T005 ramp 60->110.
FORCE_CUT = {"T005": 85, "T006": 85}

disc = pickle.load(open(os.path.join(HERE, "disc.pkl"), "rb"))
ids = {}
for r in csv.DictReader(open(os.path.join(HERE, "suspects.csv"), encoding="utf-8")):
    ids.setdefault(r["texture"], []).append(r["id"])

made, soft, log = {}, [], []
for f in sorted(os.listdir(PACK)):
    key = f[:-4]
    if not f.endswith(".png") or key not in disc: continue
    oa = gxtex.decode(disc[key])[..., 3]
    if not (oa == 0).any(): continue  # no cut-out in the original
    semi = float(((oa > 0) & (oa < 255)).mean())
    tag = ",".join(ids.get(key, [])) or "-"
    asset = disc[key].get("asset", "")
    force = [FORCE_CUT[i] for i in ids.get(key, []) if i in FORCE_CUT]
    if force:
        hd = np.array(Image.open(os.path.join(HERE, "cleanpack", f)).convert("RGBA"))
        hd[..., 3] = np.where(hd[..., 3] >= force[0], 255, 0)
        made[f] = hd
        log.append(f"{tag}\t{key}\t{asset}\tcleanpack file cut at {force[0]}"); continue
    why = f"original semi {semi:.0%}" if semi >= SOFT else \
          "original has no solid pixel" if not (oa == 255).any() else \
          "name: light/glow/flame/shadow..." if SOFT_NAMES.search(asset) else \
          "menu/boot only" if all(h == "boot" or h.startswith("mn") for h in disc[key]["hips"]) else ""
    if why:
        soft.append(f"{tag}\t{key}\t{asset}\t{why}"); continue
    hd = np.array(Image.open(os.path.join(PACK, f)).convert("RGBA"))
    a = hd[..., 3]
    note = ""
    if (a == 255).all():
        a[:] = np.array(Image.fromarray(oa).resize(a.shape[::-1], Image.BILINEAR)); note = " (alpha from the original)"
    new = np.where(a >= CUT, 255, 0).astype(np.uint8)
    n = int((new != hd[..., 3]).sum()) if not note else a.size
    if n == 0: continue  # already on/off
    hd[..., 3] = new
    made[f] = hd
    log.append(f"{tag}\t{key}\t{disc[key].get('asset', '')}\t{n} px ({n / a.size:.0%}){note}")

print(f"{len(made)} cut-out textures made on/off ({sum(1 for l in log if not l.startswith('-'))} of them suspects); "
      f"{len(soft)} soft textures left alone")
with open(os.path.join(HERE, "onoff.txt"), "w", encoding="utf-8") as fh:
    fh.write("# made on/off: ids, file, asset, pixels changed\n" + "\n".join(log) +
             "\n# soft, left alone (check their draw state with Find before touching them)\n" + "\n".join(soft) + "\n")
if "--dry" in sys.argv: sys.exit()
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
CLEAN = os.path.join(HERE, "cleanpack")
kept = []
for f in os.listdir(PACK):
    src, clean = os.path.join(PACK, f), os.path.join(CLEAN, f)
    if f in made:
        Image.fromarray(made[f], "RGBA").save(os.path.join(OUT, f))
    elif os.path.exists(clean) and not os.path.samefile(clean, src):  # not cut here, but clean.py fixed it (T005 web)
        os.link(clean, os.path.join(OUT, f)); kept.append(f[:-4])
    else:
        os.link(src, os.path.join(OUT, f))
with open(os.path.join(HERE, "onoff.txt"), "a", encoding="utf-8") as fh:
    fh.write("# not cut, cleanpack version used\n" + "\n".join(kept) + "\n")
print(f"{len(os.listdir(OUT))} files in {OUT}; cleanpack version for {len(kept)} not cut here")
