"""Tell x86-64 from ARM64EC PE files: both say Machine 0x8664; ARM64EC has a CHPE metadata pointer in the load config.
usage: pekind.py FILE..."""
import struct
import sys

for p in sys.argv[1:]:
    b = open(p, "rb").read()
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    machine = struct.unpack_from("<H", b, pe + 4)[0]
    nsec = struct.unpack_from("<H", b, pe + 6)[0]
    optsz = struct.unpack_from("<H", b, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", b, opt)[0]
    if magic != 0x20B:
        print(f"{p}: machine {machine:#x} not PE32+")
        continue
    ddir = opt + 112
    lc_rva, lc_size = struct.unpack_from("<II", b, ddir + 10 * 8)
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

    chpe = 0
    if lc_rva:
        o = off(lc_rva)
        lsize = struct.unpack_from("<I", b, o)[0]
        if lsize > 0xC8:
            chpe = struct.unpack_from("<Q", b, o + 0xC8)[0]
    kind = "ARM64EC/ARM64X" if chpe else ("x86-64" if machine == 0x8664 else f"machine {machine:#x}")
    print(f"{p}: machine {machine:#x} chpe_metadata {chpe:#x} -> {kind}; sections {[s[0] for s in secs]}")
