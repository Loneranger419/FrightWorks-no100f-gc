"""Spread names through the call graph: for every function named in both donor and target, line up the two call
lists (bl targets in order) and give unnamed target callees the donor callee's name where the alignment pairs them.
Repeats until nothing new is learned. Strong for SDK code: e.g. OSInit's callee order names EXIInit, SIInit,
__OSThreadInit; GXInit's names the GX setters it calls.

A pairing is accepted when it sits inside an aligned block (difflib 'replace' of equal length or an 'equal' run around
it) and the name is not already used elsewhere in the target. Conflicting votes for one address are dropped.

Usage: callprop.py <donor.dol> <donor MAP> <target.dol> <target MAP> <out MAP> [--rounds 8]
"""
import collections, difflib, struct, sys

def load_words(p):
    d = open(p, 'rb').read(); w = {}
    for k in range(7):
        off, addr, size = (struct.unpack('>I', d[b + k * 4:b + k * 4 + 4])[0] for b in (0, 0x48, 0x90))
        for i in range(0, size - 3, 4): w[addr + i] = struct.unpack('>I', d[off + i:off + i + 4])[0]
    return w

def load_map(p):
    m = {}
    for line in open(p):
        s = line.split()
        if len(s) >= 2: m[int(s[0], 16)] = s[1]
    return m

def calls(w, starts_sorted, start):
    import bisect
    i = bisect.bisect_right(starts_sorted, start)
    end = starts_sorted[i] if i < len(starts_sorted) else start + 0x4000
    out = []
    for a in range(start, end, 4):
        x = w.get(a)
        if x is None: break
        if x & 0xFC000003 == 0x48000001:
            disp = x & 0x03FFFFFC
            if disp & 0x02000000: disp -= 0x04000000
            out.append((a + disp) & 0xFFFFFFFF)
    return out

def main():
    ddol, dmap, tdol, tmap, out = sys.argv[1:6]
    rounds = int(sys.argv[sys.argv.index('--rounds') + 1]) if '--rounds' in sys.argv else 8
    dw, tw = load_words(ddol), load_words(tdol)
    dnames, tmap_all = load_map(dmap), load_map(tmap)
    tnames = {a: n for a, n in tmap_all.items() if not n.startswith('fn_')}
    dstarts, tstarts = sorted(dnames), sorted(tmap_all)
    by_dname = {}
    for a, n in dnames.items(): by_dname.setdefault(n, a)
    learned = {}
    for _ in range(rounds):
        used = set(tnames.values())
        votes = collections.defaultdict(collections.Counter)
        for ta, name in list(tnames.items()):
            da = by_dname.get(name)
            if da is None: continue
            dc = [dnames.get(t, '?') for t in calls(dw, dstarts, da)]
            tcalls = calls(tw, tstarts, ta)
            tc = [tnames.get(t, '?') for t in tcalls]
            sm = difflib.SequenceMatcher(None, dc, tc, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'replace' and i2 - i1 == j2 - j1:
                    for k in range(i2 - i1):
                        if tc[j1 + k] == '?' and dc[i1 + k] != '?' and dc[i1 + k] not in used:
                            votes[tcalls[j1 + k]][dc[i1 + k]] += 1
        # Upward: an unnamed target function whose named callees run in the same order as a donor function's
        # (at least 3 named, ratio >= 0.8, clearly best) gets that donor function's name.
        dcall_lists = {}
        for da, dn in dnames.items():
            if dn in used: continue
            seq = [dnames.get(t, '?') for t in calls(dw, dstarts, da)]
            if sum(1 for s in seq if s != '?') >= 3: dcall_lists[dn] = seq
        for ta in tstarts:
            if ta in tnames: continue
            tseq = [tnames.get(t, '?') for t in calls(tw, tstarts, ta)]
            named = [s for s in tseq if s != '?']
            if len(named) < 3: continue
            best = []
            for dn, dseq in dcall_lists.items():
                dnamed = [s for s in dseq if s != '?']
                if not set(named) & set(dnamed): continue
                r = difflib.SequenceMatcher(None, dnamed, named, autojunk=False).ratio()
                if r >= 0.8: best.append((r, dn))
            best.sort(reverse=True)
            if best and (len(best) == 1 or best[0][0] - best[1][0] >= 0.1):
                votes[ta][best[0][1]] += 2
        new = 0
        claimed = collections.Counter()
        for addr, c in votes.items():
            if len(c) == 1: claimed[next(iter(c))] += 1
        for addr, c in votes.items():
            if len(c) != 1: continue
            name = next(iter(c))
            if claimed[name] == 1 and addr not in tnames:
                tnames[addr] = name; learned[addr] = name; new += 1
        if not new: break
    with open(out, 'w') as f:
        for a in sorted(learned): f.write('%08X %s ; callgraph\n' % (a, learned[a]))
    print('learned %d names from the call graph' % len(learned))

if __name__ == '__main__':
    main()
