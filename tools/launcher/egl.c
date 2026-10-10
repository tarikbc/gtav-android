// EpicGamesLauncher.exe for GTA V (Epic) on GameNative. Point the container's executable path at this file; it
// does three things, then starts the game and waits for it:
//
// 1. Parent process. The Rockstar Games Launcher does its Epic "min mode" launch only when a process named
//    EpicGamesLauncher.exe started the game. Otherwise it logs "Epic Games Launcher not detected as parent process",
//    asks the Epic launcher to relaunch the title, fails, and shows its own UI without starting GTA5.exe.
//    The arguments from GameNative (the Epic exchange code and ids) are passed on unchanged and never logged.
//    Extra arguments: EPIC_EXTRA_ARGS (container env var), default -nobattleye (without it the launcher starts
//    GTA5_BE.exe and the game ends when story mode loads).
//
// 2. Social Club libcef.dll. Rockstar's CEF build needs three byte changes under FEX on ARM64EC Wine (see
//    docs/how-it-works/CEF-PATCHES.md). They are applied to the installed file only when all three sites hold the
//    known original bytes (Social Club 2.4.0.240); a copy is kept as libcef.dll.orig. Any other version is left alone.
//
// 3. X server watchdog. GameNative's X server writes events with blocking writes under a global lock; when Social
//    Club's CEF GPU helper stops reading its X connection, every window freezes (docs/how-it-works/X-SERVER-FREEZE.md).
//    A thread probes the server with an X round trip (GetCursorPos -> XQueryPointer) and ends the GPU helper after a
//    stall; Chromium starts a new one. XWATCH=0 turns this off.
//
// usage: EpicGamesLauncher.exe [target.exe] <args...>   (no target: PlayGTAV.exe next to this file, else A:\PlayGTAV.exe)
// log: %TEMP%\EpicGamesLauncher.log
// Keep this file outside the game folder: as A:\EpicGamesLauncher.exe it dies at once with c000001d inside
// libarm64ecfex.dll (GameNative 1.3.0, proton-11.0-99-arm64ec, FEX 2605); from D: or C: it runs.
#include <windows.h>
#include <tlhelp32.h>
#include <winternl.h>
#include <stdarg.h>
#include <stdio.h>
#include <wchar.h>

static FILE *logf;
static CRITICAL_SECTION log_cs;

