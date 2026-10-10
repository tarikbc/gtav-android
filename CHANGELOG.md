# Changelog

## v0.1.0 (2026-10-10)

First release: GTA V Legacy (Epic) plays in story mode on the AYN Thor with GameNative 1.3.0.

- `EpicGamesLauncher.exe`: starts `PlayGTAV.exe` as the Epic Games Launcher would, adds `-nobattleye`
  (`EPIC_EXTRA_ARGS` replaces it), patches Social Club's `libcef.dll` at three sites (known version only, backup
  kept), and watches GameNative's X server (`XWATCH=0` turns that off).
- Game settings: 1280x720, Windowed Borderless, VSync Off (the game's own choice, VSync Half, holds it at 30 FPS).
- Container settings for ARM64EC Proton with FEX, with the Epic overlay off.
- Probes: `wkill.exe`, `sdg.exe`, `wfocus.exe`.
- Measured in the prologue: 59.5 FPS at 1280x720 with VSync Off (31.3 FPS with the game's defaults).
