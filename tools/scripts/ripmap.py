"""Map sampled RIPs that fall inside one DLL to its nearest preceding export (PE export table of a file copy of the
DLL; the module base comes from the agent's `mod` line). Prints a histogram of export names.
usage: ripmap.py DLL_FILE BASE_HEX SIZE_HEX RIPS_FILE [RIPS_FILE ...]"""
import bisect
import struct
import sys

dll, base, size = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
b = open(dll, "rb").read()
pe = struct.unpack_from("<I", b, 0x3C)[0]
nsec = struct.unpack_from("<H", b, pe + 6)[0]
optsz = struct.unpack_from("<H", b, pe + 20)[0]
opt = pe + 24
secs = []
for i in range(nsec):
    s = opt + optsz + i * 40
    name = b[s:s + 8].rstrip(b"\0").decode(errors="replace")
    vsize, va, rsize, rptr = struct.unpack_from("<IIII", b, s + 8)
    secs.append((name, va, vsize, rptr))


def off(rva):
    for _, va, vs, rp in secs:
        if va <= rva < va + vs:
            return rp + rva - va
    return None


def cstr(o):
    e = b.index(b"\0", o)
    return b[o:e].decode(errors="replace")


exp_rva, exp_size = struct.unpack_from("<II", b, opt + 112)
e = off(exp_rva)
nfunc, nnames, addr_rva, names_rva, ords_rva = struct.unpack_from("<IIIII", b, e + 20)
addrs = struct.unpack_from(f"<{nfunc}I", b, off(addr_rva))
names = struct.unpack_from(f"<{nnames}I", b, off(names_rva))
ords = struct.unpack_from(f"<{nnames}H", b, off(ords_rva))
table = sorted((addrs[o], cstr(off(n))) for n, o in zip(names, ords) if addrs[o] and not (exp_rva <= addrs[o] < exp_rva + exp_size))
keys = [t[0] for t in table]


def section_of(rva):
    for name, va, vs, _ in secs:
        if va <= rva < va + vs:
            return name
    return "?"


for f in sys.argv[4:]:
    rips = [int(l, 16) for l in open(f) if l.strip()]
    inside = [r - base for r in rips if base <= r < base + size]
    hist = {}
    for rva in inside:
        i = bisect.bisect_right(keys, rva) - 1
        name = table[i][1] if i >= 0 else "?"
        key = f"{name}+{rva - keys[i]:x} [{section_of(rva)}]" if i >= 0 and rva - keys[i] > 0x2000 else f"{name} [{section_of(rva)}]"
        hist[key] = hist.get(key, 0) + 1
    print(f"{f}: {len(inside)} of {len(rips)} samples in {dll.split('/')[-1]}")
    for k, v in sorted(hist.items(), key=lambda kv: -kv[1])[:14]:
        print(f"   {v:4d} {100 * v / len(inside):5.1f}%  {k}")
