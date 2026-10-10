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
// 2. Social Club libcef.dll. Rockstar's CEF build needs four byte changes under FEX on ARM64EC Wine (see
//    docs/how-it-works/CEF-PATCHES.md). They are applied to the installed file only when all four sites hold the
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
    {0xd1dd390, 31, "disable-gpu-process-crash-limit", "disable-pinch\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0",
     L"switch disable-gpu-process-crash-limit -> disable-pinch (always passed): GPU helper restarts never give up"},
    {0xd790f12, 11, "tmmon64.dll", "ntdll.dll\0\0", L"stack sampling profiler off (deadlocks the IO thread under FEX)"},
    {0xe471a08, 3, "\x6b\xa3\x8e", "\xc4\x02\x02", L"WebGPU feature name -> SpareRendererForSitePerProcess (disabled)"},
};
#define NSITES (sizeof(sites) / sizeof(sites[0]))

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
    CloseHandle(f);
    if (size.QuadPart != LIBCEF_SIZE || olds + news != (int)NSITES) {
        logline(L"libcef: unknown version (size %lld), left alone; the sign-in page may hang", size.QuadPart);
        return;
    }
    if (news == (int)NSITES) {
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
    for (size_t i = 0; i < NSITES; i++) {
        DWORD put = 0;
        LARGE_INTEGER at = {.QuadPart = sites[i].off};
        SetFilePointerEx(f, at, NULL, FILE_BEGIN);
        WriteFile(f, sites[i].new_, sites[i].len, &put, NULL);
        logline(L"libcef: %ls: %ls", sites[i].what, put == (DWORD)sites[i].len ? L"done" : L"FAILED");
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
