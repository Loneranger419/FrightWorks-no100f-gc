"""Second pass of remap_hooks.py: move hooks that were parked (no target address at the time) now that the target
MAP names their function. Reads remap_hooks.py's report, rewrites each parked address (unique, 0x80001000 + 4n) in the
runtime sources to the function's target address, and rewrites the report. Hooks whose name is still unknown stay
parked. Safe to run again after every MAP improvement.

Usage: remap_parked.py <runtime/src> <target MAP> <hook_remap.txt>
"""
import os, re, sys

def main():
    src, target_map, report = sys.argv[1:4]
    target = {}
    for line in open(target_map):
        p = line.split()
        if len(p) >= 2 and not p[1].startswith('fn_'): target.setdefault(p[1], int(p[0], 16))
    lines, moves = [], {}
    for line in open(report):
        m = re.match(r'([0-9A-F]{8}) -> ([0-9A-F]{8})  PARKED \((\S+)\)\s+(\S+)', line)
        if m and m.group(3) in target:
            new = target[m.group(3)]
            moves[int(m.group(2), 16)] = new
            line = '%s -> %08X  %-40s %s\n' % (m.group(1), new, m.group(3), m.group(4))
        lines.append(line if line.endswith('\n') else line + '\n')
    pat = re.compile(r'(PPC_NATIVE_OVERRIDE(?:_VOID)?\(\s*|(?:REGISTER_NATIVE_FUNCTION|REGISTER_TRANSLATED_FUNCTION)\w*\(\s*0x)([0-9A-Fa-f]{8})')
    for root, _, files in os.walk(src):
        for f in files:
            if not f.endswith(('.cpp', '.h', '.inc')): continue
            path = os.path.join(root, f)
            text = open(path, encoding='utf-8').read()
            new_text = pat.sub(lambda m: m.group(1) + ('%08X' % moves[int(m.group(2), 16)] if int(m.group(2), 16) in moves else m.group(2)), text)
            if new_text != text: open(path, 'w', encoding='utf-8', newline='').write(new_text)
    open(report, 'w').writelines(lines)
    print('moved %d parked hooks; %d still parked' % (len(moves), sum(1 for l in lines if 'PARKED' in l)))

if __name__ == '__main__':
    main()
