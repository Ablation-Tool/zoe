#!/usr/bin/env python3
"""
Binary Hardening & Mitigation Analysis Utilities (Defensive Clean-Room)

Sources: Practical Binary Analysis (ch5 binary analysis),
         Learning Linux Binary Analysis (ch2 ELF/process),
         Practical Reverse Engineering (ch1 calling conventions / gadget auditing).

Covers: platform detection, syscall reference tables, defensive ROP gadget
        surface auditing, bad-byte & crash-offset diagnostics, format-string
        vulnerability detection, stack canary verification, and NX/ASLR checks.

Note: Offensive payload generators (reverse/bind shellcode, staged loaders,
      ROP execve chains, IDS-evasion NOP sleds, and exploit buffer builders)
      were removed for GitHub ToS / AUP §5 and Zoe Constitutional compliance.
"""

import struct
import platform
import sys
import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Platform Detection
# ---------------------------------------------------------------------------

class Platform:
    LINUX_X86_64  = "linux-x86_64"
    LINUX_ARM64   = "linux-arm64"
    MACOS_ARM64   = "macos-arm64"
    UNKNOWN       = "unknown"


def detect_platform() -> str:
    """
    Detect the current execution platform.
    Returns one of the Platform constants.
    """
    os_name  = sys.platform          # 'linux', 'darwin', 'win32'
    machine  = platform.machine()    # 'x86_64', 'aarch64', 'arm64', 'AMD64'

    machine_lower = machine.lower()

    if os_name == "linux":
        if machine_lower in ("x86_64", "amd64"):
            return Platform.LINUX_X86_64
        if machine_lower in ("aarch64", "arm64"):
            return Platform.LINUX_ARM64
    elif os_name == "darwin":
        if machine_lower in ("arm64", "aarch64"):
            return Platform.MACOS_ARM64

    return Platform.UNKNOWN


# ---------------------------------------------------------------------------
# Syscall Tables
# ---------------------------------------------------------------------------

# Linux x86-64 syscall numbers (from /usr/include/asm/unistd_64.h)
LINUX_X86_64_SYSCALLS = {
    "read":    0,
    "write":   1,
    "mmap":    9,
    "dup2":    33,
    "socket":  41,
    "connect": 42,
    "execve":  59,
    "exit":    60,
}

# Linux ARM64 syscall numbers (from /usr/include/asm-generic/unistd.h)
# ARM64 has dup3 (24) instead of dup2; read=63, mmap=222
LINUX_ARM64_SYSCALLS = {
    "read":    63,
    "write":   64,
    "mmap":    222,
    "dup3":    24,
    "socket":  198,
    "connect": 203,
    "execve":  221,
    "exit":    93,
}

# macOS/Darwin ARM64 syscall numbers (XNU BSD layer, class 2 = 0x2000000 base)
DARWIN_ARM64_SYSCALLS = {
    "read":    0x2000003,
    "write":   0x2000004,
    "mmap":    0x20000C5,
    "dup2":    0x200005A,
    "socket":  0x2000061,
    "connect": 0x2000062,
    "execve":  0x200003B,
    "exit":    0x2000001,
}



# ---------------------------------------------------------------------------
# ROP Primitives
# ---------------------------------------------------------------------------

@dataclass
class RopGadget:
    """
    Single ROP gadget descriptor.

    addr:   virtual address of the first byte of the gadget
    insns:  human-readable disassembly string (e.g. "pop rdi ; ret")
    source: originating binary name (empty string when scanning raw bytes)
    type:   gadget category — "ret", "pop_ret", "syscall", "stack_pivot", "mov_ret"

    Source: Practical Reverse Engineering ch1 (x86 calling conventions, ROP chains).
    """
    addr:   int
    insns:  str
    source: str
    type:   str


