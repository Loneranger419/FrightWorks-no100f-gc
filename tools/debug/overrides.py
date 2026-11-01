"""List native overrides that actually replace this game's code, with the original's side effects.

usage:
  python tools/debug/overrides.py [--all] [filter]      table: address, MAP name, native function, file:line
  python tools/debug/overrides.py --effects <filter>   + per override: original's calls, __GXData writes, FIFO/MMIO stores
  python tools/debug/overrides.py --xref <filter>      __GXData fields the original writes that translated code reads

Native overrides never touch the game's real __GXData (r13-0x7DB8); anything the original stores there is skipped.
--xref shows where that can matter: a translated function (e.g. __GXSetDirtyState, GXBegin) reading a field that
only the replaced original kept up to date. Static and linear (no control flow): a lead, not proof.

"Parked" overrides (addresses 0x80001000-0x80002FFF, below the game's text) belong to other games' builds and never run.
`filter` is a substring matched against the MAP name, native name or file.
"""
import bisect
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent))
import dol  # noqa: E402

ROOT = Path(os.path.abspath(__file__)).parents[2]
SRC = ROOT / "wiicompiled" / "runtime" / "src"
OVR = re.compile(r"^\s*PPC_NATIVE_OVERRIDE(?:_VOID)?\(\s*([0-9A-Fa-f]{8})\s*,\s*(\w+)")
TEXT_START = 0x80003000


def _live_lines(text):
    """(line number, line) for lines not inside `#if 0` blocks (nested #if tracked)."""
    stack = []  # True = this level is disabled
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("#if"):
            stack.append(s.startswith("#if 0") or (stack and stack[-1]))
            continue
        if s.startswith("#else"):
            if stack:
                parent_off = len(stack) > 1 and stack[-2]
                stack[-1] = parent_off or not stack[-1]
            continue
        if s.startswith("#endif"):
            if stack:
                stack.pop()
            continue
        if not (stack and stack[-1]):
            yield n, line


def overrides(include_parked=False):
    out = []
    for path in SRC.rglob("*.cpp"):
        for n, line in _live_lines(path.read_text(errors="replace")):
            m = OVR.match(line)
            if not m:
                continue
            addr = int(m.group(1), 16)
            if addr < TEXT_START and not include_parked:
                continue
            out.append((addr, dol.name(addr), m.group(2), f"{path.relative_to(SRC)}:{n}"))
    return sorted(out)


MEM = re.compile(r"(?:[rf]\d+), (-?0x[0-9a-f]+|\d+)\((r\d+)\)$")
NO_DEST = ("st", "cmp", "b", "mt", "tw", "dcb", "icb", "sync", "isync", "eieio", "rfi", "sc", "crxor", "creqv")


def func_end(addr):
    i = bisect.bisect_right(dol._SYM_ADDRS, addr)
    return dol._SYM_ADDRS[i] if i < len(dol._SYM_ADDRS) else addr + 0x4000


def scan(start, end):
    """Yield (address, kind, value) for one function: ('gxr'|'gxw', __GXData offset), ('pipe', None),
    ('mmio', ea), ('call', target). __GXData = the pointer loaded from -0x7DB8(r13), followed through mr/addi
    aliases; a tracked register is dropped once overwritten (linear, no control flow; good enough for SDK code)."""
    gx_regs, hw_regs = {}, {}  # reg -> offset into __GXData it points at / MMIO base
    raw = dol.read(start, end - start) or b""
    for ins in dol.MD.disasm(raw, start):
        mn, ops = ins.mnemonic, ins.op_str
        dest = ops.split(",")[0] if ops and not mn.startswith(NO_DEST) else None
        srcs = ops.split(", ")
        m = MEM.search(ops)
        if m and m.group(2) in gx_regs and mn[0] in "ls" and not mn.startswith("li"):
            yield ins.address, ("gxw" if mn.startswith("st") else "gxr"), gx_regs[m.group(2)] + int(m.group(1), 0)
        if m and m.group(2) in hw_regs and mn.startswith("st"):
            ea = (hw_regs[m.group(2)] + int(m.group(1), 0)) & 0xFFFFFFFF
            yield ins.address, ("pipe" if ea == 0xCC008000 else "mmio"), ea
        if mn == "bl" and ops.startswith("0x"):
            yield ins.address, "call", int(ops, 16)
        alias = None
        if mn == "mr" and srcs[1] in gx_regs:
            alias = gx_regs[srcs[1]]
        elif mn == "addi" and len(srcs) == 3 and srcs[1] in gx_regs:
            alias = gx_regs[srcs[1]] + int(srcs[2], 0)
        if dest:
            gx_regs.pop(dest, None)
            hw_regs.pop(dest, None)
        if m and mn[0] in "ls" and mn.endswith("u") and m.group(2) in gx_regs:  # lwzu/stwu move the base
            gx_regs[m.group(2)] += int(m.group(1), 0)
        if mn == "lwz" and ops.endswith("-0x7db8(r13)"):
            gx_regs[dest] = 0
        elif alias is not None:
            gx_regs[dest] = alias
        elif mn == "lis" and ops.endswith("-0x33ff"):
            hw_regs[dest] = 0xCC010000
        elif mn == "lis" and ops.endswith("-0x3400"):
            hw_regs[dest] = 0xCC000000


