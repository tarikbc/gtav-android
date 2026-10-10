# Performance work

The method and the numbers behind the README's settings (2026-10-10). Everything here was measured on the AYN Thor with the
container of the README (all graphics settings Low, 1280x720 borderless, VSync Off, FEX `aoe4-perf6-30`, Turnip
`turnip_v26.0.0_R6` with `maxDeviceMemory=2048`, DXVK 2.4.1-1-gplasync).

## The benchmark

GTA V has a built-in benchmark: put `-benchmark -benchmarkFrameTimes` in `commandline.txt` next to `GTA5.exe`, start
the game, and it runs five scripted passes and exits. The results land in
`Documents\Rockstar Games\GTA V\Benchmarks\`: `Benchmark-<time>.txt` with the per-pass FPS and one
`FrameTimes-Pass<n>-<time>.txt` per pass with every frame's time. Remove the two switches from `commandline.txt`
again, or the game runs the benchmark at every start.

**Only pass 4 counts.** Passes 0 to 3 last about 10 s each and swing two to one between identical runs (they depend
on what the asset streamer is doing). Pass 4 is the 117 s driving sequence, 4000 to 4500 frames, and it repeats
within a few percent. The tables below give pass 4's median frame time and FPS, and the overall FPS over all passes
as a second number.

The game exits by itself right after it writes the result. A script that polls the process must list the results
folder once more after the process is gone, or it misses the file (one run was lost that way).

## What moved the numbers

| Change | Pass 4 median | Pass 4 FPS | Overall FPS | Frames > 50 ms |
|---|---|---|---|---|
| Baseline (settings above) | 23.9 ms | 42.1 | 38.6 | 120 |
| GPU held at its top clock (power profile below) | 19.2 ms | 48.6 | 47.0 | 96 |
| GPU top clock + GTA5.exe pinned to the fast cores by the launcher stub (measured with the sampling profiler running; a clean rerun is pending) | **17.6 ms** | **57.3** | **51.0** | 62 |
| ARM64EC DXVK 2.4.1-1 (native) instead of GameNative's x86-64 build | 25.5 / 25.3 ms | 41.0 / 40.5 | 34.1 / 36.8 | 275 / 185 |
| GTA5.exe pinned to the fast cores (cpu3 to cpu7) by hand, GPU governor default | 23.0 ms | 43.5 | 37.4 | 193 |
| `FEX_TSOENABLED=0` | crashed in pass 2 in one run; the other run was in the "bad mode" below | | | |

### The GPU clock

The Adreno governor (kgsl) picks the GPU clock from the GPU's busy fraction. GTA V keeps the GPU 40 to 60 % busy, so
the governor sat at 220 to 475 MHz for the whole benchmark, and every frame waited for a slow GPU. Holding the GPU at
its top level (680 MHz) gave +15 % in pass 4 and +22 % overall, with the CPU clocks unchanged (they already run at
their maximum under load, 2.0 / 2.8 / 3.19 GHz, without a pin).

GameNative applies a power profile per container at every game start. The file is `.config/.power-profile` in the
container's home (`Z:\home\xuser-<container id>\.config\.power-profile`, mirrored to `Z:\home\xuser\.config\` while the
container runs):

```json
{"enablePowerControl":true,"adaptiveFpsCapEnabled":false,"enableAutoTuning":false,"enablePerClusterTuning":false,
 "tuningStrategy":"BALANCED","enableFanControl":false,"enableGamePinning":false,"name":"Custom","governor":"SCHEDUTIL",
 "minCpuFreq":307200,"maxCpuFreq":3187200,"minGpuPowerLevel":8,"maxGpuPowerLevel":8,"minBusLevel":0,"maxBusLevel":0}
