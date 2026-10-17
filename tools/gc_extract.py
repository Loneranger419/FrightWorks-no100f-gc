"""Extract a plain GameCube disc image (.iso/.gcm) to <out>/sys and <out>/files (same layout as the launcher).

Usage: python gc_extract.py <image> <out dir>
"""
import os, struct, sys

def main():
    image, out = sys.argv[1], sys.argv[2]
    f = open(image, 'rb')
    def read(off, n):
        f.seek(off); return f.read(n)
    hdr = read(0, 0x440)
    assert struct.unpack('>I', hdr[0x1C:0x20])[0] == 0xC2339F3D, 'not a GameCube disc'
    dol_off, fst_off, fst_size = struct.unpack('>III', hdr[0x420:0x42C])
    sysd, files = os.path.join(out, 'sys'), os.path.join(out, 'files')
    os.makedirs(sysd, exist_ok=True); os.makedirs(files, exist_ok=True)
    open(os.path.join(sysd, 'boot.bin'), 'wb').write(hdr)
    open(os.path.join(sysd, 'bi2.bin'), 'wb').write(read(0x440, 0x2000))
    ap = read(0x2440, 0x20)
    open(os.path.join(sysd, 'apploader.img'), 'wb').write(read(0x2440, 0x20 + struct.unpack('>I', ap[0x14:0x18])[0] + struct.unpack('>I', ap[0x18:0x1C])[0]))
    dh = read(dol_off, 0x100)
    size = max(struct.unpack('>I', dh[i*4:i*4+4])[0] + struct.unpack('>I', dh[0x90+i*4:0x94+i*4])[0] for i in range(18))
    open(os.path.join(sysd, 'main.dol'), 'wb').write(read(dol_off, size))
    fst = read(fst_off, fst_size)
    open(os.path.join(sysd, 'fst.bin'), 'wb').write(fst)
    count = struct.unpack('>I', fst[8:12])[0]; strtab = count * 12
    def name(i):
        s = strtab + (struct.unpack('>I', fst[i*12:i*12+4])[0] & 0xFFFFFF)
        return fst[s:fst.index(b'\0', s)].decode('latin1')
    stack, n = [(count, files)], 0
    for i in range(1, count):
        while i >= stack[-1][0]: stack.pop()
        path = os.path.join(stack[-1][1], name(i))
        flags, off, sz = struct.unpack('>III', fst[i*12:i*12+12])
        if flags >> 24:
            os.makedirs(path, exist_ok=True); stack.append((sz, path)); continue
        with open(path, 'wb') as o:
            p = 0
            while p < sz:
                chunk = read(off + p, min(1 << 22, sz - p)); o.write(chunk); p += len(chunk)
        n += 1
    print('extracted %d files' % n)

if __name__ == '__main__':
    main()
