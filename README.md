# GTA V on Android (GameNative)

Play **Grand Theft Auto V Legacy** (the Epic Games Store version) in story mode on an Android handheld with
[GameNative](https://github.com/utkarshdalal/GameNative). Out of the box the Rockstar Games Launcher opens but never
starts the game, its sign-in page hangs, and the screen freezes when story mode loads. One small Windows program
from this repo, `EpicGamesLauncher.exe`, plus a few container settings fix that.

| | GTA V Legacy (Epic) |
|---|---|
| Plays | Story mode: the prologue mission, with the player in control |
| Speed | **31 FPS** (held at 30), median frame 33.4 ms, no frame over 100 ms in a 65 s window, default 800x600 window |
| Controls | The Thor's controller; the touch screen works as a touchpad |
| Online | No. GTA Online needs BattlEye, which does not run here |

![GTA V: the prologue mission, player in control](docs/img/prologue-gameplay-2026-10-10.jpg)

| | |
|---|---|
| ![GTA V main menu](docs/img/main-menu-2026-10-10.jpg) | ![The prologue cutscene](docs/img/prologue-cutscene-2026-10-10.jpg) |

## Status

| | |
|---|---|
| Tested device | AYN Thor (Snapdragon 8 Gen 2, Adreno 740, 16 GB RAM, Android 13), GameNative 1.3.0 |
| Tested game | GTA V Legacy 1.0.3889.0 from the Epic Games Store (Premium Edition), Rockstar Games Launcher 1.0.109.3031, Social Club 2.4.0.240 |
| Works | Rockstar sign-in, the main menu, story mode (the prologue) |
| Not tested | Long sessions, missions after the prologue, other devices, the Steam version, GTA V Enhanced |
| Known issues | [Known issues](#known-issues) below |

## What you need

- An Android device with a Snapdragon / Adreno GPU and GameNative 1.3.0. Only the AYN Thor was tested.
- GTA V on the Epic Games Store, signed in inside GameNative, and a Rockstar Games account linked to that Epic
  account. The download is 117 GB (about 120 GB on disk).
- [`EpicGamesLauncher.exe`](https://github.com/tarikbc/gtav-android/releases/latest/download/EpicGamesLauncher.exe)
  from the latest release (170 KB). It is built from [`tools/launcher/egl.c`](tools/launcher/egl.c).

## Setup

### 1. Put the launcher in the Download folder

Create the folder `Download/gtav-android` on the device and put `EpicGamesLauncher.exe` in it. GameNative maps the
Download folder to drive `D:`, so the file is `D:\gtav-android\EpicGamesLauncher.exe` inside Wine.

Do not put it in the game folder: started from there (drive `A:`), it dies at once inside the emulator.

### 2. The container

Open GTA V in GameNative's Epic library, tap the **cog** next to Play, then **Edit container**. Set:

| Tab | Setting | Value |
|---|---|---|
| General | Container Variant | `bionic` |
| General | Wine Version | `proton-11.0-99-arm64ec-1` |
| General | Executable Path | `D:\gtav-android\EpicGamesLauncher.exe` |
| General | Disable Epic Overlay | **on** |
| Graphics | Graphics Driver / Version | `Wrapper` / `turnip_v26.0.0_R6` |
| Graphics | DX Wrapper | `DXVK` (2.4.1 gplasync) |
| Emulation | 64-bit Emulator | `FEXCore` |
| Emulation | FEXCore Version / Preset | `2605` / `INTERMEDIATE` |

Then tap **Save**. GameNative's own choice for this game (Box64 with an x86-64 Proton) fails: the Rockstar launcher
stops with "Failed to connect to the Rockstar Games Library Service".

What `EpicGamesLauncher.exe` does at each start ([EPIC-LAUNCH.md](docs/how-it-works/EPIC-LAUNCH.md)):

1. It starts the game as the Epic Games Launcher would, so the Rockstar launcher accepts the Epic launch.
2. It adds `-nobattleye`, without which the game ends when story mode loads. A container variable
   `EPIC_EXTRA_ARGS` replaces that default.
3. It patches Social Club's `libcef.dll` once (4 bytes and 2 strings, a backup stays as `libcef.dll.orig`), so the
   Rockstar sign-in page loads ([CEF-PATCHES.md](docs/how-it-works/CEF-PATCHES.md)). It patches only the known version
   and leaves any other alone.
4. It watches GameNative's X server and unfreezes it when Social Club stops reading
   ([X-SERVER-FREEZE.md](docs/how-it-works/X-SERVER-FREEZE.md)). `XWATCH=0` turns this off.

Its log is `C:\users\xuser\AppData\Local\Temp\EpicGamesLauncher.log`. It never writes the Epic login arguments.

### 3. First start

1. Tap Play. The Rockstar Games Launcher installer opens: accept the terms and install. The launcher then installs
   Social Club and may close; tap Play again. This second start applies the `libcef.dll` patch.
2. The Rockstar sign-in window opens. Sign in with your Rockstar account and tick **Auto Sign In**, so later starts
   skip this window. Rockstar may send a code to your email.
3. The game starts after about a minute. On the first start it shows **Display Calibration**; press Enter (or A).
4. In the main menu, choose **STORY MODE**.

## What to expect

One 65 s window in the prologue, player standing still, default settings (800x600 window), frame times from
Android's compositor ([TESTING.md](docs/guides/TESTING.md)):

| FPS | mean frame | median | p99 | worst | frames over 50 ms | over 100 ms |
|---|---|---|---|---|---|---|
| 31.3 | 32.0 ms | 33.4 ms | 33.4 ms | 50.1 ms | 19 | 0 |

The game is held at 30 FPS with GPU (about 65 %) and CPU (about 25 %) to spare. Removing that cap and raising the
resolution is the next step.

## Known issues

- **White launcher window, "Launch validation had fatal error!"** (1 of 2 starts in testing). Social Club's GPU helper
  crashes several times while the launcher starts; if that overlaps the launch check, the launcher shows an empty
  window and the game does not start. Close the game in GameNative and tap Play again.
- **Pulling down Android's quick settings pauses the game.** GameNative shows its Play button; tap it, then tap the
  game window once so GTA V gets the focus back.
- **The screen freezes and Android says "GameNative isn't responding".** That is the X server freeze. The launcher
  watches for it; if it still happens, check the log above for `xwatch` lines and tell us in an issue.
- **GTA Online** does not work (BattlEye).

## How it was found

[STORY.md](docs/STORY.md) tells the whole path, from a Steam copy that Rockstar would not activate to story mode on
the Epic copy. [TOOLS.md](docs/guides/TOOLS.md) describes the small Windows tools used to look inside the Wine
session while the X server is stuck.

## Building

`tools/build.sh` builds `EpicGamesLauncher.exe` and the probes with mingw-w64 (`brew install mingw-w64`).

## Credits

- [GameNative](https://github.com/utkarshdalal/GameNative), Wine/Proton and [FEX-Emu](https://github.com/FEX-Emu/FEX).
- The fake `EpicGamesLauncher.exe` idea comes from the [Heroic Games Launcher](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher)
  wiki and [heroic-epic-integration](https://github.com/BananaWorks07/heroic-epic-integration).
- Companion project: [ageofempires-android](https://github.com/tarikbc/ageofempires-android).

GTA V, Rockstar Games and Social Club are trademarks of Take-Two Interactive. This project is not affiliated with them;
it ships no game or Rockstar files, and you need your own copy of the game.