static void logline(const wchar_t *fmt, ...) {
    if (!logf) return;
    EnterCriticalSection(&log_cs);
    SYSTEMTIME st;
    GetLocalTime(&st);
    fwprintf(logf, L"%02d:%02d:%02d.%03d ", st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    va_list ap;
    va_start(ap, fmt);
    vfwprintf(logf, fmt, ap);
    va_end(ap);
    fwprintf(logf, L"\n");
    fflush(logf);
    LeaveCriticalSection(&log_cs);
}

// ---- 2. libcef.dll ----------------------------------------------------------------------------------------------

#define LIBCEF L"C:\\Program Files\\Rockstar Games\\Social Club\\libcef.dll"
#define LIBCEF_SIZE 249338488LL  // Social Club 2.4.0.240 (CEF 143.0.14, Chromium 143.0.7499.193)

struct site { LONGLONG off; int len; const char *old, *new_; const wchar_t *what; };
static const struct site sites[] = {
    {0xb4a3bc, 1, "\x28", "\x20", L"V8 address space 40 -> 32 bits (the Thor's kernel has 39-bit user addresses)"},
    {0xd790f12, 11, "tmmon64.dll", "ntdll.dll\0\0", L"stack sampling profiler off (deadlocks the IO thread under FEX)"},
    {0xe471a08, 3, "\x6b\xa3\x8e", "\xc4\x02\x02", L"WebGPU feature name -> SpareRendererForSitePerProcess (disabled)"},
};
#define NSITES (sizeof(sites) / sizeof(sites[0]))

// v0.1.0 also renamed the switch disable-gpu-process-crash-limit; with it, the GPU helper's crash loop at launcher
// start lasted longer and the launch check failed ("Launch validation had fatal error!"). Undo it where present.
static const struct site undo = {0xd1dd390, 31, "disable-pinch\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0",
                                 "disable-gpu-process-crash-limit", L"undo the v0.1.0 crash-limit rename"};

static void patch_libcef(void) {
    HANDLE f = CreateFileW(LIBCEF, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        logline(L"libcef: not installed yet (the Rockstar launcher installs Social Club on its first start)");
        return;
    }
    LARGE_INTEGER size;
    GetFileSizeEx(f, &size);
    int olds = 0, news = 0;
    for (size_t i = 0; i < NSITES; i++) {
        char buf[64];
        DWORD got = 0;
        LARGE_INTEGER at = {.QuadPart = sites[i].off};
        SetFilePointerEx(f, at, NULL, FILE_BEGIN);
        ReadFile(f, buf, sites[i].len, &got, NULL);
        if (got == (DWORD)sites[i].len && !memcmp(buf, sites[i].old, sites[i].len)) olds++;
        if (got == (DWORD)sites[i].len && !memcmp(buf, sites[i].new_, sites[i].len)) news++;
    }
    char ubuf[64];
    DWORD ugot = 0;
    LARGE_INTEGER uat = {.QuadPart = undo.off};
    SetFilePointerEx(f, uat, NULL, FILE_BEGIN);
    ReadFile(f, ubuf, undo.len, &ugot, NULL);
    int undo_needed = ugot == (DWORD)undo.len && !memcmp(ubuf, undo.old, undo.len);
    int undo_clean = ugot == (DWORD)undo.len && !memcmp(ubuf, undo.new_, undo.len);
    CloseHandle(f);
    if (size.QuadPart != LIBCEF_SIZE || olds + news != (int)NSITES || !(undo_needed || undo_clean)) {
        logline(L"libcef: unknown version (size %lld), left alone; the sign-in page may hang", size.QuadPart);
        return;
    }
    if (news == (int)NSITES && !undo_needed) {
        logline(L"libcef: already patched");
        return;
    }
    if (GetFileAttributesW(LIBCEF L".orig") == INVALID_FILE_ATTRIBUTES && !CopyFileW(LIBCEF, LIBCEF L".orig", TRUE))
        logline(L"libcef: backup failed (error %lu), patching anyway", GetLastError());
    f = CreateFileW(LIBCEF, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        logline(L"libcef: cannot open for writing (error %lu): is the Rockstar launcher running?", GetLastError());
        return;
    }
    for (size_t i = 0; i < NSITES + 1; i++) {
        const struct site *t = i < NSITES ? &sites[i] : &undo;
        if (t == &undo && !undo_needed) break;
        DWORD put = 0;
        LARGE_INTEGER at = {.QuadPart = t->off};
        SetFilePointerEx(f, at, NULL, FILE_BEGIN);
        WriteFile(f, t->new_, t->len, &put, NULL);
        logline(L"libcef: %ls: %ls", t->what, put == (DWORD)t->len ? L"done" : L"FAILED");
    }
    CloseHandle(f);
}

// ---- 3. X server watchdog -----------------------------------------------------------------------------------------

#define STALL_MS 1500
static volatile LONG last_beat;

static DWORD WINAPI probe(void *arg) {
    for (;;) {
        POINT p;
        GetCursorPos(&p);  // XQueryPointer: blocks while the X server is stuck
        InterlockedExchange(&last_beat, (LONG)GetTickCount());
        DWORD until = GetTickCount() + 1000;  // pump our own X events so this thread never becomes the blocker
        for (DWORD now; (now = GetTickCount()) < until;) {
            MsgWaitForMultipleObjectsEx(0, NULL, until - now, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
            MSG m;
            while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) DispatchMessageW(&m);
        }
    }
    return 0;
}

static BOOL is_gpu_helper(DWORD pid) {  // command line via the PEB (x64: +0x20 ProcessParameters, +0x70 CommandLine)
    static wchar_t cl[8192];
    HANDLE h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!h) return FALSE;
    PROCESS_BASIC_INFORMATION pbi;
    ULONG len;
    ULONG_PTR params = 0;
    UNICODE_STRING us;
    SIZE_T got;
    BOOL gpu = FALSE;
    if (NtQueryInformationProcess(h, ProcessBasicInformation, &pbi, sizeof(pbi), &len) == 0 &&
        ReadProcessMemory(h, (BYTE *)pbi.PebBaseAddress + 0x20, &params, sizeof(params), &got) &&
        ReadProcessMemory(h, (BYTE *)params + 0x70, &us, sizeof(us), &got) && us.Length < sizeof(cl) - 2 &&
        ReadProcessMemory(h, us.Buffer, cl, us.Length, &got)) {
        cl[us.Length / 2] = 0;
        gpu = wcsstr(cl, L"--type=gpu-process") != NULL;
    }
    CloseHandle(h);
    return gpu;
}

static int end_gpu_helpers(void) {
    int n = 0;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32W pe = {sizeof(pe)};
    for (BOOL ok = Process32FirstW(snap, &pe); ok; ok = Process32NextW(snap, &pe)) {
        if (_wcsicmp(pe.szExeFile, L"SocialClubHelper.exe") || !is_gpu_helper(pe.th32ProcessID)) continue;
        HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
        if (h && TerminateProcess(h, 1)) n++;
        if (h) CloseHandle(h);
        logline(L"xwatch: ended Social Club GPU helper pid %lu", pe.th32ProcessID);
    }
    CloseHandle(snap);
    return n;
}

