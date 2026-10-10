"""Run a local .bat in the live Wine session and print D:\\gtav-android\\scratch\\ew_r.txt (the batch writes its output
there; this script appends the bat_done marker line). A batch opens a console window, which takes the focus from
GTA V (it stops drawing without it), so use this between runs, not during a measurement.
usage: runbat.py <file.bat> [timeout_s]"""
import os
import sys
import tempfile
import time

import thor

src = sys.argv[1]
limit = float(sys.argv[2]) if len(sys.argv) > 2 else 40
name = os.path.basename(src)
body = open(src).read().replace("\r\n", "\n").rstrip("\n") + "\necho done > D:\\gtav-android\\scratch\\bat_done.txt\n"
with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False, newline="") as f:
    f.write(body.replace("\n", "\r\n"))
    tmp = f.name
thor.sh(f"mkdir -p {thor.SCRATCH}; rm -f {thor.SCRATCH}/bat_done.txt {thor.SCRATCH}/ew_r.txt")
thor.adb("push", tmp, f"{thor.SCRATCH}/{name}")
os.unlink(tmp)
thor.winexec("cmd", f"/c {thor.SCRATCH_WIN}\\{name}")
t0 = time.time()
while time.time() - t0 < limit:
    time.sleep(0.5)
    if "done" in thor.sh(f"cat {thor.SCRATCH}/bat_done.txt"):
        break
else:
    print(f"(batch did not finish in {limit:.0f} s)")
print("\n".join(l for l in thor.sh(f"cat {thor.SCRATCH}/ew_r.txt").splitlines() if not l.startswith("evshim")))
