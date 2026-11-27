"""Deterministic policy engine.

The gate's one inviolable rule: decisions are DETERMINISTIC. They are computed
from the ActionRequest and a PolicyContext (capability grants, sensitive paths,
egress allowlist, optional host baseline). They never call a model. The thing
injection compromises is model judgment, so model judgment cannot be load-bearing
in the defense.

Severity order: DENY > ESCALATE > ALLOW. The engine returns the most severe
verdict among all rules that fire (ties keep the earlier-registered rule, so the
most specific / highest-signal rule names the decision). If nothing fires, it
returns `default`.

POSTURE NOTE: `default` ships as ALLOW for ergonomics, but the shipped rule set
denies/escalates the sensitive cases explicitly, and several controls (SSRF,
credential-shape, DNS-exfil) fire unconditionally because they have no legitimate
use. For a hardened deployment call `harden(ctx)` and `hardened_engine()`, which
flip the default to ESCALATE and turn on the fail-closed posture flags so anything
unanticipated does not sail through.

The network parsing the egress rules depend on lives in `net.py` and is hostile-
input-hard (userinfo spoofs, trailing dots, IDN/punycode, internal-IP / cloud-
metadata classification). The credential-shape detector lives in `credentials.py`.
"""
from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Callable, List, Optional
from urllib.parse import urlsplit

from . import credentials, net
from .action import ActionRequest, Capability

if TYPE_CHECKING:  # avoid a runtime import cycle; baseline only imports net
    from .baseline import HostBaseline


class Verdict(IntEnum):
    ALLOW = 0
    ESCALATE = 1   # hold for human approval / run in sandbox first
    DENY = 2


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    rule: str
    reason: str


@dataclass
class CapabilityGrant:
    """Least-privilege scope handed to an agent for a task."""
    read_roots: List[str] = field(default_factory=list)    # dirs the agent may read
    write_roots: List[str] = field(default_factory=list)   # dirs the agent may write/delete
    egress_allowlist: List[str] = field(default_factory=list)  # hostnames it may reach
    exec_allowed: bool = False
    delete_allowed: bool = False
    external_write_roots: List[str] = field(default_factory=list)
    #   Subset of write_roots that sync off-box (a shared mount, a bucket, a repo
    #   that pushes). A WRITE of tainted data into one of these is an exfil sink as
    #   real as a network POST, so it is held. Empty (default) = none are external,
    #   which preserves the laundering-defense flow (write-to-sandbox-then-read-back
    #   stays a local round-trip the ledger re-taints). Set this for write roots
    #   whose contents leave the host.

    def __post_init__(self):
        # Freeze every scope root to an absolute, canonical path at configuration
        # time. A relative root ("./out") otherwise re-resolves against the process
        # CWD at each decision, so a later os.chdir() by the agent or a tool would
        # drift the sandbox boundary onto a different directory and wave writes
        # through it. Anchoring here makes the boundary immovable. (raw finding:
        # relative-root CWD drift)
        self.read_roots = [self._freeze_root(r) for r in self.read_roots]
        self.write_roots = [self._freeze_root(r) for r in self.write_roots]
        self.external_write_roots = [self._freeze_root(r) for r in self.external_write_roots]

    @staticmethod
    def _freeze_root(r) -> str:
        # An empty or whitespace-only root is the dangerous accident: os.path.realpath("")
        # returns the process CWD, silently putting the ENTIRE working directory --
        # source tree included -- in scope. Reject it loudly at config time instead of
        # waving writes through cwd at runtime. A leading "~" is expanded so it cannot
        # land literally as a "cwd/~/out" directory. Relative roots stay supported
        # (frozen to absolute here, defeating CWD drift). (raw finding: empty-string
        # scope root = whole-CWD scope)
        if not isinstance(r, str) or not r.strip():
            raise ValueError(f"scope root must be a non-empty path string, got {r!r}")
        return os.path.realpath(os.path.expanduser(r.strip()))


@dataclass
class PolicyContext:
    grant: CapabilityGrant
    sensitive_paths: List[str] = field(default_factory=list)  # secret-class paths

    # --- optional hardening inputs (default off => backward compatible) ----
    baseline: Optional["HostBaseline"] = None
    #   When set, first contact with a never-before-seen egress host ESCALATES.

    escalate_tainted_egress: bool = False
    #   When True, ANY egress of tainted (untrusted-derived) data ESCALATES, even
    #   to an allowlisted host. Off by default because "summarize page -> POST
    #   summary to our own API" is a legitimate tainted-egress flow; turn it on
    #   for tasks where no tainted data should ever leave.

    restrict_unscoped_reads: bool = False
    #   When True, an empty read_roots means "no reads scoped" => reads ESCALATE,
    #   instead of the lenient "no restriction". Fail-closed reads.

    deny_credential_egress: bool = False
    #   When True, a high-entropy (unnamed) credential-shaped argument heading to
    #   the network is DENIED rather than ESCALATED. Named secrets (AWS keys,
    #   private-key blocks, JWTs, ...) are always DENIED regardless of this flag.