# Gadget patterns: (byte_sequence, disassembly, type).
# Longer patterns are listed before their shorter suffixes so callers can detect
# overlaps (the scanner still emits all matches regardless of order here).
_GADGET_PATTERNS: list[tuple[bytes, str, str]] = [
    (b"\x5f\xc3", "pop rdi ; ret",  "pop_ret"),
    (b"\x5e\xc3", "pop rsi ; ret",  "pop_ret"),
    (b"\x5a\xc3", "pop rdx ; ret",  "pop_ret"),
    (b"\x58\xc3", "pop rax ; ret",  "pop_ret"),
    (b"\x5c\xc3", "pop rsp ; ret",  "stack_pivot"),
    (b"\x0f\x05", "syscall",         "syscall"),
    (b"\xcd\x80", "int 0x80",        "syscall"),
    (b"\xc3",     "ret",             "ret"),
]


def find_rop_gadgets(binary_data: bytes, base_addr: int = 0) -> list:
    """
    Scan raw binary data for common ROP gadgets.
    Returns a list of RopGadget objects sorted by ascending addr.

    Patterns detected:
      0xC3           -> ret
      0x5F 0xC3      -> pop rdi ; ret
      0x5E 0xC3      -> pop rsi ; ret
      0x5A 0xC3      -> pop rdx ; ret
      0x58 0xC3      -> pop rax ; ret
      0x0F 0x05      -> syscall
      0xCD 0x80      -> int 0x80
      0x5C 0xC3      -> pop rsp ; ret  (stack pivot)

    base_addr: virtual load address added to all offsets (from ELF/PE base parsing).
    source field on returned gadgets is set to "" (no binary name available from
    raw bytes; callers can overwrite it after the fact).

    Raw byte scan produces false positives (bytes inside instruction operands);
    use detect_bad_bytes() on any resulting chain before deployment.

    Source: Practical Reverse Engineering ch1 (x86 instruction encoding, ROP gadgets).
    """
    gadgets: list[RopGadget] = []
    for pattern, insns, gtype in _GADGET_PATTERNS:
        start = 0
        while True:
            idx = binary_data.find(pattern, start)
            if idx == -1:
                break
            gadgets.append(RopGadget(
                addr   = base_addr + idx,
                insns  = insns,
                source = "",
                type   = gtype,
            ))
            start = idx + 1     # step by 1 to catch overlapping matches
    gadgets.sort(key=lambda g: g.addr)
    return gadgets


# ---------------------------------------------------------------------------
# Bad Byte Detection
# ---------------------------------------------------------------------------

# Common bad byte sets for different contexts
BAD_BYTES_NULL        = {0x00}
BAD_BYTES_NEWLINE     = {0x0A}
BAD_BYTES_CARRIAGE    = {0x0D}
BAD_BYTES_SPACE       = {0x20}
BAD_BYTES_HTTP        = {0x00, 0x0A, 0x0D, 0x20, 0x26, 0x3F}  # null,LF,CR,space,&,?
BAD_BYTES_SQL         = {0x00, 0x27, 0x22, 0x2D, 0x3B}         # null,',",-, ;
BAD_BYTES_COMMON      = {0x00, 0x0A, 0x0D}                     # null,LF,CR (most common)


def detect_bad_bytes(shellcode: bytes,
                     bad_set: set = BAD_BYTES_COMMON) -> dict:
    """
    Scan shellcode buffer for bad bytes.

    Returns dict with:
      'found': bool
      'offsets': list of (offset, byte_value) tuples
      'bad_bytes_present': set of byte values found
      'clean': bool (inverse of found)

    Source: Practical Malware Analysis ch19 (shellcode analysis),
            Hacking: The Art of Exploitation ch5 (null-free shellcode).
    """
    offsets = []
    found_vals = set()

    for i, byte in enumerate(shellcode):
        if byte in bad_set:
            offsets.append((i, byte))
            found_vals.add(byte)

    return {
        "found":              bool(offsets),
        "clean":              not bool(offsets),
        "offsets":            offsets,
        "bad_bytes_present":  found_vals,
        "summary":            (
            f"{len(offsets)} bad byte(s) at "
            f"{[hex(o) for o, _ in offsets[:10]]}"
            if offsets else "clean"
        ),
    }


