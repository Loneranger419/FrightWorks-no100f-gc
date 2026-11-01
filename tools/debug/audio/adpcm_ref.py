"""Reference DSP-ADPCM decode of a music/sound stream straight from a HIP archive (no game code).

usage:
  adpcm_ref.py <file.HIP> --list                      list SNDS assets with their SNDI header (rate, samples)
  adpcm_ref.py <file.HIP> <asset id hex> [--wav out.wav] [--seconds N] [--compare stream_src.raw]

--compare checks a runtime capture (audio-diagnostic.patch: AX_DIAG_DIR/stream_src.raw, 48 kHz LE int16 as decoded,
before SRC) sample by sample against this decode. h002 music = boot.HIP 9974599F "action loop 06-L".

SNDI layout (GC): u32 count, then per entry [0x60-byte DSP header][u32 asset id] - the id comes AFTER its header.
SNDS data is raw ADPCM frames (8 bytes: ps byte + 14 nibbles), no header.
"""
import argparse, struct, sys, wave
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("hip"); ap.add_argument("asset", nargs="?")
ap.add_argument("--list", action="store_true"); ap.add_argument("--wav"); ap.add_argument("--compare")
ap.add_argument("--seconds", type=float, default=20.0)
args = ap.parse_args()
data = open(args.hip, "rb").read()

def assets():
    out = []
    def walk(off, end):
        while off + 8 <= end:
            tag = data[off:off + 4]; size = struct.unpack(">I", data[off + 4:off + 8])[0]; body = off + 8
            if tag == b"HIPA": off = body; continue
            if tag == b"AHDR":
                aid, typ, aoff, asz = struct.unpack(">I4sII", data[body:body + 16]); name = ""
                if data[body + 24:body + 28] == b"ADBG":
                    dsz = struct.unpack(">I", data[body + 28:body + 32])[0]
                    name = data[body + 36:body + 32 + dsz].split(b"\0")[0].decode("latin1")
                out.append((aid, typ.decode("latin1"), aoff, asz, name))
            elif tag in (b"PACK", b"DICT", b"ATOC", b"STRM"):
                walk(body, body + size)
            off = body + size
    walk(0, len(data))
    return out

A = assets()
sndi = next((a for a in A if a[1] == "SNDI"), None)
info = data[sndi[2]:sndi[2] + sndi[3]] if sndi else b""
headers = {}
if info:
    count = struct.unpack(">I", info[:4])[0]
    # entries start after the count and a padding/copy word pair; find them by stride from the first plausible header
    for i in range(4, len(info) - 0x64 + 1, 4):
        rate = struct.unpack(">I", info[i + 8:i + 12])[0]
        nn = struct.unpack(">I", info[i + 4:i + 8])[0]
        if rate in (16000, 22050, 24000, 32000, 44100, 47999, 48000) and nn > 0:
            aid = struct.unpack(">I", info[i + 0x60:i + 0x64])[0]
            h = info[i:i + 0x60]
            headers.setdefault(aid, dict(samples=struct.unpack(">I", h[:4])[0], nibbles=nn, rate=rate,
                                         loop=struct.unpack(">H", h[12:14])[0], coefs=struct.unpack(">16h", h[28:60])))

def decode(raw, co, n):
    out = np.zeros(n, np.int32); k = 0; y1 = y2 = 0
    for f in range(0, len(raw) - 7, 8):
        ps = raw[f]; p = (ps >> 4) & 7; sc = 1 << (ps & 15); c1, c2 = co[p * 2], co[p * 2 + 1]
        for b in raw[f + 1:f + 8]:
            for nib in (b >> 4, b & 15):
                if k >= n: return out
                s = nib - 16 if nib >= 8 else nib
                v = max(-32768, min(32767, s * sc + ((1024 + c1 * y1 + c2 * y2) >> 11))); y2, y1 = y1, v; out[k] = v; k += 1
    return out[:k]

if args.list:
    for aid, typ, off, sz, name in A:
        if typ != "SNDS": continue
        h = headers.get(aid)
        desc = f"rate {h['rate']} samples {h['samples']} loop {h['loop']}" if h else "(no SNDI entry)"
        print(f"{aid:08X} off {off:08X} size {sz:8d} {desc}  {name}")
    sys.exit()

aid = int(args.asset, 16)
a = next(x for x in A if x[0] == aid); h = headers[aid]
n = int(args.seconds * h["rate"])
ref = decode(data[a[2]:a[2] + a[3]], h["coefs"], n)
print(f"{a[4]}: rate {h['rate']}, decoded {len(ref)} samples, coefs {h['coefs']}")
if args.wav:
    with wave.open(args.wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(min(h["rate"], 48000) if h["rate"] != 47999 else 48000)
        w.writeframes(ref.astype("<i2").tobytes())
if args.compare:
    src = np.fromfile(args.compare, "<i2").astype(np.int32)
    m = min(len(src), len(ref)); diff = np.abs(src[:m] - ref[:m]); nz = np.nonzero(diff)[0]
    print(f"compared {m} samples: {len(nz)} differ, max |diff| {diff.max() if m else 0}"
          + (f", first at sample {nz[0]} ({nz[0] / h['rate']:.3f} s)" if len(nz) else " - bit-exact"))