# --- helpers ---------------------------------------------------------------

def _host_of(target: str) -> str:
    """Canonical host. Hardened against allowlist-evasion (see net.canonical_host)."""
    return net.canonical_host(target) or ""


def _is_network(req: ActionRequest) -> bool:
    """A request reaches the network if it is wired NETWORK *or* its target carries
    a network scheme. The second clause (BL-1) is defense-in-depth: a fetch tool a
    developer mislabeled as READ/EXEC, or an injection that smuggles a `gopher://`
    target through a non-network tool, still gets the egress rules applied."""
    return req.capability is Capability.NETWORK or net.is_network_target(req.target)


def _norm(path: str) -> str:
    # realpath collapses symlinks/.. ; normcase lowercases on case-insensitive
    # platforms (Windows/macOS) so a case game cannot dodge a scope/secret match.
    # It is a no-op on case-sensitive Linux, which is correct there.
    return os.path.normcase(os.path.realpath(path))


def _safe_norm(path: str) -> Optional[str]:
    # _norm, but a malformed path (embedded NUL, non-string) yields None instead of
    # raising. None never matches a root or a sensitive prefix, so a malformed
    # target fails closed -- no allow_inscope_* fires, write_sandbox/read_scope hold
    # it -- and a raw ValueError never propagates out of evaluate(). (raw finding:
    # NUL-byte path crash / fail-open)
    #
    # The explicit non-str guard matters: os.path.realpath(b"/x") SUCCEEDS and
    # returns bytes, which would then crash a later .startswith(str)/.casefold()
    # with a TypeError that escapes the rule -- a non-string (bytes) target must
    # fail closed here, not sail into the string ops. (raw finding: bytes target
    # crashes the path rules)
    if not isinstance(path, str):
        return None
    try:
        return _norm(path)
    except (ValueError, OSError, TypeError):
        return None


def _under_any(path: str, roots: List[str]) -> bool:
    # Scope (ALLOW) matching: must be conservative. We use normcase only, never
    # casefold, because over-matching here could mark an out-of-scope path as
    # in-scope on a case-sensitive filesystem -- the unsafe direction.
    p = _safe_norm(path)
    if p is None:
        return False
    for root in roots:
        r = _safe_norm(root)
        if r is not None and (p == r or p.startswith(r + os.sep)):
            return True
    return False


def _matches_sensitive(path: str, sensitive: List[str]) -> bool:
    # Secret-class (DENY/ESCALATE) matching: over-blocking is the safe direction,
    # so we casefold in addition to normcase to defeat case games even on a
    # case-sensitive filesystem (.SECRETS vs .secrets).
    p = _safe_norm(path)
    if p is None:
        return False
    p = p.casefold()
    for s in sensitive:
        rs = _safe_norm(s)
        if rs is None:
            continue
        rs = rs.casefold()
        if p == rs or p.startswith(rs + os.sep):
            return True
    return False


# Basenames / suffixes that name a secret regardless of where they live. Matched
# case-insensitively. Pattern-based (BL-8) so an undeclared secret file is caught
# even when the operator forgot to list it in sensitive_paths.
_SECRET_BASENAMES = frozenset({
    ".env", ".envrc", ".netrc", ".pgpass", ".htpasswd",
    "credentials", "credentials.json", "secrets.json", "secrets.yaml", "secrets.yml",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    ".npmrc", ".pypirc", ".dockercfg", ".git-credentials",
    "service-account.json", "serviceaccount.json", "kubeconfig", ".kube",
})
_SECRET_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".keystore", ".jks", ".ppk", ".asc", ".gpg")
# id_dsa/id_ecdsa and the basename-only credential dotfiles join the substring set
# so a mangled form (prod.pgpass.backup-2024) is caught even past suffix-stripping.
_SECRET_SUBSTRINGS = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "secret",
                      "credential", "_token", ".aws/",
                      ".npmrc", ".pgpass", ".netrc", ".htpasswd")
# Backup / editor / dist suffixes appended to a secret file. A `.pgpass.bak` is as
# sensitive as `.pgpass`; the basename-only families have no substring fallback, so
# any suffix used to evade the exact-name test. Strip these before matching. (raw
# finding: secret-by-name backup-suffix evasion)
_SECRET_BACKUP_SUFFIXES = (".bak", ".save", ".old", ".orig", ".swp", ".swo",
                           ".tmp", ".dist", ".sample", ".example", ".backup")


