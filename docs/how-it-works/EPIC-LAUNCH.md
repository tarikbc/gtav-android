# The Epic launch: parent process, BattlEye, overlay

How GameNative starts an Epic game, and the three things GTA V needs on top of that.

## What GameNative does

For an Epic game, GameNative runs the container's executable path (default `A:\PlayGTAV.exe`; `A:` is the game
folder) with Epic's launch arguments: a fresh exchange code (`-AUTH_PASSWORD`, valid for a few minutes and only once),
`-AUTH_TYPE=exchangecode`, `-epicapp=`, `-epicenv=Prod`, `-EpicPortal`, the Epic user name, id, locale and sandbox
id. `PlayGTAV.exe` starts the Rockstar Games Launcher (`Launcher.exe`) with those arguments.

If the executable path is an absolute Windows path (for example `D:\gtav-android\EpicGamesLauncher.exe`), GameNative
uses it as it is and still adds the Epic arguments. That is what makes a wrapper possible.

## 1. The Epic Games Launcher as parent

Started straight from GameNative, the Rockstar launcher logs:

```
[external] Creating epic min mode launch
[external] Epic Games Launcher not detected as parent process.
[startup] Relaunch from third party platform required
[ ERROR ] [startup] Failed to relaunch from third party platform. Load will continue normally.
```

It wants the Epic Games Launcher to start the game again, cannot (there is none in Wine), and opens its full UI.
After sign-in that UI only offers "Buy now": it never starts `GTA5.exe`.

`EpicGamesLauncher.exe` from this repo is a process with that name. It starts `PlayGTAV.exe` (next to itself, else
`A:\PlayGTAV.exe`) with the same arguments and waits for it. The launcher then logs:

```
[external] Running from Epic Games Launcher.
[external] Epic ownership request indicated valid entitlement of at least once audience
[external] Successfully setup title
[external] Client is ready to attempt a launch.
```

and starts the game after sign-in. The same idea is used by the Heroic Games Launcher on Linux and macOS.

**Where to keep it.** Started as `A:\EpicGamesLauncher.exe` (in the game folder) it dies at once with an illegal
instruction (`c000001d`) inside FEX's ARM64EC library, even when started by hand. The same file runs from `C:`, `D:`,
or as `A:\ewtest.exe`. The cause was not found; `D:\gtav-android\` (the Download folder) works.

## 2. `-nobattleye`

Without it, the launcher starts `GTA5_BE.exe` (the BattlEye starter), which starts `GTA5.exe`. The menu works, but
when story mode loads the game ends. With `-nobattleye` on the `PlayGTAV.exe` command line the launcher starts
`GTA5.exe` directly and story mode loads. GTA Online needs BattlEye and does not work either way.

GameNative does not pass the container's own arguments to Epic games, so the wrapper adds `-nobattleye` itself. The
container variable `EPIC_EXTRA_ARGS` replaces that default (set it to `-nobattleye -other` to add more).

## 3. The Epic overlay

GameNative installs the EOS overlay into the Wine prefix for Epic games. With it on, `EOSOverlayRenderer` started
next to the game, and two seconds later every window froze ([X-SERVER-FREEZE.md](X-SERVER-FREEZE.md)). With
**Disable Epic Overlay** on, that freeze did not come back.

## Signing in

The Rockstar sign-in page is Social Club's CEF browser. It needs the [libcef patches](CEF-PATCHES.md). Rockstar can
ask for a code sent by email at sign-in; with **Auto Sign In** ticked, later starts sign in by themselves.
