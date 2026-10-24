"""List assets in a Heavy Iron HIP archive: hip.py <file> [type filter]"""
import sys, struct
data = open(sys.argv[1], "rb").read()
flt = sys.argv[2] if len(sys.argv) > 2 else None
def walk(off, end, depth, out):
    while off + 8 <= end:
        tag = data[off:off+4].decode("latin1"); size = struct.unpack(">I", data[off+4:off+8])[0]
        body = off + 8
        if tag in ("HIPA", "PACK", "DICT", "ATOC", "LTOC", "STRM", "AHDR", "LHDR"):
            if tag == "AHDR":
                aid, typ, aoff, asz, plus, flags = struct.unpack(">I4sIIII", data[body:body+24])
                name = ""
                sub = body + 24
                if data[sub:sub+4] == b"ADBG":
                    dsz = struct.unpack(">I", data[sub+4:sub+8])[0]
                    raw = data[sub+12:sub+8+dsz]
                    name = raw.split(b"\0")[0].decode("latin1")
                out.append((aid, typ.decode("latin1"), aoff, asz, flags, name))
            elif tag != "HIPA":
                skip = 4 if tag in ("LHDR",) else 0
                walk(body + skip, body + size, depth + 1, out)
            if tag == "HIPA": off = body; continue
        off = body + size
out = []
walk(0, len(data), 0, out)
for a in out:
    if not flt or a[1] == flt:
        print(f"{a[0]:08X} {a[1]} off {a[2]:08X} size {a[3]:8d} flags {a[4]:X} {a[5]}")
