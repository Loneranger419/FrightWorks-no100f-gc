"""births.py [dir]: compare births/s per emitter asset at fps60 off vs on (births-run.ps1 output).

Path 1 (p1) = emitted by the per-frame emitter update 0x800C4AAC; p2 = through 0x800C5C0C (entity code), tagged by probe lines
in those overrides. speed = birth |velocity| x frames/s (MOVE adds the velocity to the position once per frame).
"""
import glob, os, re, struct, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.argv = sys.argv[:2]
src = open(os.path.join(os.path.dirname(__file__), "mkhip.py")).read().split("ap = argparse")[0]
ns = {"__file__": os.path.join(os.path.dirname(__file__), "mkhip.py")}
exec(src, ns)
names = {}
for f in glob.glob(os.path.join(ROOT, "Disc", "DATA", "files", "**", "*.HIP"), recursive=True):
    for aid, typ, off, sz, name in ns["assets"](open(f, "rb").read()):
        if typ == "PARE":
            names.setdefault(aid, name)

d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "autotest", "manual", "births")
def load(f):
    """id -> [births/s, speed/s (birth-weighted), tags]"""
    r = {}
    for line in open(f):
        m = re.match(r"owner \S+ id (\S+) births \d+ \(([\d.]+)/s\)(?: vel \S+ speed ([\d.]+)/s)?( p1)?( p2)?", line)
        if m:
            k, rate, speed = int(m.group(1), 16), float(m.group(2)), float(m.group(3) or 0)
            e = r.setdefault(k, [0.0, 0.0, set()])
            e[1] = (e[1] * e[0] + speed * rate) / (e[0] + rate) if e[0] + rate else 0.0
            e[0] += rate
            e[2] |= {t.strip() for t in (m.group(4), m.group(5)) if t}
    return r
for lvl in sorted({os.path.basename(f).split("-")[0] for f in glob.glob(os.path.join(d, "*.txt"))}):
    a, b = os.path.join(d, f"{lvl}-fps60false.txt"), os.path.join(d, f"{lvl}-fps60true.txt")
    if not (os.path.exists(a) and os.path.exists(b)):
        continue
    ra, rb = load(a), load(b)
    print(f"== {lvl}")
    for k in sorted(set(ra) | set(rb), key=lambda k: -max(ra.get(k, (0,))[0], rb.get(k, (0,))[0])):
        x, y = ra.get(k, [0.0, 0.0, set()]), rb.get(k, [0.0, 0.0, set()])
        ratio = f"{y[0] / x[0]:.2f}x" if x[0] else "new"
        sratio = f"{y[1] / x[1]:.2f}x" if x[1] else "  -  "
        tags = ",".join(sorted(x[2] | y[2]))
        print(f"  {names.get(k, f'{k:08X}'):28s} {tags:5s} 30fps {x[0]:7.1f}/s  60fps {y[0]:7.1f}/s  {ratio:>6s}"
              f"   speed {x[1]:7.3f} {y[1]:7.3f} {sratio:>6s}")
