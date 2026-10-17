"""Write the translator's function map for the stripped main.dol: every provable function start, named where an SDK
match is confident, else fn_XXXXXXXX.

Starts: bl targets; code right after a blr/rfi/b that opens with a prologue (stwu r1 / mflr r0); data words that
point at such code (vtables, callbacks). Names, first map wins: sigmatch (Dolphin DB), donormatch (exact), align
anchors, then fuzzy/align matches scoring >= --min.

Usage: genmap.py <main.dol> <out MAP.txt> [--min 0.85] --maps MAP_sig.txt MAP_donor.txt MAP_align.txt MAP_fuzzy.txt
"""
import re, struct, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from fuzzymatch import words_of

def main():
    dol, out = sys.argv[1:3]
    minr = float(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 0.85
    maps = sys.argv[sys.argv.index('--maps') + 1:]
    d = open(dol, 'rb').read()
    tw = words_of(d)
    def prologue(a):
        w = tw.get(a)
        return w is not None and (w & 0xFFFF0000 == 0x94210000 or w == 0x7C0802A6)  # stwu r1,-x(r1) / mflr r0
    starts = set()
    for a, w in tw.items():
        if w & 0xFC000003 == 0x48000001:
            disp = w & 0x03FFFFFC
            if disp & 0x02000000: disp -= 0x04000000
            t = (a + disp) & 0xFFFFFFFF
            if t in tw: starts.add(t)
        if (w in (0x4E800020, 0x4C000064) or w & 0xFC000003 == 0x48000000) and prologue(a + 4): starts.add(a + 4)
    for k in range(7, 18):  # data sections: vtables and callback pointers
        off, addr, size = (struct.unpack('>I', d[b + k * 4:b + k * 4 + 4])[0] for b in (0, 0x48, 0x90))
        for i in range(0, size - 3, 4):
            v = struct.unpack('>I', d[off + i:off + i + 4])[0]
            # a pointer to code right after blr/rfi/b (a function boundary) is a function too (leaf callbacks, ctors)
            prev = tw.get(v - 4)
            boundary = prev is None or prev in (0, 0x4E800020, 0x4C000064) or prev & 0xFC000003 == 0x48000000
            if v in tw and (v in starts or prologue(v) or boundary): starts.add(v)
    names, used = {}, set()
    for path in maps:
        for line in open(path):
            m = re.match(r'([0-9A-Fa-f]{8})\s+(\S+)(?:\s*;\s*(\S+))?', line)
            if not m: continue
            a, n, score = int(m.group(1), 16), m.group(2), m.group(3)
            if score and re.fullmatch(r'[0-9.]+', score) and float(score) < minr: continue  # tags like anchor/callgraph/manual are confident
            if a in names or n in used: continue
            names[a] = n; used.add(n); starts.add(a)
    with open(out, 'w') as f:
        for a in sorted(starts):
            f.write('%08X %s\n' % (a, re.sub(r'[^A-Za-z0-9_]', '_', names.get(a, 'fn_%08X' % a))))
    print('%d functions, %d named' % (len(starts), sum(1 for a in starts if a in names)))

if __name__ == '__main__':
    main()
