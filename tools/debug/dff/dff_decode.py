"""Sequential decoder for a Dolphin FIFO log (.dff) — issue #6 scratch analysis.

Tracks CP (VCD/VAT/array base+stride/matindex), XF (pos matrices, projection, viewport)
and guest memory (applying memory updates at their recorded FIFO offsets), and emits one
record per draw with everything needed to recompute its geometry.
"""
from __future__ import annotations

import pickle
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

FILE_ID = 0x0D01F1F0
MEM_SIZE = 0x01800000  # MEM1

COMP_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4}
CLR_SIZE = {0: 2, 1: 3, 2: 4, 3: 2, 4: 3, 5: 4}


def u32le(b, o):
    return struct.unpack_from("<I", b, o)[0]


@dataclass
class Draw:
    frame: int
    off: int
    prim: int
    vat: int
    n: int
    vsz: int
    vcd_lo: int
    vcd_hi: int
    vat_a: int
    pos_type: int  # 0 none 1 direct 2 idx8 3 idx16
    pos_base: int
    pos_stride: int
    pos_fmt: int
    pos_elems: int
    pos_frac: int
    pnmtx_direct: bool
    cur_mtx: int
    mtx: list
    proj: list
    viewport: list
    pos_idx: list = field(default_factory=list)  # per vertex
    pn_idx: list = field(default_factory=list)  # per vertex (direct PNMTXIDX), else []
    verts: dict = field(default_factory=dict)  # idx -> (x,y,z) model space at draw time
    mtx_rows: dict = field(default_factory=dict)  # pn row -> 12 floats (for PNMTXIDX draws)
    cull: int = 0
    tex0: int = 0


class State:
    def __init__(self, data: bytes, hdr):
        self.cp = list(struct.unpack_from("<256I", data, hdr["cp"][0]))
        self.bp = list(struct.unpack_from("<256I", data, hdr["bp"][0]))
        self.xf = list(struct.unpack_from("<4096I", data, hdr["xf"][0]))
        xfr = list(struct.unpack_from("<22I", data, hdr["xfr"][0]))
        # XF regs 0x1000..0x1057 stored as array of 0x58 u32 in Dolphin; header only has 88 bytes = 22 regs
        self.xfreg = {0x1000 + i: v for i, v in enumerate(xfr)}
        self.mem = bytearray(MEM_SIZE)

    def xf_float(self, addr):
        return struct.unpack("<f", struct.pack("<I", self.xf[addr]))[0]

    def write_xf(self, addr, val):
        if addr < 0x1000:
            self.xf[addr] = val
        else:
            self.xfreg[addr] = val

    def read_mem(self, addr, n):
        addr &= 0x01FFFFFF
        if addr + n > MEM_SIZE:
            return bytes(n)
        return bytes(self.mem[addr : addr + n])


def vtx_layout(st: State, vat: int):
    lo = st.cp[0x50]
    hi = st.cp[0x60]
    a = st.cp[0x70 + vat]
    b = st.cp[0x80 + vat]
    c = st.cp[0x90 + vat]
    size = 0
    offs = {}
    if lo & 1:
        offs["pnmtx"] = size
        size += 1
    for t in range(8):
        if (lo >> (1 + t)) & 1:
            size += 1
    pos_t = (lo >> 9) & 3
    nrm_t = (lo >> 11) & 3
    c0_t = (lo >> 13) & 3
    c1_t = (lo >> 15) & 3
    pos_elems = 3 if (a & 1) else 2
    pos_fmt = (a >> 1) & 7
    pos_frac = (a >> 4) & 31
    offs["pos"] = size
    if pos_t == 1:
        size += pos_elems * COMP_SIZE.get(pos_fmt, 4)
    elif pos_t == 2:
        size += 1
    elif pos_t == 3:
        size += 2
    nbt = (a >> 9) & 1
    nrm_fmt = (a >> 10) & 7
    nidx3 = (a >> 31) & 1
    if nrm_t == 1:
        size += (9 if nbt else 3) * COMP_SIZE.get(nrm_fmt, 4)
    elif nrm_t in (2, 3):
        k = 3 if (nbt and nidx3) else 1
        size += k * (1 if nrm_t == 2 else 2)
    for ct, fmt in ((c0_t, (a >> 14) & 7), (c1_t, (a >> 18) & 7)):
        if ct == 1:
            size += CLR_SIZE.get(fmt, 4)
        elif ct == 2:
            size += 1
        elif ct == 3:
            size += 2
    tex_fmt = [
        ((a >> 21) & 1, (a >> 22) & 7),
        ((b >> 0) & 1, (b >> 1) & 7),
        ((b >> 9) & 1, (b >> 10) & 7),
        ((b >> 18) & 1, (b >> 19) & 7),
        ((b >> 27) & 1, (b >> 28) & 7),
        ((c >> 5) & 1, (c >> 6) & 7),
        ((c >> 14) & 1, (c >> 15) & 7),
        ((c >> 23) & 1, (c >> 24) & 7),
    ]
    for t in range(8):
        tt = (hi >> (2 * t)) & 3
        el, fmt = tex_fmt[t]
        if tt == 1:
            size += (2 if el else 1) * COMP_SIZE.get(fmt, 4)
        elif tt == 2:
            size += 1
        elif tt == 3:
            size += 2
    return size, offs, pos_t, pos_fmt, pos_elems, pos_frac


