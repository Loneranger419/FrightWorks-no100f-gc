"""Decode the disc's memory-card icon (files/SD2GCIcon.tpl: 32x32 RGB5A3 frames) to RGBA PNGs.
Usage: tpl_icon.py <SD2GCIcon.tpl> <out prefix>  ->  <prefix>-<frame>.png"""
import struct, sys, zlib
b = open(sys.argv[1], 'rb').read()
n, table = struct.unpack('>II', b[4:12])
def rgb5a3(v):
    if v & 0x8000: return ((v >> 10 & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v & 31) * 255 // 31, 255)
    return ((v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17, (v >> 12 & 7) * 255 // 7)
def png(w, h, px):
    raw = b''.join(b'\0' + bytes(c for p in px[y*w:(y+1)*w] for c in p) for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
for i in range(n):
    io = struct.unpack('>I', b[table + i * 8:table + i * 8 + 4])[0]
    h, w, fmt, data = struct.unpack('>HHII', b[io:io + 12])
    assert fmt == 5, 'expected RGB5A3'
    px = [None] * (w * h)
    k = data
    for ty in range(0, h, 4):  # 4x4 tiles
        for tx in range(0, w, 4):
            for y in range(4):
                for x in range(4):
                    px[(ty + y) * w + tx + x] = rgb5a3(struct.unpack('>H', b[k:k + 2])[0]); k += 2
    open(f'{sys.argv[2]}-{i}.png', 'wb').write(png(w, h, px))
