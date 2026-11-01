"""addrrefs.py LO HI: code sites that build an address in [LO,HI) with lis + addi/load/store (raw decode of game/main.dol)."""
import sys, struct, collections
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..'))
import dol
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
hits = collections.defaultdict(list)
for base, data, text in dol.SECS:
    if not text: continue
    ws = struct.unpack(f'>{len(data)//4}I', data[:len(data)//4*4])
    for i, w in enumerate(ws):
        if w >> 26 == 15 and (w >> 16) & 31 == 0:  # lis rD, imm
            rd, imm = (w >> 21) & 31, w & 0xFFFF
            for j in range(i + 1, min(i + 10, len(ws))):
                x = ws[j]; op = x >> 26; ra = (x >> 16) & 31
                if ra == rd and op in (14, 32, 34, 36, 38, 40, 44, 48, 50, 52, 54):
                    t = ((imm << 16) + struct.unpack('>h', struct.pack('>H', x & 0xFFFF))[0]) & 0xFFFFFFFF
                    if lo <= t < hi:
                        a = base + j * 4
                        hits[t].append(a)
                    break
for t in sorted(hits):
    print(f'{t:08X}', ' '.join(f'{a:08X}({dol.name(dol.func_start(a)) or "?"})' for a in hits[t][:6]))
