"""Move the runtime's HLE hooks from Scooby-Doo! Unmasked addresses to Night of 100 Frights addresses, by name.

Each PPC_NATIVE_OVERRIDE[_VOID](XXXXXXXX ...) / REGISTER_NATIVE_FUNCTION_AS*(0xXXXXXXXX ...) address is looked up in
the donor MAP (address -> name). If that name has an address in the target MAP, the hook moves there; otherwise the
hook is parked on a unique dead address in low memory (0x80001000 + 4n, never code), so a stale address cannot land
on an unrelated target function. Writes a report of every decision. Run once on the Unmasked runtime sources.

Usage: remap_hooks.py <runtime/src> <donor MAP> <target MAP> <report.txt>
"""
import os, re, sys

def load(path):
    m = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2: m[int(p[0], 16)] = p[1]
    return m

def main():
    src, donor_map, target_map, report = sys.argv[1:5]
    donor = load(donor_map)
    target = {n: a for a, n in load(target_map).items() if not n.startswith('fn_')}
    pat = re.compile(r'(PPC_NATIVE_OVERRIDE(?:_VOID)?\(\s*|(?:REGISTER_NATIVE_FUNCTION|REGISTER_TRANSLATED_FUNCTION)\w*\(\s*0x)([0-9A-Fa-f]{8})')
    state = {'dead': 0, 'moved': 0}
    assigned, lines = {}, []
    for root, _, files in os.walk(src):
        for f in sorted(files):
            if not f.endswith(('.cpp', '.h', '.inc')): continue
            path = os.path.join(root, f)
            text = open(path, encoding='utf-8').read()
            def repl(m):
                old = int(m.group(2), 16)
                if old not in assigned:
                    name = donor.get(old)
                    if name and name in target:
                        assigned[old] = target[name]; state['moved'] += 1; why = name
                    else:
                        assigned[old] = 0x80001000 + 4 * state['dead']; state['dead'] += 1
                        why = 'PARKED (%s)' % (name or 'no donor name')
                    lines.append('%08X -> %08X  %-40s %s' % (old, assigned[old], why, os.path.relpath(path, src)))
                return m.group(1) + ('%08X' % assigned[old] if not any(c in 'abcdef' for c in m.group(2)) else '%08x' % assigned[old])
            new_text = pat.sub(repl, text)
            if new_text != text: open(path, 'w', encoding='utf-8', newline='').write(new_text)
    open(report, 'w').write('\n'.join(lines) + '\n')
    print('hooks moved %d, parked %d' % (state['moved'], state['dead']))

if __name__ == '__main__':
    main()
