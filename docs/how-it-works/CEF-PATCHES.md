# Social Club's libcef.dll: four patches

The Rockstar launcher's UI, including the sign-in page, is Chromium (CEF 143, Chromium 143.0.7499.193) running in
`SocialClubHelper.exe` processes from `C:\Program Files\Rockstar Games\Social Club`. Under FEX on GameNative's
ARM64EC Wine, the stock `libcef.dll` never shows a usable sign-in page. Four small changes fix that.
`EpicGamesLauncher.exe` applies them at each start if the file is the known original (Social Club 2.4.0.240,
249,338,488 bytes, SHA-1 `2320e1e0b0e2d1cee8f89e80a6dcf9cb3d1a6ffd`); the result has SHA-1
`1be6f14b78ce9efa3d29f82ef2172eb14fc11ebd`. A copy of the original stays as `libcef.dll.orig`.

`socialclub.dll` is signature-checked (any changed byte and `PlayGTAV.exe` refuses to start the game), so the
fixes go into `libcef.dll`, which is not. Rockstar passes its Chromium switches inside `socialclub.dll`, so a switch
cannot simply be added; the patches rename strings and pointers instead.

| File offset | Before | After | Why |
|---|---|---|---|
| `0xb4a3bc` | `28` | `20` | V8's address-space constant (40 bits to 32 bits) |
| `0xd790f12` | `tmmon64.dll` | `ntdll.dll` | Stack sampling profiler off |
| `0xe471a08` | `6b a3 8e` | `c4 02 02` | WebGPU off |
| `0xd1dd390` | `disable-gpu-process-crash-limit` | `disable-pinch` | GPU helper restarts never give up |

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

## 4. The GPU crash limit

Chromium stops restarting its GPU helper after a few crashes and then exits ("GPU process isn't usable"). The X
server watchdog ([X-SERVER-FREEZE.md](X-SERVER-FREEZE.md)) ends that helper on purpose, and the helper also crashes a
few times while the launcher starts. The patch renames the switch `disable-gpu-process-crash-limit` to
`disable-pinch`, a switch Rockstar always passes, so the limit is off.

## Tried and dropped

- `--in-process-gpu` (the same rename trick on `in-process-gpu`): the Social Club browser died at start
  ("Browser terminated and could not recover", `SC_INIT_ERR_WEBSITE_FAILED_LOAD`).
- DXVK's `dxgi.dll`/`d3d11.dll` for `SocialClubHelper.exe` (Proton sets them to Wine's builtin wined3d for it): the
  GPU helper then ran on DXVK, but the X server still froze.