def _strip_backup_suffixes(base: str) -> str:
    """Strip stacked backup/editor suffixes so the secret being backed up shows
    through: `.pgpass.bak` -> `.pgpass`, `id_dsa.bak` -> `id_dsa`, `.npmrc~` ->
    `.npmrc`. Bounded loop; deterministic; never strips the whole name away."""
    changed = True
    while changed:
        changed = False
        if base.endswith("~") and len(base) > 1:
            base = base[:-1]
            changed = True
            continue
        for suf in _SECRET_BACKUP_SUFFIXES:
            if base.endswith(suf) and len(base) > len(suf):
                base = base[:-len(suf)]
                changed = True
                break
    return base


def _looks_like_secret_name(path: str) -> bool:
    """Heuristic secret-by-name detector (BL-8). Deterministic, case-insensitive."""
    p = _safe_norm(path)
    if p is None:
        return False
    p = p.casefold()
    base = os.path.basename(p)
    core = _strip_backup_suffixes(base)   # the name with any backup suffix removed
    if base in _SECRET_BASENAMES or core in _SECRET_BASENAMES:
        return True
    if base.startswith(".env") or core.startswith(".env"):  # .env, .env.local, ...
        return True
    if base.endswith(_SECRET_SUFFIXES) or core.endswith(_SECRET_SUFFIXES):
        return True
    if any(s in p for s in _SECRET_SUBSTRINGS):
        return True
    return False


# Query-parameter names that carry a follow-on URL: an open-redirect / SSRF lever.
# The list spans the framework conventions that name a redirect target: Django/Rails
# (`redirect_to`, `next`), OAuth/OIDC (`redirect_uri`), SAML/CAS (`relaystate`,
# `service`, `shire`), and the generic `return*`/`callback*`/`forward*` family. A
# named match surfaces the embedded host regardless of where it points; the unnamed
# structural backstop in redirect_param_target still catches the off-list params that
# aim at an internal host or a smuggle scheme. (raw finding: off-allowlist redirect in
# an unlisted-but-redirect-shaped param)
_REDIRECT_PARAMS = frozenset({
    "url", "uri", "redirect", "redirect_uri", "redirecturi", "redirect_url", "redirecturl",
    "redirect_to", "redirectto", "redir", "rurl",
    "next", "dest", "destination", "return", "returnto", "return_to", "returnurl",
    "return_path", "returnpath", "continue", "callback", "callbackurl", "callback_url",
    "target", "target_url", "to", "out", "link", "goto", "image",
    "forward", "forward_url", "forwardurl", "back", "backurl", "back_url",
    "success_url", "successurl", "cancel_url", "cancelurl", "failure_url",
    "relaystate", "service", "shire", "sso", "openid_return_to",
})


# Arg keys that are pure transport metadata, not attacker-controllable payload.
# Their presence alone does not make an egress an exfiltration -- but only when the
# value really is that metadata (see _payload_present): a `method` slot holding a
# verb is transport; a `method` slot stuffed with prose is exfil wearing the slot
# as a disguise. (raw finding: payload smuggled in the method slot)
_NON_PAYLOAD_ARG_KEYS = frozenset({"method"})

# Recognized request "method" values. A method arg holding one of these is genuine
# transport metadata and skipped; anything else in that slot is treated as payload.
_HTTP_VERBS = frozenset({
    "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT",
    "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE", "LOCK", "UNLOCK", "REPORT", "SEARCH",
})

# A ;key=value matrix parameter embedded in a URL path is request data the same way
# a ?query is, and rides to the server -- so it is a payload channel, not decoration.
_MATRIX_PARAM = re.compile(r";[^/;]+=[^/;]+")

_PAYLOAD_DEPTH_CAP = 6


def _has_nonempty_value(v, _depth: int = 0, _seen=None) -> bool:
    """True if v carries any non-empty scalar, recursing into dict/list/tuple/set.
    A header value, a cookie, a nested field, or one chunk of split data all count.

    A non-empty dict KEY counts as payload too: a secret can ride out as a header
    name or a form-field name, not only as a value (raw finding: dict-key payload).
    Recursion is depth-capped and cycle-guarded so a deeply nested or self-
    referential structure cannot blow the stack -- hitting the cap returns True
    (treat-as-payload, the held/safe direction). (raw finding: deep-nest recursion
    crash)"""
    if _depth > _PAYLOAD_DEPTH_CAP:
        return True
    if v is None:
        return False
    if isinstance(v, dict):
        if _seen is None:
            _seen = set()
        if id(v) in _seen:
            return True
        _seen.add(id(v))
        for k, x in v.items():
            if isinstance(k, (str, bytes)) and len(k) > 0:
                return True
            if _has_nonempty_value(x, _depth + 1, _seen):
                return True
        return False
    if isinstance(v, (list, tuple, set)):
        if _seen is None:
            _seen = set()
        if id(v) in _seen:
            return True
        _seen.add(id(v))
        return any(_has_nonempty_value(x, _depth + 1, _seen) for x in v)
    if isinstance(v, (str, bytes)):
        return len(v) > 0
    return True  # a non-empty scalar of some other type (int, etc.)


