"""A real, working tool stack wired through the gate.

This replaces the toy `ExampleToolAdapter` with tools that actually touch the
filesystem and network, and -- the part that matters -- *taint at ingestion*
instead of relying on the caller to hand-tag. The README's load-bearing warning
is "taint at ingestion, not by hand; hand-tagging will drift." So:

  - Every READ returns a `Tainted` value. A read is UNTRUSTED unless the path is
    under an explicitly-declared `trusted_roots` (files your system authored).
  - Every NETWORK fetch returns an UNTRUSTED `Tainted` value -- you did not
    author what came back.
  - Taint *persists across steps* via a `TaintLedger`: bytes written to a file
    carry their taint onto that path, and a later read re-attaches it. This is
    what closes the write-then-read-back laundering path.
  - `target_from_untrusted` is computed, not passed: the adapter remembers the
    string content of every untrusted value it has handled, and flags a network
    target whose host/URL was lifted out of that content. That is the EchoLeak
    sink-from-the-page shape, detected deterministically.

Side effects go through `Enforcer.guard`, so the gate decides BEFORE the read,
write, or request happens.

Network and filesystem backends are injectable (`transport`, `fs`) so the same
tools run live, in a sandboxed dry-run, or under test without real egress.
"""
from __future__ import annotations

import base64
import binascii
import html
import os
import re
import stat
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import unquote, urlsplit

# Refuse to slurp an unbounded stream (a device, a runaway file) into memory on a
# READ. 64 MiB is well past any config/source file a task legitimately reads.
_MAX_READ_BYTES = 64 * 1024 * 1024

from .action import ActionRequest, Capability
from .adapters import GatingAdapter
from .enforcer import Enforcer
from .ledger import TaintLedger
from .net import canonical_host
from .provenance import TaintSet, TaintTag, Tainted, Trust

# O_NOFOLLOW makes open() fail (ELOOP) if the final path component is a symlink.
# Absent on some platforms (Windows); fall back to 0 (a no-op flag) there.
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
# O_DIRECTORY makes open() fail unless the component is a directory -- used while
# descending the path so each step opens a real directory, never a symlink to one.
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)


