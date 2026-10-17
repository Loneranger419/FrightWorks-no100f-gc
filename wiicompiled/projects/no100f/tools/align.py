"""Name a stripped target's SDK functions by aligning them, in link order, with a symbolised donor's.

Within each SDK library the functions keep their order between versions, though libraries may link in another order
and functions are added/removed/changed. Anchors (exact/fuzzy matches) sorted by donor address are split into runs
where the target address keeps rising at a similar pace (one per library stretch), the monotonic core of each run is
kept, and each stretch between consecutive anchors is aligned Needleman-Wunsch style with masked-instruction
similarity as the pair score. Pairs scoring below --min are left unnamed.

Usage: align.py <donor.dol> <donor syms "addr size name"> <target.dol> <out MAP> --anchors MAP [--anchors MAP ...]
                [--lo 800F0000] [--hi 80190000] [--dlo 80140000] [--dhi 80200000] [--min 0.55]
MAP output lines: "XXXXXXXX name ; score|anchor".
"""
import bisect, difflib, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from sigmatch import op_key
from fuzzymatch import words_of, arg

def target_funcs(tw, lo, hi, extra):
    starts = set(a for a in extra if lo <= a < hi)
    for a, w in tw.items():
        if w & 0xFC000003 == 0x48000001:
            disp = w & 0x03FFFFFC
            if disp & 0x02000000: disp -= 0x04000000
            t = (a + disp) & 0xFFFFFFFF
            if t in tw and lo <= t < hi: starts.add(t)
        if w == 0x4E800020 and lo <= a + 4 < hi and a + 4 in tw: starts.add(a + 4)
    starts = sorted(starts)
    return [(s, [op_key(tw[a]) for a in range(s, (starts[i + 1] if i + 1 < len(starts) else hi), 4) if a in tw])
            for i, s in enumerate(starts)]

def sim(a, b):
    if not a or not b or not (0.4 <= len(a) / len(b) <= 2.5): return 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.ratio() if sm.quick_ratio() >= 0.4 else 0.0

def lis(pairs):  # longest chain increasing in both coordinates
    pairs = sorted(pairs); idx, prev = [], [None] * len(pairs)
    for i, (_, t) in enumerate(pairs):
        k = bisect.bisect_left([pairs[j][1] for j in idx], t)
        if k == len(idx): idx.append(i)
        else: idx[k] = i
        prev[i] = idx[k - 1] if k else None
    out, i = [], idx[-1] if idx else None
    while i is not None: out.append(pairs[i]); i = prev[i]
    return out[::-1]

def main():
    donor_dol, donor_syms, target_dol, out = sys.argv[1:5]
    lo, hi = arg('--lo', 0x800F0000, lambda s: int(s, 16)), arg('--hi', 0x80190000, lambda s: int(s, 16))
    dlo, dhi = arg('--dlo', 0x80140000, lambda s: int(s, 16)), arg('--dhi', 0x80200000, lambda s: int(s, 16))
    minr = arg('--min', 0.55, float)
    dw, tw = words_of(open(donor_dol, 'rb').read()), words_of(open(target_dol, 'rb').read())
    dfuncs, by_name = [], {}
    for line in open(donor_syms):
        p = line.split()
        if len(p) >= 3:
            a, sz, n = int(p[0], 16), int(p[1], 16), p[2]
            by_name.setdefault(n, a)
            if dlo <= a < dhi and sz >= 4: dfuncs.append((a, n, [op_key(dw[x]) for x in range(a, a + sz, 4) if x in dw]))
    dfuncs.sort()
    anchors = []
    for i, a in enumerate(sys.argv):
        if a == '--anchors':
            for line in open(sys.argv[i + 1]):
                p = line.split()
                if len(p) >= 2 and p[1] in by_name and dlo <= by_name[p[1]] < dhi and lo <= int(p[0], 16) < hi:
                    anchors.append((by_name[p[1]], int(p[0], 16)))
    runs, run = [], []
    for d, t in sorted(set(anchors)):
        if run and (t <= run[-1][1] or t - run[-1][1] > 3 * (d - run[-1][0]) + 0x2000):
            runs.append(run); run = []
        run.append((d, t))
    if run: runs.append(run)
    runs = [lis(r) for r in runs if len(r) >= 2]
    tfuncs = target_funcs(tw, lo, hi, [t for r in runs for _, t in r])
    dpos = {a: i for i, (a, _, _) in enumerate(dfuncs)}
    tpos = {s: i for i, (s, _) in enumerate(tfuncs)}
    runs = [[(dpos[d], tpos[t]) for d, t in r if d in dpos and t in tpos] for r in runs]
    result = {}
    for r in runs:
        for di, ti in r: result[tfuncs[ti][0]] = (dfuncs[di][1], 'anchor')
    gap = -0.3
    for (d0, t0), (d1, t1) in [(a, b) for r in runs for a, b in zip(r, r[1:])]:
        D, T = list(range(d0 + 1, d1)), list(range(t0 + 1, t1))
        if not D or not T or len(D) * len(T) > 400000: continue
        S = [[sim(dfuncs[d][2], tfuncs[t][1]) for t in T] for d in D]
        n, m = len(D), len(T)
        H = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1): H[i][0] = i * gap
        for j in range(1, m + 1): H[0][j] = j * gap
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                H[i][j] = max(H[i - 1][j - 1] + S[i - 1][j - 1] - 0.45, H[i - 1][j] + gap * 0.1, H[i][j - 1] + gap * 0.1)
        i, j = n, m
        while i and j:
            if H[i][j] == H[i - 1][j - 1] + S[i - 1][j - 1] - 0.45:
                if S[i - 1][j - 1] >= minr: result[tfuncs[T[j - 1]][0]] = (dfuncs[D[i - 1]][1], '%.2f' % S[i - 1][j - 1])
                i, j = i - 1, j - 1
            elif H[i][j] == H[i - 1][j] + gap * 0.1: i -= 1
            else: j -= 1
    with open(out, 'w') as f:
        for s in sorted(result): f.write('%08X %s ; %s\n' % (s, result[s][0], result[s][1]))
    print('%d donor SDK functions, %d target functions, %d anchors kept, %d named'
          % (len(dfuncs), len(tfuncs), sum(len(r) for r in runs), len(result)))

if __name__ == '__main__':
    main()
