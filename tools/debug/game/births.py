"""births.py [dir]: compare births/s per emitter asset at fps60 off vs on (births-run.ps1 output).

Path 1 (p1) = emitted by the per-frame emitter update 0x800C4AAC (fixed); others come through 0x800C5C0C (entity code).
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
    r = {}
    for line in open(f):
        m = re.match(r"owner \S+ id (\S+) births \d+ \(([\d.]+)/s\)( p1)?", line)
        if m:
            k = int(m.group(1), 16)
            rate, p1 = r.get(k, (0.0, False))
            r[k] = (rate + float(m.group(2)), p1 or bool(m.group(3)))
    return r
for lvl in sorted({os.path.basename(f).split("-")[0] for f in glob.glob(os.path.join(d, "*.txt"))}):
    a, b = os.path.join(d, f"{lvl}-fps60false.txt"), os.path.join(d, f"{lvl}-fps60true.txt")
    if not (os.path.exists(a) and os.path.exists(b)):
        continue
    ra, rb = load(a), load(b)
    print(f"== {lvl}")
    for k in sorted(set(ra) | set(rb), key=lambda k: -max(ra.get(k, (0,))[0], rb.get(k, (0,))[0])):
        x, y = ra.get(k, (0.0, False)), rb.get(k, (0.0, False))
        ratio = f"{y[0] / x[0]:.2f}x" if x[0] else "new"
        print(f"  {names.get(k, f'{k:08X}'):28s} {'p1' if x[1] or y[1] else '  '} 30fps {x[0]:7.1f}/s  60fps {y[0]:7.1f}/s  {ratio}")
