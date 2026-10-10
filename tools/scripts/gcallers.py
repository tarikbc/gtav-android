"""Who waits, and on what: for the busiest GTA5.exe threads, the AoE agent's `callers` command samples the thread
and, for the samples inside one ntdll syscall stub, histograms RCX (the first argument: the handle for
NtWaitForSingleObject, the alertable flag for NtDelayExecution) and the GTA5.exe return addresses on the stack.
The stub RVAs are those of proton-11.0-99-arm64ec's ntdll (second stub table, found by the RIP profile of
2026-10-10, see docs/how-it-works/PERFORMANCE.md); the sampled PC lands one instruction past the stub's `ret`, so
each range is widened by 4 bytes. For another ntdll, find the stubs with ripmap.py and the export table.
usage: gcallers.py LABEL [top_n] [samples]"""
import os
import re
import sys
import time

import thor
import agent  # noqa: E402

label = sys.argv[1]
top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
samples = int(sys.argv[3]) if len(sys.argv) > 3 else 300
STUBS = {"NtWaitForSingleObject": (0xC6468, 0xC6480), "NtDelayExecution": (0xC5160, 0xC5178),
         "NtReleaseSemaphore": (0xC5D84, 0xC5D9C), "NtSetEvent": (0xC5FEC, 0xC6004)}
out = open(os.path.join(thor.RESULTS, f"gcallers_{label}.txt"), "w")


def say(s):
    print(s, flush=True)
    out.write(s + "\n")
    out.flush()


agent.start()
agent.call("target GTA5.exe")
m = re.search(r"base=([0-9a-f]+)", agent.call("mod ntdll.dll")[0])
base = int(m.group(1), 16)
say(f"{label}: ntdll base {base:#x}")


def snap():
    rows = {}
    for l in agent.call("threads", timeout=60)[1:]:
        m = re.match(r"tid (\w+) start=(\S+) user=(\d+) kernel=(\d+)", l)
        if m:
            rows[m.group(1)] = (m.group(2), int(m.group(3)) + int(m.group(4)))
    return rows


a = snap()
time.sleep(8)
b = snap()
busy = sorted(((b[t][1] - a[t][1], t, b[t][0]) for t in b if t in a), reverse=True)[:top_n]
for ms, tid, start in busy:
    say(f"{label}: thread {tid} start {start} ({ms / 80:.0f} % of a core)")
    for name, (lo, hi) in STUBS.items():
        rsp = agent.call(f"callers #{tid} {samples} 10 {base + lo:x} {base + hi + 4:x}", timeout=samples * 0.05 + 90)
        hits = [l for l in rsp[1:] if l.strip()]
        say(f"  {name}: {rsp[0]}")
        for l in hits[:12]:
            say("     " + l)