def _payload_present(req: ActionRequest) -> bool:
    """Does this egress carry data that could exfiltrate untrusted bytes?

    Payload = a non-empty URL query or fragment, OR any non-empty value anywhere
    in req.args except pure transport metadata (the HTTP method). We recurse so a
    value hidden in a header, a cookie, an arbitrary arg key, a nested field, or
    one chunk of split data is still seen -- the earlier version checked only a
    fixed handful of body keys and missed the header/cookie/arbitrary-key/chunk
    channels (raw finding). A bare GET with none of these is just a fetch; data
    riding out is the exfil shape we hold (BL-5). Only consulted on tainted egress,
    so widening it never holds an ordinary clean fetch."""
    try:
        sp = urlsplit(str(req.target))
        if sp.query or sp.fragment:
            return True
        # A ;k=v matrix parameter in the path is a payload channel too.
        if ";" in sp.path and _MATRIX_PARAM.search(sp.path):
            return True
    except (ValueError, TypeError):
        t = str(req.target)
        if "?" in t or "#" in t or _MATRIX_PARAM.search(t):
            return True
    for key, val in req.args.items():
        # Skip the method slot ONLY when it actually holds a request verb. A
        # `method` arg carrying anything else (prose, PII, a base64 blob) is exfil
        # disguised as transport metadata and must count as payload.
        if key in _NON_PAYLOAD_ARG_KEYS:
            if isinstance(val, str) and val.strip().upper() in _HTTP_VERBS:
                continue
        if _has_nonempty_value(val):
            return True
    return False


# --- rule type -------------------------------------------------------------

@dataclass
class PolicyRule:
    name: str
    # returns a Decision if the rule fires, else None
    check: Callable[[ActionRequest, PolicyContext], Optional[Decision]]


# --- network rules ---------------------------------------------------------

def _r_internal_egress(req, ctx):
    # SSRF guard: egress to loopback / RFC1918 / link-local / cloud-metadata.
    # These have no legitimate use for an external task and are the sink an
    # injection reaches for to lift instance credentials (169.254.169.254). They
    # are DENIED, never merely escalated -- closing the "untainted SSRF only
    # escalates" hole in the bare allowlist rule.
    if _is_network(req):
        hc = net.classify_host(req.target)
        if hc.is_metadata:
            return Decision(Verdict.DENY, "internal_egress",
                            "egress to a cloud-metadata endpoint (SSRF credential theft)")
        if hc.is_internal:
            return Decision(Verdict.DENY, "internal_egress",
                            f"egress to an internal/link-local host '{hc.host}'")
        if not hc.parse_ok or hc.raw_had_userinfo:
            return Decision(Verdict.DENY, "internal_egress",
                            "egress to an unparseable or userinfo-spoofed target")
    return None


def _r_scheme_guard(req, ctx):
    # A NETWORK action may only speak http(s). Anything else -- file://, gopher://,
    # dict://, ftp://, ldap:// -- is protocol smuggling or a local-resource SSRF
    # (gopher:// to Redis, file:// to /etc/passwd). DENY regardless of allowlist:
    # the scheme alone is the tell. (BL-2)
    if _is_network(req):
        sc = net.scheme_of(req.target)
        if sc and sc not in net._OK_SCHEMES:
            return Decision(Verdict.DENY, "scheme_guard",
                            f"non-http(s) scheme '{sc}://' on a network action (protocol smuggling)")
    return None


def _r_egress_untrusted_sink(req, ctx):
    # The crown jewel: tainted data heading to a sink that itself came out of
    # untrusted content. This is the EchoLeak / zero-click exfiltration shape.
    if _is_network(req) and req.is_tainted and req.target_from_untrusted:
        return Decision(Verdict.DENY, "egress_untrusted_sink",
                        "tainted data sent to an untrusted-derived destination")
    return None


def _r_credential_egress(req, ctx):
    # Credential-shaped bytes heading to the network -- regardless of allowlist or
    # taint. Catches secret exfil to an *allowlisted* host, which every taint rule
    # misses (a config-loaded key is "trusted" data).
    if _is_network(req):
        hit = credentials.scan_request_payload(req)
        if hit is not None:
            # Named secrets (AWS keys, private-key blocks, JWTs, ...) are always
            # denied. Unnamed shapes -- a high-entropy opaque token or a long hex
            # run -- are held for review by default and only hard-denied under the
            # fail-closed flag, since a hex/opaque blob has legitimate uses.
            named = hit.kind not in ("high_entropy_token", "hex_blob")
            deny = named or ctx.deny_credential_egress
            v = Verdict.DENY if deny else Verdict.ESCALATE
            return Decision(v, "credential_egress",
                            f"credential-shaped argument ({hit.kind}: {hit.snippet}) on egress")
    return None


