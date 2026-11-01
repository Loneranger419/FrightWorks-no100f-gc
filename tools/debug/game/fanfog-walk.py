"""fanfog-walk.py <pool peek log> <list head hex>: walk a particle list from a dev menu peek of the pool."""
import re, struct, sys, collections
BASE = 0x80210858
t = open(sys.argv[1]).read()
w = {BASE + int(a, 16): int(b, 16) for a, b in re.findall(r"\+([0-9A-F]+) ([0-9A-F]{8})", t)}
f = lambda a: struct.unpack(">f", struct.pack(">I", w[a]))[0]
p, n, rows = int(sys.argv[2], 16), 0, []
while p and n < 2000:
    rows.append((p, f(p + 8), w[p + 0xC], f(p + 0x10), f(p + 0x14), f(p + 0x18), f(p + 0x1C), f(p + 0x20), f(p + 0x24), f(p + 0x28), w[p + 0x3C]))
    p = w[p]; n += 1
print("count", n)
alpha = collections.Counter(r[2] & 0xFF for r in rows)
print("alpha histogram", sorted(alpha.items())[:20])
print("life min/max %.3f %.3f" % (min(r[1] for r in rows), max(r[1] for r in rows)))
print("owners", collections.Counter(f"{r[10]:08X}" for r in rows))
for r in sorted(rows, key=lambda r: -(r[2] & 0xFF))[:12]:
    print(f"{r[0]:08X} life {r[1]:7.3f} col {r[2]:08X} pos {r[3]:8.2f} {r[4]:7.2f} {r[5]:8.2f} size {r[6]:6.2f} vel {r[7]:6.3f} {r[8]:6.3f} {r[9]:6.3f}")