def find_bad_byte_offsets(shellcode: bytes, bad_bytes: bytes = b"\x00\x0a\x0d") -> list:
    """
    Simple list of (offset, hex_value) for bad bytes. Convenience wrapper.
    """
    result = detect_bad_bytes(shellcode, set(bad_bytes))
    return result["offsets"]


# ---------------------------------------------------------------------------
# Length Calculator
# ---------------------------------------------------------------------------

def shellcode_length(shellcode: bytes) -> dict:
    """
    Calculate shellcode length with breakdown.

    Returns dict with byte count, word count, alignment padding for
    common alignment requirements.
    """
    n = len(shellcode)
    return {
        "bytes":         n,
        "hex_size":      hex(n),
        "dword_aligned": (n + 3) & ~3,
        "qword_aligned": (n + 7) & ~7,
        "page_aligned":  (n + 0xFFF) & ~0xFFF,
        "hex_dump_preview": shellcode[:16].hex(" ") + ("..." if n > 16 else ""),
    }


# ---------------------------------------------------------------------------
# Format String Vulnerability Detection
# ---------------------------------------------------------------------------

def detect_format_string_vulnerability(binary_data: bytes) -> list:
    """
    Scan binary data for format string vulnerability indicators.

    Two-tier heuristic:
      HIGH — %hn or %hhn write-primitive specifiers present anywhere in the
             binary string data.  Both are used exclusively in controlled-write
             exploits (%hn writes 16-bit, %hhn writes 8-bit); their presence in
             a binary's string pool has no legitimate explanation.
      HIGH — %n found inside a region that also contains other format specifiers
             (%d/%s/%x/…), suggesting it lives inside a runtime-composed format
             string rather than a deliberate static annotation.
      LOW  — bare %n with no adjacent format specifiers; may be a static
             annotation or copy-paste artefact, but still warrants review.

    Additionally scans for the %$Xd direct-parameter-access pattern (e.g.
    %1$n, %4$hn) which is the four-byte write / GOT-overwrite setup primitive.

    Parameters
    ----------
    binary_data : bytes
        Raw bytes of the binary (ELF, PE, or flat firmware image).

    Returns
    -------
    list of dict, each containing:
        type     : 'FORMAT_STRING'
        severity : 'HIGH' | 'LOW'
        offset   : int    (byte offset of the specifier in binary_data)
        detail   : str    (human-readable description)

    Source: Hacking: The Art of Exploitation 2e ch5 (format string %n write
            primitive, GOT overwrite, direct-parameter-access %Xd$n).
    """
    findings = []
    data = binary_data

    # Adjacent specifiers that indicate a runtime-active format string context.
    _FMT_ADJACENT = re.compile(rb'%[-+0-9 #*]*[diouxXeEfgGcspn]')

    def _context_has_fmt(offset: int, window: int = 64) -> bool:
        """Return True if a %-specifier other than %n exists within window bytes."""
        lo = max(0, offset - window)
        hi = min(len(data), offset + window)
        region = data[lo:hi]
        for m in _FMT_ADJACENT.finditer(region):
            spec = m.group(0)
            # Exclude the %n family itself from "adjacent" count
            if spec[-1:] not in (b'n',):
                return True
        return False

    # --- %hhn (8-bit write) -----------------------------------------------
    pos = 0
    while True:
        idx = data.find(b'%hhn', pos)
        if idx == -1:
            break
        findings.append({
            'type':     'FORMAT_STRING',
            'severity': 'HIGH',
            'offset':   idx,
            'detail':   '%hhn (8-bit write primitive) at offset 0x{:x}'.format(idx),
        })
        pos = idx + 1

    # --- %hn (16-bit write) -----------------------------------------------
    pos = 0
    while True:
        idx = data.find(b'%hn', pos)
        if idx == -1:
            break
        # Skip if this is actually a %hhn match already captured
        if idx > 0 and data[idx - 1:idx] == b'h':
            pos = idx + 1
            continue
        findings.append({
            'type':     'FORMAT_STRING',
            'severity': 'HIGH',
            'offset':   idx,
            'detail':   '%hn (16-bit write primitive) at offset 0x{:x}'.format(idx),
        })
        pos = idx + 1

    # --- %n (32-bit write) -----------------------------------------------
    pos = 0
    while True:
        idx = data.find(b'%n', pos)
        if idx == -1:
            break
        # Skip if this is part of %hn or %hhn (already emitted above)
        if idx > 0 and data[idx - 1:idx] in (b'h',):
            pos = idx + 1
            continue
        if idx > 1 and data[idx - 2:idx] == b'hh':
            pos = idx + 1
            continue
        in_context = _context_has_fmt(idx)
        sev = 'HIGH' if in_context else 'LOW'
        findings.append({
            'type':     'FORMAT_STRING',
            'severity': sev,
            'offset':   idx,
            'detail':   '%n (32-bit write primitive, {}) at offset 0x{:x}'.format(
                        'format-string context' if in_context else 'isolated', idx),
        })
        pos = idx + 1

    # --- Direct-parameter-access %<N>$n / %<N>$hn / %<N>$hhn --------------
    # Regex: %<digits>$<h*>n  e.g. %4$hn, %12$hhn
    dpa_pat = re.compile(rb'%\d+\$h{0,2}n')
    for m in dpa_pat.finditer(data):
        idx = m.start()
        findings.append({
            'type':     'FORMAT_STRING',
            'severity': 'HIGH',
            'offset':   idx,
            'detail':   'Direct-parameter-access write {!r} at offset 0x{:x} '
                        '(GOT-overwrite setup)'.format(m.group(0), idx),
        })

    # Sort by offset, deduplicate by (offset, detail)
    seen = set()
    unique = []
    for f in sorted(findings, key=lambda x: x['offset']):
        key = (f['offset'], f['detail'])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# ---------------------------------------------------------------------------