def effects(addr):
    """Summarise the original function: calls, __GXData field writes/reads, gather-pipe / MMIO stores."""
    calls, gx_writes, gx_reads, pipe, mmio = [], set(), set(), 0, set()
    for _, kind, v in scan(addr, func_end(addr)):
        if kind == "call":
            calls.append(dol.name(v))
        elif kind == "gxw":
            gx_writes.add(v)
        elif kind == "gxr":
            gx_reads.add(v)
        elif kind == "pipe":
            pipe += 1
        else:
            mmio.add(v)
    return {
        "calls": sorted(set(calls)),
        "gxdata_writes": sorted(gx_writes),
        "gxdata_reads": sorted(gx_reads),
        "pipe_stores": pipe,
        "mmio": sorted(mmio),
    }


def gx_field_users():
    """__GXData offset -> {'r': set(func), 'w': set(func)} over every function in the DOL's text."""
    users = {}
    starts = [a for a in dol._SYM_ADDRS if a >= TEXT_START and any(
        b <= a < b + len(d) and t for b, d, t in dol.SECS)]
    for s in starts:
        for _, kind, v in scan(s, func_end(s)):
            if kind in ("gxr", "gxw"):
                users.setdefault(v, {"r": set(), "w": set()})[kind[2]].add(s)
    return users


def xref(flt):
    """For each override: __GXData fields its original writes that non-overridden (translated) code reads."""
    ovr = overrides()
    replaced = {a for a, *_ in ovr}
    users = gx_field_users()
    for addr, mapname, native, where in ovr:
        if flt and flt not in f"{mapname} {native} {where}".lower():
            continue
        fx = effects(addr)
        hits = []
        for off in fx["gxdata_writes"]:
            readers = sorted(users.get(off, {}).get("r", set()) - replaced)
            if readers:
                hits.append(f"+0x{off:X} <- " + ", ".join(dol.name(r) for r in readers[:6]) +
                            (f" (+{len(readers) - 6})" if len(readers) > 6 else ""))
        print(f"{addr:08X}  {mapname:28s} {native}")
        for h in hits or ["(no field it writes is read by translated code)"]:
            print(f"    {h}")


def main(argv):
    show_all = "--all" in argv
    show_fx = "--effects" in argv
    args = [x for x in argv[1:] if not x.startswith("--")]
    flt = args[0].lower() if args else ""
    if "--xref" in argv:
        xref(flt)
        return 0
    for addr, mapname, native, where in overrides(show_all):
        if flt and flt not in f"{mapname} {native} {where}".lower():
            continue
        print(f"{addr:08X}  {mapname:32s} {native:40s} {where}")
        if show_fx and addr >= TEXT_START:
            fx = effects(addr)
            fmt = lambda xs: ", ".join(f"+0x{x:X}" for x in xs) or "-"  # noqa: E731
            print(f"    calls: {', '.join(fx['calls']) or '-'}")
            print(f"    __GXData writes: {fmt(fx['gxdata_writes'])}   reads: {fmt(fx['gxdata_reads'])}")
            print(f"    gather-pipe stores: {fx['pipe_stores']}   other MMIO: {', '.join(f'{x:08X}' for x in fx['mmio']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
