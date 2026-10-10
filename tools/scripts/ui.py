"""GameNative UI helper (Android uiautomator tree). usage: ui.py list [filter] | ui.py tap <text> [index] | ui.py back
Lists clickable/text nodes with their bounds (screen pixels), or taps the node whose text/desc contains <text>.
Needs gn_nav.py from the AoE repo (AOE_REPO, see thor.py)."""
import re
import sys

import thor  # noqa: F401  (puts the AoE tools on sys.path)
from gn_nav import GN  # noqa: E402

g = GN(thor.SERIAL or None)
cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
if cmd == "back":
    thor.sh("input keyevent 4")
    sys.exit(0)
root = g.dump()
items = []
for n in root.iter("node"):
    label = (n.get("text", "") + " | " + n.get("content-desc", "")).strip(" |")
    b = n.get("bounds", "")
    if label and b:
        items.append((label, b))
if cmd == "list":
    f = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    for label, b in items:
        if f in label.lower():
            print(f"{b}  {label[:90]}")
elif cmd == "tap":
    want = sys.argv[2].lower()
    idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    hits = [(l, b) for l, b in items if want in l.lower()]
    if len(hits) <= idx:
        sys.exit(f"no node with '{want}' (found {len(hits)})")
    l, b = hits[idx]
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", b))
    g.tap((x1 + x2) // 2, (y1 + y2) // 2)
    print(f"tapped '{l[:60]}' at {(x1 + x2) // 2},{(y1 + y2) // 2}")