def _r_dns_exfil(req, ctx):
    # Data smuggled in a high-entropy / over-long subdomain label.
    if _is_network(req):
        reason = net.looks_like_dns_exfil(req.target, ctx.grant.egress_allowlist)
        if reason:
            return Decision(Verdict.ESCALATE, "dns_exfil", reason)
    return None


def _r_egress_redirect_param(req, ctx):
    # Open-redirect / SSRF-via-redirect: a redirect-class query param on the
    # (possibly allowlisted) target carries a follow-on URL pointing off-allowlist
    # or at an internal host. The allowlist check passes on the outer host while
    # the real destination rides in `?next=https://evil/...`. (raw HIGH finding)
    if not _is_network(req):
        return None
    embedded = net.redirect_param_target(req.target, _REDIRECT_PARAMS)
    if embedded is None:
        return None
    # The embedded URL gets the same scheme guard as a direct target: a
    # gopher://, file://, or dict:// hiding in `?next=` is protocol smuggling to a
    # local resource even when the outer host is allowlisted. (raw finding:
    # non-http(s) scheme inside a redirect parameter)
    esc = net.scheme_of(embedded)
    if esc and esc not in net._OK_SCHEMES:
        return Decision(Verdict.DENY, "egress_redirect_param",
                        f"redirect parameter carries a non-http(s) scheme '{esc}://' (protocol smuggling)")
    ehc = net.classify_host(embedded)
    if ehc.is_internal or not ehc.parse_ok:
        return Decision(Verdict.DENY, "egress_redirect_param",
                        f"redirect parameter points at an internal/unparseable host '{ehc.host}'")
    if not net.host_allowed(embedded, ctx.grant.egress_allowlist):
        return Decision(Verdict.DENY, "egress_redirect_param",
                        f"redirect parameter points off-allowlist to '{ehc.host}'")
    return None


def _r_egress_allowlist(req, ctx):
    if _is_network(req):
        if not net.host_allowed(req.target, ctx.grant.egress_allowlist):
            # off-allowlist egress: deny outright if tainted, else escalate
            v = Verdict.DENY if req.is_tainted else Verdict.ESCALATE
            return Decision(v, "egress_allowlist",
                            f"egress to non-allowlisted host '{_host_of(req.target)}'")
    return None


def _r_egress_tainted_payload(req, ctx):
    # Tainted (untrusted-derived) data riding OUT in a query/body, even to an
    # allowlisted host. A bare tainted GET is just a fetch and stays allowed; data
    # leaving is the exfil shape, so it is HELD by default, not allowed. (BL-5)
    # The opt-in escalate_tainted_egress flag (below) is the stricter superset that
    # holds even a bare tainted GET.
    if _is_network(req) and req.is_tainted and _payload_present(req):
        return Decision(Verdict.ESCALATE, "egress_tainted_payload",
                        "tainted (untrusted-derived) data riding out in a query/body")
    return None


def _r_tainted_egress(req, ctx):
    # Optional: hold ANY tainted egress, even to an allowlisted host.
    if (ctx.escalate_tainted_egress and _is_network(req) and req.is_tainted):
        return Decision(Verdict.ESCALATE, "tainted_egress",
                        "tainted (untrusted-derived) data leaving to an allowlisted host")
    return None


def _r_first_seen_host(req, ctx):
    # Optional tripwire: first contact with a never-seen host escalates.
    if ctx.baseline is not None and _is_network(req):
        if net.host_allowed(req.target, ctx.grant.egress_allowlist):
            return None  # allowlisted hosts are already vetted
        if ctx.baseline.is_new(req.target):
            return Decision(Verdict.ESCALATE, "first_seen_host",
                            f"first contact with host '{_host_of(req.target)}'")
    return None


# --- filesystem rules ------------------------------------------------------

def _r_write_sandbox(req, ctx):
    if req.capability is Capability.WRITE and not _under_any(req.target, ctx.grant.write_roots):
        return Decision(Verdict.DENY, "write_sandbox",
                        "write outside the task's write roots")
    return None


def _r_sensitive_write(req, ctx):
    # Writing INTO a secret-class path (clobbering config / an allowlist file /
    # credentials) is never in scope.
    if req.capability is Capability.WRITE and _matches_sensitive(req.target, ctx.sensitive_paths):
        return Decision(Verdict.DENY, "sensitive_write",
                        "write into a secret-class path")
    return None


def _r_sensitive_delete(req, ctx):
    # Deleting a declared secret-class path is destructive tampering -- unlinking an
    # egress-allowlist file, a credentials store, or a policy file is never in
    # scope, and sensitive_write only ever covered WRITE. (raw finding: DELETE of a
    # sensitive path slipped past the write-only guard)
    if req.capability is Capability.DELETE and _matches_sensitive(req.target, ctx.sensitive_paths):
        return Decision(Verdict.DENY, "sensitive_delete",
                        "delete of a secret-class path")
    return None


