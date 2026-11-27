"""Deterministic credential-shape detection.

A whole class of exfiltration never trips a taint rule because the *value* being
sent looks innocuous to the taint layer (it was read from a trusted config, so
it is "trusted"), yet it is a live secret. This module looks at the *shape* of
the bytes about to leave the process and flags things that look like keys,
tokens, and private material.

This is pattern matching, not judgment. No model. False positives are fine here:
the verdict for a credential-shaped argument heading to the network is ESCALATE
(hold for a human) or DENY, not silent block-everything, so a real secret in a
legitimately-outbound payload surfaces for review rather than leaking silently.

It is deliberately conservative about what counts as "high entropy" so ordinary
prose and IDs do not constantly trip it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, List, Optional

# Named, high-confidence secret shapes. Each is specific enough to rarely misfire.
#
# The fixed-prefix signatures (AKIA, ghp_, GOCSPX-, AIza, xox, eyJ, sk_live_) carry
# NO leading \b. A \b between two word chars does not exist, so `keyAKIA...` (a real
# key with a filler prefix glued on) defeated `\bAKIA` -- one character of padding
# walked the secret straight past the detector. The prefix+length of each of these
# is distinctive enough that dropping the boundary does not add false positives.
# The two short/common prefixes (`sk-`, `Bearer`) keep a non-alnum lookbehind so
# they do not fire inside ordinary words like "task-" or "uBearer". (raw finding:
# word-boundary credential evasion)
_SIGNATURES = [
    ("aws_access_key_id", re.compile(r"(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}")),
    ("aws_secret_access_key", re.compile(r"aws_secret_access_key\s*[=:]\s*[0-9A-Za-z/+]{40}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("google_oauth_secret", re.compile(r"GOCSPX-[0-9A-Za-z_\-]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("openai_key", re.compile(r"(?<![A-Za-z0-9])sk-(?:proj-)?[0-9A-Za-z_\-]{20,}")),
    ("stripe_key", re.compile(r"[rs]k_(?:live|test)_[0-9A-Za-z]{16,}")),
    ("jwt", re.compile(r"eyJ[0-9A-Za-z_\-]{8,}\.[0-9A-Za-z_\-]{8,}\.[0-9A-Za-z_\-]{8,}")),
    ("bearer_header", re.compile(r"(?<![A-Za-z0-9])Bearer\s+[0-9A-Za-z._\-]{20,}")),
    ("generic_assignment", re.compile(
        r"(?i)\b(?:api[_-]?key|apikey|secret|passwd|password|pwd|pw|pass|cred|token|client[_-]?secret)\b"
        r"\s*[=:]\s*['\"]?[0-9A-Za-z/+_\-]{12,}")),
]

# A long, high-entropy opaque token with no spaces is secret-shaped even when
# it matches no named signature. Floor lowered 32 -> 20: token_urlsafe(16) is 22
# chars and a base64-wrapped AWS key id is 28, both of which lived in the dead band
# under the old floor while being unmistakably secret-shaped. The entropy gate below
# keeps ordinary 20-char IDs from tripping it, and the verdict for an unnamed match
# is hold-for-review, not a hard block. (raw finding: opaque-token floor dead band)
_OPAQUE_TOKEN = re.compile(r"[0-9A-Za-z+/=_\-]{20,}")

# A long contiguous hex run is a reversible encoding of *something*. Hex of prose
# has only ~3.3 bits/char (16-symbol alphabet), so it slips under the entropy
# floor while round-tripping perfectly back to the original bytes -- the laundering
# move the corpus-taint and entropy checks both miss. Flag it on shape, not entropy.
# 64+ chars (>=32 bytes) clears ordinary IDs/short hashes; the verdict is the same
# hold-for-review an unnamed token gets, not a hard block. (raw finding: hex
# laundering under the entropy floor)
_HEX_BLOB = re.compile(r"\b[0-9a-fA-F]{64,}\b")

# A scalar that is ENTIRELY token characters (no spaces / punctuation) is a plausible
# secret fragment; one with a space is prose. Used to build the token-only spine that
# survives a split secret interleaved with ordinary fields. (raw finding: split secret
# interleaved with space-bearing fields)
_TOKEN_RUN = re.compile(r"[0-9A-Za-z/+_=\-]+")

# Hard bound on nodes visited while walking an args structure, so a pathological or
# cyclic payload terminates. Set far above any realistic request body. Replaces a
# recursion DEPTH cap that silently failed OPEN -- a secret nested past the cap was
# never scanned at all. (raw finding: depth cap blinds the credential scan)
_MAX_SCAN_NODES = 100_000


@dataclass(frozen=True)
class CredentialHit:
    kind: str
    snippet: str  # short, redacted-ish preview for the audit log (never the full secret)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _preview(token: str) -> str:
    token = str(token)
    if len(token) <= 8:
        return token[:2] + "***"
    return f"{token[:4]}...{token[-2:]} (len {len(token)})"


_HEXISH = re.compile(r"[^0-9a-fA-F]")
_B64ISH = re.compile(r"^[0-9A-Za-z+/=_\-]+$")
_B32ISH = re.compile(r"^[A-Z2-7]+=*$")
_A85ISH = re.compile(r"^[\x21-\x75]+$")


def _decode_variants(text: str) -> List[str]:
    """Reversible decodings an exfil uses to wrap a secret past a shape match:
    URL-unquote, hex, base64, and a plain reversal. Bad decodes are dropped.
    Deterministic, no network. Mirrors tools._reversible_decodings so the
    credential detector and the corpus-taint detector strip the same wrappers."""
    out: List[str] = []
    s = text.strip()
    try:
        from urllib.parse import unquote
        u = unquote(s)
        if u != s:
            out.append(u)
    except Exception:
        pass
    compact = _HEXISH.sub("", s)
    if len(compact) >= 32 and len(compact) % 2 == 0:
        try:
            out.append(bytes.fromhex(compact).decode("utf-8", "ignore"))
        except ValueError:
            pass
    b64 = re.sub(r"\s", "", s)
    if len(b64) >= 16 and _B64ISH.match(b64):
        import base64 as _b64
        cand = b64.replace("-", "+").replace("_", "/")
        cand += "=" * (-len(cand) % 4)
        try:
            dec = _b64.b64decode(cand, validate=False).decode("utf-8", "ignore")
            if dec:
                out.append(dec)
        except Exception:
            pass
    # base32 / base85 / Ascii85: mirror tools._reversible_decodings so a named secret
    # wrapped in one of these is still recovered by the decode pass. (raw finding:
    # base32 / base85 / Ascii85 laundering past the decoder set)
    import base64 as _b64
    b32 = re.sub(r"\s", "", s).upper()
    if len(b32) >= 16 and _B32ISH.match(b32):
        try:
            out.append(_b64.b32decode(b32 + "=" * (-len(b32) % 8)).decode("utf-8", "ignore"))
        except Exception:
            pass
    a = re.sub(r"\s", "", s)
    if len(a) >= 16 and _A85ISH.match(a):
        for _decoder in (_b64.a85decode, _b64.b85decode):
            try:
                out.append(_decoder(a).decode("utf-8", "ignore"))
            except Exception:
                pass
    if len(s) >= 20:
        out.append(s[::-1])
    return out


def _scan_named(text: str) -> List[CredentialHit]:
    """Named signatures only (no entropy/opaque fallback). Used on decoded
    variants so a base64/hex/reversed-wrapped named secret is still caught without
    the opaque detector double-flagging the wrapper itself."""
    hits: List[CredentialHit] = []
    for kind, rx in _SIGNATURES:
        m = rx.search(text)
        if m:
            hits.append(CredentialHit(kind, _preview(m.group(0))))
    return hits


def scan_text(text: str, *, min_entropy: float = 3.6) -> List[CredentialHit]:
    """Return credential-shaped hits in a single string. Deterministic."""
    if not isinstance(text, str) or not text:
        return []
    hits: List[CredentialHit] = []
    for kind, rx in _SIGNATURES:
        m = rx.search(text)
        if m:
            hits.append(CredentialHit(kind, _preview(m.group(0))))
    if not hits:
        # A long contiguous hex run is reversible-encoded data regardless of its
        # (low) entropy, so check shape before falling through to the entropy gate.
        m = _HEX_BLOB.search(text)
        if m:
            hits.append(CredentialHit("hex_blob", _preview(m.group(0))))
    if not hits:
        # Only fall back to entropy when no named signature matched, to keep
        # noise down. A long opaque token with high entropy is the tell.
        for tok in _OPAQUE_TOKEN.findall(text):
            if _shannon_entropy(tok) >= min_entropy:
                hits.append(CredentialHit("high_entropy_token", _preview(tok)))
                break
    if not hits:
        # Last: a named secret hidden inside a reversible wrapper (base64/hex/url/
        # reversed). Decode and re-test only the NAMED signatures so the wrapper's
        # own shape does not double-flag. (raw finding: encoded-credential evasion)
        for variant in _decode_variants(text):
            named = _scan_named(variant)
            if named:
                hits.extend(named)
                break
    return hits


def scan_value(value: Any, *, min_entropy: float = 3.6) -> List[CredentialHit]:
    """Scan an arbitrary argument value (str / dict / list / bytes) for credential
    shapes. Both keys and values are scanned.

    Iterative traversal with an id()-based cycle guard and a node-count bound, NOT a
    recursion depth cap. The old cap (depth > 6) silently failed OPEN: a named secret
    nested deeper than six levels in a JSON body was never scanned, so it egressed
    clean. A security control must not stop looking partway down. The bound and cycle
    guard keep a pathological or cyclic structure terminating. (raw finding: depth cap
    blinds the credential scan)"""
    out: List[CredentialHit] = []
    stack: List[Any] = [value]
    seen: set = set()
    nodes = 0
    while stack and nodes < _MAX_SCAN_NODES:
        v = stack.pop()
        nodes += 1
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8", "ignore")
            except Exception:
                continue
        if isinstance(v, str):
            out += scan_text(v, min_entropy=min_entropy)
            continue
        if isinstance(v, dict):
            if id(v) in seen:
                continue
            seen.add(id(v))
            for k, val in v.items():
                stack.append(k)
                stack.append(val)
        elif isinstance(v, (list, tuple, set)):
            if id(v) in seen:
                continue
            seen.add(id(v))
            for item in v:
                stack.append(item)
    return out


def _iter_scalars(value: Any):
    """Yield every scalar string *value* in an arbitrary structure (str/bytes/dict/
    list) in document order, used to build the split-secret spine.

    Dict KEYS are deliberately NOT yielded: a key is a structural field name
    ('method', 'body', 'headers', 'Cookie'), not a fragment of a leaked secret.
    Joining keys into the no-separator spine manufactured junk high-entropy runs
    ('method'+'body'+'headers' -> 'methodbodyheaders') that misfired as credentials.
    A secret riding out AS a key is still caught -- by scan_value (which scans keys)
    and by the policy layer's dict-key payload check -- just not by this reassembly
    spine. (raw finding: dict keys in the spine manufacture false hits)

    Iterative + id()-cycle-guarded + node-bounded, like scan_value, so a secret split
    across fields nested arbitrarily deep is still reassembled (the old depth-6 cap
    dropped the whole subtree). Children are pushed reversed so the LIFO stack still
    yields scalars in document order, which the spine reassembly depends on."""
    stack: List[Any] = [value]
    seen: set = set()
    nodes = 0
    while stack and nodes < _MAX_SCAN_NODES:
        v = stack.pop()
        nodes += 1
        if isinstance(v, bytes):
            try:
                v = v.decode("utf-8", "ignore")
            except Exception:
                continue
        if isinstance(v, str):
            if v:
                yield v
        elif isinstance(v, dict):
            if id(v) in seen:
                continue
            seen.add(id(v))
            for val in reversed(list(v.values())):
                stack.append(val)
        elif isinstance(v, (list, tuple, set)):
            if id(v) in seen:
                continue
            seen.add(id(v))
            for item in reversed(list(v)):
                stack.append(item)


def scan_request_payload(req, *, min_entropy: float = 3.6) -> Optional[CredentialHit]:
    """Scan everything an ActionRequest would put on the wire: target + args.

    Returns the first hit (enough to drive a verdict) or None.
    """
    hits = scan_value(req.target, min_entropy=min_entropy)
    if not hits:
        hits = scan_value(req.args, min_entropy=min_entropy)
    if not hits:
        # Split-secret defense: an exfil can break one key across two args
        # ("AKIA..." in arg a, the last chars in arg b) so no single value matches.
        # Join every ARG scalar (no separator) into one spine and rescan, so the
        # reassembled run trips the shape match. The target is deliberately left OUT
        # of the spine: it is already scanned whole above, and folding its URL path
        # in (the opaque-token class includes '/') merged path segments with arg keys
        # into junk high-entropy runs that misfired as credentials. (raw finding:
        # split-credential across args)
        scalars = list(_iter_scalars(req.args))
        spine = "".join(scalars)
        if spine:
            hits = scan_text(spine, min_entropy=min_entropy)
        if not hits:
            # Interleaved split secret: an exfil can place secret fragments in separate
            # fields with ordinary PROSE fields between them ('access_id_p1', 'note',
            # 'access_id_p2', ...). The no-separator spine then splices the prose -- and
            # its spaces -- between the fragments, breaking the contiguous run the shape
            # match needs. Join ONLY the pure-token scalars (no spaces/punctuation, i.e.
            # plausible secret fragments), in order, and rescan: the prose fields drop
            # out, the fragments re-touch, and the match fires. Prose carries no secret
            # shape, so excluding it loses nothing. (raw finding: split secret
            # interleaved with space-bearing fields)
            token_spine = "".join(s for s in scalars if _TOKEN_RUN.fullmatch(s))
            if token_spine and token_spine != spine:
                hits = scan_text(token_spine, min_entropy=min_entropy)
    return hits[0] if hits else None
