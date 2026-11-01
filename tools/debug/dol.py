"""Disassemble the game's main.dol (PowerPC, capstone) to compare HLE overrides with the original code.

usage:
  python tools/debug/dol.py callers <addr>          every `bl <addr>` site and the function containing it
  python tools/debug/dol.py func <addr>             disassemble one function (prologue scan to blr/next prologue)
  python tools/debug/dol.py dis <addr> <count>      disassemble <count> instructions
  python tools/debug/dol.py name <addr>             MAP.txt name for an address

`bl` targets are annotated with names from wiicompiled/projects/no100f/MAP.txt (stripped DOL: many are fn_XXXXXXXX).
Needs: pip install capstone
"""
import bisect
import os
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(os.path.abspath(__file__)).parents[2]
DOL = ROOT / "game" / "main.dol"
MAP = ROOT / "wiicompiled" / "projects" / "no100f" / "MAP.txt"


def _load_dol(path=DOL):
    d = path.read_bytes()
    offs = struct.unpack_from(">18I", d, 0)
    addrs = struct.unpack_from(">18I", d, 0x48)
    sizes = struct.unpack_from(">18I", d, 0x90)
    return [(addrs[i], d[offs[i]: offs[i] + sizes[i]], i < 7) for i in range(18) if sizes[i]]


def _load_map(path=MAP):
    syms = {}
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    syms[int(parts[0], 16)] = parts[1]
                except ValueError:
                    pass
    return syms


SECS = _load_dol()
SYMS = _load_map()
_SYM_ADDRS = sorted(SYMS)
MD = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)


def read(addr, n):
    for base, data, _ in SECS:
        if base <= addr < base + len(data):
            return data[addr - base: addr - base + n]
    return None


def name(addr):
    i = bisect.bisect_right(_SYM_ADDRS, addr) - 1
    if i < 0:
        return f"{addr:08X}"
    a = _SYM_ADDRS[i]
    return SYMS[a] if a == addr else f"{SYMS[a]}+0x{addr - a:X}"


def callers(target):
    out = []
    for base, data, is_text in SECS:
        if not is_text:
            continue
        for o in range(0, len(data) - 3, 4):
            w = struct.unpack_from(">I", data, o)[0]
            if (w >> 26) == 18 and (w & 3) == 1:  # bl
                li = w & 0x03FFFFFC
                if li & 0x02000000:
                    li -= 0x04000000
                if base + o + li == target:
                    out.append(base + o)
    return out


def func_start(addr):
    """Nearest preceding `stwu r1,-x(r1)` prologue (or `mflr r0` just before it)."""
    a = addr
    while a > addr - 0x8000:
        w = struct.unpack(">I", read(a, 4))[0]
        if (w & 0xFFFF0000) == 0x94210000:
            prev = read(a - 4, 4)
            if prev and struct.unpack(">I", prev)[0] == 0x7C0802A6:  # mflr r0
                return a - 4
            return a
        a -= 4
    return addr


def dis(addr, count):
    for ins in MD.disasm(read(addr, count * 4) or b"", addr):
        note = ""
        if ins.mnemonic in ("bl", "b") and ins.op_str.startswith("0x"):
            note = f"   ; {name(int(ins.op_str, 16))}"
        print(f"  {ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}{note}")


def func(addr, limit=2000):
    start = func_start(addr) if addr not in SYMS else addr
    print(f"{name(start)} @ {start:08X}")
    a = start
    for _ in range(limit):
        w = struct.unpack(">I", read(a, 4))[0]
        dis(a, 1)
        a += 4
        if w == 0x4E800020:  # blr; stop unless more of the function follows (no new prologue next)
            nxt = struct.unpack(">I", read(a, 4))[0]
            if (nxt & 0xFFFF0000) == 0x94210000 or nxt == 0x7C0802A6 or a in SYMS:
                break


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, addr = argv[1], int(argv[2], 16)
    if cmd == "callers":
        for c in callers(addr):
            print(f"call @ {c:08X}  in {name(func_start(c))}")
    elif cmd == "func":
        func(addr)
    elif cmd == "dis":
        dis(addr, int(argv[3]) if len(argv) > 3 else 32)
    elif cmd == "name":
        print(name(addr))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
