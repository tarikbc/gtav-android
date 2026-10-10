"""Where GTA5.exe's threads run: samples /proc/<pid>/task/*/stat every second for N seconds (no root; one adb shell
call per sample), then prints the busiest threads with their CPU time in the window and a histogram of the core they
were on at each sample (cpu0-2 little, cpu3-6 big, cpu7 prime on the Thor), plus Cpus_allowed_list.
usage: corewatch.py [seconds] [exe]"""
import sys
import time

import thor

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 60
exe = sys.argv[2] if len(sys.argv) > 2 else "GTA5.exe"

pid = ""
for l in thor.sh("ps -A -o PID,NAME").splitlines():
    if l.rstrip().endswith(exe):
        pid = l.split()[0]
if not pid:
    sys.exit(f"{exe} not running")
allowed = thor.sh(f"grep Cpus_allowed_list /proc/{pid}/status").strip()
first = {}
last = {}
hist = {}
t0 = time.time()
n = 0
while time.time() - t0 < secs:
    out = thor.sh(f"cat /proc/{pid}/task/*/stat 2>/dev/null")
    n += 1
    for l in out.splitlines():
        if ")" not in l:
            continue
        head, rest = l.split(")", 1)
        tid = head.split()[0]
        f = rest.split()
        # after the comm field: state(0) ppid(1) ... utime(11) stime(12) ... processor(36)
        cpu_ms = (int(f[11]) + int(f[12])) * 10
        core = int(f[36])
        first.setdefault(tid, cpu_ms)
        last[tid] = cpu_ms
        hist.setdefault(tid, [0] * 8)[core] += 1
    time.sleep(1)
dt = time.time() - t0
rows = sorted(((last[t] - first[t], t) for t in last), reverse=True)[:8]
print(f"{exe} pid {pid} {allowed}; {len(last)} threads, {n} samples over {dt:.0f} s")
for ms, t in rows:
    h = hist[t]
    little, big, prime = sum(h[:3]), sum(h[3:7]), h[7]
    print(f"  tid {int(t):5d} {ms / dt / 10:5.1f} % of a core; on little {little:3d} big {big:3d} prime {prime:3d} samples; per core {h}")
