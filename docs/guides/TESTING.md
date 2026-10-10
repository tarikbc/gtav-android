# Measuring

## Frame times

`tools/scripts/frametimes.py` (from [ageofempires-android](https://github.com/tarikbc/ageofempires-android)) reads
the game's real frame times from Android's compositor over adb (`dumpsys SurfaceFlinger --latency` on GameNative's
SurfaceView), with nothing running inside Wine:

```
python3 tools/scripts/frametimes.py 60 --csv run.csv
```

It prints FPS, the mean, median, 99th-percentile and worst frame time, and the frames over 50 ms and over 100 ms.
Set `ANDROID_SERIAL` when more than one device is connected.

## The built-in benchmark

GTA V runs its own benchmark when `commandline.txt` next to `GTA5.exe` (drive `A:` in the container) holds
`-benchmark -benchmarkFrameTimes` (`tools/scripts/bats/cmdline_on.bat` writes it, `cmdline_off.bat` removes it;
`runbat.py` runs a batch inside the session). The game then plays five scripted passes and exits by itself. The
results land in `Documents\Rockstar Games\GTA V\Benchmarks\`: `Benchmark-<time>.txt` with the per-pass FPS and one
`FrameTimes-Pass<n>-<time>.txt` per pass with every frame's time. `wbench.exe` copies them out without a console
window, `benchsum.py` and `passcmp.py` summarize them, and `gexp.py` runs one experiment end to end
([PERFORMANCE.md](../how-it-works/PERFORMANCE.md), "Tools").

**Only pass 4 counts.** Passes 0 to 3 last about 10 s each and swing two to one between identical runs; pass 4 is
the 117 s driving sequence with 4000 to 4500 frames and repeats within a few percent. Remove the switches after the
series, or every start runs the benchmark.

### Benchmark runs of 2026-10-10

All with the container of the README (all settings Low, 1280x720 borderless, VSync Off, FEX `aoe4-perf6-30`,
Turnip `turnip_v26.0.0_R6` with `maxDeviceMemory=2048`, `WINEDEBUG=-all` from run 4 on, Social Club's audio and
video helpers ended). "Bad mode" = the game's heaviest threads sat on the slow cores (see PERFORMANCE.md);
"perturbed" = the sampling profiler ran during the pass.

| Run | Change | Passes 0 to 4 (FPS) | Overall FPS | Pass 4 median | Frames > 50 ms |
|---|---|---|---|---|---|
| 3 | baseline (bad mode) | 42.0 / 53.9 / 32.5 / 33.9 / 27.5 | 26.0 | 36 ms | 924 |
| 4 | `WINEDEBUG=-all`, the CEF profile restored | 41.5 / 43.8 / 33.1 / 49.0 / 42.1 | 38.6 | 23.9 ms | 120 |
| 5 | ARM64EC DXVK 2.4.1-1 gplasync (cold cache) | 41.2 / 31.0 / 28.1 / 26.8 / 41.0 | 34.1 | 25.5 ms | 275 |
| 6 | ARM64EC DXVK, warm cache | 42.8 / 56.8 / 34.9 / 25.3 / 40.5 | 36.8 | 25.3 ms | 185 |
| 7 | x86-64 DXVK back, `FEX_TSOENABLED=0` (bad mode) | 44.4 / 43.5 / 33.0 / 49.8 / 25.3 | 25.7 | 37 ms | 906 |
| 8 | GTA5.exe pinned to cpu3 to cpu7 by hand | 44.8 / 38.5 / 32.8 / 34.3 / 43.5 | 37.4 | 23.0 ms | 193 |
| 9 | `FEX_TSOENABLED=0` again | 43.6 / 62.5, then GTA5.exe crashed in pass 2 | | | |
| 10 | GPU held at its top clock (power profile) | 50.9 / 70.5 / 59.8 / 62.7 / 48.6 | 47.0 | 19.2 ms | 96 |
| 11 | same, no pin (bad mode, perturbed) | 45.0 / 64.4 / 31.7 / 27.1 / 24.2 | 24.6 | 41 ms | 1070 |
| 12 | GPU top clock, pinned by the launcher stub (perturbed) | 44.3 / 48.3 / 50.5 / 66.7 / 57.3 | 51.0 | 17.6 ms | 62 |

## Rules used for the numbers in the README

- One window per setting, a few runs at most; stop when the trend is clear.
- The Thor's fan on **Custom** (88 %) only while measuring, back to **Smart** right after.
- Judge a benchmark run by pass 4 only, and look at the run's probes (`gexp.py` records thread placement and the
  busiest processes at 150 s) before trusting a slow run.
- Do not start console programs in Wine while measuring (a `cmd` batch from adb, for example): the console window
  takes the focus and GTA V stops drawing.
- Check that frames flow before recording. Opening Android's quick settings (for example to change the fan) pauses
  GameNative: tap its Play button, then tap the game window so GTA V has the focus again. GameNative's log line
  `PowerMetrics: fps=...` (every 5 s) shows whether the game draws.

## Results

| Date | Scene | Settings | FPS | median | p99 | worst | >50 ms | >100 ms |
|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | Prologue, player still, 65 s | Defaults: 800x600 window, VSync Half | 31.3 | 33.4 ms | 33.4 ms | 50.1 ms | 19 | 0 |
| 2026-10-10 | Prologue, player still, 64 s | 1280x720 borderless, VSync Off, display 120 Hz | 59.5 | 16.8 ms | 42.1 ms | 134.8 ms | 20 | 3 |
| 2026-10-10 | Prologue, player still, 64 s | Same, with the patched Turnip `turnip-main-c78a9e9-ubwc` from ageofempires-android | 57.9 | 16.9 ms | 42.1 ms | 210.6 ms | 19 | 2 |

The patched Turnip driver that gave Age of Empires IV +27 % made no difference here (57.9 against 59.5 FPS, within
the spread of one run), so the README keeps GameNative's `turnip_v26.0.0_R6`. At about 58 to 60 FPS the CPU was 74 to
84 % busy and the GPU about 70 %, at 88 °C: the next work is on the CPU side (FEX) and on heat.
