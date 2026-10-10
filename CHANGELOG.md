# Changelog

## v0.1.0 (2026-10-10)

First release: GTA V Legacy (Epic) plays in story mode on the AYN Thor with GameNative 1.3.0.

- `EpicGamesLauncher.exe`: starts `PlayGTAV.exe` as the Epic Games Launcher would, adds `-nobattleye`
  (`EPIC_EXTRA_ARGS` replaces it), patches Social Club's `libcef.dll` (known version only, backup kept), and
  watches GameNative's X server (`XWATCH=0` turns that off).
- Container settings for ARM64EC Proton with FEX, with the Epic overlay off.
- Probes: `wkill.exe`, `sdg.exe`.
- Measured: 31.3 FPS (held at 30) in the prologue, default 800x600 window.
