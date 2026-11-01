"""fogsum.py <log> <emitter addr>: summarise i004 fog particles from a dev menu log with 'peek <emitter> 8',
'peek <system> 4' (system = emitter +0x14) and 'peek 80210858 40000' (the particle pool)."""
import math, re, struct, sys

text = open(sys.argv[1]).read()
emitter = int(sys.argv[2], 16)
mem = {}
for block in re.split(r"(?=^peek )", text, flags=re.M):
    m = re.match(r"peek ([0-9A-Fa-f]+) \d+ -> ", block)
    if not m:
        continue
    base = int(m.group(1), 16)
    for off, val in re.findall(r"\+([0-9A-F]+) ([0-9A-F]{8})", block):
        mem[base + int(off, 16)] = int(val, 16)
f = lambda a: struct.unpack(">f", struct.pack(">I", mem[a]))[0]

FAN = (43.22, -249.2)  # FANBASE x, z; updraft centre (43, -249)
enabled = mem[emitter + 0x18] & 1
system = mem[emitter + 0x14]
parts, p = [], mem[system]  # system +0 = list head, particle +0 = next
while p and len(parts) < 2000:
    parts.append(p)
    p = mem[p]
floor = [a for a in parts if f(a + 0x14) < 10]
dist = sorted(math.hypot(f(a + 0x10) - FAN[0], f(a + 0x18) - FAN[1]) for a in floor)
where = re.search(r"^where -> (.*)$", text, re.M)
print(f"emitter {'ON' if enabled else 'off'}  fog particles {len(parts)}  on the floor (y < 10) {len(floor)}  "
      f"risen {len(parts) - len(floor)}")
if dist:
    print(f"floor distance from fan: min {dist[0]:.1f} median {dist[len(dist) // 2]:.1f} max {dist[-1]:.1f}; "
          f"> 20 units: {sum(d > 20 for d in dist)}")
if where:
    print("scooby", where.group(1))
