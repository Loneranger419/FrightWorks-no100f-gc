"""levels.py [scene ...] [--md]: the game's own level table from game/main.dol, checked against Disc/DATA/files.

Reads the area table (0x801D6428: name, letter, index) and the level table (0x801D651C: 36-byte entries of title, index,
Scooby Snacks, Scooby Snacks, monster tokens, up to 4 scene IDs) of the main.dol whose SHA recomp.yml pins.
Part numbers are the order of the scenes in the entry.
  levels.py            every level, plus disc scenes that are not in the table and table scenes missing from the disc
  levels.py i004 c001  title, part and area of these scenes
  levels.py --md       the table as Markdown (for levels.md)
"""
import glob, os, struct, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import dol  # noqa: E402

AREAS, LEVELS = 0x801D6428, 0x801D651C


def cstr(addr):
    b = dol.read(addr, 64)
    return b[:b.find(b"\0")].decode("latin1")


def areas():
    out = {}
    for a in range(AREAS, AREAS + 13 * 16, 16):
        name, letter, _, _ = struct.unpack(">IIII", dol.read(a, 16))
        out[chr(letter >> 24)] = cstr(name)
    return out


def levels():
    out, a = [], LEVELS
    while True:
        title, index, snacks, _, tokens = struct.unpack(">5I", dol.read(a, 20))
        if not 0x80000000 <= title < 0x81800000 or index != len(out) + 1:
            return out
        scenes = [dol.read(a + 20 + 4 * k, 4).decode("latin1") for k in range(4)]
        out.append((index, cstr(title), snacks, tokens, [s for s in scenes if s != "\0\0\0\0"]))
        a += 36


def main():
    args = sys.argv[1:]
    ar, lv = areas(), levels()
    disc = {os.path.basename(f)[:-4].upper() for f in glob.glob(os.path.join(ROOT, "Disc", "DATA", "files", "**", "*.HIP"),
                                                                   recursive=True)}
    if "--md" in args:
        print("| # | Level | Area | Scenes (part 1, 2, ...) | Snacks | Tokens |")
        print("| ---: | --- | --- | --- | ---: | ---: |")
        for i, t, sn, tk, sc in lv:
            names = ", ".join(f"`{s.lower()}`" + ("" if s in disc or not disc else " (not on disc)") for s in sc)
            print(f"| {i} | {t} | {ar.get(sc[0][0], '?')} | {names} | {sn} | {tk} |")
        return
    want = {a.upper() for a in args}
    for i, t, sn, tk, sc in lv:
        for part, s in enumerate(sc, 1):
            if want and s not in want:
                continue
            miss = "" if s in disc or not disc else "  (not on disc)"
            print(f"{s.lower()}  {t} part {part}/{len(sc)}  [{ar.get(s[0], '?')}]  level {i}, {sn} snacks, {tk} tokens{miss}")
    if not want and disc:
        listed = {s for *_, sc in lv for s in sc}
        print("on disc, not in the table:", " ".join(sorted(s.lower() for s in disc - listed)))


if __name__ == "__main__":
    main()