def _resolve_beneath(root: str, path: str):
    """Descend to `path`'s parent from `root`, refusing a symlink at EVERY
    component, and return (parent_dir_fd, final_name). Caller closes the fd.

    O_NOFOLLOW on a single open only guards the FINAL component, so an attacker who
    swaps an *intermediate* directory to a symlink after the gate decided can still
    redirect the write outside the sandbox (the TOCTOU the final-component guard
    misses). Here we openat each component below the validated root with
    O_NOFOLLOW + O_DIRECTORY relative to a held dir_fd, so an intermediate symlink
    swapped in mid-flight fails ELOOP instead of redirecting the I/O. Returns
    (None, None) when `path` is not under `root` (caller falls back). (raw finding:
    intermediate-component symlink TOCTOU)
    """
    rroot = os.path.realpath(root)
    abstarget = os.path.normpath(os.path.abspath(path))
    if abstarget == rroot or abstarget.startswith(rroot + os.sep):
        rel = os.path.relpath(abstarget, rroot)
    else:
        rt = os.path.realpath(path)
        if rt == rroot or rt.startswith(rroot + os.sep):
            rel = os.path.relpath(rt, rroot)
        else:
            return None, None
    parts = [p for p in rel.split(os.sep) if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        return None, None
    dir_fd = os.open(rroot, os.O_RDONLY | _O_DIRECTORY)
    try:
        for comp in parts[:-1]:
            nxt = os.open(comp, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = nxt
        return dir_fd, parts[-1]
    except BaseException:
        try:
            os.close(dir_fd)
        except OSError:
            pass
        raise


# --- pluggable backends ----------------------------------------------------

class Filesystem:
    """Real filesystem backend. Swap for an in-memory one under test.

    Reads and writes go through os.open with O_NOFOLLOW so a symlink swapped in at
    the final path component cannot redirect the I/O outside the sandbox between
    the gate's check and the syscall (the classic TOCTOU on a scoped path). When
    the caller supplies `confine_to` (the validated sandbox root), the open
    descends component-by-component beneath that root with O_NOFOLLOW so an
    *intermediate* directory symlink swapped in mid-flight cannot redirect the I/O
    either. The policy layer also rejects a symlink/special-file/hardlink write
    target; this is the backend-level belt to those suspenders.
    """
    def __init__(self, confine: bool = True):
        # confine=True enables the per-component O_NOFOLLOW descent when the caller
        # passes a root. Off => the prior final-component-only behavior.
        self.confine = confine

    def _open(self, path: str, flags: int, mode: int, confine_to):
        if self.confine and confine_to is not None:
            try:
                parent_fd, name = _resolve_beneath(confine_to, path)
            except OSError:
                # An intermediate component is a symlink: either a benign in-root
                # symlinked directory (common, legitimate) or a swapped one. Re-
                # validate by realpath -- if the fully resolved path is still under
                # the confine root, serve it with a final-component O_NOFOLLOW open;
                # if it escaped, the descent's refusal stands. This keeps a benign
                # symlinked-dir read working instead of erroring out, without
                # serving an out-of-scope target. (raw finding: in-root symlinked
                # directory raised instead of resolving)
                rp = os.path.realpath(path)
                rr = os.path.realpath(confine_to)
                if rp == rr or rp.startswith(rr + os.sep):
                    return os.open(path, flags | _O_NOFOLLOW, mode)
                raise
            if parent_fd is not None:
                try:
                    return os.open(name, flags | _O_NOFOLLOW, mode, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
        return os.open(path, flags | _O_NOFOLLOW, mode)

    def read(self, path: str, *, confine_to=None) -> str:
        # O_NONBLOCK so opening a FIFO/device cannot block forever; fstat after the
        # open so a non-regular target (FIFO, char/block device, socket) is refused
        # at the backend even if the policy layer was bypassed; bounded read so a
        # large/unbounded file cannot exhaust memory. (raw finding: read of a
        # special/unbounded file)
        fd = self._open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0), 0o600, confine_to)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise OSError(f"refusing to read non-regular file: {path}")
            with os.fdopen(fd, "r", errors="replace") as fh:
                return fh.read(_MAX_READ_BYTES)
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    def write(self, path: str, data: str, *, confine_to=None) -> int:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        fd = self._open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600, confine_to)
        with os.fdopen(fd, "w") as fh:
            return fh.write(data)

    def delete(self, path: str, *, confine_to=None) -> None:
        if self.confine and confine_to is not None:
            try:
                parent_fd, name = _resolve_beneath(confine_to, path)
            except OSError:
                # Intermediate symlink during descent: re-validate by realpath and
                # only delete if the resolved target is still under the confine root,
                # else let the refusal stand. (raw finding: in-root symlinked
                # directory raised instead of resolving)
                rp = os.path.realpath(path)
                rr = os.path.realpath(confine_to)
                if rp == rr or rp.startswith(rr + os.sep):
                    os.remove(path)
                    return
                raise
            if parent_fd is not None:
                try:
                    os.unlink(name, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
                return
        os.remove(path)


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse a 3xx that bounces egress to a different host.

    Without this, an allowlisted host can answer with `Location: http://evil/` or
    `Location: http://169.254.169.254/` and urllib follows it -- the gate only ever
    saw the first, allowlisted URL, so the redirect is an egress-scope escape /
    SSRF. Same-host redirects (to another path) are still followed. A cross-host
    redirect is surfaced as an error rather than silently followed."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old_host = urlsplit(req.full_url).hostname
        new_host = urlsplit(newurl).hostname
        if new_host and new_host != old_host:
            raise urllib.error.HTTPError(
                newurl, code, f"cross-host redirect to '{new_host}' blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpTransport:
    """Real HTTP backend over urllib. Swap for a fake under test / dry-run.

    Cross-host redirects are blocked (see `_NoCrossHostRedirect`) so a 3xx cannot
    smuggle egress past the gate to a host the gate never evaluated.
    """
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoCrossHostRedirect())

    def request(self, method: str, url: str, body: Optional[bytes],
                headers: Dict[str, str]) -> str:
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        with self._opener.open(req, timeout=self.timeout) as resp:  # noqa: S310
            return resp.read().decode("utf-8", "replace")


# --- the gated tool stack --------------------------------------------------

def _as_text(value: Any) -> str:
    if isinstance(value, Tainted):
        value = value.value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else repr(value)


def _taint_of(value: Any) -> TaintSet:
    return value.taint if isinstance(value, Tainted) else TaintSet()


_NONALNUM = re.compile(r"[^a-z0-9]+")
_HEX_RUN = re.compile(r"^[0-9a-fA-F]+$")
_B64_CHARS = re.compile(r"^[0-9A-Za-z+/=_\-]+$")
_B32_CHARS = re.compile(r"^[A-Z2-7]+=*$")          # RFC4648 base32 (after upcasing)
_A85_CHARS = re.compile(r"^[\x21-\x75]+$")          # Ascii85 '!'..'u' (also covers b85)
# A path-like token (a filename, a component) as it would appear inside an
# untrusted blob. Used to match a write/delete basename against the corpus.
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_.\-]+")


