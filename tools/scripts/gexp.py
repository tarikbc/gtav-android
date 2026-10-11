"""One GTA V benchmark experiment on the Thor, end to end: apply container edits (epic_cfg.py syntax: key:=value,
VAR=VALUE, -VAR), fan Custom, run the built-in benchmark (gbench.py --trim, restart or --attach), probes at 150 s
(corewatch.py: thread placement and load; top: the session's busiest processes), fan Smart (always), and append one
row to results/results.tsv with the pass FPS, overall FPS, frame-time stats, PowerMetrics and the FEX build.
usage: gexp.py LABEL [--attach] [--timeout MIN] [--note TEXT] [cfg edits ...]
A:\\commandline.txt must hold -benchmark -benchmarkFrameTimes (gbench --setup or bats/cmdline_on.bat writes it).
Judge runs by pass 4 (passcmp.py): passes 0 to 3 swing two to one between identical runs."""
import os
import re
import subprocess
import sys
import threading
import time

import thor

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
label = next(a for a in args if not a.startswith("--"))  # the first plain argument, wherever it is
args.remove(label)
attach = "--attach" in args
setup = "--setup" in args  # forwarded to gbench: write the benchmark switches at the session start
timeout = "25"
note = ""
cfg = []
i = 0
while i < len(args):
    a = args[i]
    if a in ("--attach", "--setup"):
        pass
    elif a == "--timeout":
        i += 1
        timeout = args[i]
    elif a == "--note":
        i += 1
        note = args[i]
    else:
        cfg.append(a)
    i += 1

RL = thor.RESULTS
tsv = os.path.join(RL, "results.tsv")
if not os.path.exists(tsv):
    open(tsv, "w").write("time\tlabel\tcfg\tpasses\toverall_fps\tmedian_ms\tp99_ms\tover50\tover100\tframes\tpm\tfex\tnote\n")


def log(s):
    print(f"{label}: {s}", flush=True)


if cfg:
    if "winhandler.exe" not in thor.exes():
        log("opening the session for the config edit")
        subprocess.run(["python3", os.path.join(HERE, "epic_play.py")], capture_output=True)
        for _ in range(60):
            if "winhandler.exe" in thor.exes():
                break
            time.sleep(2)
        time.sleep(5)
    out = subprocess.run(["python3", os.path.join(HERE, "epic_cfg.py"), *cfg], capture_output=True, text=True)
    log(f"cfg: {out.stdout.strip()[-400:]} {out.stderr.strip()[-200:]}")
    if attach:
        log("config edits need a restart; --attach ignored")
        attach = False

log(f"fan {thor.fan('custom')}")
summary = pm = fex = ""
try:
    cmd = ["python3", "-u", os.path.join(HERE, "gbench.py"), "--trim"] + (["--attach"] if attach else []) + (["--setup"] if setup else []) + [label, timeout]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def probes():  # the run's own signature: thread placement and load at 150 s, and the session's top processes
        time.sleep(150)
        out = subprocess.run(["python3", os.path.join(HERE, "corewatch.py"), "60"], capture_output=True, text=True).stdout
        top = thor.sh("top -b -n 2 -d 3 -m 10 -s 2 -o PID,%CPU,RES,CMDLINE 2>/dev/null | tail -n 11")  # frame 2 has real %CPU
        with open(os.path.join(RL, f"probes_{label}.txt"), "w") as f:
            f.write(out + "\n--- top ---\n" + top)
        log("probes: " + " | ".join(l.strip() for l in out.splitlines()[:3]))
        rows = [l.strip()[:60] for l in top.splitlines() if l.strip() and l.split()[0].isdigit()]
        log("top: " + " | ".join(rows[:6]))

    started = False
    for line in p.stdout:
        print(line, end="", flush=True)
        if not started and "GTA5.exe after" in line:
            started = True
            threading.Thread(target=probes, daemon=True).start()
        if "passes" in line and "overall" in line:
            summary = line.strip()
        if "PowerMetrics while drawing" in line:
            pm = line.split("drawing:", 1)[1].strip()
    p.wait()
    fex = thor.fexcore_in_use()
finally:
    log(f"fan {thor.fan('smart')}")
m = re.search(r"passes (.*?)  overall ([\d.]+) FPS  median ([\d.]+) ms  p99 ([\d.]+) ms  >50 ms (\d+)  >100 ms (\d+)  \((\d+) frames\)", summary)
row = [time.strftime("%Y-%m-%d %H:%M"), label, " ".join(cfg)] + (list(m.groups()) if m else ["", "", "", "", "", "", ""]) + [pm, fex, note]
open(tsv, "a").write("\t".join(row) + "\n")
log(f"row: {row[1:]}")