static DWORD WINAPI watchdog(void *arg) {
    InterlockedExchange(&last_beat, (LONG)GetTickCount());
    CreateThread(NULL, 0, probe, NULL, 0, NULL);
    int stalls = 0;
    for (;;) {
        Sleep(250);
        DWORD age = GetTickCount() - (DWORD)last_beat;
        if (age < STALL_MS + 1000) continue;  // a probe cycle is 1 s of pumping plus the round trip
        // A paused session (GameNative's pause button) also stops this thread; the first check after it sees a
        // huge age with a server that answers at once, so give the probe a moment before acting.
        Sleep(500);
        if (GetTickCount() - (DWORD)last_beat < STALL_MS + 1000) continue;
        stalls++;
        logline(L"xwatch: X stall #%d (no reply for %lu ms)", stalls, GetTickCount() - (DWORD)last_beat);
        if (!end_gpu_helpers()) logline(L"xwatch: no GPU helper to end");
        for (int i = 0; i < 40 && GetTickCount() - (DWORD)last_beat >= STALL_MS + 1000; i++) Sleep(250);
        logline(L"xwatch: X server %ls", GetTickCount() - (DWORD)last_beat < STALL_MS + 1000 ? L"answers again" : L"still stuck");
    }
    return 0;
}

// ---- pin: keep GTA5.exe off the little cores -----------------------------------------------------------------------
// Android's scheduler sometimes parks the game's two heaviest threads on the slow cores (cpu0-2 on the Thor, 2.0 GHz
// A510) for most of a session: pass 4 of the benchmark then runs at 24 FPS instead of 48, with the GPU 20 % busy.
// GameNative pins the process it starts (this stub) to the fast cores, but the game is started by the Rockstar
// launcher and comes up with every core allowed. This thread sets the game's affinity, process and threads, to
// GTA_PIN_MASK (hex, default f8 = cpu3 to cpu7 on an 8-core SoC; 0 turns it off) as soon as the process exists.

static DWORD_PTR pin_mask = 0xf8;

static int pin_process(DWORD pid) {
    HANDLE h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_INFORMATION, FALSE, pid);
    if (!h) return -1;
    DWORD_PTR cur = 0, sys = 0;
    GetProcessAffinityMask(h, &cur, &sys);
    DWORD_PTR want = pin_mask & sys;
    int n = 0;
    if (want && cur != want) {
        SetProcessAffinityMask(h, want);
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te = {sizeof(te)};
        for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
            if (te.th32OwnerProcessID != pid) continue;
            HANDLE t = OpenThread(THREAD_SET_INFORMATION | THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
            if (t && SetThreadAffinityMask(t, want)) n++;
            if (t) CloseHandle(t);
        }
        CloseHandle(snap);
        logline(L"pin: GTA5.exe pid %lu affinity %llx -> %llx (%d threads)", pid, (unsigned long long)cur,
                (unsigned long long)want, n);
    }
    CloseHandle(h);
    return n;
}

// While the game runs, the Rockstar launcher tree keeps working: Social Club's renderer helper (the overlay's web
// page) took 59 % of a core in a benchmark, its GPU helper 24 %, the launcher 12 %. They are not pinned, so they
// take big-core time from the game. Once GTA5.exe exists, this moves them to GTA_SC_MASK (hex, default 07 = the
// little cores) at below-normal priority. Ending them is not an option: Social Club then ends the session.

static DWORD_PTR sc_mask = 0x07;
static const wchar_t *sc_names[] = {L"SocialClubHelper.exe", L"Launcher.exe", L"RockstarService.exe", L"RockstarErrorHandler.exe", NULL};

static void park_process(DWORD pid, const wchar_t *name) {
    HANDLE h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_INFORMATION, FALSE, pid);
    if (!h) return;
    DWORD_PTR cur = 0, sys = 0;
    GetProcessAffinityMask(h, &cur, &sys);
    DWORD_PTR want = sc_mask & sys;
    if (want && cur != want) {
        SetProcessAffinityMask(h, want);
        SetPriorityClass(h, BELOW_NORMAL_PRIORITY_CLASS);
        int n = 0;
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te = {sizeof(te)};
        for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
            if (te.th32OwnerProcessID != pid) continue;
            HANDLE t = OpenThread(THREAD_SET_INFORMATION | THREAD_QUERY_INFORMATION, FALSE, te.th32ThreadID);
            if (t && SetThreadAffinityMask(t, want)) n++;
            if (t) CloseHandle(t);
        }
        CloseHandle(snap);
        logline(L"pin: %ls pid %lu parked on cores %llx, below normal priority (%d threads)", name, pid,
                (unsigned long long)want, n);
    }
    CloseHandle(h);
}