```

`minGpuPowerLevel` and `maxGpuPowerLevel` are 0 (slowest) to 8 (fastest); GameNative writes the sysfs level as 8
minus the value. The CPU range above lets the CPU scale (it ramps to the top clock under load on its own).
The file is `tools/scripts/power-profile-gpu-max.json`; `thor.py`'s `gcopy` or any file copy inside the session puts it in
place. GameNative's container settings also have a Power Control tab for the same values (not tried here).

### DXVK: native is slower

GameNative's DXVK 2.4.1-1-gplasync is an x86-64 build, so FEX emulates it like the game. The Winlator WCP Hub also
ships ARM64EC builds of the same DXVK (verified by the CHPE metadata pointer in the DLLs' load config; plain x86-64
DLLs have none). The native build ran about 4 % slower in pass 4, uniformly, in two runs. The likely reason: every
D3D11 call from the emulated game code crosses from FEX's JIT into ARM64EC code through the exit thunks, thousands
of times per frame, while the x86-64 DXVK stays inside the JIT. The `dxvk-cs` thread did get cheaper (33.5 % of a
core against 39 %), but it was never the limiter.

### What did not matter

- **TSO off.** `FEX_TSOENABLED=0` makes FEX drop x86 memory ordering. The first two passes were the fastest seen
  (43.6 / 62.5 FPS), then GTA5.exe crashed in pass 2. The other TSO-off run completed but in the bad mode. The game
  needs x86 ordering; TSO stays on.
- **Big-core pin.** The scheduler already keeps the main thread on cpu3 to cpu7 for about 90 % of the samples
  (`corewatch`). A pin gained 3 %, inside the noise.
- **FEX exceptions.** The FEX counters of the `aoe4-perf6` build read zero fast traps and zero continues per second
  during the benchmark, and 35 SMC queries per second. GTA V has none of the exception storm that drove the Age of
  Empires IV work, so the FEX patches for it bring nothing here.
- **WINEDEBUG=-all.** Set before run 4; the run after it jumped from 26.0 to 38.6 FPS overall, but the run before it
  was a "bad mode" run (next section), so the gain cannot be credited to the variable. It stays on because it costs
  nothing.

### The bad mode: the little cores

Three of eleven runs came out at 24 to 27 FPS in pass 4 with 900 to 1070 frames over 50 ms, the GPU 20 to 40 % busy
instead of 60 %, and the CPU at 98 %. The run-level probes (`corewatch`, one `/proc/<pid>/task/*/stat` read per
second) caught the third one: the game's two heaviest threads sat on the little cores (cpu0 to cpu2, 2.0 GHz A510)
in 21 and 22 of 57 samples, against 5 of 57 in a good run. Android's scheduler had parked them there, and at that
clock the main thread cannot feed the GPU. Checked and excluded before that: a cold shader cache (the Mesa cache
got no new files all day and `GTA5.dxvk-cache` was not rewritten), the game's settings (`settings.xml`: VSync 0,
all Low), the X-server watchdog (no kills), CPU clocks (at maximum).

GameNative pins the process it starts to the fast cores, but that is the launcher stub; the game is started by the
Rockstar launcher and comes up with every core allowed (affinity 0xff on all 116 threads). The stub now carries a
pin thread: every 2 s it looks for `GTA5.exe` and sets the process and all its threads to `GTA_PIN_MASK` (hex,
default `f8` = cpu3 to cpu7 on an 8-core SoC; `GTA_PIN_MASK=0` turns it off). A run with the same pin done by hand
through the agent gave 43.5 FPS in pass 4 (baseline 42.1), inside the noise, which is expected: the pin does not
make a good run faster, it stops the bad ones.

### The Rockstar tree on the little cores

The per-run `top` probe showed what else runs while the game draws: Social Club's renderer helper (the overlay's web
page, which nobody sees in the game) at 59 % of a core, its GPU helper at 24 %, the launcher at 12 %, and
`wineserver` at 38 %. None of them is pinned, so they take big-core time from the game. Ending the helpers is not an
option (Social Club then ends the session with "duplicate sign in"), so the stub parks them: once `GTA5.exe` runs,
every `SocialClubHelper.exe`, `Launcher.exe`, `RockstarService.exe` and `RockstarErrorHandler.exe` goes to
`GTA_SC_MASK` (hex, default `07` = the little cores) at below-normal priority. `wineserver` is a Linux process and
stays where the scheduler puts it. The stub's log shows one `parked` line per process.

## The threads

GTA5.exe runs 116 to 139 threads. Over a 57 s window of the benchmark (x86-64 DXVK):

| Thread | Share of one core | Note |
|---|---|---|
| main thread (start `GTA5.exe+187f638`) | 74 to 78 % | 20 to 24 % of its time in the kernel |
| render thread (start `exe+1352048`) | 49 to 59 % | submits the D3D11 calls |
| worker (same start) | 42 to 49 % | half of its time in the kernel |
| `dxvk-cs` | 39 % (33.5 % with the native DXVK) | DXVK's command stream |
| 12 more workers | 7 to 18 % each | |

All of GTA5.exe's threads come up with affinity 0xff (see the bad mode above). The CPU as a whole runs at about 380
to 400 % of one core, so no single thread saturates a core, and the GPU is half idle at its top clock: the frame
rate is set by the main thread's critical path.

## Where the main thread's time goes

The AoE agent (`tools/probes/aoeagent.exe` of ageofempires-android) samples a thread's instruction pointer 300
times, 10 ms apart, and splits the samples by module (`gprof.py`). In the pinned run with the GPU at its top clock:

| Thread | GTA5.exe code | ntdll.dll | D3D11 (DXVK) |
|---|---|---|---|
| main (78 % of a core) | 58.7 % | 40.3 % | 0 |
| render (59 %) | 48.7 % | 36.7 % | 13.7 % |
| worker (42 %) | 20.7 % | 79.3 % | 0 |

The game-code samples spread over hundreds of pages (the main thread's top page holds 4 of 176), so there is no
single hot loop to look at. The ntdll samples are the interesting part. They sit in four spots of code that no
export names. Disassembled as ARM64 (`ripmap.py` and `llvm-mc`), each spot is one instruction past the `ret` of a
system call stub: `mov x8, #id` and a jump into Wine's syscall dispatcher. That is where an emulated thread is
parked while the host runs the call, and the stub before the sampled address is the call. The ids map to names
through ntdll's own export table (every `Nt*` export starts with the same `mov x8, #id`):

| Call | Share of the thread's ntdll samples |
|---|---|
| `NtWaitForSingleObject` (id 4) | main 41 %, render 87 % |
| `NtReleaseSemaphore` (id 10) | main 26 % |
| `NtSetEvent` (id 14) | main 12 % |
| `NtDelayExecution` (id 52) | worker 99.6 % |

So the main thread spends about 38 % of its samples signalling or waiting on events and semaphores, the render
thread waits 32 % of its samples, and one worker sits in `Sleep` with 6 s of kernel time per minute: a polling
loop that burns 42 % of a fast core. On Wine, events and semaphores are either a wineserver round trip each (slow)
or, with esync or fsync, a cheap eventfd or futex call. The Thor's kernel is 5.15, so fsync (`futex_waitv`, 5.16)
is out; esync (`WINEESYNC=1` in the container) is the only cheap path, and whether it is active here is not yet
verified. The next step is `gcallers.py`: for each of those calls, the handle and the game's return addresses, to
see which objects the threads wait on and who the sleeper is.

## Tools

All in `tools/scripts/` (host side, Python over adb; `thor.py` holds the shared helpers and reads `ANDROID_SERIAL`,
`AOE_REPO` and `THOR_FAN_TOOL`), with the probes of `tools/probes/` inside the Wine session. The ones marked (agent)
need `aoeagent.exe` and `agent.py` from ageofempires-android.

| Script | What it does |
|---|---|
| `gexp.py` | One experiment end to end: container edit, fan, benchmark, probes at 150 s, fan back, one row in `results/results.tsv` |
| `gbench.py` | One run of the built-in benchmark: restart, wait for GTA5.exe, poll the results folder with `wbench.exe`, summarize |
| `benchsum.py`, `passcmp.py` | Per-pass FPS and frame-time statistics of result folders; the per-pass time split by frame-time bucket |
| `corewatch.py` | Which core each of the game's threads runs on, from `/proc`, no root |
| `clk.py` | CPU and GPU clocks, GPU busy and temperature every 5 s |
| `gtadash.py` | Live dashboard in the browser: frame graph, clocks, threads and cores, FEX counters |
| `gprof.py` (agent) | Busiest threads and RIP samples split by module |
| `ripmap.py` | Maps sampled addresses inside one DLL to its exports (PE export table of a file copy) |
| `gfex.py` (agent) | FEX's SMC, fast-trap and fast-continue counters per second |
| `gcallers.py` (agent) | For the hot syscall stubs: the handle argument and the game's return addresses |
| `pin.py` (agent) | Pins GTA5.exe to a core mask by hand (the launcher stub does it on its own) |
| `pekind.py` | Tells an x86-64 PE from an ARM64EC one (CHPE metadata pointer) |
| `epic_cfg.py`, `epic_play.py`, `ui.py`, `runbat.py` | Container edits through winhandler, GameNative launch automation, batches inside the session |
| `when_gta.py`, `shot.py` | Run a command N s after GTA5.exe starts; a scaled screenshot |
| `bats/` | `cmdline_on.bat` / `cmdline_off.bat` (the benchmark switches), `renderer_restore.bat` (the launcher's CEF profile) |
| `power-profile-gpu-max.json` | The container power profile with the GPU at its top level |
