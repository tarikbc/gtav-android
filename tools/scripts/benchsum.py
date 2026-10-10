"""Summarize GTA V benchmark output folders (Benchmark-<t>.txt + FrameTimes-Pass<n>-<t>.txt), newest set per folder.
usage: benchsum.py DIR [DIR ...]   prints one row per DIR: per-pass avg FPS, overall FPS (all frames / all time),
median and p99 frame time, frames over 50 and 100 ms"""
import glob
import os
import re
import statistics
import sys

rows = []
for d in sys.argv[1:]:
    sums = sorted(glob.glob(os.path.join(d, "Benchmark-*.txt")))
    if not sums:
        print(d, "no Benchmark-*.txt")
        continue
    stamp = re.search(r"Benchmark-(.*)\.txt", sums[-1]).group(1)
    txt = open(sums[-1], errors="replace").read()
    avgs = [float(m) for m in re.findall(r"^Pass \d+, [\d.]+, [\d.]+, ([\d.]+)$", txt.split("Time in milliseconds")[0], re.M)]
    frames = []
    for n in range(5):
        f = os.path.join(d, f"FrameTimes-Pass{n}-{stamp}.txt")
        if os.path.exists(f):
            frames += [float(l.split()[1]) for l in open(f) if re.match(r"^\d+\s+[\d.]+", l)]
    fps = len(frames) * 1000 / sum(frames) if frames else 0
    q = statistics.quantiles(frames, n=100) if len(frames) > 100 else [0] * 99
    print(f"{os.path.basename(d.rstrip('/')):22} passes {' / '.join(f'{a:.1f}' for a in avgs)}  overall {fps:.1f} FPS  "
          f"median {statistics.median(frames):.1f} ms  p99 {q[98]:.1f} ms  >50 ms {sum(f > 50 for f in frames)}  "
          f">100 ms {sum(f > 100 for f in frames)}  ({len(frames)} frames)")
