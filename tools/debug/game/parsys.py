"""parsys.py <postool dump>: particles per registered system (registry 0x80237958, pool 2000 x 0x50 at 0x80210858)."""
import sys, numpy as np
d = open(sys.argv[1], 'rb').read()
f = np.frombuffer(d, '>f4'); u = np.frombuffer(d, '>u4'); A = lambda a: (a - 0x80000000) // 4
tot = 0
for i in range(256):
    s = int(u[A(0x80237958) + i])
    if not s: continue
    b = A(s); p = int(u[b]); n = 0; lifes = []; pos = None
    while p and n < 3000:
        lifes.append(f[A(p) + 2])
        if pos is None: pos = (f[A(p) + 4], f[A(p) + 5], f[A(p) + 6])
        p = int(u[A(p)]); n += 1
    tot += n
    if n:
        print(f'{i:3d} sys {s:08X} n{n:4d} prio {(u[b+4]>>16)&0xFF:2d} fl {(u[b+4]>>8)&0xFF:02X} life {min(lifes):.2f}..{max(lifes):.2f} pos0 {pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f}')
print('total alive', tot, 'of 2000')