def read_comp(b, o, fmt):
    if fmt == 4:
        return struct.unpack_from(">f", b, o)[0]
    if fmt == 0:
        return b[o]
    if fmt == 1:
        return struct.unpack_from(">b", b, o)[0]
    if fmt == 2:
        return struct.unpack_from(">H", b, o)[0]
    return struct.unpack_from(">h", b, o)[0]


def mtx_rows(st: State, row: int):
    return [st.xf_float(row * 4 + i) for i in range(12)]


def proj(st: State):
    vals = []
    for r in range(0x1020, 0x1027):
        v = st.xfreg.get(r, 0)
        vals.append(struct.unpack("<f", struct.pack("<I", v))[0] if r < 0x1026 else v)
    return vals


def viewport(st: State):
    return [struct.unpack("<f", struct.pack("<I", st.xfreg.get(r, 0)))[0] for r in range(0x101A, 0x1020)]


def decode(path: Path, frames_wanted=None, keep=lambda d: True):
    data = path.read_bytes()
    magic = u32le(data, 0)
    assert magic == FILE_ID
    hdr = {
        "bp": struct.unpack_from("<QI", data, 12),
        "cp": struct.unpack_from("<QI", data, 24),
        "xf": struct.unpack_from("<QI", data, 36),
        "xfr": struct.unpack_from("<QI", data, 48),
    }
    frames_off, frame_count, _flags = struct.unpack_from("<QII", data, 60)
    st = State(data, hdr)
    draws = []
    stats = {"dl_calls": 0, "indx_xf": 0, "unknown": 0}
    for fi in range(frame_count):
        o = frames_off + fi * 64
        fifo_off, fifo_sz, _fs, _fe = struct.unpack_from("<QIII", data, o)
        mem_off, mem_n = struct.unpack_from("<QI", data, o + 20)
        mems = []
        for i in range(mem_n):
            mo = mem_off + i * 24
            fifo_pos, addr, d_off, d_sz, typ = struct.unpack_from("<IIQIB", data, mo)
            mems.append((fifo_pos, addr, d_off, d_sz, typ))
        mems.sort(key=lambda m: m[0])
        mi = 0
        fifo = data[fifo_off : fifo_off + fifo_sz]
        pos = 0

        def apply_mems(upto):
            nonlocal mi
            while mi < len(mems) and mems[mi][0] <= upto:
                _, addr, d_off, d_sz, _t = mems[mi]
                a = addr & 0x01FFFFFF
                if a + d_sz <= MEM_SIZE:
                    st.mem[a : a + d_sz] = data[d_off : d_off + d_sz]
                mi += 1

        def run(buf, base_off, in_dl):
            p = 0
            L = len(buf)
            while p < L:
                if not in_dl:
                    apply_mems(base_off + p)
                cmd = buf[p]
                start = p
                p += 1
                if cmd == 0x00:
                    continue
                if cmd == 0x08:
                    reg = buf[p]
                    val = struct.unpack_from(">I", buf, p + 1)[0]
                    st.cp[reg] = val
                    p += 5
                elif cmd == 0x10:
                    w = struct.unpack_from(">I", buf, p)[0]
                    cnt = (w >> 16) + 1
                    addr = w & 0xFFFF
                    p += 4
                    for i in range(cnt):
                        st.write_xf(addr + i, struct.unpack_from(">I", buf, p + 4 * i)[0])
                    p += 4 * cnt
                elif cmd in (0x20, 0x28, 0x30, 0x38):
                    w = struct.unpack_from(">I", buf, p)[0]
                    p += 4
                    idx = w >> 16
                    cnt = ((w >> 12) & 0xF) + 1
                    addr = w & 0xFFF
                    arr = 12 + ((cmd - 0x20) >> 3)
                    base = st.cp[0xA0 + arr]
                    stride = st.cp[0xB0 + arr]
                    src = st.read_mem(base + idx * stride, cnt * 4)
                    for i in range(cnt):
                        st.write_xf(addr + i, struct.unpack_from(">I", src, 4 * i)[0])
                    stats["indx_xf"] += 1
                elif cmd == 0x40:
                    addr, size = struct.unpack_from(">II", buf, p)
                    p += 8
                    stats["dl_calls"] += 1
                    run(st.read_mem(addr, size), base_off + start, True)
                elif cmd in (0x44, 0x48):
                    pass
                elif cmd == 0x61:
                    val = struct.unpack_from(">I", buf, p)[0]
                    st.bp[val >> 24] = val & 0xFFFFFF
                    p += 4
                elif cmd & 0x80:
                    prim = cmd & 0xF8
                    vat = cmd & 7
                    n = struct.unpack_from(">H", buf, p)[0]
                    p += 2
                    vsz, offs, pos_t, pos_fmt, pos_elems, pos_frac = vtx_layout(st, vat)
                    body = buf[p : p + n * vsz]
                    p += n * vsz
                    cur = st.cp[0x30] & 0x3F
                    d = Draw(
                        frame=fi,
                        off=base_off + start,
                        prim=prim,
                        vat=vat,
                        n=n,
                        vsz=vsz,
                        vcd_lo=st.cp[0x50],
                        vcd_hi=st.cp[0x60],
                        vat_a=st.cp[0x70 + vat],
                        pos_type=pos_t,
                        pos_base=st.cp[0xA0] & 0x01FFFFFF,
                        pos_stride=st.cp[0xB0],
                        pos_fmt=pos_fmt,
                        pos_elems=pos_elems,
                        pos_frac=pos_frac,
                        pnmtx_direct=bool(st.cp[0x50] & 1),
                        cur_mtx=cur,
                        mtx=mtx_rows(st, cur),
                        proj=proj(st),
                        viewport=viewport(st),
                        cull=(st.bp[0x00] >> 14) & 3,
                        tex0=st.bp[0x94] & 0xFFFFFF,
                    )
                    if keep(d) and len(body) == n * vsz and pos_t in (2, 3):
                        po = offs["pos"]
                        for v in range(n):
                            vo = v * vsz
                            if pos_t == 3:
                                idx = (body[vo + po] << 8) | body[vo + po + 1]
                            else:
                                idx = body[vo + po]
                            d.pos_idx.append(idx)
                            if d.pnmtx_direct:
                                pn = body[vo + offs["pnmtx"]]  # XF row index (matrix n = row 3n)
                                d.pn_idx.append(pn)
                                if pn not in d.mtx_rows:
                                    d.mtx_rows[pn] = mtx_rows(st, pn)
                        cs = COMP_SIZE.get(pos_fmt, 4)
                        scale = 1.0 / (1 << pos_frac) if pos_fmt != 4 else 1.0
                        for idx in set(d.pos_idx):
                            raw = st.read_mem(d.pos_base + idx * d.pos_stride, pos_elems * cs)
                            comps = [read_comp(raw, k * cs, pos_fmt) * scale for k in range(pos_elems)]
                            if pos_elems == 2:
                                comps.append(0.0)
                            d.verts[idx] = tuple(comps)
                        draws.append(d)
                else:
                    stats["unknown"] += 1
                    # cannot resync reliably; stop this buffer
                    print(f"unknown cmd 0x{cmd:02X} at frame {fi} off {base_off + start}", file=sys.stderr)
                    return

        run(fifo, 0, False)
        apply_mems(1 << 62)
        if frames_wanted is not None and fi + 1 >= frames_wanted:
            break
    return draws, stats


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    nf = int(sys.argv[3]) if len(sys.argv) > 3 else None
    draws, stats = decode(src, nf)
    print(stats, "draws kept:", len(draws))
    with out.open("wb") as f:
        pickle.dump(draws, f)
