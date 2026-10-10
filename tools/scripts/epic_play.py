"""Force-stop GameNative, start it, open the Epic tab, open GTA V (Legacy, not Enhanced) and press Play.
Uses ui.py (GameNative's UI tree through uiautomator; needs gn_nav.py from the AoE repo, see thor.py)."""
import os
import re
import subprocess
import sys
import time

import thor

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.py")


def ui(*a):
    r = subprocess.run(["python3", UI, *a], capture_output=True, text=True)
    return r.stdout + r.stderr


thor.sh("am force-stop app.gamenative")
time.sleep(2)
thor.sh("monkey -p app.gamenative -c android.intent.category.LAUNCHER 1")
time.sleep(8)
print(ui("tap", "Epic ("))
time.sleep(3)
listing = ui("list", "grand theft auto v")
line = next((l for l in listing.splitlines() if l.rstrip().endswith("Grand Theft Auto V")), None)
if not line:
    sys.exit("GTA V card not found:\n" + listing)
x1, y1, x2, y2 = map(int, re.findall(r"\d+", line.split("]  ")[0] + "]"))
thor.sh(f"input tap {(x1 + x2) // 2} {(y1 + y2) // 2}")
time.sleep(4)
print(ui("tap", "Play"))