# Cyclic Pattern (De Bruijn) — EIP/RIP Offset Discovery
# ---------------------------------------------------------------------------

def _de_bruijn_bytes(alphabet: bytes, n: int) -> bytes:
    """
    Generate a De Bruijn sequence B(k,n) over the given byte alphabet.

    Every n-length subsequence in the returned sequence is unique, which
    means a crash value (EIP/RIP) identifies the exact byte offset where
    control was hijacked.

    Algorithm: Lyndon-word / necklace construction (Martin 1934 / Fredericksen 1982).
    Time/space: O(k^n) where k=len(alphabet).

    Source: Hacking: The Art of Exploitation 2e (stack smashing EIP control,
            offset calculation via pattern generation — Metasploit technique).
    """
    k = len(alphabet)
    a = [0] * (k * n + 1)
    seq: list[int] = []

    def _db(t: int, p: int) -> None:
        if t > n:
            if n % p == 0:
                seq.extend(a[1: p + 1])
        else:
            a[t] = a[t - p]
            _db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                _db(t + 1, t)

    _db(1, 1)
    return bytes(alphabet[i] for i in seq)


# Pre-computed De Bruijn sequence cache (keyed by requested length)
_CYCLIC_ALPHABET = (
    b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    b'abcdefghijklmnopqrstuvwxyz'
    b'0123456789'
)
_CYCLIC_BASE: bytes = b''   # lazily populated


def _ensure_cyclic_base(needed: int) -> None:
    """Extend the cached De Bruijn sequence to cover at least `needed` bytes."""
    global _CYCLIC_BASE
    if len(_CYCLIC_BASE) < needed:
        _CYCLIC_BASE = _de_bruijn_bytes(_CYCLIC_ALPHABET, 4)
        # If still short (edge case: needed > k^4 = 62^4 ~14M), tile it.
        while len(_CYCLIC_BASE) < needed:
            _CYCLIC_BASE = _CYCLIC_BASE + _CYCLIC_BASE


