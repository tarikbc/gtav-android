# Tools for looking inside the Wine session

All are small static x86-64 Windows programs built by `tools/build.sh`. They open no console and no window, so they
also work while GameNative's X server is stuck (a console program needs `conhost.exe`, which needs the X server).
Copy them to the Download folder (drive `D:` in Wine) and start them through GameNative's `winhandler` (see
`tools/run_watch.py` in [ageofempires-android](https://github.com/tarikbc/ageofempires-android): a launch request
holds only 51 bytes of program and arguments).

## wkill

```
wkill.exe list                 process list with parent PIDs and the CEF process type ([gpu-process], [renderer] ...)
wkill.exe cl                   the same, plus the full command line of each SocialClubHelper.exe
wkill.exe NAME|#PID|@TYPE ...  end processes by exe name, by PID, or by CEF type (@gpu-process)
```

Output: `wkill.txt` next to `wkill.exe`. It reads command lines from each process's PEB, because this Wine does not answer
`NtQueryInformationProcess(ProcessCommandLineInformation)`. The `cl` mode prints only Social Club helpers: the
launcher's own command line holds the Epic login code. `wkill.exe wins` also lists windows, but it hangs while the X
server is stuck (loading `winex11.drv` opens a new X connection).

## sdg (stack dump)

```
sdg.exe <pid|exe-name> <out-file>
```

Lists the modules of a process and, for each thread, the return addresses on its stack. Under ARM64EC Wine,
`GetThreadContext` on an emulated thread can hang, so it reads the x64 registers from the thread's CHPE area
(`TEB+0x1788`, `ContextAmd64`). Libcef addresses can be named with Chromium's symbol files for CEF 143.0.14 by
matching code bytes against the stock build.

## Java stacks of a frozen GameNative

Android writes them to `/data/anr/` when it shows "isn't responding"; `adb bugreport` copies them out
(`FS/data/anr/` in the zip). **Do not take the bug report while the dialog is on screen**: on the Thor its window dump
hung Android's system server, and the watchdog restarted Android two minutes later, closing the game. Take it after
the dialog is gone, and copy the zip only after `adb bugreport` prints its final line.

## Notes

- Wine's winsock here has no `AF_UNIX` sockets (`WSAEAFNOSUPPORT`), so a Windows program cannot open the X socket.
- `GetCursorPos` makes an X round trip (`XQueryPointer`): a cheap way to test whether the X server answers.
- A thread that opens an X connection must keep pumping messages, or it becomes a blocked client itself.
