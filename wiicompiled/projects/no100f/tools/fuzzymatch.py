"""Fuzzy-match donor (symbolised) SDK functions to a stripped target by masked-instruction similarity.

Target functions = sorted candidate starts (bl targets, code after blr) running to the next start. For each wanted
donor name, every target function in [--lo, --hi) of similar size is scored with difflib's ratio over Dolphin
signature keys; the best is taken when it scores >= --min and beats the runner-up by --margin. Known anchors (MAP
files given with --known) are never reassigned.

Usage: fuzzymatch.py <donor.dol> <donor syms "addr size name"> <target.dol> <names.txt> <out MAP>
                     [--known MAP ...] [--lo 800F0000] [--hi 80190000] [--min 0.80] [--margin 0.06]
"""
import difflib, struct, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from sigmatch import dol_text, op_key

def words_of(d):
    w = {}
    for addr, data in dol_text(d):
        for i in range(0, len(data) - 3, 4): w[addr + i] = struct.unpack('>I', data[i:i + 4])[0]
    return w

def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

def main():
    donor_dol, donor_syms, target_dol, names_file, out = sys.argv[1:6]
    lo, hi = arg('--lo', 0x800F0000, lambda s: int(s, 16)), arg('--hi', 0x80190000, lambda s: int(s, 16))
    minr, margin = arg('--min', 0.80, float), arg('--margin', 0.06, float)
    known = {}
    for i, a in enumerate(sys.argv):
        if a == '--known':
            for line in open(sys.argv[i + 1]):
                p = line.split()
                if len(p) >= 2: known[int(p[0], 16)] = p[1]
    dw, tw = words_of(open(donor_dol, 'rb').read()), words_of(open(target_dol, 'rb').read())
    syms = {}
    for line in open(donor_syms):
        p = line.split()
        if len(p) >= 3: syms[p[2]] = (int(p[0], 16), int(p[1], 16))
    starts = set(known)
    for a, w in tw.items():
        if w & 0xFC000003 == 0x48000001:
            disp = w & 0x03FFFFFC
            if disp & 0x02000000: disp -= 0x04000000
            if (a + disp) & 0xFFFFFFFF in tw: starts.add((a + disp) & 0xFFFFFFFF)
        if w == 0x4E800020 and a + 4 in tw: starts.add(a + 4)
    starts = sorted(s for s in starts if lo <= s < hi)
    funcs = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else hi
        funcs.append((s, [op_key(tw[a]) for a in range(s, e, 4) if a in tw]))
    taken, result = set(known), {}
    for name in [l.strip() for l in open(names_file) if l.strip()]:
        if name not in syms or name in known.values(): continue
        addr, size = syms[name]
        dk = [op_key(dw[a]) for a in range(addr, addr + size, 4) if a in dw]
        if len(dk) < 2: continue
        scores = []
        for s, tk in funcs:
            if s in taken or not (0.5 * len(dk) <= len(tk) <= 2.0 * len(dk) + 4): continue
            sm = difflib.SequenceMatcher(None, dk, tk, autojunk=False)
            if sm.real_quick_ratio() < minr or sm.quick_ratio() < minr: continue
            scores.append((sm.ratio(), s))
        scores.sort(reverse=True)
        if scores and scores[0][0] >= minr and (len(scores) == 1 or scores[0][0] - scores[1][0] >= margin):
            result[scores[0][1]] = (name, scores[0][0])
    with open(out, 'w') as f:
        for s in sorted(result): f.write('%08X %s ; %.2f\n' % (s, result[s][0], result[s][1]))
    print('%d target functions in range, %d names matched' % (len(funcs), len(result)))

if __name__ == '__main__':
    main()
