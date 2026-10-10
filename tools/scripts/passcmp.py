"""Per-pass frame-time distribution of GTA V benchmark folders (newest set in each): frames, seconds, median, and the
time spent in frame-time buckets. usage: passcmp.py DIR..."""
import glob
import os
import re
import statistics
import sys

for d in sys.argv[1:]:
    f = sorted(glob.glob(os.path.join(d, "Benchmark-*.txt")))[-1]
    stamp = re.search(r"Benchmark-(.*)\.txt", f).group(1)
    for n in range(5):
        p = os.path.join(d, f"FrameTimes-Pass{n}-{stamp}.txt")
        fr = [float(l.split()[1]) for l in open(p) if re.match(r"^\d+\s+[\d.]+", l)]
        b = {"<25": 0.0, "25-50": 0.0, "50-100": 0.0, ">100": 0.0}
        for x in fr:
            k = "<25" if x < 25 else "25-50" if x < 50 else "50-100" if x < 100 else ">100"
            b[k] += x / 1000
        print(f"{os.path.basename(d)[7:]:16} pass{n} {len(fr):4d} fr {sum(fr) / 1000:5.1f} s  median {statistics.median(fr):5.1f} ms  "
              + "  ".join(f"{k} {v:4.1f}s" for k, v in b.items()) + f"  max {max(fr):.0f}")
