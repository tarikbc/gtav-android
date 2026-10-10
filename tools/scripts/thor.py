"""Shared helpers for the GTA V measurement scripts: adb to the Thor, the Wine session's process list, launching a
program through GameNative's winhandler, windowless file copies inside the session, the Rockstar launcher's UI
state, the FEX build in use, and the fan.

Environment:
  ANDROID_SERIAL or THOR_SERIAL   adb serial when several devices are connected (empty: adb picks the one device)
  AOE_REPO                        checkout of github.com/tarikbc/ageofempires-android, for its tools/agent.py,
                                  tools/probes/aoeagent.exe, tools/probes/gcopy.exe and tools/gn_nav.py
                                  (default: ../ageofempires-android next to this repo)
  THOR_FAN_TOOL                   optional command that takes `custom` or `smart` (the AoE repo's tools/thor_fan.py);
                                  unset: the fan is left alone

Inside the session, D:\\ is /sdcard/Download. The scripts keep their scratch files in D:\\gtav-android\\scratch
(/sdcard/Download/gtav-android/scratch) and gcopy.exe must sit at D:\\aoe\\gcopy.exe (push it from the AoE repo).
"""
import os
import struct
import subprocess
import sys
import tempfile
import time

SERIAL = os.environ.get("ANDROID_SERIAL") or os.environ.get("THOR_SERIAL") or ""
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
AOE_REPO = os.environ.get("AOE_REPO") or os.path.join(os.path.dirname(REPO), "ageofempires-android")
AOE_TOOLS = os.path.join(AOE_REPO, "tools")
RESULTS = os.path.join(HERE, "results")  # gitignored
SCRATCH = "/sdcard/Download/gtav-android/scratch"  # D:\gtav-android\scratch in Wine
SCRATCH_WIN = r"D:\gtav-android\scratch"
TOOLS_DIR = "/sdcard/Download/gtav-android"  # D:\gtav-android: the launcher stub and the probes
LAUNCHER_LOG = r"%USERPROFILE%\Documents\Rockstar Games\Launcher\launcher.log"
os.makedirs(RESULTS, exist_ok=True)
if AOE_TOOLS not in sys.path:
    sys.path.insert(0, AOE_TOOLS)


def adb(*a, timeout=60):
    return subprocess.run(["adb", *(["-s", SERIAL] if SERIAL else []), *a], capture_output=True, text=True,
                          timeout=timeout).stdout


def sh(cmd, timeout=60):
    return adb("shell", cmd, timeout=timeout)


def exes():
    """Base names of the .exe processes of the Wine session."""
    return {l.strip().split("\\")[-1] for l in sh("ps -A -o NAME").splitlines() if l.strip().endswith(".exe")}


def winexec(program, params):
    """Start a program inside the running session through winhandler (UDP port 7946 on the Thor). A request holds
    only 51 bytes of program and arguments."""
    if len(program) + len(params) > 51:
        raise ValueError("program + params must fit in 51 bytes")
    body = bytes([2]) + struct.pack("<iii", len(program) + len(params) + 8, len(program), len(params))
    pkt = (body + program.encode() + params.encode()).ljust(64, b"\0")
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(pkt)
        tmp = f.name
    try:
        adb("push", tmp, "/data/local/tmp/winhandler_exec.bin", timeout=30)
        sh("timeout 3 nc -u 127.0.0.1 7946 < /data/local/tmp/winhandler_exec.bin", timeout=15)
    finally:
        os.unlink(tmp)


def gcopy(pairs, wait=6):
    """Copy files inside the session with no console window: D:\\aoe\\gcopy.exe (from the AoE repo's probes) reads
    src/dst pairs from D:\\aoe\\gcopy.txt. Paths may use %VARIABLES%."""
    body = "".join(f"{s}\r\n{d}\r\n" for s, d in pairs)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, newline="") as f:
        f.write(body)
        tmp = f.name
    try:
        sh("mkdir -p /sdcard/Download/aoe")
        adb("push", tmp, "/sdcard/Download/aoe/gcopy.txt")
    finally:
        os.unlink(tmp)
    winexec("D:\\aoe\\gcopy.exe", "")
    time.sleep(wait)


def launcher_log(dst=None):
    """Copy the Rockstar launcher log out of the session; returns its text ('' if the session has none yet)."""
    dst = dst or os.path.join(RESULTS, "launcher_live.log")
    sh(f"mkdir -p {SCRATCH}; rm -f {SCRATCH}/launcher_live.log")
    gcopy([(LAUNCHER_LOG, SCRATCH_WIN + r"\launcher_live.log")])
    adb("pull", f"{SCRATCH}/launcher_live.log", dst)
    try:
        return open(dst, errors="replace").read()
    except OSError:
        return ""


def launcher_state(text=None):
    """Last UiWindowController context of the launcher: 'Auth' (sign-in page up), 'MainWindow', or '' (unknown)."""
    text = launcher_log() if text is None else text
    ctx = ""
    for l in text.splitlines():
        if "SetContext:" in l:
            ctx = l.rsplit("-> ", 1)[-1].strip()
    return ctx


def say(msg):
    """Audible prompt on the Mac (macOS `say`); silent elsewhere."""
    try:
        subprocess.run(["say", msg], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass


def fexcore_in_use():
    for l in adb("logcat", "-d").splitlines():
        if "fexcoreVersion in use" in l:
            return l.split("fexcoreVersion in use", 1)[1].strip(" :=")
    return ""


def fan(mode):
    """`custom` while measuring, `smart` right after; needs THOR_FAN_TOOL (the AoE repo's tools/thor_fan.py)."""
    tool = os.environ.get("THOR_FAN_TOOL")
    if not tool:
        return "(no fan tool)"
    return subprocess.run([*tool.split(), mode], capture_output=True, text=True).stdout.strip()


def wait_gta5(limit, label="", on_tick=None):
    """Wait for GTA5.exe up to limit s. Every 30 s checks the launcher: if the sign-in page is up for 120 s, calls the
    user once (say + a 'SIGNIN NEEDED' line for a monitor). Returns True when GTA5.exe runs."""
    t0 = time.time()
    last_check = 0
    auth_since = None
    called = False
    while time.time() - t0 < limit:
        if "GTA5.exe" in exes():
            return True
        time.sleep(3)
        if time.time() - last_check > 30 and "winhandler.exe" in exes() and "Launcher.exe" in exes():
            last_check = time.time()
            st = launcher_state()
            if st == "Auth":
                auth_since = auth_since or time.time()
                if not called and time.time() - auth_since > 120:
                    called = True
                    print(f"{label}: SIGNIN NEEDED: the Rockstar launcher waits on the sign-in page", flush=True)
                    say("The Rockstar launcher on the Thor needs you to sign in. Please check the screen.")
            else:
                auth_since = None
            if on_tick:
                on_tick(st)
    return "GTA5.exe" in exes()
