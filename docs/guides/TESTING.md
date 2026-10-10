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

## Rules used for the numbers in the README

- One window per setting, a few runs at most; stop when the trend is clear.
- The Thor's fan on **Custom** (88 %) only while measuring, back to **Smart** right after.
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
