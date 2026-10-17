"""Tiny PowerPC disassembler for quick looks at the stripped NO100F main.dol (common integer/float ops only).

Usage: dis.py <main.dol> <MAP.txt> <start hex> [count]      (count instructions, default until the first blr)
"""
import struct, sys

def load(dol):
    d = open(dol, 'rb').read(); w = {}
    for k in range(18):
        off, addr, size = (struct.unpack('>I', d[b + k * 4:b + k * 4 + 4])[0] for b in (0, 0x48, 0x90))
        for i in range(0, size - 3, 4): w[addr + i] = struct.unpack('>I', d[off + i:off + i + 4])[0]
    return w

D_FORM = {32: 'lwz', 33: 'lwzu', 34: 'lbz', 35: 'lbzu', 36: 'stw', 37: 'stwu', 38: 'stb', 39: 'stbu', 40: 'lhz',
          41: 'lhzu', 42: 'lha', 44: 'sth', 45: 'sthu', 46: 'lmw', 47: 'stmw', 48: 'lfs', 49: 'lfsu', 50: 'lfd',
          52: 'stfs', 53: 'stfsu', 54: 'stfd'}
IMM = {14: 'addi', 15: 'addis', 12: 'addic', 13: 'addic.', 7: 'mulli', 24: 'ori', 25: 'oris', 26: 'xori', 28: 'andi.',
       11: 'cmpwi', 10: 'cmplwi'}

def dis(x, a, names):
    op = x >> 26; rd = (x >> 21) & 31; ra = (x >> 16) & 31; rb = (x >> 11) & 31
    imm = x & 0xFFFF; simm = (imm ^ 0x8000) - 0x8000
    if op in D_FORM:
        fp = op >= 48
        return '%s %s%d,%d(r%d)' % (D_FORM[op], 'f' if fp else 'r', rd, simm, ra)
    if op in IMM:
        if op in (11, 10): return '%s cr%d,r%d,%d' % (IMM[op], rd >> 2, ra, simm if op == 11 else imm)
        if op == 14 and ra == 0: return 'li r%d,%d' % (rd, simm)
        if op == 15 and ra == 0: return 'lis r%d,0x%X' % (rd, imm)
        return '%s r%d,r%d,%s' % (IMM[op], rd if op < 24 else ra, ra if op < 24 else rd, simm if op < 24 else hex(imm))
    if op == 18:
        disp = x & 0x03FFFFFC
        if disp & 0x02000000: disp -= 0x04000000
        t = (a + disp) & 0xFFFFFFFF
        return '%s %08X %s' % ('bl' if x & 1 else 'b', t, names.get(t, ''))
    if op == 16:
        bd = x & 0xFFFC
        if bd & 0x8000: bd -= 0x10000
        return 'bc%s %d,%d,%08X' % ('l' if x & 1 else '', rd, ra, (a + bd) & 0xFFFFFFFF)
    if op == 19:
        xo = (x >> 1) & 0x3FF
        return {16: 'bclr' + ('l' if x & 1 else ''), 528: 'bcctr' + ('l' if x & 1 else '')}.get(xo, 'op19/%d' % xo)
    if op in (20, 21, 23):
        sh, mb, me = rb, (x >> 6) & 31, (x >> 1) & 31
        return '%s r%d,r%d,%d,%d,%d' % ({20: 'rlwimi', 21: 'rlwinm', 23: 'rlwnm'}[op], ra, rd, sh, mb, me)
    if op == 31:
        xo = (x >> 1) & 0x3FF
        names31 = {444: 'or', 266: 'add', 40: 'subf', 235: 'mullw', 28: 'and', 0: 'cmpw', 32: 'cmplw', 339: 'mfspr',
                   467: 'mtspr', 23: 'lwzx', 151: 'stwx', 87: 'lbzx', 215: 'stbx', 279: 'lhzx', 407: 'sthx', 24: 'slw',
                   536: 'srw', 824: 'srawi', 792: 'sraw', 954: 'extsb', 922: 'extsh', 104: 'neg', 459: 'divwu', 491: 'divw'}
        if xo == 444 and rd == rb: return 'mr r%d,r%d' % (ra, rd)
        if xo in (339, 467): return '%s r%d,spr%d' % (names31[xo], rd, ((x >> 16) & 31) | (((x >> 11) & 31) << 5))
        return '%s r%d,r%d,r%d' % (names31.get(xo, 'op31/%d' % xo), rd, ra, rb)
    return '.long 0x%08X' % x

def main():
    dol, mp, start = sys.argv[1:4]
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    w = load(dol)
    names = {}
    for line in open(mp):
        p = line.split()
        if len(p) >= 2: names[int(p[0], 16)] = p[1]
    a = int(start, 16); n = 0
    while a in w:
        tag = ('  <%s>' % names[a]) if a in names else ''
        print('%08X  %08X  %s%s' % (a, w[a], dis(w[a], a, names), tag))
        n += 1
        if (count and n >= count) or (not count and w[a] == 0x4E800020): break
        a += 4

if __name__ == '__main__':
    main()