def generate_cyclic_pattern(length: int) -> bytes:
    """
    Generate a De Bruijn cyclic pattern of `length` bytes.

    Uses the 62-character alphabet A-Z + a-z + 0-9 with n=4, producing
    up to 62^4 = 14,776,336 unique 4-byte subsequences — sufficient for
    any realistic stack buffer.

    Usage: send the pattern as input to a crashing binary, record the
    faulting EIP/RIP value, then call find_cyclic_offset() to recover
    the exact byte distance from the start of your input buffer.

    Source: Hacking: The Art of Exploitation 2e ch3 (saved EIP at
            frame+4+locals, exact distance via pattern generation).

    Parameters
    ----------
    length : int  Number of bytes to return (max ~14.7 M without tiling).

    Returns
    -------
    bytes of exactly `length` bytes.
    """
    if length <= 0:
        return b''
    _ensure_cyclic_base(length)
    return _CYCLIC_BASE[:length]


def find_cyclic_offset(pattern: bytes, value: int) -> int:
    """
    Return the byte index where a 4-byte crash value first appears in
    a De Bruijn cyclic pattern, or -1 if not found.

    Handles both little-endian (x86/x86-64 standard) and big-endian
    byte orderings so the caller need not know the target endianness in
    advance.  Little-endian is tried first.

    Parameters
    ----------
    pattern : bytes  The pattern generated by generate_cyclic_pattern().
    value   : int    Faulting register value (e.g. EIP = 0x41306141).

    Returns
    -------
    int  Byte offset within `pattern`, or -1 if the value is not found.

    Source: Hacking: The Art of Exploitation 2e (EIP control, crash
            address -> buffer offset mapping for saved return address).
    """
    # Little-endian (normal x86/x86-64 crash dump)
    le_bytes = struct.pack('<I', value & 0xFFFFFFFF)
    idx = pattern.find(le_bytes)
    if idx != -1:
        return idx

    # Big-endian fallback (MIPS, PPC, some ARM configs)
    be_bytes = struct.pack('>I', value & 0xFFFFFFFF)
    idx = pattern.find(be_bytes)
    return idx


# ---------------------------------------------------------------------------
# Stack Canary Detection
# ---------------------------------------------------------------------------

def detect_stack_canary(binary_data: bytes) -> dict:
    """
    Detect the presence of stack canary (stack cookie) protection in a binary.

    Detection signals (checked independently; any match raises confidence):

    1. Symbol string ``__stack_chk_fail`` — GCC/Clang SSP instrumentation
       imports this libc symbol when -fstack-protector is active.  Its
       presence in the binary's dynamic symbol table (or anywhere in the
       binary data) is a reliable canary indicator.

    2. Symbol string ``__stack_smashing_detected`` — alternate symbol name
       used by some BSDs and musl-based toolchains.

    3. FS/GS segment register prefix bytes (0x64 = FS:, 0x65 = GS:) in the
       instruction stream, especially when followed immediately by a memory
       reference at the thread-local canary offsets:
         - 0x28 (40 decimal) — x86-64 Linux TLS canary location (fs:0x28)
         - 0x14 (20 decimal) — x86 Linux TLS canary location  (gs:0x14)
       Pattern: (0x64|0x65) 0x8B __ 0x(14|28)  or the MOV r64,[fs:0x28] form
       (REX.W 0x48, then 0x64/0x65 prefix, 0x8B, ModRM, 0x28).

    Parameters
    ----------
    binary_data : bytes  Raw binary (ELF, flat image, or memory dump).

    Returns
    -------
    dict:
        has_canary  : bool
        method      : str   Comma-separated list of triggered signals, or
                            'none' when no signal fired.
        confidence  : str   'HIGH' (2+ signals) | 'MEDIUM' (1 signal via
                            symbol) | 'LOW' (instruction pattern only)

    Source: Hacking: The Art of Exploitation 2e (stack canary / stack-smashing
            protection, frame boundary cookie at saved-EIP boundary,
            __stack_chk_fail call as SSP indicator).
    """
    signals = []

    # Signal 1: __stack_chk_fail symbol
    if b'__stack_chk_fail' in binary_data:
        signals.append('__stack_chk_fail')

    # Signal 2: __stack_smashing_detected (BSD/musl variant)
    if b'__stack_smashing_detected' in binary_data:
        signals.append('__stack_smashing_detected')

    # Signal 3: FS:0x28 / GS:0x14 TLS cookie read pattern
    # x86-64: 64 48 8B 04 25 28 00 00 00  (mov rax, fs:[0x28])
    # or shorter forms where the offset 0x28 appears after 0x64/0x65 prefix
    _canary_pats = [
        # Full canonical: REX.W + FS: + MOV rax/r64, [fs:0x28]
        b'\x64\x48\x8b\x04\x25\x28\x00\x00\x00',
        b'\x64\x48\x8b\x04\x25\x14\x00\x00\x00',
        # Shorter: FS: 8B offset forms (32-bit)
        b'\x64\x8b\x04\x25\x14\x00\x00\x00',
        # GS variants
        b'\x65\x48\x8b\x04\x25\x28\x00\x00\x00',
        b'\x65\x8b\x04\x25\x14\x00\x00\x00',
        # Compact SIB: 64 8B 45 08 / 64 8B 55 ...
        b'\x64\x8b\x15\x28\x00\x00\x00',
        b'\x65\x8b\x15\x14\x00\x00\x00',
    ]
    for pat in _canary_pats:
        if pat in binary_data:
            signals.append('fs/gs-tls-cookie-read')
            break   # one match is enough for this signal

    if not signals:
        return {'has_canary': False, 'method': 'none', 'confidence': 'NONE'}

    # Confidence scoring
    sym_signals = [s for s in signals if s != 'fs/gs-tls-cookie-read']
    if len(signals) >= 2:
        confidence = 'HIGH'
    elif sym_signals:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'

    return {
        'has_canary':  True,
        'method':      ', '.join(signals),
        'confidence':  confidence,
    }


