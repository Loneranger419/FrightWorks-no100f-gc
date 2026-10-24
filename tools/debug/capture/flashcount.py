"""flashcount.py <mp4>: count one-frame brightness flashes in the lower half of a recording (record.ps1 output).

Duplicate frames (capture faster than the game) are dropped first; frame indices are in unique-frame numbering (for triplet.py).
"""
import sys, subprocess, numpy as np
FF, FP = r'C:\Utilities\ffmpeg\bin\ffmpeg', r'C:\Utilities\ffmpeg\bin\ffprobe'
f = sys.argv[1]
W, H = map(int, subprocess.run([FP, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                'stream=width,height', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip().split(','))
p = subprocess.run([FF, '-v', 'error', '-i', f, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W).astype(np.float32)
keep = [0] + [i for i in range(1, len(a)) if np.abs(a[i] - a[i - 1]).mean() > 0.05]
a = a[keep]
# 8x16 grid over the lower half; a "flash" = a cell that rises >3 for exactly one frame and comes back
ch, cw = H // 2 // 8, W // 16
g = a[:, H - 8 * ch:, :16 * cw].reshape(len(a), 8, ch, 16, cw).mean(axis=(2, 4))
flash = (g[1:-1] - np.maximum(g[:-2], g[2:])) > 3
print(f'{f}: unique frames {len(a)}, flash cells {int(flash.sum())}, frames with a flash {int(flash.any(axis=(1,2)).sum())}')
idx = [i + 1 for i in range(len(flash)) if flash[i].any()]
print('flash frame indices (unique-frame numbering):', idx[:40])
