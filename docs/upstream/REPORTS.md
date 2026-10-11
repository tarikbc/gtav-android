# Notes for upstream

Two findings from this project belong to GameNative, not to this repo. GameNative asks for a Discord conversation
before a GitHub issue, so these are drafts to post there; each names the evidence in this repo.

## 1. The X server freezes when one client stops reading

**What happens.** `XServer` writes to a client under its global lock, and `ClientSocket.write` blocks when the
client's socket buffer is full. One client that stops reading (Social Club's CEF GPU helper, whose `CrGpuMain`
thread does not pump messages while it is busy) therefore stops every other client: the game's window freezes, the
touch handler blocks, Android shows "GameNative isn't responding", and about 60 s later the game exits.

**Evidence.** [docs/how-it-works/X-SERVER-FREEZE.md](../how-it-works/X-SERVER-FREEZE.md): the Java stacks of the
frozen app, the client that holds the lock, and the workaround in this repo's launcher (a watchdog that probes the
server through `GetCursorPos` and ends the stuck helper).

**Suggestion.** Write to clients outside the global lock, or with a per-client queue and a bounded wait; drop or
disconnect a client whose queue stays full, as X servers do.

## 2. The game process is not the one GameNative pins

**What happens.** `PowerManager` pins the process named in the container's executable path to the fast cores. For
games started through a launcher (Rockstar's here, but any launcher-started game), the real game process is a
grandchild with every core allowed. Android's scheduler then parks the game's heaviest threads on the little cores
in some sessions: on the AYN Thor (Snapdragon 8 Gen 2), pass 4 of GTA V's benchmark ran at 24 FPS instead of 48,
with the GPU 20 % busy, in 3 of 12 runs.

**Evidence.** [docs/how-it-works/PERFORMANCE.md](../how-it-works/PERFORMANCE.md), "The bad mode: the little cores":
the per-thread core samples of a bad run and a good run, and the fix in this repo's launcher (a thread that pins
`GTA5.exe` and parks the launcher tree on the little cores).

**Suggestion.** An option to pin every process of the Wine session except a list, or to pin the process that owns
the foreground window; and the GPU power level held at its top value as a per-container option in the UI (it is in
the power profile already; it gave +22 % here because the kgsl governor keeps the clock low when the GPU looks half
busy).

## Not for upstream

- Social Club's CEF GPU helper dying at start (`skia_output_surface_impl.cc:1330`) is Rockstar's build against
  Wine's GL path; this repo renders it in software instead.
- `socialclub.dll` is signature-checked; nothing there can change.
