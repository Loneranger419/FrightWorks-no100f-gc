"""Name the GameCube SDK functions in a stripped main.dol with Dolphin's signature database (totaldb.dsy).

Dolphin's HashSignatureDB checksum: per instruction, keep the opcode and its non-address fields (register fields for
D-form, extended opcode for X-form ...), rotate-left-17 and xor. A DB entry matches when a function starting at a
candidate address has that checksum over exactly `size` bytes. Candidates: bl targets and code after a blr.
totaldb.dsy layout: LE u32 count, then count x {u32 checksum, u32 size, char name[128]}.

Usage: sigmatch.py <main.dol> <totaldb.dsy> <out MAP.txt>    (MAP lines: "XXXXXXXX name")
"""
import collections, struct, sys

def dol_text(d):
    secs = []
    for k in range(7):
        off, addr, size = (struct.unpack('>I', d[b + k * 4:b + k * 4 + 4])[0] for b in (0, 0x48, 0x90))
        if size: secs.append((addr, d[off:off + size]))
    return secs

def op_key(w):
    op = w & 0xFC000000; aux = op >> 26; op2 = op3 = 0
    if aux == 4:
        op2 = w & 0x3F
        if op2 in (0, 8, 16, 21, 22): op3 = w & 0x7C0
    elif aux in (7, 8, 10, 11, 12, 13, 14, 15):
        op2 = w & 0x03FF0000
    elif aux in (19, 31, 63):
        op2 = w & 0x7FF
    elif aux == 59:
        op2 = w & 0x3F
        if op2 < 16: op3 = w & 0x7C0
    elif 32 <= aux < 56:
        op2 = w & 0x03FF0000
    return op | op2 | op3

def main():
    dol, dsy, out = sys.argv[1:4]
    d = open(dol, 'rb').read()
    db = open(dsy, 'rb').read()
    count = struct.unpack('<I', db[:4])[0]
    sigs = collections.defaultdict(list)
    for k in range(count):
        e = 4 + k * 136
        csum, size = struct.unpack('<II', db[e:e + 8])
        name = db[e + 8:e + 136].split(b'\0')[0].decode('latin1').split('\t')[0].strip()
        if size >= 12 and name: sigs[(csum, size)].append(name)
    words = {}
    for addr, data in dol_text(d):
        for i in range(0, len(data) - 3, 4): words[addr + i] = struct.unpack('>I', data[i:i + 4])[0]
    starts = set()
    for a, w in words.items():
        if w & 0xFC000003 == 0x48000001:  # bl
            disp = w & 0x03FFFFFC
            if disp & 0x02000000: disp -= 0x04000000
            t = (a + disp) & 0xFFFFFFFF
            if t in words: starts.add(t)
        if w == 0x4E800020 and a + 4 in words: starts.add(a + 4)
    maxsize = max(s for (_, s) in sigs)
    found = {}
    for s in sorted(starts):
        csum, a = 0, s
        while a in words and a - s < maxsize:
            csum = ((csum << 17) & 0xFFFE0000 | (csum >> 15) & 0x1FFFF) ^ op_key(words[a])
            a += 4
            names = sigs.get((csum, a - s))
            w = words[a - 4]
            if names and (w in (0x4E800020, 0x4C000064) or w & 0xFC000003 == 0x48000000):
                found[s] = (a - s, names)
            if w == 0x4E800020 and s in found: break
    lines = []
    for s in sorted(found):
        uniq = sorted(set(found[s][1]))
        lines.append('%08X %s' % (s, uniq[0] if len(uniq) == 1 else uniq[0] + '  ; also ' + ', '.join(uniq[1:4])))
    open(out, 'w').write('\n'.join(lines) + '\n')
    print('%d candidate starts, %d matched, %d DB signatures' % (len(starts), len(found), len(sigs)))

if __name__ == '__main__':
    main()
