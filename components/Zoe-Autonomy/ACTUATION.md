# Owner-granted actuation

Zoe-Autonomy supports real host, network, and hardware actuation under an explicit local-owner grant. The grant is bound to the current hostname and the current OS account's permissions. It does not elevate privileges or transfer to another computer.

Zoe authors goals and selects external candidates through the same value-and-guard loop used for internal autonomy. The base autonomy experiment remains internal and records `external_actions=0`. External execution occurs only when an enabled external candidate is selected.

## Enable the owner grant

```bash
zoe-autonomy actuate enable --all --owner-approved
zoe-autonomy actuate status
```

Scopes can also be enabled independently with `--host`, `--network`, or `--hardware`.

The default grant and audit directory is `~/.zoe/actuation`. Set `ZOE_ACTUATION_ROOT` or use `actuate --root PATH` to select another directory. Enabling writes `owner-grant.json` with mode 0600 and does not clear an existing emergency stop.

## Host actuation

Host execution accepts a JSON argument array. No shell is used.

```bash
zoe-autonomy actuate host \
  --argv '["/usr/bin/printf", "zoe-host-ok"]' \
  --cwd /tmp \
  --output host-result.json
```

The host adapter applies a 1–120 second timeout, terminates the entire child process group on timeout, captures stdout and stderr with bounded evidence, and records the exit code. It runs with the current OS user's permissions.

## Network actuation

```bash
zoe-autonomy actuate network \
  --url http://127.0.0.1:8080/status \
  --method GET \
  --output network-result.json
```

Network operations support GET, HEAD, POST, PUT, PATCH, and DELETE over HTTP(S). The adapter enforces timeouts, bounded request and response bodies, default TLS certificate verification, and explicit URL validation. URLs containing embedded credentials are rejected.

## Hardware actuation

```bash
zoe-autonomy actuate hardware \
  --device /dev/ttyUSB0 \
  --payload-hex 5a4f45 \
  --read-bytes 16 \
  --output hardware-result.json
```

Hardware operations write hexadecimal bytes to an explicit `/dev/` character device. The adapter rejects regular files and symbolic-link targets, bounds payload and read sizes, and applies nonblocking timeouts. It does not infer a protocol, configure a driver, or access a physical device during tests.

## Emergency stop

```bash
zoe-autonomy actuate stop --reason "Stop all external actuation"
```

While the stop file exists, every host, network, and hardware check fails before execution, including candidates already selected by Zoe's policy. Resume requires another explicit owner approval:

```bash
zoe-autonomy actuate resume --owner-approved
```

The emergency stop is an application-level control within the current OS account. It is not a kernel security boundary or protection against another process with the same permissions.

## Audit evidence

Grant changes, stops, denials, failures, and completed operations append to `actuation-audit.jsonl`. Events contain sequence numbers, UTC timestamps, hostname, previous-event hashes, and canonical SHA-256 event hashes. Evidence is tamper-evident, not authenticated.

Direct operations can also write a new no-overwrite JSON result with `--output`. Secret-bearing URLs, headers, environment variables, and command arguments should not be placed in an actuation request unless their appearance in evidence is acceptable.

## Verification

The test suite executes:

- a harmless local Python process;
- an HTTP request to an explicitly created loopback server;
- a byte write to a virtual PTY, not physical hardware;
- Zoe's own selection of a host candidate through value ranking;
- emergency-stop denial after a successful action;
- grant hostname binding and audit-chain verification.

Run:

```bash
PYTHONPATH=src:/path/to/zoe/guiai-lab ZOE_ROOT=/path/to/zoe \
  python -m unittest discover -s tests -v
```

Tests use temporary actuation roots and do not create or modify the real owner grant.