static DWORD WINAPI pinner(void *arg) {
    for (;;) {
        Sleep(2000);
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        PROCESSENTRY32W pe = {sizeof(pe)};
        int game = 0;
        for (BOOL ok = Process32FirstW(snap, &pe); ok; ok = Process32NextW(snap, &pe))
            if (!_wcsicmp(pe.szExeFile, L"GTA5.exe")) {
                game = 1;
                pin_process(pe.th32ProcessID);
            }
        if (game && sc_mask) {
            for (BOOL ok = Process32FirstW(snap, &pe); ok; ok = Process32NextW(snap, &pe))
                for (int i = 0; sc_names[i]; i++)
                    if (!_wcsicmp(pe.szExeFile, sc_names[i])) park_process(pe.th32ProcessID, sc_names[i]);
        }
        CloseHandle(snap);
    }
    return 0;
}

// ---- 1. start the game ---------------------------------------------------------------------------------------------

static const wchar_t *skip_token(const wchar_t *p) {
    while (*p == L' ' || *p == L'\t') p++;
    int quoted = 0;
    for (; *p; p++) {
        if (*p == L'"') quoted = !quoted;
        else if (!quoted && (*p == L' ' || *p == L'\t')) break;
    }
    while (*p == L' ' || *p == L'\t') p++;
    return p;
}

static int ends_with_exe(const wchar_t *s, size_t n) {
    while (n && s[n - 1] == L'"') n--;
    return n >= 4 && _wcsnicmp(s + n - 4, L".exe", 4) == 0;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show) {
    static wchar_t target[MAX_PATH], dir[MAX_PATH], workdir[MAX_PATH], cmd[32768], path[MAX_PATH], extra[1024];
    InitializeCriticalSection(&log_cs);
    GetTempPathW(MAX_PATH, path);
    wcsncat(path, L"EpicGamesLauncher.log", MAX_PATH - wcslen(path) - 1);
    logf = _wfopen(path, L"a");
    logline(L"--- start");

    const wchar_t *tail = skip_token(GetCommandLineW());
    const wchar_t *rest = skip_token(tail);
    size_t first_len = rest - tail;
    while (first_len && (tail[first_len - 1] == L' ' || tail[first_len - 1] == L'\t')) first_len--;
    GetModuleFileNameW(NULL, dir, MAX_PATH);
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (slash) *slash = 0;
    if (first_len && ends_with_exe(tail, first_len)) {  // explicit target
        size_t j = 0;
        for (size_t i = 0; i < first_len && j < MAX_PATH - 1; i++)
            if (tail[i] != L'"') target[j++] = tail[i];
        target[j] = 0;
        tail = rest;
    } else {  // PlayGTAV.exe next to this file, else on A: (GameNative maps the Epic install folder there)
        _snwprintf(target, MAX_PATH, L"%ls\\PlayGTAV.exe", dir);
        if (GetFileAttributesW(target) == INVALID_FILE_ATTRIBUTES) wcscpy(target, L"A:\\PlayGTAV.exe");
    }
    wcsncpy(workdir, target, MAX_PATH - 1);
    slash = wcsrchr(workdir, L'\\');
    if (slash) *slash = 0;

    DWORD n = GetEnvironmentVariableW(L"EPIC_EXTRA_ARGS", extra, 1024);
    if (!n && GetLastError() == ERROR_ENVVAR_NOT_FOUND) wcscpy(extra, L"-nobattleye");
    patch_libcef();
    wchar_t xw[8];
    if (!(GetEnvironmentVariableW(L"XWATCH", xw, 8) && xw[0] == L'0')) CreateThread(NULL, 0, watchdog, NULL, 0, NULL);
    else logline(L"xwatch: off (XWATCH=0)");
    wchar_t pm[32];
    if (GetEnvironmentVariableW(L"GTA_PIN_MASK", pm, 32)) pin_mask = (DWORD_PTR)wcstoull(pm, NULL, 16);
    if (GetEnvironmentVariableW(L"GTA_SC_MASK", pm, 32)) sc_mask = (DWORD_PTR)wcstoull(pm, NULL, 16);
    if (pin_mask) {
        CreateThread(NULL, 0, pinner, NULL, 0, NULL);
        logline(L"pin: GTA5.exe will be kept on cores %llx", (unsigned long long)pin_mask);
    } else logline(L"pin: off (GTA_PIN_MASK=0)");

    _snwprintf(cmd, 32768, L"\"%ls\" %ls%ls%ls", target, tail, extra[0] ? L" " : L"", extra);
    STARTUPINFOW si = {sizeof(si)};
    PROCESS_INFORMATION pi;
    BOOL ok = CreateProcessW(target, cmd, NULL, NULL, FALSE, 0, NULL, workdir, &si, &pi);
    logline(L"start %ls (extra args: %ls): %ls (error %lu)", target, extra[0] ? extra : L"none", ok ? L"ok" : L"failed",
            ok ? 0 : GetLastError());
    if (!ok) return 1;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    logline(L"exit 0x%08lx", code);
    return (int)code;
}
