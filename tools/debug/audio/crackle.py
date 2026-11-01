"""Find crackle candidates in an AUDIO_RAW_DUMP capture (BE16 stereo, right/left pairs, 32 kHz by default).

usage: crackle.py <dump.raw> [--fmt ai|bus|mono16] [--rate 32000] [--wav out.wav] [--top 25] [--from S] [--to S]

Reports, per channel:
  * near-full-scale samples (|x| >= 32000) and samples in the output limiter's knee (|x| > 24576),
  * flat tops: runs of >= 3 identical samples at |x| >= 20000 (a hard clamp somewhere upstream),
  * clicks: second-difference spikes far above the local level (a step or kink a smooth waveform can't make),
  * gaps: runs of >= 64 exact zeros between non-silent audio (dropped/zeroed blocks).
Then a per-second table and the strongest click times, so they can be lined up with what a listener heard.
--wav writes a normal little-endian L/R WAV of the capture (or the --from/--to slice) to listen to.
"""
import argparse
import sys
import wave

import numpy as np

KNEE = 24576
NEAR_FULL = 32000


def load(path, rate, t0, t1, fmt="ai"):
    if fmt == "bus":  # AX_DIAG_DIR bus.raw: LE int32, left/right, before the output limiter
        raw = np.fromfile(path, dtype="<i4")
        lr = raw[: len(raw) // 2 * 2].reshape(-1, 2).astype(np.int64)
    elif fmt == "mono16":  # AX_DIAG_DIR voice dumps: LE int16 mono
        raw = np.fromfile(path, dtype="<i2").astype(np.int64)
        lr = np.stack([raw, raw], 1)
    else:
        raw = np.fromfile(path, dtype=">i2")
        raw = raw[: len(raw) // 2 * 2].reshape(-1, 2)
        lr = raw[:, ::-1].astype(np.int32)  # AI order is right, left
    a = int(t0 * rate) if t0 else 0
    b = int(t1 * rate) if t1 else len(lr)
    return lr[a:b], a


def runs(mask):
    """(start, length) of True runs."""
    if not mask.any():
        return np.empty(0, int), np.empty(0, int)
    d = np.diff(np.concatenate(([0], mask.view(np.int8), [0])))
    s = np.nonzero(d == 1)[0]
    e = np.nonzero(d == -1)[0]
    return s, e - s


def local_level(x, win):
    """Moving median-ish level: moving mean of |x| over win samples (cheap, robust enough for spikes)."""
    k = np.ones(win) / win
    return np.convolve(np.abs(x), k, mode="same")


def analyse(ch, rate):
    x = ch.astype(np.int64)
    res = {}
    res["near_full"] = np.nonzero(np.abs(x) >= NEAR_FULL)[0]
    res["knee"] = np.nonzero(np.abs(x) > KNEE)[0]

    same = np.concatenate(([False], x[1:] == x[:-1])) & (np.abs(x) >= 20000)
    s, n = runs(same)
    keep = n >= 2  # 2 repeats after the first = 3 identical samples
    res["flat"] = s[keep] - 1

    d2 = np.zeros_like(x)
    d2[1:-1] = x[2:] - 2 * x[1:-1] + x[:-2]
    lvl = local_level(d2, int(rate * 0.005)) + 64  # 5 ms window; floor so silence doesn't flag dither
    score = np.abs(d2) / lvl
    cand = np.nonzero((score > 12) & (np.abs(d2) > 2000))[0]
    # Merge hits closer than 2 ms into one event, keep its strongest sample.
    events = []
    for i in cand:
        if events and i - events[-1][0] < rate * 0.002:
            if score[i] > events[-1][1]:
                events[-1] = (i, score[i], int(d2[i]))
        else:
            events.append((i, score[i], int(d2[i])))
    res["clicks"] = events

    zero = x == 0
    s, n = runs(zero)
    loud = local_level(x, int(rate * 0.02))
    gaps = [(int(st), int(ln)) for st, ln in zip(s, n)
            if ln >= 64 and st > 0 and st + ln < len(x) and loud[max(st - 1, 0)] > 200]
    res["gaps"] = gaps
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--rate", type=int, default=32000)
    ap.add_argument("--wav")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--from", dest="t0", type=float)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--fmt", choices=["ai", "bus", "mono16"], default="ai")
    a = ap.parse_args()

    lr, base = load(a.dump, a.rate, a.t0, a.t1, a.fmt)
    rate = a.rate
    secs = len(lr) / rate
    off = base / rate
    print(f"{a.dump}: {secs:.1f} s at {rate} Hz (starting {off:.1f} s), peak L {np.abs(lr[:, 0]).max()} R {np.abs(lr[:, 1]).max()}")

    per_sec = {}
    allclicks = []
    for c, name in enumerate("LR"):
        r = analyse(lr[:, c], rate)
        print(f"  {name}: near-full {len(r['near_full'])}  in-knee {len(r['knee'])}  flat-tops {len(r['flat'])}  "
              f"clicks {len(r['clicks'])}  gaps {len(r['gaps'])}")
        for key in ("near_full", "knee", "flat"):
            for i in r[key]:
                per_sec.setdefault(int(i / rate), {}).setdefault(key, 0)
                per_sec[int(i / rate)][key] += 1
        for i, sc, d in r["clicks"]:
            per_sec.setdefault(int(i / rate), {}).setdefault("clicks", 0)
            per_sec[int(i / rate)]["clicks"] += 1
            allclicks.append((sc, i, name, d, int(lr[i, c])))
        for st, ln in r["gaps"]:
            per_sec.setdefault(int(st / rate), {}).setdefault("gaps", 0)
            per_sec[int(st / rate)]["gaps"] += 1
            print(f"    gap {name} at {off + st / rate:8.3f} s, {ln} samples ({ln / rate * 1000:.1f} ms)")

    print("\n  second   peak  knee  flat clicks gaps")
    for s in sorted(per_sec):
        seg = lr[s * rate:(s + 1) * rate]
        p = per_sec[s]
        print(f"  {off + s:6.0f} {np.abs(seg).max():6d} {p.get('knee', 0):5d} {p.get('flat', 0):5d} "
              f"{p.get('clicks', 0):6d} {p.get('gaps', 0):4d}")

    allclicks.sort(reverse=True)
    print(f"\n  strongest clicks (score = |2nd diff| / local level):")
    for sc, i, name, d, v in allclicks[: a.top]:
        print(f"    {off + i / rate:9.4f} s  frame {(base + i) // 160:6d}  {name}  score {sc:6.1f}  d2 {d:7d}  sample {v:6d}")

    if a.wav:
        with wave.open(a.wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(np.clip(lr, -32768, 32767).astype("<i2").tobytes())
        print(f"\n  wrote {a.wav}")


if __name__ == "__main__":
    sys.exit(main())
