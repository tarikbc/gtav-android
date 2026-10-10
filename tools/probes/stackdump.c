// stackdump.exe <pid|imagename> [out] : for each process, list modules and scan each
// thread's stack for return addresses inside loaded modules.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

typedef LONG (WINAPI *NtQIT)(HANDLE, int, PVOID, ULONG, PULONG);
typedef HRESULT (WINAPI *GetDescFn)(HANDLE, PWSTR *);

typedef struct { ULONG_PTR base, size, text_lo, text_hi; char name[64]; } Mod;
static Mod mods[512];
static int nmods;
static FILE *out;

static int is_code(ULONG_PTR v) {
    for (int i = 0; i < nmods; i++)
        if (v >= mods[i].text_lo && v < mods[i].text_hi) return i;
    return -1;
}

static void load_mods(HANDLE p) {
    HMODULE hm[512]; DWORD need = 0;
    nmods = 0;
    if (!EnumProcessModulesEx(p, hm, sizeof(hm), &need, LIST_MODULES_ALL)) {
        fprintf(out, "EnumProcessModulesEx failed %lu\n", GetLastError());
        return;
    }
    int n = need / sizeof(HMODULE);
    for (int i = 0; i < n && nmods < 512; i++) {
        MODULEINFO mi; char nm[MAX_PATH];
        if (!GetModuleInformation(p, hm[i], &mi, sizeof(mi))) continue;
        if (!GetModuleBaseNameA(p, hm[i], nm, sizeof(nm))) strcpy(nm, "?");
        Mod *m = &mods[nmods++];
        m->base = (ULONG_PTR)mi.lpBaseOfDll; m->size = mi.SizeOfImage;
        m->text_lo = m->base; m->text_hi = m->base + m->size;
        // narrow to executable sections from the PE header
        BYTE hdr[4096]; SIZE_T got = 0;
        if (ReadProcessMemory(p, (void *)m->base, hdr, sizeof(hdr), &got) && got == sizeof(hdr)) {
            IMAGE_DOS_HEADER *d = (IMAGE_DOS_HEADER *)hdr;
            if (d->e_lfanew > 0 && d->e_lfanew < 3000) {
                IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(hdr + d->e_lfanew);
                IMAGE_SECTION_HEADER *s = IMAGE_FIRST_SECTION(nt);
                ULONG_PTR lo = ~(ULONG_PTR)0, hi = 0;
                for (int k = 0; k < nt->FileHeader.NumberOfSections && (BYTE *)(s + k + 1) < hdr + sizeof(hdr); k++) {
                    if (s[k].Characteristics & IMAGE_SCN_MEM_EXECUTE) {
                        ULONG_PTR a = m->base + s[k].VirtualAddress;
                        if (a < lo) lo = a;
                        if (a + s[k].Misc.VirtualSize > hi) hi = a + s[k].Misc.VirtualSize;
                    }
                }
                if (hi > lo) { m->text_lo = lo; m->text_hi = hi; }
            }
        }
        snprintf(m->name, sizeof(m->name), "%s", nm);
        fprintf(out, "mod %016llx %08llx %s\n", (unsigned long long)m->base, (unsigned long long)m->size, m->name);
    }
}

