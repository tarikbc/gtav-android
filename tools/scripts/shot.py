"""Screenshot of the Thor's display, scaled to 960 px wide: shot.py NAME -> results/shots/NAME.png (prints the path).
THOR_DISPLAY selects a display id for screencap -d (the Thor's main panel is not display 0)."""
import os
import subprocess
import sys

import thor

T = os.path.join(thor.RESULTS, "shots")
os.makedirs(T, exist_ok=True)
name = sys.argv[1] if len(sys.argv) > 1 else "shot"
full = f"{T}/{name}_full.png"
small = f"{T}/{name}.png"
disp = os.environ.get("THOR_DISPLAY")
png = subprocess.run(["adb", *(["-s", thor.SERIAL] if thor.SERIAL else []), "exec-out", "screencap", "-p",
                      *(["-d", disp] if disp else [])], capture_output=True).stdout
open(full, "wb").write(png)
if subprocess.run(["sips", "-Z", "960", full, "--out", small], capture_output=True).returncode:
    small = full  # no sips (not macOS): keep the full-size file
print(small)
