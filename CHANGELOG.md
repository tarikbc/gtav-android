# Changelog

## Unreleased

- `EpicGamesLauncher.exe` keeps `GTA5.exe` on the fast cores (`GTA_PIN_MASK`, default `f8`, `0` turns it off):
  Android's scheduler parked the game's heaviest threads on the slow cores in 3 of 12 benchmark runs, at half the
  frame rate. While the game runs it also parks the Rockstar launcher and the Social Club helpers on the slow cores
  at below-normal priority (`GTA_SC_MASK`, default `07`).
- Power profile with the GPU held at its top clock (`tools/scripts/power-profile-gpu-max.json`): +22 % overall in
  the built-in benchmark. With the pin, pass 4 went from 42.1 to 57.3 FPS.
- `wbench.exe` copies the benchmark results out of the session; `wkill.exe` matches CEF process types by prefix.
- `tools/scripts/`: the measurement scripts (experiment runner, dashboard, thread placement, clocks, sampling
  profiler and FEX counters through the ageofempires-android agent).
- Docs: [PERFORMANCE.md](docs/how-it-works/PERFORMANCE.md) (method, every run, what helped and what did not, where
  the main thread's time goes), the benchmark section of TESTING.md, README.

## v0.1.0 (2026-10-10)

First release: GTA V Legacy (Epic) plays in story mode on the AYN Thor with GameNative 1.3.0.

- `EpicGamesLauncher.exe`: starts `PlayGTAV.exe` as the Epic Games Launcher would, adds `-nobattleye`
  (`EPIC_EXTRA_ARGS` replaces it), patches Social Club's `libcef.dll` at three sites (known version only, backup
  kept), and watches GameNative's X server (`XWATCH=0` turns that off).
- Game settings: 1280x720, Windowed Borderless, VSync Off (the game's own choice, VSync Half, holds it at 30 FPS).
- Container settings for ARM64EC Proton with FEX, with the Epic overlay off.
- Probes: `wkill.exe`, `sdg.exe`, `wfocus.exe`.
- Measured in the prologue: 59.5 FPS at 1280x720 with VSync Off (31.3 FPS with the game's defaults).
