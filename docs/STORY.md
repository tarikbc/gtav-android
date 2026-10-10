# The story: from "Activation required" to story mode

GTA V Legacy on an AYN Thor through GameNative, 2026-10-09 and 10. Each step names what failed and what fixed it.

## 1. The Steam copy: "Activation required"

GameNative 1.3.0 added Rockstar support for Steam games: a stand-in for the Rockstar launcher starts `GTA5.exe`
without the real one. The game reached its own screen "Activation required". Tracing it showed the cause was the
Rockstar account: Rockstar's entitlement list for it had no "Access to GTA V for PC", and asking Rockstar to scan
the linked Steam account added nothing, while Steam itself confirmed the ownership. Nothing on the device could fix
that.

## 2. The real Rockstar launcher on ARM64EC Wine

On the way, the real Rockstar Games Launcher was made to run on GameNative's ARM64EC Proton with FEX. Its UI is
Chromium (CEF 143). Three things broke it, each fixed with a small patch to Social Club's `libcef.dll`
([CEF-PATCHES.md](how-it-works/CEF-PATCHES.md)):

- V8 could not reserve its address space on the Thor's 39-bit kernel.
- Chromium's background stack sampler deadlocked the browser's IO thread under FEX; every child process timed out.
- WebGPU crashed the sign-in page's renderer.

## 3. The Epic copy

The same person also owns GTA V Legacy on Epic, with Epic linked to the Rockstar account. The Steam copy was removed
and the Epic one downloaded through GameNative (117 GB). GameNative's default container for it (Box64, x86-64 Proton)
stopped at "Failed to connect to the Rockstar Games Library Service"; with ARM64EC Proton and FEX
([README](../README.md#2-the-container)) the launcher installed and showed its sign-in page.

## 4. Signed in, but no game

After sign-in the launcher showed its own library with "Buy now" and never started the game. Its log said why:
"Epic Games Launcher not detected as parent process" ([EPIC-LAUNCH.md](how-it-works/EPIC-LAUNCH.md)). A small
stand-in named `EpicGamesLauncher.exe`, an idea from the Heroic Games Launcher, now starts `PlayGTAV.exe`. Placed in
the game folder it died at once inside FEX; from another drive it worked. The launcher then reported the Epic
ownership as valid and started `GTA5.exe`. Rockstar asked for an email code once more after this change.

## 5. Freezes

- With GameNative's Epic overlay on, every window froze two seconds after the game window appeared. With
  **Disable Epic Overlay** it did not.
- With `GTA5_BE.exe` (BattlEye), the game ended when story mode loaded. `-nobattleye` fixed that.
- About 20 s into story mode the X server froze again: Social Club's CEF GPU helper had stopped reading its X
  connection, and GameNative's X server blocks on such a client while holding its global lock
  ([X-SERVER-FREEZE.md](how-it-works/X-SERVER-FREEZE.md)). Ending only that helper unfroze it every time, so the
  launcher stand-in now watches the X server and does that by itself. A fourth `libcef.dll` patch that turned off
  Chromium's GPU crash limit made the helper's start-up crashes last so long that half the starts failed; it was
  dropped.

## 6. Story mode

With all of that, the prologue loaded and played with the player in control: 31.3 FPS, held at 30, no frame over
100 ms in a 65 s window ([TESTING.md](guides/TESTING.md)).

## 7. Twice as fast

The 30 FPS cap was the game's own choice: `VSync` 2 (Half) in `settings.xml`. With VSync off and the game at
1280x720 in a borderless window (exclusive fullscreen minimized itself whenever Android took the focus), the same
scene ran at 59.5 FPS.

## Side lessons

- `adb bugreport` while Android shows "isn't responding" can hang the system server; Android then restarts itself.
- Opening Android's quick settings pauses GameNative; GTA V then needs a tap on its window to draw again.
- For a sign-in away from the device, a small web page that showed the Thor's screen and forwarded taps and typed text
  (Android `input text` reaches Wine's text fields) let the account owner type their own password and code.
