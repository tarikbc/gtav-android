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


# End an open session gently before the restart: GameNative restores the CPU and GPU clocks it pinned only when the
# game exits and the session ends by itself; a force-stop of the app skips that and leaves the clocks pinned.
if {"GTA5.exe", "PlayGTAV.exe", "Launcher.exe"} & thor.exes():
    for name in ("GTA5.exe", "Launcher.exe", "PlayGTAV.exe"):
        thor.winexec("D:\\gtav-android\\wkill.exe", name)  # wkill.exe runs inside Wine; the adb shell cannot signal the app's processes
        time.sleep(3)
    for _ in range(20):
        time.sleep(2)
        if "winhandler.exe" not in thor.exes():
            break
thor.sh("am force-stop app.gamenative")
time.sleep(2)
thor.sh("monkey -p app.gamenative -c android.intent.category.LAUNCHER 1")
# After a cold start the tab bar can show before the library is ready: a tap then leaves the All tab in place, where
# the GTA V card is off screen. Tap again until the card shows.
listing = ""
for _ in range(10):
    time.sleep(4)
    print(ui("tap", "Epic (").strip())
    time.sleep(3)
    listing = ui("list", "grand theft auto v")
    line = next((l for l in listing.splitlines() if l.rstrip().endswith("Grand Theft Auto V")), None)
    if line:
        break
else:
    sys.exit("GTA V card not found:\n" + listing)
x1, y1, x2, y2 = map(int, re.findall(r"\d+", line.split("]  ")[0] + "]"))
thor.sh(f"input tap {(x1 + x2) // 2} {(y1 + y2) // 2}")
time.sleep(4)
print(ui("tap", "Play"))