def _r_sensitive_name(req, ctx):
    # Pattern-based secret-by-name guard (BL-8): a file whose name marks it a
    # secret (.env, id_rsa, *.pem, credentials.json, ...) is sensitive even when
    # the operator did not list it. READ holds (DENY if the read is tainted-
    # derived); WRITE/DELETE onto a secret name is denied outright.
    if req.capability in (Capability.READ, Capability.WRITE, Capability.DELETE) \
            and _looks_like_secret_name(req.target):
        if req.capability is Capability.READ:
            v = Verdict.DENY if req.is_tainted else Verdict.ESCALATE
            return Decision(v, "sensitive_name",
                            "read of a path whose name marks it a secret")
        return Decision(Verdict.DENY, "sensitive_name",
                        f"{req.capability.value} onto a path whose name marks it a secret")
    return None


def _r_delete_guard(req, ctx):
    if req.capability is Capability.DELETE:
        if not ctx.grant.delete_allowed or not _under_any(req.target, ctx.grant.write_roots):
            return Decision(Verdict.DENY, "delete_guard",
                            "delete not permitted for this task / outside write roots")
    return None


def _r_write_special(req, ctx):
    # A WRITE whose target already exists as a symlink or a non-regular file
    # (FIFO, device, socket) is a clobber/redirect trap: following it can land the
    # write outside the sandbox or onto a device. DENY. (BL-10)
    if req.capability is Capability.WRITE:
        t = req.target
        try:
            if os.path.islink(t):
                return Decision(Verdict.DENY, "write_special",
                                "write target is a symlink (could redirect outside the sandbox)")
            if os.path.exists(t) and not os.path.isfile(t):
                return Decision(Verdict.DENY, "write_special",
                                "write target exists and is not a regular file (special file)")
        except (OSError, ValueError):
            return Decision(Verdict.DENY, "write_special", "write target could not be stat-ed safely")
    return None


def _r_read_special(req, ctx):
    # Reading a non-regular file (FIFO, char/block device, socket) is a trap: a
    # FIFO read blocks until someone writes, /dev/zero or /dev/urandom streams
    # unboundedly, a device read can have side effects. None of these is a normal
    # in-scope file read, so HOLD it. A symlink is handled at the backend by
    # O_NOFOLLOW (and by hardlink/scope rules); only a special *target file* trips
    # this. (raw finding: read of a special file / no S_ISREG guard)
    if req.capability is Capability.READ:
        t = req.target
        if not isinstance(t, str):
            return None
        try:
            st = os.lstat(t)
        except (OSError, ValueError):
            return None  # absent/unstattable -> the read fails naturally, nothing to hold
        if stat.S_ISLNK(st.st_mode):
            return None
        if not stat.S_ISREG(st.st_mode):
            return Decision(Verdict.ESCALATE, "read_special",
                            "read target is not a regular file (FIFO/device/socket)")
    return None


def _not_special_file(path: str) -> bool:
    """True unless `path` exists as a non-regular, non-symlink file. Used to keep
    the affirmative read-allow from blessing a FIFO/device as a clean in-scope read."""
    if not isinstance(path, str):
        return False
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return True  # absent/unstattable -> not a known special file
    return stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)


def _r_hardlink_alias(req, ctx):
    # A hardlink is a second directory entry for an inode that may live OUTSIDE the
    # sandbox. realpath cannot see it -- there is no symlink to follow -- so a
    # path-prefix scope check reads the in-scope name as in-scope while the bytes
    # belong to an out-of-scope file. A multiply-linked target inside a sandbox is
    # the tell: WRITE/DELETE could clobber a file outside the box (DENY), READ could
    # exfiltrate one (HOLD). O_NOFOLLOW does not help -- a hardlink is a regular
    # file, not a symlink. (raw finding: hardlink sandbox escape)
    if req.capability not in (Capability.WRITE, Capability.DELETE, Capability.READ):
        return None
    try:
        st = os.lstat(req.target)
    except (OSError, ValueError):
        return None
    if not stat.S_ISREG(st.st_mode) or st.st_nlink <= 1:
        return None
    if req.capability is Capability.READ:
        return Decision(Verdict.ESCALATE, "hardlink_alias",
                        "read target is a hardlink (may alias a file outside the sandbox)")
    return Decision(Verdict.DENY, "hardlink_alias",
                    f"{req.capability.value} target is a hardlink (may clobber a file outside the sandbox)")


def _r_malformed_target(req, ctx):
    # A filesystem target the OS path layer cannot even parse (embedded NUL,
    # non-string) must yield a deterministic DENY, never let a raw ValueError
    # escape evaluate(): a host that catches ActionBlocked but not ValueError would
    # crash, and one that swallows gate exceptions would fail OPEN. (raw finding:
    # NUL-byte path crash / fail-open)
    if req.capability in (Capability.READ, Capability.WRITE, Capability.DELETE, Capability.EXEC):
        t = req.target
        if not isinstance(t, str) or "\x00" in t:
            return Decision(Verdict.DENY, "malformed_target",
                            "filesystem/exec target is malformed (embedded NUL or non-string)")
    return None


