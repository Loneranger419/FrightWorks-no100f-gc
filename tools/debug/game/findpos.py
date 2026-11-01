"""findpos.py <dump.bin> X Y Z [tol]: addresses of float triples near (X,Y,Z) in a postool MEM1 dump."""
import sys, numpy as np
d = np.frombuffer(open(sys.argv[1], 'rb').read(), dtype='>f4')
x, y, z = map(float, sys.argv[2:5]); tol = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
with np.errstate(invalid='ignore'):
    m = (np.abs(d[:-2] - x) < tol) & (np.abs(d[1:-1] - y) < tol) & (np.abs(d[2:] - z) < tol)
for i in np.nonzero(m)[0][:60]:
    print(f"{0x80000000 + i*4:08X}  {d[i]:9.3f} {d[i+1]:8.3f} {d[i+2]:9.3f}")
