// wbench: copy GTA V's benchmark results out of the Wine prefix without a console window (a console window takes
// the focus, and GTA V stops drawing without it). Copies every file of the Benchmarks folder into bench\ next to
// itself and writes wbench.txt there too: the folder listing and the newest Benchmark-*.txt summary.
// GTA V writes Benchmark-<time>.txt (per-scene FPS) and, with -benchmarkFrameTimes, FrameTimes-Pass<n>-<time>.txt.
// usage: wbench.exe [folder]   default %USERPROFILE%\Documents\Rockstar Games\GTA V\Benchmarks
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show) {
    wchar_t here[MAX_PATH], out[MAX_PATH], dir[MAX_PATH], pattern[MAX_PATH], copydir[MAX_PATH], newest[MAX_PATH] = L"";
    GetModuleFileNameW(NULL, here, MAX_PATH);
    wchar_t *sep = wcsrchr(here, L'\\');
    if (sep) *sep = 0;
    _snwprintf(out, MAX_PATH, L"%ls\\wbench.txt", here);
    _snwprintf(copydir, MAX_PATH, L"%ls\\bench", here);
    CreateDirectoryW(copydir, NULL);
    FILE *f = _wfopen(out, L"w");
    if (!f) return 1;
    if (cmdline && *cmdline) wcsncpy(dir, cmdline, MAX_PATH - 1);
    else ExpandEnvironmentStringsW(L"%USERPROFILE%\\Documents\\Rockstar Games\\GTA V\\Benchmarks", dir, MAX_PATH);
    _snwprintf(pattern, MAX_PATH, L"%ls\\*", dir);
    WIN32_FIND_DATAW fd;
    FILETIME best = {0};
    HANDLE h = FindFirstFileW(pattern, &fd);
    int n = 0;
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            SYSTEMTIME st;
            FileTimeToSystemTime(&fd.ftLastWriteTime, &st);
            fwprintf(f, L"%04d-%02d-%02d %02d:%02d:%02d %10lu %ls\n", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute,
                     st.wSecond, fd.nFileSizeLow, fd.cFileName);
            wchar_t src[MAX_PATH], dst[MAX_PATH];
            _snwprintf(src, MAX_PATH, L"%ls\\%ls", dir, fd.cFileName);
            _snwprintf(dst, MAX_PATH, L"%ls\\%ls", copydir, fd.cFileName);
            CopyFileW(src, dst, FALSE);
            if (!_wcsnicmp(fd.cFileName, L"Benchmark-", 10) && CompareFileTime(&fd.ftLastWriteTime, &best) >= 0) {
                best = fd.ftLastWriteTime;
                wcsncpy(newest, fd.cFileName, MAX_PATH - 1);
            }
            n++;
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    fwprintf(f, L"%d files in %ls\n", n, dir);
    if (newest[0]) fwprintf(f, L"newest: %ls -> copied\n", newest);
    fclose(f);
    return 0;
}
