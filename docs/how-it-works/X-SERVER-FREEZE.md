# The X server freeze

**Symptom.** About 20 s after STORY MODE (or 2 s after the Epic overlay starts), every window stops updating. A
touch then makes Android show "GameNative isn't responding". About a minute later `GTA5.exe` ends.

## Cause

GameNative's X server (Winlator's Java X server) handles all clients on one thread and writes events to each
client's socket with **blocking** writes while it holds the server's global lock. If one client stops reading its
connection, its socket buffer fills, the write blocks, and the whole server stops. Android's UI thread then waits for
the same lock when it forwards a touch, which is the "isn't responding" dialog.

The Java stacks from that moment (from the ANR traces):

```
"main" ... Waiting
  at java.util.concurrent.locks.ReentrantLock.lock
  at com.winlator.xserver.XServer$MultiXLock.<init>
  at com.winlator.xserver.XServer.lock
  at com.winlator.xserver.XServer.injectPointerMoveDelta
  at com.winlator.widget.TouchpadView.handleFingerMove

"XConnectorEpoll:.../tmp/.X11-unix/X0 [XClientConnectionHandler/XClientRequestHandler]" ... Native
  native: libc.so (write+8)
  at com.winlator.xconnector.ClientSocket.write
  at com.winlator.xconnector.XOutputStream.flush
  at com.winlator.xserver.events.ConfigureNotify.send
  at com.winlator.xserver.WindowManager.configureWindow
  at com.winlator.xserver.XClientRequestHandler.handleNormalRequest
```

The client that stopped reading was **Social Club's CEF GPU helper** (`SocialClubHelper.exe --type=gpu-process`):
ending only that process unblocked the server at once, every time it was tried (4 times). Its main thread
(`CrGpuMain`) waits in Chromium's task loop and does not pump Windows messages, so Wine never reads the X events
queued for that thread. Wine subscribes every thread that opens an X connection to property changes on the root
window (`XSelectInput(root, PropertyChangeMask)` in `x11drv_init_thread_data`), so such a thread keeps receiving
events it never reads. With the Epic overlay on, the trace above showed the same blocked write; that blocking client was not
identified, but `EOSOverlayRenderer` is also CEF-based.

A conventional X server (Xorg) keeps a per-client output buffer and uses non-blocking writes, so one slow client
does not stop the others.

## The workaround

`EpicGamesLauncher.exe` runs a watchdog thread (`xwatch`):

- A probe thread calls `GetCursorPos`, which Wine turns into `XQueryPointer`, an X round trip. It then pumps its own
  messages for a second, so it never becomes a blocked client itself.
- If no probe has returned for about 3 s, the watchdog ends every `SocialClubHelper.exe` whose command line has
  `--type=gpu-process`. Chromium starts a new GPU helper (it did after each of three kills in a row).
- It logs each stall to `%TEMP%\EpicGamesLauncher.log`.

Do not end the whole `SocialClubHelper.exe` tree: the new browser signs in again and Rockstar signs the first session
out ("Kicked by duplicate sign in"), and the launcher shuts down.

## The real fix

GameNative's `XConnector` should not block on a slow client: non-blocking client sockets with a per-client output
buffer, as Xorg does, and some limit for a client whose buffer only grows. Separately, `WindowManager.configureWindow`
sends `Expose` to every listener of a resized window, not only to those that asked for exposure events.

## Tried and dropped

- `UseXRandR=N` for `SocialClubHelper.exe` (Wine's per-app X11 Driver setting): the launcher's window never appeared.
- DXVK instead of wined3d in the Social Club processes: the GPU helper still blocked the server.
- `--in-process-gpu`: the Social Club browser died at start.
- A Windows-side X client to watch the root window's events: this Wine has no `AF_UNIX` sockets (error 10047).
