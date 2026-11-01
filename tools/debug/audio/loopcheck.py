# loopcheck.py <AUDIO_RAW_DUMP file> [--skip S] [--len S] [--scan W]: is the output stuck repeating a short loop?
# Dump = BE16 stereo, 32 kHz. Takes a mono window, finds the lag between 0.2 and 4 s where the signal best matches
# itself, and prints its normalised correlation. Stuck music (a ring buffer that is never refilled) repeats almost
# sample for sample: ~0.95-1.0. Real music: well below that (~0.1 in h001).
# --scan W: check the whole dump in W-second windows and print one line each (where in a long session it got stuck).
# --selftest: tile 0.875 s of the dump and check that it is flagged.
import sys
import numpy as np

RATE = 32000

def best_repeat(seg):
    seg = seg - seg.mean()
    lo, hi, n = int(0.2 * RATE), int(4 * RATE), len(seg)
    f = np.fft.rfft(seg, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:hi + 1]
    e = np.concatenate([[0], np.cumsum(seg ** 2)])  # normalise per lag by the energy of the overlapping parts
    lags = np.arange(lo, hi + 1)
    r = ac[lo:hi + 1] / np.maximum(np.sqrt((e[n] - e[lags]) * (e[n - lags] - e[0])), 1e-9)
    i = int(np.argmax(r))
    return lags[i] / RATE, r[i]

path = sys.argv[1]
args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
x = np.fromfile(path, dtype=">i2").astype(np.float64).reshape(-1, 2).mean(axis=1)
print(f"{path}: {len(x) / RATE:.1f} s, peak {np.abs(x).max():.0f}")
if "--selftest" in sys.argv:
    chunk = x[int(10 * RATE):int(10.875 * RATE)]
    lag, r = best_repeat(np.tile(chunk, 12) + np.random.default_rng(0).normal(0, 300, len(chunk) * 12))
    print(f"selftest (0.875 s tiled + noise): lag {lag:.4f} s, correlation {r:.3f}")
elif "--scan" in args:
    w = float(args["--scan"])
    for s in np.arange(0, len(x) / RATE - w + 0.01, w):
        seg = x[int(s * RATE):int((s + w) * RATE)]
        if np.abs(seg).max() < 200:
            print(f"{s:7.0f} s  silent"); continue
        lag, r = best_repeat(seg)
        print(f"{s:7.0f} s  lag {lag:.3f} s  corr {r:.3f}{'  STUCK LOOP' if r > 0.9 else ''}")
else:
    skip, length = float(args.get("--skip", 8)), float(args.get("--len", 10))
    seg = x[int(skip * RATE):int((skip + length) * RATE)]
    if len(seg) < 6 * RATE:
        sys.exit("too short")
    lag, r = best_repeat(seg)
    print(f"best repeat: lag {lag:.4f} s ({int(lag * RATE)} samples), correlation {r:.3f}"
          f" -> {'STUCK LOOP' if r > 0.9 else 'not looping'}")
