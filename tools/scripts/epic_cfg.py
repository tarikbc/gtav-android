"""Edit the GTA V Epic container's files (the source copy and the applied copy) through winhandler while the
session is open. Arguments: key:=value sets a top-level JSON key (string), VAR=VALUE adds or replaces an env var,
-VAR removes one. Prints the changed keys of both files after the copy back.
usage: epic_cfg.py [key:=value | VAR=VALUE | -VAR] ...
  e.g. epic_cfg.py WINEDEBUG=-all
       epic_cfg.py "dxwrapperConfig:=version=2.4.1-1-gplasync-0,framerate=0,..."
GTA_CONTAINER names the container id (default EPIC_19; GameNative shows it in the container's folder name
Z:\\home\\xuser-<id>). GameNative may rewrite the container from memory when the session ends, so restart through
epic_play.py right after an edit and check the logcat line "fexcoreVersion in use"."""
import json
import os
import subprocess
import sys
import tempfile
import time

import thor

CID = os.environ.get("GTA_CONTAINER", "EPIC_19")
FILES = {"src": rf"Z:\home\xuser-{CID}\.container", "app": r"Z:\home\xuser\.container"}
HERE = os.path.dirname(os.path.abspath(__file__))


def run_bat(body):
    with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False, newline="") as f:
        f.write(body)
        tmp = f.name
    out = subprocess.run(["python3", os.path.join(HERE, "runbat.py"), tmp, "20"], capture_output=True, text=True).stdout
    os.unlink(tmp)
    if "did not finish" in out:
        sys.exit("the batch did not finish: is the session open?")


keys = [a.split(":=", 1) for a in sys.argv[1:] if ":=" in a]
envs = [a for a in sys.argv[1:] if ":=" not in a]
S = thor.SCRATCH_WIN
run_bat("@echo off\n" + "".join(f'copy /y "{p}" {S}\\gcfg_{k}.json >nul\n' for k, p in FILES.items()) + f"echo copied > {S}\\ew_r.txt\n")
local = {}
for k in FILES:
    local[k] = os.path.join(thor.RESULTS, f"gcfg_{k}.json")
    thor.adb("pull", f"{thor.SCRATCH}/gcfg_{k}.json", local[k])
    o = json.load(open(local[k]))
    if o.get("id") != CID:
        sys.exit(f"{k}: active container is {o.get('id')}, not {CID}")
    for key, val in keys:
        o[key] = val
    env = o.get("envVars", "").split()
    for kv in envs:
        name = kv.lstrip("-").split("=", 1)[0]
        env = [e for e in env if e.split("=", 1)[0] != name] + ([] if kv.startswith("-") else [kv])
    o["envVars"] = " ".join(env)
    new = os.path.join(thor.RESULTS, f"gcfg_{k}_new.json")
    json.dump(o, open(new, "w"), separators=(",", ":"))
    thor.adb("push", new, f"{thor.SCRATCH}/gcfg_{k}_new.json")
push = "@echo off\n" + "".join(f'copy /y {S}\\gcfg_{k}_new.json "{p}" >nul\n' for k, p in FILES.items())
push += "".join(f'copy /y "{p}" {S}\\gcfg_{k}_check.json >nul\n' for k, p in FILES.items())
run_bat(push + f"echo pushed > {S}\\ew_r.txt\n")
time.sleep(1)
for k in FILES:
    chk = os.path.join(thor.RESULTS, f"gcfg_{k}_check.json")
    thor.adb("pull", f"{thor.SCRATCH}/gcfg_{k}_check.json", chk)
    o = json.load(open(chk))
    print(k, {key: o.get(key) for key, _ in keys}, [e for e in o.get("envVars", "").split()
                                                     if any(e.split("=", 1)[0] == kv.lstrip("-").split("=", 1)[0] for kv in envs)])