def _normalize_for_match(s: str) -> str:
    """NFKC-fold, lowercase, and drop every non-alphanumeric byte. NFKC collapses
    fullwidth / homoglyph / compatibility characters to their plain ASCII form FIRST
    (so 'ＡＢＣ' and 'ABC' match) -- without it, stripping non-ASCII would simply
    DELETE those characters and a fullwidth copy of untrusted bytes would not match
    the source blob. Then chunk-splitting ('ab cd ef'), punctuation insertion, and
    case games are collapsed too. (raw finding: fullwidth/homoglyph laundering)"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return _NONALNUM.sub("", s.lower())


def _rot(s: str, n: int) -> str:
    """Caesar-shift the ASCII letters of `s` by n (non-letters untouched)."""
    out = []
    for c in s:
        o = ord(c)
        if 65 <= o <= 90:
            out.append(chr((o - 65 + n) % 26 + 65))
        elif 97 <= o <= 122:
            out.append(chr((o - 97 + n) % 26 + 97))
        else:
            out.append(c)
    return "".join(out)


def _reversible_decodings(text: str, floor: int) -> List[str]:
    """Best-effort decodings of `text` under the reversible transforms an exfil uses
    to launder bytes past a substring match: URL-encoding, hex, base64, a plain
    reversal, a Caesar/rot-N shift, and HTML entities. Each transform is its own
    inverse or is undone by trying every shift, so the original blob bytes re-surface
    for the substring test. Bad decodes are skipped. Deterministic, no network. (raw
    finding: reversal / rot-N / HTML-entity laundering)"""
    out: List[str] = []
    s = text.strip()
    u = unquote(s)
    if u != s:
        out.append(u)
    compact = re.sub(r"[^0-9a-fA-F]", "", s)
    if len(compact) >= 2 * floor and len(compact) % 2 == 0 and _HEX_RUN.match(compact):
        try:
            out.append(bytes.fromhex(compact).decode("utf-8", "replace"))
        except ValueError:
            pass
    b64 = re.sub(r"\s", "", s)
    if len(b64) >= 16 and _B64_CHARS.match(b64):
        candidate = b64.replace("-", "+").replace("_", "/")
        candidate += "=" * (-len(candidate) % 4)
        try:
            dec = base64.b64decode(candidate, validate=False).decode("utf-8", "replace")
            if dec:
                out.append(dec)
        except (binascii.Error, ValueError):
            pass
    # base32 / base85 / Ascii85: three more reversible wrappers an exfil uses to copy
    # untrusted bytes past the corpus substring match. base64/hex/url were covered but
    # these three were not, so an a85/b32/b85 re-encoding of a remembered untrusted blob
    # never re-derived its taint and egressed/wrote clean. Each is shape-gated so we
    # only attempt a decode on plausibly-encoded input, and every bad decode is dropped
    # -- a junk decode simply will not contain the corpus marker. (raw finding: base32 /
    # base85 / Ascii85 laundering past the decoder set)
    b32 = re.sub(r"\s", "", s).upper()
    if len(b32) >= 2 * floor and _B32_CHARS.match(b32):
        pad = b32 + "=" * (-len(b32) % 8)
        try:
            out.append(base64.b32decode(pad).decode("utf-8", "replace"))
        except (binascii.Error, ValueError):
            pass
    a = re.sub(r"\s", "", s)
    if len(a) >= floor and _A85_CHARS.match(a):
        for _decoder in (base64.a85decode, base64.b85decode):
            try:
                out.append(_decoder(a).decode("utf-8", "replace"))
            except (binascii.Error, ValueError):
                pass
    # Plain reversal: "...secret..."[::-1] is a one-line exfil obfuscation.
    if len(s) >= floor:
        out.append(s[::-1])
    # Caesar / rot-N: try every shift so rot13 and any other rotation un-rotate back
    # to the source. Only worth doing when the value actually carries letters.
    if len(s) >= floor and any(c.isalpha() for c in s):
        for shift in range(1, 26):
            out.append(_rot(s, shift))
    # HTML entities (&#115; &amp; ...): a copy entity-encoded for an HTML sink.
    h = html.unescape(s)
    if h != s:
        out.append(h)
    return out


@dataclass
class GatedTools(GatingAdapter):
    """Concrete adapter mapping a real toolset onto gated, taint-tracking calls."""

    enforcer: Enforcer
    ledger: TaintLedger = field(default_factory=TaintLedger)
    fs: Filesystem = field(default_factory=Filesystem)
    transport: HttpTransport = field(default_factory=HttpTransport)
    # Files under these roots were authored by your system => reads are trusted.
    trusted_roots: List[str] = field(default_factory=list)
    # Content of untrusted values we've handled, for sink-provenance detection.
    _untrusted_corpus: List[str] = field(default_factory=list)

    def __post_init__(self):
        super().__init__(self.enforcer)

    # --- provenance plumbing ---------------------------------------------

    def _is_trusted_read(self, path: str) -> bool:
        rp = os.path.realpath(path)
        for root in self.trusted_roots:
            r = os.path.realpath(root)
            if rp == r or rp.startswith(r + os.sep):
                return True
        return False

    def _confine_root(self, path: str, roots: List[str]):
        """The configured scope root `path` sits under, for the backend's symlink-
        safe descent. Matched by REALPATH (matching the policy layer, which decides
        scope on realpath) so the per-component O_NOFOLLOW descent engages for every
        path the gate accepted -- including one reached through a benign in-root
        symlinked directory, which a lexical-only match would skip (returning None
        and dropping the safe descent). The descent itself re-validates each
        component, and _open re-checks realpath on an intermediate-symlink ELOOP, so
        a swapped symlink still cannot redirect the I/O outside the root. None => no
        match (backend falls back to a plain final-component O_NOFOLLOW open). (raw
        finding: lexical confine_root skipped the safe descent for in-root symlinks)"""
        if not isinstance(path, str):
            return None
        # A malformed path (embedded NUL) makes os.path.realpath raise ValueError.
        # This runs BEFORE the gate's call(), so an unguarded raise would escape the
        # tool as a raw ValueError -- crashing a host that catches ActionBlocked but
        # not ValueError, before malformed_target could DENY. Fail soft to None
        # (no confine match) and let the gate return its deterministic DENY. (raw
        # finding: NUL path crashes _confine_root before the gate runs)
        try:
            rp = os.path.realpath(path)
        except (ValueError, OSError):
            return None
        for root in roots:
            rr = os.path.realpath(root)
            if rp == rr or rp.startswith(rr + os.sep):
                return rr
        return None

    def _remember_untrusted(self, text: str) -> None:
        if text:
            self._untrusted_corpus.append(text)

    def _target_from_untrusted(self, target: str) -> bool:
        """Was this network target lifted out of untrusted content we've seen?

        Deterministic: the target's host (and the raw target) is checked against
        the corpus of untrusted strings handled so far. A URL the model only
        could have learned from a poisoned page will be found there.
        """
        host = canonical_host(target)
        needles = [n for n in (target, host) if n]
        for blob in self._untrusted_corpus:
            for needle in needles:
                if needle and needle in blob:
                    return True
        return False

    # Minimum match length so a trivial common substring ("/", ".txt") does not
    # over-taint. A path/filename or data chunk this long appearing verbatim in
    # untrusted content is a real provenance signal, not a coincidence.
    _MIN_PROVENANCE_LEN = 12
    # A shorter floor for the "value is a slice of a remembered blob" direction, so
    # chunk-split exfil (untrusted bytes cut into sub-12-char pieces) is still caught.
    # An 8-char run appearing verbatim in untrusted content is still a real signal;
    # below that, a match is plausibly coincidental. (raw finding: sub-floor chunk
    # laundering)
    _MIN_SLICE_LEN = 8
    # A basename this long, matched as a whole token in untrusted content, is a real
    # signal even when it is shorter than the full-path floor (cron, hosts, init).
    _MIN_BASENAME_TOKEN = 3

    def _path_from_untrusted(self, path: str) -> bool:
        """Did untrusted content choose this filesystem path? (BL-11)

        An injection that says "save this to ../../etc/cron.d/x" leaves the path
        string in the untrusted corpus. We flag a write/delete whose full path we
        have seen verbatim, OR whose basename appears as a standalone token in
        untrusted content. The basename-token check has no 12-char floor (only a
        3-char one) so a short attacker-chosen filename -- `cron`, `hosts`, `init` --
        does not slip the full-path length floor. (raw finding: short untrusted-
        chosen filename evades the provenance floor)
        """
        base = os.path.basename(path.rstrip("/")) if isinstance(path, str) else ""
        full = path if isinstance(path, str) and len(path) >= self._MIN_PROVENANCE_LEN else None
        base_l = base.lower()
        check_base = len(base) >= self._MIN_BASENAME_TOKEN
        for blob in self._untrusted_corpus:
            if full and full in blob:
                return True
            if check_base and base_l in {t.lower() for t in _PATH_TOKEN.findall(blob)}:
                return True
        return False

    def _corpus_derived_taint(self, text: str) -> TaintSet:
        """Taint a value whose *bytes* came from untrusted content, even if the
        caller dropped the Tainted wrapper AND chunk-split or reversibly encoded
        (hex/base64/url) the bytes to dodge an exact substring test. (BL-12,
        hardened against laundering transforms)

        Closes copy-through laundering: read a page (Tainted), pull `.value` into a
        plain string, transform it, write/egress that string. We normalize both
        sides (lowercase, strip every non-alphanumeric byte) so separators and
        punctuation cannot launder a copy, and we also test the value's reversible
        decodings. A match in either form re-derives UNTRUSTED taint.
        """
        if not text:
            return TaintSet()
        floor = self._MIN_PROVENANCE_LEN
        norm_blobs = [nb for nb in (_normalize_for_match(b) for b in self._untrusted_corpus)
                      if len(nb) >= floor]
        if not norm_blobs:
            return TaintSet()
        for cand in [text] + _reversible_decodings(text, floor):
            nc = _normalize_for_match(cand)
            # Use the shorter SLICE floor here: a value that is an 8+ char slice of a
            # remembered blob (chunk-split exfil) is still untrusted bytes leaving.
            # The `nb in nc` direction is naturally floored at _MIN_PROVENANCE_LEN
            # because every nb already cleared it. (raw finding: sub-floor chunk)
            if len(nc) < self._MIN_SLICE_LEN:
                continue
            for nb in norm_blobs:
                # Either the value was sliced out of a blob, or a blob's chunk was
                # embedded into the value -- both mean untrusted bytes are leaving.
                if nc in nb or nb in nc:
                    return TaintSet.of(TaintTag(Trust.UNTRUSTED, "corpus-derived"))
        return TaintSet()

    # --- tools ------------------------------------------------------------

    def read_file(self, agent_id: str, path: str, *, declared_task: str = "") -> Tainted:
        # Taint is decided by the SYSTEM: untrusted unless under a trusted root,
        # plus any taint the ledger remembers for this path (cross-step).
        base_origin = "file:" + path
        if self._is_trusted_read(path):
            taint = TaintSet.of(TaintTag(Trust.TRUSTED, base_origin))
        else:
            taint = TaintSet.of(TaintTag(Trust.UNTRUSTED, base_origin))
        taint = taint.merge(self.ledger.taint_for("file", path))
        confine = self._confine_root(path, self.enforcer.ctx.grant.read_roots)

        def run():
            return self.fs.read(path, confine_to=confine)

        content = self.call(
            agent_id=agent_id, capability=Capability.READ, target=path,
            taint=taint, declared_task=declared_task, run=run,
        )
        result = Tainted(content, taint)
        if taint.is_tainted:
            self._remember_untrusted(_as_text(content))
        return result

    def write_file(self, agent_id: str, path: str, data: Any, *,
                   declared_task: str = "") -> Any:
        taint = _taint_of(data)
        text = _as_text(data)
        # BL-12: if the caller dropped the Tainted wrapper but the bytes came from
        # untrusted content, re-derive the taint from the corpus so a copy-through
        # write cannot launder provenance.
        if not taint.is_tainted:
            taint = taint.merge(self._corpus_derived_taint(text))
        confine = self._confine_root(path, self.enforcer.ctx.grant.write_roots)

        def run():
            return self.fs.write(path, text, confine_to=confine)

        out = self.call(
            agent_id=agent_id, capability=Capability.WRITE, target=path,
            args={"data": text}, taint=taint, declared_task=declared_task,
            target_from_untrusted=self._path_from_untrusted(path),  # BL-11
            run=run,
        )
        # Persist taint onto the resource so a later read re-attaches it.
        if taint.is_tainted:
            self.ledger.record_write("file", path, taint)
        return out

    def delete_file(self, agent_id: str, path: str, *, declared_task: str = "") -> Any:
        confine = self._confine_root(path, self.enforcer.ctx.grant.write_roots)
        return self.call(
            agent_id=agent_id, capability=Capability.DELETE, target=path,
            target_from_untrusted=self._path_from_untrusted(path),  # BL-11
            declared_task=declared_task, run=lambda: self.fs.delete(path, confine_to=confine),
        )

    def http_get(self, agent_id: str, url: str, *, headers: Optional[Dict[str, str]] = None,
                 declared_task: str = "") -> Tainted:
        return self._http(agent_id, "GET", url, None, headers or {}, declared_task)

    def http_post(self, agent_id: str, url: str, body: Any, *,
                  headers: Optional[Dict[str, str]] = None, declared_task: str = "") -> Tainted:
        return self._http(agent_id, "POST", url, body, headers or {}, declared_task)

    def _http(self, agent_id: str, method: str, url: str, body: Any,
              headers: Dict[str, str], declared_task: str) -> Tainted:
        # Taint of what's leaving = taint of the body + taint of any header values.
        out_taint = _taint_of(body)
        for hv in headers.values():
            out_taint = out_taint.merge(_taint_of(hv))
        body_text = _as_text(body) if body is not None else None
        # F5: a plain-string body/header whose bytes came from untrusted content
        # (wrapper dropped, or hex/base64/chunk-encoded) is still untrusted leaving
        # the box. Re-derive taint from the corpus the same way write_file does, so
        # the egress path cannot launder provenance the write path already holds.
        if not out_taint.is_tainted and body_text:
            out_taint = out_taint.merge(self._corpus_derived_taint(body_text))
        if not out_taint.is_tainted:
            for hv in headers.values():
                t = self._corpus_derived_taint(_as_text(hv))
                if t.is_tainted:
                    out_taint = out_taint.merge(t)
                    break

        def run():
            resp = self.transport.request(
                method, url,
                body_text.encode("utf-8") if body_text is not None else None,
                {k: _as_text(v) for k, v in headers.items()},
            )
            return resp

        resp = self.call(
            agent_id=agent_id, capability=Capability.NETWORK, target=url,
            args={"method": method, "body": body_text, "headers": dict(headers)},
            taint=out_taint, declared_task=declared_task,
            target_from_untrusted=self._target_from_untrusted(url),
            run=run,
        )
        # Whatever came back is untrusted -- you did not author it.
        resp_taint = TaintSet.of(TaintTag(Trust.UNTRUSTED, "web:" + canonical_host(url)))
        self._remember_untrusted(_as_text(resp))
        return Tainted(resp, resp_taint)

    def run_exec(self, agent_id: str, command: str, run: Callable[[], Any], *,
                 declared_task: str = "") -> Any:
        return self.call(
            agent_id=agent_id, capability=Capability.EXEC, target=command,
            declared_task=declared_task, run=run,
        )

    def quarantine(self, process: Callable[[str], str]) -> Callable[[Any], Tainted]:
        """Corpus-backed CaMeL quarantine: wrap `process` so its output is UNTRUSTED
        data AND its bytes are remembered in this adapter's untrusted corpus.

        The free `camel.quarantine` only tags the wrapper. If downstream glue drops
        the Tainted wrapper and feeds the raw `.value` into write_file/_http, the
        gate's corpus-derived taint backstop never saw those bytes and the launder
        succeeds. Binding the quarantine to the tools closes that: the output is in
        the corpus, so a later write/egress of those bytes (even wrapper-stripped,
        even transformed) re-derives UNTRUSTED taint. Prefer this over the free
        function when running through GatedTools. (raw finding: quarantine output
        bypasses the corpus backstop when the wrapper is dropped)
        """
        def wrapped(value: Any) -> Tainted:
            text = _as_text(value)
            out = process(text)
            self._remember_untrusted(_as_text(out))
            return Tainted(out, TaintSet.of(TaintTag(Trust.UNTRUSTED, "quarantined-llm")))
        return wrapped