def _r_write_tainted_external(req, ctx):
    # A WRITE of tainted (untrusted-derived) data into a write root that syncs
    # off-box is an exfil sink as real as a network POST. Held. Default-off: only
    # fires for roots the operator marked external_write_roots, so the local
    # laundering-defense round-trip (write-to-sandbox-then-read-back) is unaffected.
    # (BL-6)
    if (req.capability is Capability.WRITE and req.is_tainted
            and ctx.grant.external_write_roots
            and _under_any(req.target, ctx.grant.external_write_roots)):
        return Decision(Verdict.ESCALATE, "write_tainted_external",
                        "tainted data written into an off-box (external) write root")
    return None


def _r_untrusted_fs_target(req, ctx):
    # The path being written/deleted was itself lifted from untrusted content
    # (the injection chose the filename). Even inside the sandbox, that is the
    # model letting poisoned input pick a destructive target. Held. (BL-11)
    if req.capability in (Capability.WRITE, Capability.DELETE) and req.target_from_untrusted:
        return Decision(Verdict.ESCALATE, "untrusted_fs_target",
                        f"{req.capability.value} to a target chosen by untrusted content")
    return None


def _r_exec_guard(req, ctx):
    if req.capability is Capability.EXEC and not ctx.grant.exec_allowed:
        return Decision(Verdict.DENY, "exec_guard", "exec not permitted for this task")
    return None


def _r_sensitive_read(req, ctx):
    # Reading a declared secret-class path. A tainted (untrusted-derived) read of a
    # secret is the front half of read-secret-then-exfil; DENY it rather than merely
    # holding, since an injection that reached this point already controls the flow.
    # (BL-7)
    if req.capability is Capability.READ and _matches_sensitive(req.target, ctx.sensitive_paths):
        v = Verdict.DENY if req.is_tainted else Verdict.ESCALATE
        return Decision(v, "sensitive_read",
                        "read of a secret-class path the task did not declare")
    return None


def _r_read_scope(req, ctx):
    if req.capability is Capability.READ:
        if ctx.grant.read_roots:
            if not _under_any(req.target, ctx.grant.read_roots):
                return Decision(Verdict.ESCALATE, "read_scope",
                                "read outside the task's read roots")
        elif ctx.restrict_unscoped_reads:
            # No read scope declared + fail-closed posture => hold every read.
            return Decision(Verdict.ESCALATE, "read_scope",
                            "read with no read scope declared (fail-closed)")
    return None


# --- affirmative-allow rules -----------------------------------------------
# A denylist of bad actions is not enough for a *fail-closed* engine: with
# default=ESCALATE, an action no rule speaks to is held, which would hold every
# legitimate in-scope read/write/egress too. These rules explicitly ALLOW the
# clearly-in-scope cases so the ESCALATE default only catches the genuinely
# unanticipated. ALLOW is the least-severe verdict, so it never overrides a
# DENY/ESCALATE that any control rule raises -- it only beats the default.

def _r_allow_inscope_read(req, ctx):
    if (req.capability is Capability.READ and ctx.grant.read_roots
            and _under_any(req.target, ctx.grant.read_roots)
            and not _matches_sensitive(req.target, ctx.sensitive_paths)
            and not _looks_like_secret_name(req.target)
            and _not_special_file(req.target)):
        return Decision(Verdict.ALLOW, "allow_inscope_read", "read inside the task's read roots")
    return None


def _r_allow_inscope_write(req, ctx):
    if (req.capability is Capability.WRITE
            and _under_any(req.target, ctx.grant.write_roots)
            and not _matches_sensitive(req.target, ctx.sensitive_paths)
            and not _looks_like_secret_name(req.target)
            and not req.target_from_untrusted):
        return Decision(Verdict.ALLOW, "allow_inscope_write", "write inside the task's write roots")
    return None


def _r_allow_clean_egress(req, ctx):
    # Affirmative ALLOW only for the unambiguously-clean case: a real NETWORK
    # action, allowlisted host, http(s), not internal, and no tainted payload
    # riding out. Anything dirtier is left to the control rules / fail-closed
    # default rather than positively allowed. (ALLOW is least-severe, so even if
    # this fired alongside a control it could not override it -- this guard just
    # keeps it from emitting a misleading clean verdict.)
    hc = net.classify_host(req.target)
    if (req.capability is Capability.NETWORK
            and net.scheme_of(req.target) in net._OK_SCHEMES
            and net.host_allowed(req.target, ctx.grant.egress_allowlist)
            and not hc.is_internal
            # Only http(s) default ports get the affirmative clean ALLOW. An explicit
            # non-standard port (api.host:6379 to Redis, :8080, ...) is held by the
            # fail-closed default instead of positively blessed, since a port that is
            # not 80/443 on an "egress" target is the gopher/Redis SSRF shape. (raw
            # finding: non-standard egress port waved through as clean)
            and (hc.port is None or hc.port in (80, 443))
            and not (req.is_tainted and _payload_present(req))):
        return Decision(Verdict.ALLOW, "allow_clean_egress", "egress to an allowlisted host")
    return None


