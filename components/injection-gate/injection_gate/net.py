"""Deterministic network-target analysis for the gate.

Egress is the crown jewel of the whole design, so the parsing that feeds the
egress rules has to be hostile-input-hard. A model never touches anything here;
these are pure, deterministic string/IP operations a rule can lean on.

Three jobs:

  1. `host_of`        -- parse a target into a *canonical* host, defeating the
                         classic allowlist-evasion tricks (userinfo, trailing
                         dot, case, IDN/punycode, whitespace/control chars).
  2. `host_allowed`   -- match a host against an allowlist with an explicit,
                         opt-in subdomain policy. Exact-match by default; a
                         leading "." entry means "this host and its subdomains".
  3. `classify_host`  -- is the destination an *internal* / link-local / cloud-
                         metadata / loopback address? Those are the SSRF sinks an
                         injection reaches for (169.254.169.254 et al). They are
                         denied outright, never merely escalated.

`urlparse` alone is not safe for an allowlist check: `urlparse` happily parses
`https://api.good.com@evil.example/...` with hostname `evil.example`, but a lot
of naive code compares the wrong slice and lets it through. We go through the
hostname `urlparse` extracts but then re-validate it and strip the evasions.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import unquote, urlsplit

# Schemes a NETWORK action may legitimately use. Anything else (file, gopher,
# dict, ftp, ...) is a protocol-smuggling / local-resource SSRF attempt.
_OK_SCHEMES = frozenset({"", "http", "https"})
# Schemes that mean "this target reaches the network" regardless of the
# capability the wiring declared. Used to catch a network action mislabeled as
# a READ/EXEC so the egress rules still fire on it.
_NET_SCHEMES = frozenset({
    "http", "https", "ftp", "ftps", "ws", "wss",
    "gopher", "dict", "ldap", "ldaps", "tftp", "sftp", "smb", "telnet", "redis",
})
# Schemes that do NOT reach the network -- a local-file scheme. Everything with an
# explicit scheme that is not one of these is treated as network-bound, because a
# closed allowlist of "network schemes" misses the next exotic one (nfs://, git://,
# scp://, ssh://) and lets it dodge the egress rules. Open-by-default is the safe
# direction here. (raw finding: closed network-scheme allowlist)
_LOCAL_SCHEMES = frozenset({"file"})
# Schemes that may legitimately ride inside a redirect parameter value but smuggle
# a local-resource fetch when they do (gopher:// to Redis, dict:// to a service,
# file: to /etc/passwd). Surfaced from a redirect param so a rule classifies them
# even without a "//" in the value.
_SMUGGLE_SCHEMES = (_NET_SCHEMES - {"http", "https", "ws", "wss"}) | {"file"}
# A leading "scheme:" on a value (colon-opaque or scheme://).
_VALUE_SCHEME = re.compile(r"^([a-z][a-z0-9+.\-]*):", re.IGNORECASE)
# Unicode full-stop homoglyphs a resolver/UTS-46 treats as a label separator. They
# must fold to "." BEFORE the trailing-dot strip, or "127.0.0.1。" keeps a
# trailing label and dodges the loopback match. (raw finding: unicode-dot SSRF)
_UNICODE_DOTS = {0x3002: ".", 0xFF0E: ".", 0xFF61: "."}
# Raw control chars anywhere in a target are a smuggling tell. Checked on the RAW
# string before urlsplit, which silently strips \t\n\r out of the host -- so
# "goo\ndomain.com" must be rejected here, not after the parser has hidden it.
# (raw finding: control-char host splitting)
_RAW_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# A host that is only digits / hex / dots -- an obfuscated-IP candidate.
_NUMERICISH = re.compile(r"^[0-9a-fx.]+$")
# An octet that is a bare integer with no dots: 2130706433 (decimal),
# 0x7f000001 (hex), 017700000001 (octal) all decode to 127.0.0.1.
_INT_HOST = re.compile(r"^(0x[0-9a-f]+|0[0-7]*|[1-9][0-9]*)$")

# Hostnames that are never legitimate external egress destinations.
_LOCAL_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
# Suffixes that resolve to internal infrastructure by convention.
_INTERNAL_SUFFIXES = (".local", ".internal", ".localdomain", ".lan", ".home.arpa", ".cluster.local")
# Cloud-metadata IPs an SSRF injection targets to lift credentials.
_METADATA_IPS = {"169.254.169.254", "100.100.100.200", "fd00:ec2::254"}

# Characters that must never survive into a host we compare against an allowlist.
_BAD_HOST_CHARS = re.compile(r"[\s\x00-\x1f\x7f]")


@dataclass(frozen=True)
class HostClass:
    host: str            # canonical host, or "" if unparseable
    is_ip: bool
    is_internal: bool    # loopback / private / link-local / metadata / *.internal
    is_metadata: bool    # specifically a cloud-metadata endpoint
    raw_had_userinfo: bool  # the target embedded user@ -- an allowlist-spoof tell
    parse_ok: bool
    scheme: str = ""     # lowercased URL scheme, "" for a bare host:port
    port: Optional[int] = None  # explicit port, or None for none/default


def scheme_of(target: str) -> str:
    """The lowercased URL scheme, or "" for a bare host / host:port / path."""
    if not isinstance(target, str) or "://" not in target:
        # urlsplit would read "redis" out of "redis:6379"; only an explicit
        # "scheme://" counts as a real scheme for our purposes.
        return ""
    try:
        return (urlsplit(target.strip()).scheme or "").lower()
    except ValueError:
        return ""


def is_network_target(target: str) -> bool:
    """True when the target reaches the network, independent of declared capability.

    Defense-in-depth for BL-1: a tool that does HTTP but is wired as READ/EXEC
    would dodge every egress rule if those rules keyed only on Capability.NETWORK.
    Any explicit scheme that is not a local-file scheme is treated as network-bound
    -- an OPEN-by-default test, so an exotic scheme the closed allowlist never
    enumerated (nfs://, git://, scp://, ssh://) still gets the egress rules applied
    instead of slipping through. A bare hostname with no scheme is ambiguous with a
    relative filename, so it is *not* force-classified here; wire genuine fetch
    tools as NETWORK (GatedTools already does). (raw finding: closed network-scheme
    allowlist let nfs://, git:// dodge egress rules)
    """
    sc = scheme_of(target)
    return bool(sc) and sc not in _LOCAL_SCHEMES


def _strip_trailing_dot(host: str) -> str:
    # "api.good.com." is the same FQDN as "api.good.com" to a resolver, so an
    # allowlist check must treat them identically.
    return host[:-1] if host.endswith(".") and len(host) > 1 else host


def _idna_encode(host: str) -> Optional[str]:
    """Punycode a non-ASCII host the way the real client will resolve it.

    Prefer UTS-46 (uts46=True, transitional_processing=False) via the `idna`
    package: that is what current browsers/resolvers use, so a deviation character
    (German eszett, Greek final sigma) encodes to the punycode the client actually
    requests. The stdlib `str.encode('idna')` is legacy IDNA2003 and folds eszett
    to "ss", which would let `straße.good.com` match an allowlisted
    `strasse.good.com` while the resolver fetches `xn--strae-oqa.good.com` -- a
    different host. Fall back to the codec only if the package is unavailable.
    Returns None for an undecodable IDN (do not trust it for a match). (raw finding:
    IDNA2003 deviation-character allowlist bypass)
    """
    try:
        import idna as _idna  # third-party (ships with requests); soft dependency
        try:
            return _idna.encode(host, uts46=True,
                                transitional=False).decode("ascii").lower()
        except _idna.IDNAError:
            return None
    except ImportError:
        try:
            return host.encode("idna").decode("ascii").lower()
        except (UnicodeError, ValueError):
            return None


def canonical_host(target: str) -> str:
    """Best-effort canonical host for matching. "" when the target is hostile/unparseable."""
    return classify_host(target).host


def classify_host(target: str) -> HostClass:
    """Parse + classify a network target. Pure and deterministic."""
    if not isinstance(target, str) or not target:
        return HostClass("", False, False, False, False, False)

    raw = target.strip()
    # A raw control char (\t \n \r NUL ...) anywhere in the target is hostile and
    # must be caught BEFORE urlsplit, which silently strips \t\n\r out of the host
    # ("goo\nd.com" -> "good.com") and would otherwise hide the splice. (raw
    # finding: control-char host splitting)
    if _RAW_CONTROL.search(raw):
        return HostClass("", False, False, False, "@" in raw, False, scheme_of(raw))
    scheme = scheme_of(raw)
    # Give a bare "host" or "host:port" a scheme so urlsplit populates .hostname.
    work = raw if "://" in raw else "//" + raw
    try:
        parts = urlsplit(work)
        host = parts.hostname or ""
        port = parts.port  # raises ValueError on a bad port -> hostile (caught)
        had_userinfo = bool(parts.username or parts.password) or "@" in (parts.netloc or "")
    except ValueError:
        # urlsplit raises on some malformed IPv6 / port inputs -- treat as hostile.
        return HostClass("", False, False, False, "@" in raw, False, scheme)

    if not host:
        return HostClass("", False, False, False, had_userinfo, False, scheme)

    # Fold unicode full-stop homoglyphs to "." BEFORE stripping the trailing dot,
    # so "127.0.0.1。" -> "127.0.0.1." -> "127.0.0.1" instead of keeping a phantom
    # trailing label that dodges the loopback match. (raw finding: unicode-dot SSRF)
    host = host.translate(_UNICODE_DOTS)
    host = _strip_trailing_dot(host).strip().lower()

    # Any whitespace/control char surviving parse means a smuggling attempt.
    if _BAD_HOST_CHARS.search(host):
        return HostClass("", False, False, False, had_userinfo, False, scheme)

    # IDN/punycode: normalize to ASCII (Punycode) via UTS-46 so a homograph can't
    # dodge a plain-ASCII allowlist entry, a punycode entry can't dodge a Unicode
    # one, AND a deviation char can't resolve to a host other than the one matched.
    if any(ord(c) > 127 for c in host):
        encoded = _idna_encode(host)
        if encoded is not None:
            host = encoded
    # IDNA / UTS-46 can re-introduce a trailing dot from a folded unicode stop; strip
    # it again so the canonical host has none.
    host = _strip_trailing_dot(host)

    ip_obj = _as_ip(host)
    if ip_obj is not None:
        canon = str(ip_obj)
        # An IPv4-mapped IPv6 literal (::ffff:100.100.100.200) hides a metadata v4
        # address behind a v6 wrapper; compare the unwrapped v4 form too so the
        # wrapped Alibaba/AWS metadata endpoint is still caught. (raw finding:
        # v4-mapped metadata-IP bypass)
        mapped = getattr(ip_obj, "ipv4_mapped", None)
        is_meta = canon in _METADATA_IPS or (mapped is not None and str(mapped) in _METADATA_IPS)
        return HostClass(
            host=canon,
            is_ip=True,
            is_internal=_ip_is_internal(ip_obj) or is_meta,
            is_metadata=is_meta,
            raw_had_userinfo=had_userinfo,
            parse_ok=True,
            scheme=scheme,
            port=port,
        )

    is_internal = (
        host in _LOCAL_NAMES
        or host in _METADATA_IPS
        or any(host == s.lstrip(".") or host.endswith(s) for s in _INTERNAL_SUFFIXES)
    )
    return HostClass(
        host=host,
        is_ip=False,
        is_internal=is_internal,
        is_metadata=host in _METADATA_IPS,
        raw_had_userinfo=had_userinfo,
        parse_ok=True,
        scheme=scheme,
        port=port,
    )


def _as_ip(host: str):
    """Canonicalize any IP literal, including the obfuscated forms an SSRF uses.

    `ipaddress.ip_address` only accepts the dotted-quad / standard IPv6 forms, so
    on its own it misses the classic loopback-laundering encodings: a bare 32-bit
    integer (2130706433), a hex word (0x7f000001), an octal word (017700000001),
    mixed dotted-octal (0177.0.0.01), and IPv4-mapped IPv6 (::ffff:127.0.0.1).
    A naive parser sees those as "not 127.0.0.1" and an internal-IP rule that
    keyed on the string would wave the SSRF straight through. We decode them all
    to a canonical address so `_ip_is_internal` sees the truth.
    """
    if not host:
        return None
    # 1. Standard forms (dotted-quad, full IPv6, ::ffff:127.0.0.1).
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    # 2. Bare integer / hex / octal word -> a single 32- or 128-bit address.
    #    ipaddress.ip_address(int) yields IPv4 when it fits in 32 bits, else IPv6.
    if _INT_HOST.match(host):
        n = _parse_int_host(host)
        if n is not None and 0 <= n <= (2 ** 128 - 1):
            try:
                return ipaddress.ip_address(n)
            except (ValueError, ipaddress.AddressValueError):
                return None
    # 3. inet_aton short / mixed forms: a.b, a.b.c, a.b.c.d, with hex/octal octets
    #    and a final part that absorbs the remaining low-order bytes. 127.1 ->
    #    127.0.0.1, 192.168.257 -> 192.168.1.1, 0x7f.1 -> 127.0.0.1, 0177.0.0.01 ->
    #    127.0.0.1. A string-matching internal-IP check reads these as "not
    #    internal"; inet_aton (and the libc resolver behind a real fetch) reads them
    #    as loopback/RFC1918, so an SSRF rule must canonicalize them the same way.
    if "." in host and _NUMERICISH.match(host):
        parts = host.split(".")
        if 2 <= len(parts) <= 4:
            vals = [_parse_int_host(p) for p in parts]
            if all(v is not None for v in vals):
                packed = _pack_inet_aton(vals)
                if packed is not None:
                    try:
                        return ipaddress.IPv4Address(packed)
                    except (ValueError, ipaddress.AddressValueError):
                        return None
    return None


def _pack_inet_aton(vals) -> Optional[int]:
    """Pack inet_aton-style parts into a 32-bit IPv4 int, or None if out of range.

    The leading parts are single octets (0-255); the final part absorbs all the
    remaining low-order bytes, so `a.b` is an 8-bit head + 24-bit tail and `a.b.c`
    is two octets + a 16-bit tail. This is exactly how libc inet_aton decodes the
    classic short forms an SSRF uses to dodge a string-matching loopback check.
    """
    n = len(vals)
    if not (2 <= n <= 4):
        return None
    head, tail = vals[:-1], vals[-1]
    if any(v < 0 or v > 0xFF for v in head):
        return None
    tail_bits = (4 - (n - 1)) * 8
    if tail < 0 or tail > (1 << tail_bits) - 1:
        return None
    packed = 0
    for v in head:
        packed = (packed << 8) | v
    return (packed << tail_bits) | tail


def _parse_int_host(s: str):
    """Decode one octet/word as Python's inet_aton would: 0x=hex, 0=octal, else dec."""
    try:
        if s.startswith(("0x", "0X")):
            return int(s, 16)
        if s.startswith("0") and s != "0":
            return int(s, 8)
        return int(s, 10)
    except ValueError:
        return None


def _ip_is_internal(ip) -> bool:
    # An IPv4-mapped IPv6 (::ffff:127.0.0.1) hides an internal v4 address behind a
    # v6 literal; unwrap it before classifying so the SSRF can't dodge the check.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
    )


def host_allowed(target: str, allowlist: List[str]) -> bool:
    """Deterministic allowlist match with opt-in subdomain policy.

    Entry forms:
      "api.good.com"   -- exact host only.
      ".good.com"      -- good.com and any subdomain of it (explicit opt-in).

    A target whose host fails to parse, embeds userinfo, or is internal is never
    "allowed" here -- those are handled (denied) by dedicated rules upstream, but
    we also refuse to treat them as a clean allowlist hit.
    """
    hc = classify_host(target)
    if not hc.parse_ok or not hc.host or hc.raw_had_userinfo:
        return False
    host = hc.host
    for entry in allowlist:
        e = _strip_trailing_dot((entry or "").strip().lower())
        if not e:
            continue
        if e.startswith("."):
            base = e[1:]
            if host == base or host.endswith("." + base):
                return True
        elif host == e:
            return True
    return False


def _embedded_url_form(candidate: str) -> Optional[str]:
    """If `candidate` is a follow-on URL (absolute, scheme-relative, or a
    colon-opaque smuggle scheme), return a classifiable form, else None.

      https://evil/x        -> itself (cross-host absolute)
      //evil/x              -> http://evil/x (scheme-relative; browser keeps scheme)
      gopher:127.0.0.1:6379 -> itself (colon-opaque local-resource smuggle)
      file:/etc/passwd      -> itself
    A bare /path or relative value is same-host and returns None.
    """
    if "://" in candidate:
        return candidate
    if candidate.startswith("//") and not candidate.startswith("///"):
        return "http:" + candidate
    m = _VALUE_SCHEME.match(candidate)
    if m and m.group(1).lower() in _SMUGGLE_SCHEMES:
        return candidate
    return None


def redirect_param_target(target: str, param_names) -> Optional[str]:
    """If a query/fragment param carries a follow-on URL, return it for classifying.

    `https://api.good.com/r?next=https://evil.example/x` parses to outer host
    `api.good.com` (which may be allowlisted) while the real destination hides in
    `next=`. We surface the embedded URL so a rule can classify *its* host.

    Two surfacing tiers, to catch the gaps a name-allowlist alone leaves:
      - A NAMED redirect param (in `param_names`) always surfaces its URL value,
        even to an off-allowlist http(s) host -- that is the open-redirect lever.
      - ANY other param surfaces only when its value targets an INTERNAL host or a
        non-http smuggle scheme (gopher:/file:/dict:). A benign off-allowlist link
        sitting in a plain `?q=` is left alone (no false DENY), but `?img=gopher:
        //169.254.169.254` is not, regardless of the param's name.
    The fragment (`#next=...`) is scanned too: it never reaches the server but a
    client-side router/redirect acts on it, so it is the same SSRF lever. (raw
    finding: redirect via fragment / unnamed param / colon-opaque scheme)
    Deterministic, no network.
    """
    if not isinstance(target, str) or ("?" not in target and "#" not in target and ";" not in target):
        return None
    try:
        parts = urlsplit(target)
    except ValueError:
        return None
    names = {n.lower() for n in param_names}
    # Path MATRIX parameters (`/r;next=gopher://169.254.169.254/`) are a server-bound
    # payload channel too -- the gate's own _payload_present already treats `;k=v` in
    # the path as such -- yet the redirect scanner only looked at query+fragment, so a
    # follow-on smuggle URL parked in a matrix param sailed past as clean egress. Fold
    # the matrix params into the same scan. (raw finding: redirect via path matrix param)
    matrix = _matrix_param_blob(parts.path)
    blobs = [b for b in (parts.query, parts.fragment, matrix) if b]
    for blob in blobs:
        for pair in re.split(r"[&;]", blob):
            key, _, val = pair.partition("=")
            if not val:
                continue
            candidate = _normalize_redirect_value(val)
            absform = _embedded_url_form(candidate)
            if absform is None:
                continue
            if key.lower() in names:
                return absform
            # Unnamed param: only surface a genuinely dangerous destination, so a
            # benign URL-valued query does not trip a false DENY.
            m = _VALUE_SCHEME.match(candidate)
            sc = m.group(1).lower() if m else ""
            if classify_host(absform).is_internal or (sc and sc in _SMUGGLE_SCHEMES):
                return absform
    return None


def _matrix_param_blob(path: str) -> str:
    """Surface the `;k=v` matrix parameters of a path as one &-joined blob, so the
    same param scanner that handles query/fragment handles them too.
    `/r;next=gopher://169.254.169.254/_/x` -> `next=gopher://169.254.169.254/_/x`.

    Everything after the FIRST ';' is matrix-parameter territory (the params are
    ';'-separated); we deliberately do NOT split on '/', because a smuggled redirect
    VALUE carries its own slashes (`gopher://host/path`) and splitting would truncate
    it to the bare scheme. Over-capturing a trailing path segment into a value is
    harmless: it just will not parse as a URL. Returns "" when there is no matrix
    parameter. Deterministic, no network."""
    if not isinstance(path, str) or ";" not in path:
        return ""
    return path.split(";", 1)[1].replace(";", "&")


def _normalize_redirect_value(val: str) -> str:
    r"""Decode a redirect-param value to a stable form before classifying it.

    Defeats two evasions a naive single-unquote misses: multi-level URL-encoding
    that hides the //host (or scheme://) shape until fully decoded
    (`%252f%252fevil`, and deeper), and backslashes a browser/UA folds to forward
    slashes (`https:\\evil`, `/\evil`). We unquote to a fixed point (bounded high
    so a deeply nested encoding still fully resolves), then fold backslashes, so the
    cross-host jump cannot stay hidden behind encoding. (raw finding: backslash +
    multi-level-encoded redirect bypass)
    """
    candidate = val
    for _ in range(64):
        nxt = unquote(candidate)
        if nxt == candidate:
            break
        candidate = nxt
    return candidate.replace("\\", "/")


# --- DNS / subdomain exfiltration heuristics -------------------------------

_HEX_LABEL = re.compile(r"^[0-9a-f]{16,}$")
_B32_LABEL = re.compile(r"^[a-z2-7]{20,}$")


def _matched_public_suffix_wildcard(host: str, allowlist: List[str]) -> bool:
    """True if `host` is allowed via a bare-TLD wildcard entry like ".com"/".io".

    Such an entry registers an entire public suffix, so the registrable-domain
    label (index -2) is operator-chosen and the *data-bearing* label sits at
    index 0 even in a 2-label host. labels[:-2] would skip it. We only treat a
    single-label-after-the-dot wildcard as a public suffix; ".good.com" is a normal
    subdomain wildcard and does not qualify.
    """
    for entry in allowlist or []:
        e = (entry or "").strip().lower()
        if not e.startswith("."):
            continue
        base = e[1:]
        if base and "." not in base and host.endswith("." + base):
            return True
    return False


def looks_like_dns_exfil(target: str, allowlist: List[str]) -> Optional[str]:
    """Detect data smuggled into a high-entropy / over-long subdomain label.

    Returns a reason string if suspicious, else None. Deterministic: it keys on
    label length and charset shape, the way a DNS-tunnel/exfil subdomain looks
    (`<base32-of-secret>.collect.attacker.com` or `<hex>.allowed.com`).
    """
    hc = classify_host(target)
    if not hc.parse_ok or hc.is_ip or not hc.host:
        return None
    labels = hc.host.split(".")
    # The leftmost labels are where smuggled data rides. Normally that is every
    # label except the registrable domain + TLD (labels[:-2]). But under a 2-label
    # host, or a public-suffix wildcard allowlist (".com"), the registrable label
    # IS the leftmost one, so labels[:-2] would skip the exact label carrying the
    # data -- include index 0 in those cases. (raw finding: 2-label / public-suffix
    # DNS-exfil dead spot)
    scan = list(labels[:-2]) if len(labels) > 2 else []
    if (len(labels) == 2 or _matched_public_suffix_wildcard(hc.host, allowlist)) and labels:
        if labels[0] not in scan:
            scan.insert(0, labels[0])
    for label in scan:
        if len(label) >= 32:
            return f"over-long subdomain label ({len(label)} chars): possible DNS/subdomain exfil"
        if _HEX_LABEL.match(label) or _B32_LABEL.match(label):
            return f"high-entropy subdomain label '{label[:12]}...': possible encoded-data exfil"
    return None
