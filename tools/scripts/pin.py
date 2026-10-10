"""Pin GTA5.exe (process mask and every thread) to the cores in MASK (hex, default f8 = cpu3 to cpu7, the fast cores
of the Thor's SD8G2) through the AoE agent; prints the old masks and the thread count. The launcher stub does the
same by itself (GTA_PIN_MASK); this is the manual version for a test. usage: pin.py [MASK] [exe]"""
import sys

import thor  # noqa: F401
import agent  # noqa: E402

mask = sys.argv[1] if len(sys.argv) > 1 else "f8"
exe = sys.argv[2] if len(sys.argv) > 2 else "GTA5.exe"
agent.start()
print(agent.call(f"target {exe}")[0], agent.call("ping")[0])
print(agent.call(f"procaffin {mask}", timeout=60)[0])
