"""CPU profile of GTA5.exe with the AoE agent (ageofempires-android's tools/probes/aoeagent.exe, a GUI exe, so no
console takes the focus): the busiest threads over a window (user+kernel ms from two thread snapshots), their
names, then RIP samples of each of the top threads split by module (GTA5.exe code, DXVK d3d11/dxgi, ntdll, FEX,
Vulkan, ...). Sampling suspends the thread 300 times, which costs the run a few FPS: do not record that run's FPS.
Run while GTA V draws. Needs AOE_REPO (thor.py). The raw samples go to D:\\aoe\\agent\\rips_<label>_<tid>.txt
(/sdcard/Download/aoe/agent/) for ripmap.py.
usage: gprof.py LABEL [top_n] [samples] [window_s]   top_n 0 = thread list only, no sampling"""
import os
import re
import sys
import time

import thor
import agent  # noqa: E402  (from the AoE repo, on sys.path through thor)

label = sys.argv[1]
top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 300
window = float(sys.argv[4]) if len(sys.argv) > 4 else 10
out = open(os.path.join(thor.RESULTS, f"gprof_{label}.txt"), "w")


def say(s):
    print(s, flush=True)
    out.write(s + "\n")
    out.flush()


say(f"{label}: agent {agent.start()}")
say(f"{label}: {agent.call('target GTA5.exe')[0]}")
say(f"{label}: {agent.call('ping')[0]}")


def snap():
    rows = {}
    for l in agent.call("threads", timeout=60)[1:]:
        m = re.match(r"tid (\w+) start=(\S+) user=(\d+) kernel=(\d+) affinity=(\w+)", l)
        if m:
            rows[m.group(1)] = (m.group(2), int(m.group(3)), int(m.group(4)), m.group(5))
    return rows


a = snap()
t0 = time.time()
time.sleep(window)
b = snap()
dt = (time.time() - t0) * 1000
names = {}
for l in agent.call("prio list", timeout=60)[1:]:
    m = re.match(r"tid (\w+) prio (-?\d+) name ?(.*)", l)
    if m:
        names[m.group(1)] = (m.group(3).strip(), m.group(2))
busy = []
for tid, (start, u, k, aff) in b.items():
    if tid in a:
        du, dk = u - a[tid][1], k - a[tid][2]
        busy.append((du + dk, du, dk, tid, start, aff))
busy.sort(reverse=True)
tot = sum(x[0] for x in busy)
say(f"{label}: {len(b)} threads; CPU over {dt / 1000:.1f} s: {tot / dt * 100:.0f} % of one core in total")
for ms, du, dk, tid, start, aff in busy[:20]:
    nm, pr = names.get(tid, ("", "?"))
    say(f"  tid {tid} {ms / dt * 100:5.1f} % (user {du} kernel {dk} ms) prio {pr} aff {aff} start {start} name '{nm}'")
for ms, du, dk, tid, start, aff in busy[:top_n]:
    rsp = agent.call(f"sample #{tid} {samples} 10 D:\\aoe\\agent\\rips_{label}_{tid}.txt", timeout=samples * 0.05 + 60)
    say(f"{label}: tid {tid} '{names.get(tid, ('', ''))[0]}' {ms / dt * 100:.0f} %: {rsp[0]}")
    for l in rsp[1:]:
        say("    " + l)
for m in ("GTA5.exe", "d3d11.dll", "dxgi.dll", "ntdll.dll", "libarm64ecfex.dll", "winevulkan.dll"):
    try:
        say(f"{label}: mod {m}: {agent.call(f'mod {m}')[0]}")
    except RuntimeError as e:
        say(f"{label}: mod {m}: {e}")
