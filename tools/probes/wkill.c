// wkill: end processes by exe name inside the Wine session without a console or a window (works while the X server
// is stuck, unlike taskkill under cmd/conhost). usage: wkill.exe NAME|#PID|@CEFTYPE ...   ("list" = only list; @renderer, @gpu-process, @utility:...)
// Result: wkill.txt next to wkill.exe (process list, then what was ended).
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <wchar.h>
#include <winternl.h>

// CEF process type from the command line ("--type=gpu-process" etc.), "-" when none; PID mode: NAME "#1234" ends one PID
static wchar_t g_cl[16384];
static void cef_type(DWORD pid, wchar_t *out, size_t n) {
    g_cl[0] = 0;
    wcscpy(out, L"-");
    HANDLE h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!h) return;
    static wchar_t cl[16384];
    PROCESS_BASIC_INFORMATION pbi;
    ULONG len = 0;
    ULONG_PTR params = 0;
    UNICODE_STRING us;
    SIZE_T got = 0;
    // PEB (x64): +0x20 ProcessParameters; RTL_USER_PROCESS_PARAMETERS +0x70 CommandLine
    if (NtQueryInformationProcess(h, ProcessBasicInformation, &pbi, sizeof(pbi), &len) == 0 &&
        ReadProcessMemory(h, (BYTE *)pbi.PebBaseAddress + 0x20, &params, sizeof(params), &got) &&
        ReadProcessMemory(h, (BYTE *)params + 0x70, &us, sizeof(us), &got) && us.Length < sizeof(cl) - 2 &&
        ReadProcessMemory(h, us.Buffer, cl, us.Length, &got)) {
        cl[us.Length / 2] = 0;
        wcsncpy(g_cl, cl, 16383);
        wchar_t *t = wcsstr(cl, L"--type=");
        if (t) {
            size_t i = 0;
            for (t += 7; *t && *t != L' ' && *t != L'"' && i < n - 1; t++) out[i++] = *t;
            out[i] = 0;
            wchar_t *u = wcsstr(cl, L"--utility-sub-type=");
            if (u && wcslen(out) + 2 < n) {
                wcscat(out, L":");
                i = wcslen(out);
                for (u += 19; *u && *u != L' ' && *u != L'"' && i < n - 1; u++) out[i++] = *u;
                out[i] = 0;
            }
        }
    }
    CloseHandle(h);
}

static FILE *wlog;
static BOOL CALLBACK win_cb(HWND w, LPARAM lp) {
    DWORD pid = 0, tid = GetWindowThreadProcessId(w, &pid);
    wchar_t cls[128] = L"", title[128] = L"";
    GetClassNameW(w, cls, 128);
    InternalGetWindowText(w, title, 128);  // no WM_GETTEXT: safe with hung owners
    RECT r = {0};
    GetWindowRect(w, &r);
    fwprintf(wlog, L"  %ls %p pid %lu tid %lu %ls %ls (%ld,%ld %ldx%ld) \"%ls\"\n", lp ? L" child" : L"win", (void *)w,
             pid, tid, IsWindowVisible(w) ? L"VIS" : L"hid", cls, r.left, r.top, r.right - r.left, r.bottom - r.top, title);
    if (!lp) EnumChildWindows(w, win_cb, 1);
    return TRUE;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show) {
    int argc = 0;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    wchar_t logpath[MAX_PATH];  // wkill.txt next to wkill.exe
    GetModuleFileNameW(NULL, logpath, MAX_PATH);
    wchar_t *sep = wcsrchr(logpath, L'\\');
    wcscpy(sep ? sep + 1 : logpath, L"wkill.txt");
    FILE *log = _wfopen(logpath, L"w");
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32W pe = {sizeof(pe)};
    for (BOOL ok = Process32FirstW(snap, &pe); ok; ok = Process32NextW(snap, &pe)) {
        int hit = 0;
        wchar_t type[128];
        cef_type(pe.th32ProcessID, type, 128);
        for (int i = 1; i < argc; i++) {
            if (_wcsicmp(argv[i], pe.szExeFile) == 0) hit = 1;
            if (argv[i][0] == L'#' && (DWORD)_wtoi(argv[i] + 1) == pe.th32ProcessID) hit = 1;
            if (argv[i][0] == L'@' && _wcsnicmp(argv[i] + 1, type, wcslen(argv[i] + 1)) == 0) hit = 1;  // @gpu-process, @utility:audio (prefix)
        }
        if (log) fwprintf(log, L"%5lu %5lu %ls [%ls]%ls", pe.th32ProcessID, pe.th32ParentProcessID, pe.szExeFile,
                          type, hit ? L"  -> " : L"\n");
        // "cl": full command line of Social Club helpers only (launcher command lines carry Epic auth tokens)
        if (log && argc > 1 && _wcsicmp(argv[1], L"cl") == 0 && _wcsicmp(pe.szExeFile, L"SocialClubHelper.exe") == 0)
            fwprintf(log, L"      cl: %.1500ls\n", g_cl);
        if (hit) {
            HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
            BOOL done = h && TerminateProcess(h, 1);
            if (log) fwprintf(log, L"%ls (error %lu)\n", done ? L"ended" : L"FAILED", done ? 0 : GetLastError());
            if (h) CloseHandle(h);
        }
    }
    CloseHandle(snap);
    if (log && argc > 1 && _wcsicmp(argv[1], L"wins") == 0) {  // also list top-level windows with owner pid/tid
        wlog = log;
        EnumWindows(win_cb, 0);
        for (HWND m = NULL; (m = FindWindowExW(HWND_MESSAGE, m, NULL, NULL));) {  // message-only windows
            DWORD pid = 0, tid = GetWindowThreadProcessId(m, &pid);
            wchar_t cls[128] = L"";
            GetClassNameW(m, cls, 128);
            fwprintf(wlog, L"  msg %p pid %lu tid %lu %ls\n", (void *)m, pid, tid, cls);
        }
    }
    if (log) fclose(log);
    return 0;
}
