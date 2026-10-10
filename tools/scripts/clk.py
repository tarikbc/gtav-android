"""CPU and GPU clocks of the Thor over adb every 5 s for N seconds (shell builtins only, no root); prints each sample
and a summary (min / mean / max per clock, samples at a lower clock than the first). usage: clk.py SECONDS"""
import sys
import time

import thor

CMD = ("read a < /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; read b < /sys/devices/system/cpu/cpu3/cpufreq/scaling_cur_freq; "
       "read c < /sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq; read g < /sys/class/kgsl/kgsl-3d0/gpuclk; "
       "read u < /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage; read t < /sys/class/thermal/thermal_zone0/temp; echo $a $b $c $g $u $t")
rows = []
t0 = time.time()
limit = float(sys.argv[1]) if len(sys.argv) > 1 else 300
while time.time() - t0 < limit:
    out = [x for x in thor.sh(CMD).replace("%", " ").split() if x.isdigit()]
    if len(out) >= 5:
        v = [int(x) for x in out[:6]]
        rows.append(v)
        print(f"{time.time() - t0:5.0f} s cpu0 {v[0] // 1000} cpu3 {v[1] // 1000} cpu7 {v[2] // 1000} MHz  gpu {v[3] // 1000000} MHz busy {v[4]} %", flush=True)
    time.sleep(5)
names = ["cpu0 MHz", "cpu3 MHz", "cpu7 MHz", "gpu MHz", "gpu busy %"]
div = [1000, 1000, 1000, 1000000, 1]
for i, n in enumerate(names):
    col = [r[i] / div[i] for r in rows]
    if not col:
        break
    below = sum(1 for x in col if x < col[0] * 0.95)
    print(f"{n}: min {min(col):.0f} mean {sum(col) / len(col):.0f} max {max(col):.0f}; samples under 95 % of the first: {below}/{len(col)}")
