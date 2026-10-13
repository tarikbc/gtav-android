"""One run of GTA V's built-in benchmark on the Thor (A:\\commandline.txt must hold -benchmark -benchmarkFrameTimes,
see bats/cmdline_on.bat or --setup): relaunch through GameNative (epic_play.py), wait for GTA5.exe, then poll the
Benchmarks folder with the windowless wbench.exe (a console window would take the game's focus) until a new result
appears; pull it, print the per-pass FPS (benchsum.py), and the GameNative PowerMetrics (CPU/GPU load and
temperature) seen during the run. GTA V exits by itself after the benchmark, so the folder is listed once more after
the process is gone.
usage: gbench.py [--setup] [--trim] [--attach] LABEL [timeout_min]
  --setup   write A:\\commandline.txt early in this start, before GTA5.exe runs (needs bats/cmdline_on.bat)
  --trim    end Social Club's audio and video-capture helpers once GTA5.exe runs (wkill.exe @utility:audio ...)
  --attach  no restart: wait for GTA5.exe in the session that is already open
Needs D:\\gtav-android\\wbench.exe and wkill.exe (tools/build.sh) on the Thor."""
import os
import re
import subprocess
import sys
import threading
import time

import thor

HERE = os.path.dirname(os.path.abspath(__file__))
trim = "--trim" in sys.argv
setup = "--setup" in sys.argv
attach = "--attach" in sys.argv
args = [a for a in sys.argv[1:] if a not in ("--setup", "--trim", "--attach")]
label = args[0]
limit = float(args[1]) * 60 if len(args) > 1 else 20 * 60
adb, sh, exes = thor.adb, thor.sh, thor.exes


def bench_listing():
    sh(f"rm -f {thor.TOOLS_DIR}/wbench.txt")
    thor.winexec("D:\\gtav-android\\wbench.exe", "")
    for _ in range(20):
        time.sleep(1)
        out = sh(f"cat {thor.TOOLS_DIR}/wbench.txt")
        if "files in" in out:
            return out
    return ""


peak = {}  # process name -> max RSS (kB); "MemAvailable" -> min
sc_list = []
stop_mem = False


def mem_sampler():
    while not stop_mem:
        out = sh("ps -A -o RSS,NAME; grep MemAvailable /proc/meminfo; echo KGSL $(cat /sys/class/kgsl/kgsl/page_alloc)")
        tot = 0
        if "aff" not in peak:
            pid_out = sh("for p in $(ps -A -o PID,NAME | grep -i 'A:.GTA5.exe' | cut -c1-6); do grep -E 'Cpus_allowed_list|Threads' /proc/$p/status; done")
            if "Cpus_allowed_list" in pid_out:
                peak["aff"] = " ".join(pid_out.split())
                print(f"{label}: GTA5.exe {peak['aff']}", flush=True)
        for l in out.splitlines():
            if l.startswith("KGSL "):
                v = int(l.split()[1]) // 1024
                peak["GPU memory (kgsl)"] = max(peak.get("GPU memory (kgsl)", 0), v)
                continue
            if l.startswith("MemAvailable"):
                v = int(l.split()[1])
                peak["MemAvailable"] = min(peak.get("MemAvailable", v), v)
                continue
            parts = l.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                name = parts[1].split("\\")[-1].strip()
                if name.endswith(".exe") or "gamenative" in name or "wine" in name:
                    tot += int(parts[0])
                peak[name] = max(peak.get(name, 0), int(parts[0])) if not name.startswith("SocialClubHelper") else peak.get(name, 0)
        scl = sorted((int(l.split()[0]) for l in out.splitlines() if "SocialClubHelper" in l and l.split()[0].isdigit()), reverse=True)
        sc = sum(scl)
        if sc > peak.get("SocialClubHelper (all)", 0):
            peak["SocialClubHelper (all)"] = sc
            sc_list[:] = scl
        peak["game session total"] = max(peak.get("game session total", 0), tot)
        time.sleep(10)


