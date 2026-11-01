"""Extract GameCube textures from NO100F HIP files (RWTX = RenderWare GC texture dictionaries), decode them to RGBA and
name them the way the recomp's texture replacement does (aurora texture_replacement.cpp: tex1_WxH_<xxh64 of base level>
[_<xxh64 of the used TLUT range>]_<GX format>)."""
import os, struct
import numpy as np

# ---- XXH64 (pure Python; seed 0) ----
P1, P2, P3, P4, P5 = 11400714785074694791, 14029467366897019727, 1609587929392839161, 9650029242287828579, 2870177450012600261
M = (1 << 64) - 1
def _rotl(x, r): return ((x << r) | (x >> (64 - r))) & M
def _round(acc, lane): acc = (acc + lane * P2) & M; return (_rotl(acc, 31) * P1) & M
def _merge(acc, v): acc ^= _round(0, v); return (acc * P1 + P4) & M
def xxh64(b, seed=0):
    n = len(b); p = 0
    if n >= 32:
        v1, v2, v3, v4 = (seed + P1 + P2) & M, (seed + P2) & M, seed, (seed - P1) & M
        lim = n - 32
        unpack = struct.Struct("<4Q").unpack_from
        while p <= lim:
            a, c, d, e = unpack(b, p)
            v1 = (_rotl((v1 + a * P2) & M, 31) * P1) & M
            v2 = (_rotl((v2 + c * P2) & M, 31) * P1) & M
            v3 = (_rotl((v3 + d * P2) & M, 31) * P1) & M
            v4 = (_rotl((v4 + e * P2) & M, 31) * P1) & M
            p += 32
        h = (_rotl(v1, 1) + _rotl(v2, 7) + _rotl(v3, 12) + _rotl(v4, 18)) & M
        h = _merge(h, v1); h = _merge(h, v2); h = _merge(h, v3); h = _merge(h, v4)
    else:
        h = (seed + P5) & M
    h = (h + n) & M
    while p + 8 <= n:
        k, = struct.unpack_from("<Q", b, p); h ^= _round(0, k); h = (_rotl(h, 27) * P1 + P4) & M; p += 8
    if p + 4 <= n:
        k, = struct.unpack_from("<I", b, p); h ^= (k * P1) & M; h = (_rotl(h, 23) * P2 + P3) & M; p += 4
    while p < n:
        h ^= (b[p] * P5) & M; h = (_rotl(h, 11) * P1) & M; p += 1
    h ^= h >> 33; h = (h * P2) & M; h ^= h >> 29; h = (h * P3) & M; h ^= h >> 32
    return h

# ---- HIP / RenderWare walking ----
def hip_assets(data):
    out = []
    def walk(off, end):
        while off + 8 <= end:
            tag = data[off:off+4]; size = struct.unpack(">I", data[off+4:off+8])[0]; body = off + 8
            if tag == b"HIPA": off = body; continue
            if tag in (b"DICT", b"ATOC"): walk(body, min(end, body + size))
            elif tag == b"AHDR":
                aid, typ, aoff, asz = struct.unpack(">I4sII", data[body:body+16])
                name = ""
                if data[body+24:body+28] == b"ADBG": name = data[body+36:body+36+64].split(b"\0")[0].decode("latin1").strip()
                out.append((aid, typ.decode("latin1"), aoff, asz, name))
            off = body + size
    walk(0, len(data)); return out

def rw_chunks(b, off, end):
    while off + 12 <= end:
        t, s, v = struct.unpack_from("<III", b, off)
        yield t, off + 12, s
        off += 12 + s

# GX texture block sizes (block w, block h, bits per pixel)
BLOCK = {0: (8, 8, 4), 1: (8, 4, 8), 2: (8, 8, 4), 3: (4, 4, 16), 4: (4, 4, 16), 5: (4, 4, 16), 6: (4, 4, 32),
         8: (8, 8, 4), 9: (8, 4, 8), 10: (4, 4, 16), 14: (8, 8, 4)}
def base_size(w, h, fmt):
    bw, bh, bpp = BLOCK[fmt]
    return ((w + bw - 1) // bw) * ((h + bh - 1) // bh) * bw * bh * bpp // 8

def rwtx_textures(b):
    """Yields dicts: name, w, h, fmt, levels, data (base level bytes), tlut (bytes or None), tlutfmt."""
    for t, o, s in rw_chunks(b, 0, len(b)):
        if t != 0x16: continue
        for t2, o2, s2 in rw_chunks(b, o, o + s):
            if t2 != 0x15: continue
            for t3, o3, s3 in rw_chunks(b, o2, o2 + s2):
                if t3 != 1: continue
                h = b[o3:o3+s3]
                name = h[0x18:0x38].split(b"\0")[0].decode("latin1")
                w, hh, depth, lv, fmt, tl = struct.unpack_from(">HHBBBB", h, 0x5C)
                payload = h[0x6C:]
                bs = base_size(w, hh, fmt)
                tlut = None
                if fmt in (8, 9):
                    n = 16 if fmt == 8 else 256
                    # palette at +0x68 (the u32 at +0x68 is part of it), 4 bytes, then the indices; checked against dumps
                    tlut = h[0x68:0x68 + 2 * n]
                    data = h[0x68 + 2 * n + 4:0x68 + 2 * n + 4 + bs]
                else:
                    data = payload[:bs]
                yield dict(name=name, w=w, h=hh, fmt=fmt, levels=lv, data=bytes(data), tlut=tlut, tlutfmt=tl)
                break

def tex_key(t):
    th = xxh64(t["data"])
    if t["fmt"] in (8, 9):
        d = np.frombuffer(t["data"], np.uint8)
        idx = np.concatenate([d >> 4, d & 15]) if t["fmt"] == 8 else d
        lo, hi = int(idx.min()), int(idx.max())
        tlh = xxh64(t["tlut"][2 * lo:2 * (hi + 1)])
        return f"tex1_{t['w']}x{t['h']}_{th:016x}_{tlh:016x}_{t['fmt']}"
    return f"tex1_{t['w']}x{t['h']}_{th:016x}_{t['fmt']}"

# ---- decoders (RGBA8 out) ----
def _untile(blocks, w, h, bw, bh):
    """blocks: (nby, nbx, bh, bw, C) -> (h, w, C)"""
    nby, nbx = blocks.shape[:2]
    img = blocks.transpose(0, 2, 1, 3, 4).reshape(nby * bh, nbx * bw, -1)
    return img[:h, :w]

def _rgb565(v):
    r = (v >> 11) & 31; g = (v >> 5) & 63; b = v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2), np.full_like(r, 255)], -1).astype(np.uint8)