static void dump_process(DWORD pid) {
    HANDLE p = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!p) { fprintf(out, "OpenProcess %lu failed %lu\n", pid, GetLastError()); return; }
    char cmd[64] = "";
    fprintf(out, "=== process %lu\n", pid);
    load_mods(p);
    NtQIT ntqit = (NtQIT)GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationThread");
    GetDescFn getdesc = (GetDescFn)GetProcAddress(GetModuleHandleA("kernelbase.dll"), "GetThreadDescription");
    if (!getdesc) getdesc = (GetDescFn)GetProcAddress(GetModuleHandleA("kernel32.dll"), "GetThreadDescription");
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te; te.dwSize = sizeof(te);
    for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
        if (te.th32OwnerProcessID != pid) continue;
        fprintf(out, ".. open %lu\n", te.th32ThreadID);
        HANDLE t = OpenThread(THREAD_ALL_ACCESS, FALSE, te.th32ThreadID);
        if (!t) { fprintf(out, "-- thread %lu open failed %lu\n", te.th32ThreadID, GetLastError()); continue; }
        PWSTR desc = NULL; char dn[128] = "";
        if (getdesc && SUCCEEDED(getdesc(t, &desc)) && desc) { WideCharToMultiByte(CP_UTF8, 0, desc, -1, dn, sizeof(dn), NULL, NULL); LocalFree(desc); }
        struct { LONG st; PVOID teb; ULONG_PTR pid, tid; ULONG_PTR aff; LONG pri, base; } tbi = {0};
        ntqit(t, 0, &tbi, sizeof(tbi), NULL);
        ULONG_PTR tib[3] = {0}; SIZE_T got = 0;
        ReadProcessMemory(p, tbi.teb, tib, sizeof(tib), &got);
        ULONG_PTR sbase = tib[1], slimit = tib[2];
        DWORD sc = getenv("SD_SUSPEND") ? SuspendThread(t) : 0;
        CONTEXT c; memset(&c, 0, sizeof(c)); c.ContextFlags = CONTEXT_FULL;
        fprintf(out, ".. desc '%s'\n", dn);
        BOOL gc = getenv("SD_CTX") ? GetThreadContext(t, &c) : 0;
        // ARM64EC: TEB+0x1788 -> CHPE_V2_CPU_AREA_INFO {u8 InSim; u8 InSysCb; u64 EmuStackBase; u64 EmuStackLimit; CONTEXT *ContextAmd64; ...}
        ULONG_PTR chpe = 0; BYTE ci[0x30] = {0}; CONTEXT ec; memset(&ec, 0, sizeof(ec));
        if (ReadProcessMemory(p, (BYTE *)tbi.teb + 0x1788, &chpe, 8, &got) && chpe &&
            ReadProcessMemory(p, (void *)chpe, ci, sizeof(ci), &got)) {
            ULONG_PTR ctxp = *(ULONG_PTR *)(ci + 0x18);
            if (ctxp) ReadProcessMemory(p, (void *)ctxp, &ec, sizeof(ec), &got);
            fprintf(out, "   chpe insim=%d insyscb=%d emu_rip=%016llx emu_rsp=%016llx",
                    ci[0], ci[1], (unsigned long long)ec.Rip, (unsigned long long)ec.Rsp);
            int em = is_code(ec.Rip);
            if (em >= 0) fprintf(out, " emu_rip=%s+%llx", mods[em].name, (unsigned long long)(ec.Rip - mods[em].base));
            fprintf(out, "\n");
            if (!gc && ec.Rsp >= slimit && ec.Rsp < sbase) { c.Rsp = ec.Rsp; gc = 2; }
        }
        fprintf(out, "-- thread %lu '%s' suspend=%ld ctx=%d rip=%016llx rsp=%016llx stack=[%016llx,%016llx)",
                te.th32ThreadID, dn, (long)sc, gc, (unsigned long long)c.Rip, (unsigned long long)c.Rsp,
                (unsigned long long)slimit, (unsigned long long)sbase);
        int mi = is_code(c.Rip);
        if (mi >= 0) fprintf(out, " rip=%s+%llx", mods[mi].name, (unsigned long long)(c.Rip - mods[mi].base));
        fprintf(out, "\n");
        ULONG_PTR from = (gc && c.Rsp >= slimit && c.Rsp < sbase) ? c.Rsp : (sbase > 0x10000 ? sbase - 0x10000 : slimit);
        if (sbase > from && sbase - from > 0x40000) from = sbase - 0x40000;
        int hits = 0;
        static ULONG_PTR buf[0x8000];
        for (ULONG_PTR a = from; a < sbase && hits < 120; a += sizeof(buf)) {
            SIZE_T want = sbase - a < sizeof(buf) ? sbase - a : sizeof(buf);
            if (!ReadProcessMemory(p, (void *)a, buf, want, &got)) break;
            for (SIZE_T k = 0; k < got / 8 && hits < 120; k++) {
                int j = is_code(buf[k]);
                if (j >= 0) {
                    fprintf(out, "   %016llx %s+%llx\n", (unsigned long long)(a + k * 8), mods[j].name,
                            (unsigned long long)(buf[k] - mods[j].base));
                    hits++;
                }
            }
        }
        if (getenv("SD_SUSPEND")) ResumeThread(t);
        CloseHandle(t);
    }
    CloseHandle(snap);
    CloseHandle(p);
    (void)cmd;
}

int main(int argc, char **argv) {
    if (argc < 2) { printf("usage: stackdump <pid|image> [out]\n"); return 1; }
    out = argc > 2 ? fopen(argv[2], "w") : stdout;
    if (!out) out = stdout;
    setvbuf(out, NULL, _IONBF, 0);
    DWORD pid = strtoul(argv[1], NULL, 10);
    if (pid) { dump_process(pid); }
    else {
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        PROCESSENTRY32 pe; pe.dwSize = sizeof(pe);
        for (BOOL ok = Process32First(snap, &pe); ok; ok = Process32Next(snap, &pe))
            if (!_stricmp(pe.szExeFile, argv[1])) dump_process(pe.th32ProcessID);
        CloseHandle(snap);
    }
    if (out != stdout) fclose(out);
    return 0;
}