def default_rules() -> List[PolicyRule]:
    """The full deterministic rule set.

    Order matters only for tie-breaking the rule *name* on equal severity; the
    verdict is always the most severe that fires. Internal-egress and the crown-
    jewel sink rule are first so a DENY they raise names the decision. The
    affirmative-allow rules are last: ALLOW is least-severe, so they never mask a
    control, they only out-rank the (fail-closed) default for clearly-in-scope work.
    """
    return [
        # network / egress (DENY/ESCALATE controls first so they name the verdict)
        PolicyRule("internal_egress", _r_internal_egress),
        PolicyRule("scheme_guard", _r_scheme_guard),
        PolicyRule("egress_untrusted_sink", _r_egress_untrusted_sink),
        PolicyRule("credential_egress", _r_credential_egress),
        PolicyRule("egress_redirect_param", _r_egress_redirect_param),
        PolicyRule("egress_allowlist", _r_egress_allowlist),
        PolicyRule("dns_exfil", _r_dns_exfil),
        PolicyRule("egress_tainted_payload", _r_egress_tainted_payload),
        PolicyRule("tainted_egress", _r_tainted_egress),
        PolicyRule("first_seen_host", _r_first_seen_host),
        # filesystem
        PolicyRule("malformed_target", _r_malformed_target),
        PolicyRule("write_sandbox", _r_write_sandbox),
        PolicyRule("sensitive_write", _r_sensitive_write),
        PolicyRule("sensitive_delete", _r_sensitive_delete),
        PolicyRule("sensitive_name", _r_sensitive_name),
        PolicyRule("write_special", _r_write_special),
        PolicyRule("read_special", _r_read_special),
        PolicyRule("hardlink_alias", _r_hardlink_alias),
        PolicyRule("write_tainted_external", _r_write_tainted_external),
        PolicyRule("untrusted_fs_target", _r_untrusted_fs_target),
        PolicyRule("delete_guard", _r_delete_guard),
        PolicyRule("exec_guard", _r_exec_guard),
        PolicyRule("sensitive_read", _r_sensitive_read),
        PolicyRule("read_scope", _r_read_scope),
        # affirmative allow (least-severe; only out-rank the fail-closed default)
        PolicyRule("allow_inscope_read", _r_allow_inscope_read),
        PolicyRule("allow_inscope_write", _r_allow_inscope_write),
        PolicyRule("allow_clean_egress", _r_allow_clean_egress),
    ]


# --- engine ----------------------------------------------------------------

class PolicyEngine:
    def __init__(self, rules: Optional[List[PolicyRule]] = None,
                 default: Verdict = Verdict.ALLOW):
        self.rules = rules if rules is not None else default_rules()
        self.default = default

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(self, req: ActionRequest, ctx: PolicyContext) -> Decision:
        winner: Optional[Decision] = None
        for rule in self.rules:
            try:
                d = rule.check(req, ctx)
            except Exception:
                # A rule that raises on hostile input must FAIL CLOSED, not crash the
                # gate (a host catching ActionBlocked but not the raw exception would
                # error out; one swallowing gate exceptions would fail OPEN). Convert
                # any rule fault into a deterministic DENY. (raw finding: a raising
                # rule escapes the gate before malformed_target can DENY)
                d = Decision(Verdict.DENY, "rule_error",
                             f"rule '{rule.name}' faulted on this request (fail-closed deny)")
            if d is None:
                continue
            if winner is None or d.verdict > winner.verdict:
                winner = d
        if winner is not None:
            return winner
        return Decision(self.default, "default", "no rule fired")


# --- hardened posture ------------------------------------------------------

def hardened_engine(rules: Optional[List[PolicyRule]] = None) -> PolicyEngine:
    """A fail-closed engine: anything no rule anticipated ESCALATES (held)."""
    return PolicyEngine(rules=rules, default=Verdict.ESCALATE)


def harden(ctx: PolicyContext) -> PolicyContext:
    """Return a copy of `ctx` with every fail-closed posture flag turned on."""
    return PolicyContext(
        grant=ctx.grant,
        sensitive_paths=list(ctx.sensitive_paths),
        baseline=ctx.baseline,
        escalate_tainted_egress=True,
        restrict_unscoped_reads=True,
        deny_credential_egress=True,
    )