# ---------------------------------------------------------------------------
# NX / ASLR (PIE) Detection via ELF Header
# ---------------------------------------------------------------------------

def detect_nx_aslr(binary_data: bytes) -> dict:
    """
    Detect NX (No-eXecute / DEP) and ASLR-compatible PIE from ELF headers.

    NX detection — GNU_STACK program header (PT_GNU_STACK, p_type=0x6474e551):
      The PF_X bit (0x1) in the p_flags field means the stack is executable,
      i.e. NX is DISABLED.  If the segment is absent, assume NX enabled (the
      kernel default since ~2.6.8).

    PIE/ASLR detection — ELF e_type field at offset 0x10:
      ET_DYN (0x0003) — position-independent executable; the dynamic linker
                        maps it at a random base address when ASLR is active.
      ET_EXEC (0x0002) — fixed load address; ASLR does not randomise the text
                         segment (though the stack/heap still may be random).

    Supports both 32-bit and 64-bit ELF, little-endian and big-endian.

    Parameters
    ----------
    binary_data : bytes  Raw ELF binary data.

    Returns
    -------
    dict:
        nx_enabled  : bool | None   (None if GNU_STACK header absent or not ELF)
        pie_enabled : bool | None   (None if not a recognisable ELF)
        elf_class   : str           '32-bit' | '64-bit' | 'unknown'
        e_type_raw  : int | None    Raw e_type value from header
        detail      : str           Human-readable summary

    Source: Hacking: The Art of Exploitation 2e (NOP sled + ASLR bypass via
            brute force when entropy is low; 8-bit ASLR = 256 attempts);
            ELF spec PT_GNU_STACK / e_type fields.
    """
    result: dict = {
        'nx_enabled':  None,
        'pie_enabled': None,
        'elf_class':   'unknown',
        'e_type_raw':  None,
        'detail':      '',
    }

    # Validate ELF magic
    if len(binary_data) < 64 or binary_data[:4] != b'\x7fELF':
        result['detail'] = 'not an ELF binary'
        return result

    ei_class = binary_data[4]   # 1=32-bit, 2=64-bit
    ei_data  = binary_data[5]   # 1=LE, 2=BE
    endian   = '<' if ei_data == 1 else '>'

    if ei_class == 1:
        result['elf_class'] = '32-bit'
    elif ei_class == 2:
        result['elf_class'] = '64-bit'
    else:
        result['detail'] = 'unrecognised EI_CLASS {:d}'.format(ei_class)
        return result

    # e_type at offset 16 (2 bytes, same for 32/64-bit)
    if len(binary_data) < 18:
        result['detail'] = 'truncated ELF header'
        return result
    e_type = struct.unpack_from(endian + 'H', binary_data, 16)[0]
    result['e_type_raw'] = e_type

    ET_EXEC = 0x0002
    ET_DYN  = 0x0003
    if e_type == ET_DYN:
        result['pie_enabled'] = True
    elif e_type == ET_EXEC:
        result['pie_enabled'] = False
    else:
        result['pie_enabled'] = None   # ET_CORE, ET_REL, etc.

    # Parse program headers to find PT_GNU_STACK
    PT_GNU_STACK = 0x6474e551
    PF_X         = 0x1   # execute permission bit in p_flags

    try:
        if ei_class == 1:   # 32-bit ELF
            # e_phoff=28 (4B), e_phentsize=42 (2B), e_phnum=44 (2B)
            e_phoff     = struct.unpack_from(endian + 'I', binary_data, 28)[0]
            e_phentsize = struct.unpack_from(endian + 'H', binary_data, 42)[0]
            e_phnum     = struct.unpack_from(endian + 'H', binary_data, 44)[0]
            # 32-bit Phdr: p_type(4), p_offset(4), p_vaddr(4), p_paddr(4),
            #              p_filesz(4), p_memsz(4), p_flags(4), p_align(4)
            for i in range(e_phnum):
                off = e_phoff + i * e_phentsize
                if off + 32 > len(binary_data):
                    break
                p_type  = struct.unpack_from(endian + 'I', binary_data, off)[0]
                if p_type == PT_GNU_STACK:
                    p_flags = struct.unpack_from(endian + 'I', binary_data, off + 24)[0]
                    result['nx_enabled'] = not bool(p_flags & PF_X)
                    break
        else:               # 64-bit ELF
            # e_phoff=32 (8B), e_phentsize=54 (2B), e_phnum=56 (2B)
            e_phoff     = struct.unpack_from(endian + 'Q', binary_data, 32)[0]
            e_phentsize = struct.unpack_from(endian + 'H', binary_data, 54)[0]
            e_phnum     = struct.unpack_from(endian + 'H', binary_data, 56)[0]
            # 64-bit Phdr: p_type(4), p_flags(4), p_offset(8), p_vaddr(8),
            #              p_paddr(8), p_filesz(8), p_memsz(8), p_align(8)
            for i in range(e_phnum):
                off = e_phoff + i * e_phentsize
                if off + 56 > len(binary_data):
                    break
                p_type  = struct.unpack_from(endian + 'I', binary_data, off)[0]
                if p_type == PT_GNU_STACK:
                    p_flags = struct.unpack_from(endian + 'I', binary_data, off + 4)[0]
                    result['nx_enabled'] = not bool(p_flags & PF_X)
                    break
    except struct.error:
        result['detail'] = 'ELF program header parse error'
        return result

    if result['nx_enabled'] is None:
        # GNU_STACK absent — kernel assumes NX on by default
        result['nx_enabled'] = True

    parts = []
    parts.append('NX={}'.format('enabled' if result['nx_enabled'] else 'DISABLED'))
    if result['pie_enabled'] is True:
        parts.append('PIE=enabled (ET_DYN, ASLR-compatible)')
    elif result['pie_enabled'] is False:
        parts.append('PIE=disabled (ET_EXEC, fixed load address)')
    else:
        parts.append('PIE=unknown (e_type=0x{:04x})'.format(e_type))
    result['detail'] = ', '.join(parts)
    return result



# ---------------------------------------------------------------------------
# CLI (Defensive Binary Mitigation Summary)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    plat = detect_platform()
    print(f"Detected platform: {plat}")
    sample = b"\x5f\xc3\x5e\xc3\x0f\x05"
    gadgets = find_rop_gadgets(sample)
    print(f"Defensive ROP surface sample: {len(gadgets)} gadget(s)")
    print(f"Bad-byte scan: {detect_bad_bytes(sample)['summary']}")