def _rgb5a3(v):
    op = (v & 0x8000) != 0
    r5 = (v >> 10) & 31; g5 = (v >> 5) & 31; b5 = v & 31
    r4 = (v >> 8) & 15; g4 = (v >> 4) & 15; b4 = v & 15; a3 = (v >> 12) & 7
    r = np.where(op, (r5 << 3) | (r5 >> 2), r4 * 17)
    g = np.where(op, (g5 << 3) | (g5 >> 2), g4 * 17)
    b = np.where(op, (b5 << 3) | (b5 >> 2), b4 * 17)
    a = np.where(op, 255, (a3 << 5) | (a3 << 2) | (a3 >> 1))
    return np.stack([r, g, b, a], -1).astype(np.uint8)

def _ia8(v):
    a = (v >> 8) & 255; i = v & 255
    return np.stack([i, i, i, a], -1).astype(np.uint8)

def decode(t):
    w, h, fmt, d = t["w"], t["h"], t["fmt"], np.frombuffer(t["data"], np.uint8)
    bw, bh, bpp = BLOCK[fmt]
    nbx, nby = (w + bw - 1) // bw, (h + bh - 1) // bh
    if fmt in (4, 5):
        v = d.view(">u2").astype(np.uint32).reshape(nby, nbx, bh, bw)
        px = _rgb565(v) if fmt == 4 else _rgb5a3(v)
        return _untile(px, w, h, bw, bh)
    if fmt == 6:
        blk = d.reshape(nby, nbx, 2, 16, 2)  # AR plane then GB plane, 16 px each
        a = blk[:, :, 0, :, 0]; r = blk[:, :, 0, :, 1]; g = blk[:, :, 1, :, 0]; b = blk[:, :, 1, :, 1]
        px = np.stack([r, g, b, a], -1).reshape(nby, nbx, 4, 4, 4)
        return _untile(px, w, h, 4, 4)
    if fmt in (8, 9):
        if fmt == 9:
            idx = d.reshape(nby, nbx, bh, bw)
        else:
            idx = np.stack([d >> 4, d & 15], -1).reshape(nby, nbx, bh, bw)
        pal = np.frombuffer(t["tlut"], ">u2").astype(np.uint32)
        lut = {0: _ia8, 1: _rgb565, 2: _rgb5a3}[t["tlutfmt"]](pal)
        return _untile(lut[idx], w, h, bw, bh)
    if fmt == 14:
        sub = d.reshape(nby, nbx, 2, 2, 8)  # 2x2 DXT1 sub-blocks of 8 bytes, 4x4 px each
        c0 = sub[..., 0].astype(np.uint32) << 8 | sub[..., 1]
        c1 = sub[..., 2].astype(np.uint32) << 8 | sub[..., 3]
        bits = sub[..., 4:8]
        p0 = _rgb565(c0).astype(np.int32); p1 = _rgb565(c1).astype(np.int32)
        gt = (c0 > c1)[..., None]
        p2 = np.where(gt, (2 * p0 + p1) // 3, (p0 + p1) // 2)
        p3 = np.where(gt, (p0 + 2 * p1) // 3, 0)
        p2[..., 3] = 255
        p3[..., 3] = np.where(gt[..., 0], 255, 0)
        pal = np.stack([p0, p1, p2, p3], -2)  # (..., 4, 4ch)
        sel = np.stack([(bits >> s) & 3 for s in (6, 4, 2, 0)], -1)  # (nby,nbx,2,2,4 rows,4 cols)
        flat_pal = pal.reshape(-1, 4, 4)
        flat_sel = sel.reshape(-1, 16)
        out = flat_pal[np.arange(flat_pal.shape[0])[:, None], flat_sel]  # (nsub, 16, 4)
        out = out.reshape(nby, nbx, 2, 2, 4, 4, 4).transpose(0, 1, 2, 4, 3, 5, 6).reshape(nby, nbx, 8, 8, 4)
        return _untile(out.astype(np.uint8), w, h, 8, 8)
    raise ValueError(f"format {fmt}")

def disc_textures(root="Disc/DATA/files"):
    """{key: dict(tex..., hips=set())} for every RWTX texture on the disc."""
    seen = {}
    for dp, dn, fn in os.walk(root):
        for f in sorted(fn):
            if not f.upper().endswith(".HIP"): continue
            data = open(os.path.join(dp, f), "rb").read()
            hip = f[:-4].lower()
            for aid, typ, aoff, asz, aname in hip_assets(data):
                if typ != "RWTX": continue
                for t in rwtx_textures(data[aoff:aoff+asz]):
                    k = tex_key(t)
                    if k not in seen:
                        t["hips"] = set(); t["asset"] = aname; seen[k] = t
                    seen[k]["hips"].add(hip)
    return seen
