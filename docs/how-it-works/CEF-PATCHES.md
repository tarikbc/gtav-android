# Social Club's libcef.dll: four patches

The Rockstar launcher's UI, including the sign-in page, is Chromium (CEF 143, Chromium 143.0.7499.193) running in
`SocialClubHelper.exe` processes from `C:\Program Files\Rockstar Games\Social Club`. Under FEX on GameNative's
ARM64EC Wine, the stock `libcef.dll` never shows a usable sign-in page. Four small changes fix that.
`EpicGamesLauncher.exe` applies them at each start if the file is the known original (Social Club 2.4.0.240,
249,338,488 bytes, SHA-1 `2320e1e0b0e2d1cee8f89e80a6dcf9cb3d1a6ffd`). A copy of the original stays as
`libcef.dll.orig`.

`socialclub.dll` is signature-checked (any changed byte and `PlayGTAV.exe` refuses to start the game), so the
fixes go into `libcef.dll`, which is not. Rockstar passes its Chromium switches inside `socialclub.dll`, so a switch
cannot simply be added; the patches rename strings and pointers instead.

| File offset | Before | After | Why |
|---|---|---|---|
| `0xb4a3bc` | `28` | `20` | V8's address-space constant (40 bits to 32 bits) |
| `0xd790f12` | `tmmon64.dll` | `ntdll.dll` | Stack sampling profiler off |
| `0xe471a08` | `6b a3 8e` | `c4 02 02` | WebGPU off |
| `0xd1dd2dd` | `disable-gpu` | `disable-pinch` | CEF renders in software (no GPU helper crash loop) |

## 1. V8 and the address space

The Thor's kernel gives processes 39 bits of user address space. V8's reservation sized for 40 bits (`0x28`)
failed in the renderers; with the constant at 32 bits (`0x20`) they start. A FEX build with a larger address-space
setting did not help, because the limit is the kernel's.

## 2. The stack sampling profiler

Chromium samples thread stacks in the background. Under FEX on ARM64EC this sampling deadlocked the browser
process's IO thread (`Chrome_IOThread`), and every child process gave up with "Terminating current process after 15
seconds with no connection". Chromium skips the profiler when `GetModuleHandleA("tmmon64.dll")` finds that module (a
Trend Micro module known to conflict). The patch renames the string to `ntdll.dll`, which is always loaded, so the
profiler never starts. Passing `--disable-stack-profiler` has the same effect, but the switch cannot be added.

## 3. WebGPU

The sign-in page's renderer crashed in `blink::GPU::RequestAdapterImpl` → `gpu::CommandHeader::Init` (an access
violation), so the window stayed hidden. Rockstar already passes `--disable-features=SpareRendererForSitePerProcess`.
The patch points the `kWebGPUService` feature's name (a pointer in `.data`) at the string
`SpareRendererForSitePerProcess`, so that switch now turns WebGPU off too.

## 4. GPU rendering off

Social Club's GPU helper (`SocialClubHelper.exe --type=gpu-process`) dies at start with
`FATAL components\viz\service\display_embedder\skia_output_surface_impl.cc:1330` (its Skia surface has no valid
format on this GL path; `Renderer\chrome_debug.log` shows three in a row). Chromium restarts it, and after a
few crashes gives up on it; whether the launcher's page ever shows depended on that race. On 2026-10-10 about half
the starts ended with a blank sign-in page, which cost the benchmark series an hour. During the game the same helper
took 24 % of a fast core, and it is the process whose stuck `CrGpuMain` thread freezes GameNative's X server
([X-SERVER-FREEZE.md](X-SERVER-FREEZE.md)).

Rockstar always passes `--disable-pinch` to its CEF browsers. The patch renames libcef's own name for the switch
`disable-gpu` to `disable-pinch` (the string has seven padding bytes after it, so the longer name fits), so CEF sees
`--disable-gpu` on every command line it gets and renders in software. Checked before the patch with the stock CEF
sample client (`cefclient.exe --disable-gpu`): software compositing presents on this Wine and X server. With the
patch: zero FATAL lines in the CEF log, the sign-in page at the first try (`Auth` at 63 s, `MainWindow` at 87 s, the
game at 111 s). A GPU helper process still exists; it hosts the software display compositor.

`socialclub.dll` has its own switch table (`disable-gpu` is in it, at `0x34ee68`), but the file is signature-checked:
with one string changed the launcher logs "Could not do OpenProcess on parent process" and then
`SC_INIT_ERR_WEBSITE_FAILED_LOAD`.

## Tried and dropped

- Turning off Chromium's GPU crash limit (renaming the switch `disable-gpu-process-crash-limit` to `disable-pinch`, a
  switch Rockstar always passes). Social Club's GPU helper crashes a few times while the launcher starts; without the
  limit that went on much longer (18 to 36 crash lines instead of 3), and 2 of 4 starts failed the launcher's check
  ("Launch validation had fatal error!"). The limit is not needed for the X server watchdog: Chromium restarted the
  GPU helper after each of three kills in a row. `EpicGamesLauncher.exe` undoes this rename where an earlier build
  applied it.
- `--in-process-gpu` (the same rename trick on `in-process-gpu`): the Social Club browser died at start
  ("Browser terminated and could not recover", `SC_INIT_ERR_WEBSITE_FAILED_LOAD`).
- DXVK's `dxgi.dll`/`d3d11.dll` for `SocialClubHelper.exe` (Proton sets them to Wine's builtin wined3d for it): the
  GPU helper then ran on DXVK, but the X server still froze.
