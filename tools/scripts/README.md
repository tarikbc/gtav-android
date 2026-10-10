# Measurement scripts

Host-side Python (macOS or Linux) that drives the Thor over adb. Nothing here runs inside Wine except the probes
of `tools/probes/` and, for the profiler, the agent of
[ageofempires-android](https://github.com/tarikbc/ageofempires-android).

## Prerequisites

- `adb` with the Thor connected; `ANDROID_SERIAL` when more than one device is attached.
- The probes on the Thor: `tools/build.sh`, then push `build/EpicGamesLauncher.exe`, `wbench.exe`, `wkill.exe`,
  `wfocus.exe` to `/sdcard/Download/gtav-android/` (drive `D:\gtav-android` in the container).
- From ageofempires-android (clone it next to this repo, or set `AOE_REPO`): `tools/probes/gcopy.exe` pushed to
  `/sdcard/Download/aoe/gcopy.exe` (windowless file copies inside the session), and for `gprof.py`, `gfex.py`,
  `gcallers.py`, `pin.py` and the dashboard's FEX panel also `tools/probes/aoeagent.exe` with `tools/agent.py`
  (the scripts start it themselves). `epic_play.py` and `ui.py` use its `tools/gn_nav.py`.
- Optional: `THOR_FAN_TOOL="python3 ../ageofempires-android/tools/thor_fan.py"` so `gexp.py` sets the fan to Custom
  while it measures and back to Smart after.
- The container runs GTA V once by hand first (sign-in done, settings set as in the README).

## One experiment

```
cd tools/scripts
python3 runbat.py bats/cmdline_on.bat        # once, with the session open: the benchmark switches
python3 gexp.py baseline                     # restart, benchmark, probes, one row in results/results.tsv
python3 gexp.py tso_off FEX_TSOENABLED=0     # the same with a container edit (epic_cfg.py syntax)
python3 gexp.py gpu8 --note "power profile with the GPU at its top level"
python3 passcmp.py results/gbench_baseline results/gbench_gpu8   # per-pass frame-time split
python3 runbat.py bats/cmdline_off.bat       # at the end: the switches off, or every start runs the benchmark
```

`gexp.py` restarts the game through GameNative (`epic_play.py`), waits for `GTA5.exe` (and calls out if the Rockstar
sign-in page stays up), ends Social Club's audio and video helpers, polls the results folder with `wbench.exe`, and
at 150 s records the run's probes: `corewatch.py` (which core each thread runs on) and the session's busiest
processes. Judge runs by pass 4 (see `docs/guides/TESTING.md`).

## Watching live

```
python3 gtadash.py            # then open http://127.0.0.1:8791
```

Frame graph from Android's compositor, CPU and GPU clocks, GPU busy, temperature, free memory, the game's ten
busiest threads with their cores, and FEX's counters. Two long-lived shell loops on the Thor, builtins plus one
`cat` every 3 s, no screen readback.

## Profiling

```
python3 when_gta.py 150 python3 gprof.py rip 3 300 10    # 150 s after the game starts: 3 threads x 300 samples
python3 ripmap.py results/ntdll.dll <base> <size> /sdcard-pulled/rips_rip_<tid>.txt
python3 gfex.py 15                                       # FEX counters per second (RVAs for aoe4-perf6-30)
python3 gcallers.py waits                                # handles and return addresses of the hot syscalls
```

Sampling suspends the thread, so that run's FPS is not a result. The agent protocol is one request at a time; the
dashboard and a profiler can share it (a file lock in `agent.py`).
