// wfocus: report which window has the focus, then give it to a window class (default grcWindow, GTA V's window).
// GTA V stops drawing while its window is not the foreground window; on Android nothing can alt-tab back to it.
// usage: wfocus.exe [class]   result: wfocus.txt next to wfocus.exe
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static void describe(FILE *f, const wchar_t *label, HWND w) {
    wchar_t cls[128] = L"", title[128] = L"";
    DWORD pid = 0;
    if (w) {
        GetClassNameW(w, cls, 128);
        InternalGetWindowText(w, title, 128);
        GetWindowThreadProcessId(w, &pid);
    }
    fwprintf(f, L"%ls: %p class %ls pid %lu \"%ls\"%ls\n", label, (void *)w, cls, pid, title,
             w && IsIconic(w) ? L" (minimized)" : L"");
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show) {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    wchar_t *sep = wcsrchr(path, L'\\');
    wcscpy(sep ? sep + 1 : path, L"wfocus.txt");
    FILE *f = _wfopen(path, L"w");
    if (!f) return 1;
    const wchar_t *cls = cmdline && *cmdline ? cmdline : L"grcWindow";
    describe(f, L"foreground before", GetForegroundWindow());
    HWND w = FindWindowW(cls, NULL);
    describe(f, L"target", w);
    if (w) {
        if (IsIconic(w)) ShowWindow(w, SW_RESTORE);
        BOOL ok = SetForegroundWindow(w);
        fwprintf(f, L"SetForegroundWindow: %ls\n", ok ? L"ok" : L"failed");
    }
    describe(f, L"foreground after", GetForegroundWindow());
    fclose(f);
    return 0;
}
