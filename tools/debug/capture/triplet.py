"""triplet.py <mp4> <unique-frame k> <out.png> [x0 y0 x1 y1]: frames k-1, k, k+1 side by side (crop) + (k - mean(k-1,k+1)) x4"""
import os, sys, subprocess, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffbin
FF, FP = ffbin.ffmpeg(), ffbin.ffprobe()
f, k, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
W, H = map(int, subprocess.run([FP, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', f],
                               capture_output=True, text=True).stdout.strip().split(','))
box = tuple(map(int, sys.argv[4:8])) if len(sys.argv) > 7 else (0, 0, W, H)
p = subprocess.run([FF, '-v', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W, 3)
g = a.astype(np.float32).mean(axis=3)
keep = [0] + [i for i in range(1, len(a)) if np.abs(g[i] - g[i - 1]).mean() > 0.05]
x0, y0, x1, y1 = box
fr = [a[keep[j]][y0:y1, x0:x1] for j in (k - 1, k, k + 1)]
d = np.clip((fr[1].astype(int) - (fr[0].astype(int) + fr[2].astype(int)) // 2) * 4 + 128, 0, 255).astype(np.uint8)
Image.fromarray(np.concatenate([np.concatenate(fr[:2], 1), np.concatenate([fr[2], d], 1)], 0)).save(out)
