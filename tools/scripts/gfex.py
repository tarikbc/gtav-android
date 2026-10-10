"""FEX counters of GTA5.exe over a window, through the AoE agent (a memory peek at libarm64ecfex.dll's data, no
suspend): patch 0004 SmcHideStats (SMCHIDE1), patch 0010 FastContinueStats (FSTCONT1: fast/slow exception continues)
and patch 0017 FastTrapStats (FASTTRP1: taken/fallback, ill/trap/segv) of the ageofempires-android FEX builds.
The RVAs below are for the build `aoe4-perf6-30` (perf6.dll); for another build read them with
`llvm-nm libarm64ecfex.dll | grep -E 'SmcHideStats|FastTrapStats|FastContinueStats'` minus the image base
0x180000000. A missing marker means the RVA is wrong or the build has no counters.
Prints the counts and the rates per second. usage: gfex.py [window_s] [exe]"""
import struct
import sys
import time

import thor  # noqa: F401
import agent  # noqa: E402

window = float(sys.argv[1]) if len(sys.argv) > 1 else 10
exe = sys.argv[2] if len(sys.argv) > 2 else "GTA5.exe"
BLOCKS = {  # name: (rva, marker, field names)
    "SmcHide": (0x3EF2C0, b"SMCHIDE1", ["QueriesFiltered", "QueriesCorrected", "ProtectsFiltered", "ProtectsCorrected"]),
    "FastTrap": (0x3EF328, b"FASTTRP1", ["Taken", "Fallback", "Ill", "Trap", "Segv"]),
    "FastContinue": (0x3EF358, b"FSTCONT1", ["Fast", "Slow"]),
}


def read():
    out = {}
    for name, (rva, marker, fields) in BLOCKS.items():
        data = agent.peek("libarm64ecfex.dll", rva, 8 * (1 + len(fields)))
        if data[:8] != marker:
            out[name] = None
            continue
        out[name] = dict(zip(fields, struct.unpack_from(f"<{len(fields)}Q", data, 8)))
    return out


agent.start()
print(agent.call(f"target {exe}")[0], agent.call("ping")[0])
a = read()
t0 = time.time()
time.sleep(window)
b = read()
dt = time.time() - t0
for name in BLOCKS:
    if b[name] is None:
        print(f"{name}: marker not found (wrong RVA for this FEX build?)")
        continue
    print(f"{name}: " + ", ".join(f"{k} {b[name][k]} (+{(b[name][k] - a[name][k]) / dt:.0f}/s)" for k in b[name]))