def mem_report():
    top = sorted(((v, k) for k, v in peak.items() if k not in ("MemAvailable", "aff")), reverse=True)[:10]
    print(f"{label}: memory peaks (MB): " + ", ".join(f"{k} {v / 1024:.0f}" for v, k in top) +
          f"; MemAvailable min {peak.get('MemAvailable', 0) / 1024:.0f} MB; SocialClubHelper each (MB): "
          + " ".join(str(v // 1024) for v in sc_list), flush=True)


threading.Thread(target=mem_sampler, daemon=True).start()
adb("logcat", "-c")
for attempt in range(1, 4):  # the Rockstar launcher sometimes ends on its own before the game; a new start gets past it
    if attach:
        t0 = time.time()
        if thor.wait_gta5(limit, label):
            break
        sys.exit(f"{label}: GTA5.exe did not start in {limit / 60:.0f} min (attach)")
    subprocess.run(["python3", os.path.join(HERE, "epic_play.py")], capture_output=True)
    t0 = time.time()
    if setup:
        for _ in range(180):
            if "winhandler.exe" in exes():
                break
            time.sleep(1)
        else:
            print(f"{label}: start {attempt}: no session after 180 s", flush=True)
            continue
        time.sleep(5)  # winhandler's port opens a few seconds after the process appears
        out = subprocess.run(["python3", os.path.join(HERE, "runbat.py"), os.path.join(HERE, "bats", "cmdline_on.bat")],
                             capture_output=True, text=True).stdout
        print(f"{label}: commandline.txt: {' | '.join(l.strip() for l in out.splitlines() if l.strip())}", flush=True)
    if thor.wait_gta5(240, label):
        break
    print(f"{label}: start {attempt}: GTA5.exe did not start in 240 s", flush=True)
else:
    sys.exit(f"{label}: GTA5.exe did not start in 3 tries")
print(f"{label}: GTA5.exe after {time.time() - t0:.0f} s; FEX in use: {thor.fexcore_in_use() or '?'}", flush=True)
if trim:
    time.sleep(20)
    for t in ("@utility:audio", "@utility:video"):
        thor.winexec("D:\\gtav-android\\wkill.exe", t)
        time.sleep(4)
        out = sh(f"cat {thor.TOOLS_DIR}/wkill.txt")
        print(f"{label}: trim {t}: {[l.strip() for l in out.splitlines() if 'ended' in l or 'FAILED' in l]}", flush=True)
before = bench_listing()
newest_before = re.findall(r"newest: (.*) ->", before)
print(f"{label}: results before: {before.strip().splitlines()[-1:] if before else 'none'}", flush=True)
while time.time() - t0 < limit:
    time.sleep(30)
    gone = "GTA5.exe" not in exes()  # GTA V exits by itself after the benchmark: one last look at the folder
    now = bench_listing()
    newest = re.findall(r"newest: (.*) ->", now)
    if newest and newest != newest_before and "copied" in now:
        break
    if gone:
        mem_report()
        sys.exit(f"{label}: GTA5.exe ended before a result")
else:
    sys.exit(f"{label}: no new benchmark result in {limit / 60:.0f} min")
print(f"{label}: result after {time.time() - t0:.0f} s", flush=True)
mem_report()
dest = os.path.join(thor.RESULTS, f"gbench_{label}")
os.makedirs(dest, exist_ok=True)
adb("pull", f"{thor.TOOLS_DIR}/bench/.", dest)
print(subprocess.run(["python3", os.path.join(HERE, "benchsum.py"), dest], capture_output=True, text=True).stdout.strip(), flush=True)
pm = [l for l in adb("logcat", "-d", "-v", "time").splitlines() if "PowerMetrics" in l and "fps=" in l]
vals = {k: [] for k in ("fps", "cpu", "gpu", "cpuTemp")}
for l in pm:
    for k in vals:
        m = re.search(rf"\b{k}=([\d.]+)", l)
        if m and float(re.search(r"fps=([\d.]+)", l).group(1)) > 5:
            vals[k].append(float(m.group(1)))
print(f"{label}: PowerMetrics while drawing: " + ", ".join(
    f"{k} mean {sum(v) / len(v):.1f} max {max(v):.0f}" for k, v in vals.items() if v), flush=True)
