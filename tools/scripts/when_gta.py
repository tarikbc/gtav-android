"""Wait until GTA5.exe runs in the Wine session, then DELAY s more, then run the command.
usage: when_gta.py DELAY CMD ARGS...   e.g. when_gta.py 150 python3 gprof.py rip 3 300 10"""
import subprocess
import sys
import time

import thor

delay = float(sys.argv[1])
t0 = time.time()
while "GTA5.exe" not in thor.exes():
    time.sleep(5)
    if time.time() - t0 > 3600:
        sys.exit("GTA5.exe did not start in an hour")
print(f"GTA5.exe seen after {time.time() - t0:.0f} s; waiting {delay:.0f} s", flush=True)
time.sleep(delay)
sys.exit(subprocess.call(sys.argv[2:]))
