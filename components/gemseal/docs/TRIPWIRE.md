# GEMSEAL vault tripwire

The tripwire combines encrypted files with access-event monitoring. It is intended to make suspicious interaction with a watched vault more visible in logs. It does not make an AI unable to touch files, and encryption itself does not generate audit events.

## Security model

The useful boundary is:

```text
Encrypted vault                       Private key storage
+ encrypted files                     + random 32-byte key
+ no key                              + inaccessible to the AI
        |                                      |
        | AI can read only ciphertext          |
        v                                      v
Linux inotify watcher               Separate account/keyring
        |
        +-- JSONL audit log outside the vault
        +-- immediate alert on stderr
```

For meaningful confidentiality, the AI must not have the key, an unlocked keyring, or access to decrypted output. For meaningful audit integrity, it must not be able to modify the log or stop the watcher.

## Quick start

Choose new paths. Initialization refuses to reuse an existing vault or key path.

```sh
gemseal-tripwire init /safe/vault /safe/private/vault.key
```

This creates:

- `/safe/vault/project_notes.gemseal`, an encrypted canary containing no secrets.
- `/safe/private/vault.key`, a random 32-byte key outside the watched directory.

Start the watcher before starting the AI or agent:

```sh
gemseal-tripwire watch /safe/vault --log /safe/audit/vault.jsonl
```

In another terminal, read a few ciphertext bytes:

```sh
head -c 16 /safe/vault/project_notes.gemseal
```

On a supported local filesystem, the watcher should print an alert resembling:

```text
TRIPWIRE open '/safe/vault/project_notes.gemseal'
```

The JSON log contains records such as:

```json
{"events":["open"],"mask":"0x00000020","path":"/safe/vault/project_notes.gemseal","timestamp":"2026-01-01T12:00:00+00:00"}
```

The timestamp above is illustrative. Every real record is generated from the current UTC time.

## Add and release real files

Encrypt a file into the watched vault:

```sh
gemseal encrypt /safe/private/vault.key secret.pdf /safe/vault/secret.pdf.gemseal
```

Decrypt only to a separate, explicitly approved release directory:

```sh
gemseal decrypt /safe/private/vault.key /safe/vault/secret.pdf.gemseal /safe/release/secret.pdf
```

The release operation changes the security boundary: anyone with access to `/safe/release` may read the plaintext. Do not leave released files there after the approved task. Use a native permission-enforcing filesystem and minimize plaintext lifetime.

## Watcher options

```sh
# Exit after the first published event; intended for testing
gemseal-tripwire watch /safe/vault --log /safe/audit/test.jsonl --once

# Disable per-path/event duplicate suppression
gemseal-tripwire watch /safe/vault --log /safe/audit/verbose.jsonl --dedup 0

# Keep duplicate events within a custom five-second interval
gemseal-tripwire watch /safe/vault --log /safe/audit/vault.jsonl --dedup 5
```

The default deduplication interval is one second. Different event types for the same path are logged separately. Events include:

- `open` and `read`: access attempts and actual read activity.
- `modify` and `close-write`: content changes and writable-close activity.
- `metadata`: attribute changes.
- `create`, `delete`, `delete-self`, and `move-self`.
- `moved-from` and `moved-to`: rename activity.
- `queue-overflow`: the kernel dropped events, creating a monitoring gap.

Each JSON record contains the UTC timestamp, event list, hexadecimal inotify mask, and path. File contents and keys are not logged. Every record is flushed and `fsync`ed.

## What an event proves—and does not prove

An event means the kernel reported a particular operation on a watched path. It does not establish:

- Which process, user, model, or agent performed it.
- Whether access was intentional, accidental, malicious, or part of ordinary backup/indexing.
- Whether an open attempt succeeded in reading useful plaintext.
- Whether the same file was accessed earlier through an unwatched path.
- Whether the log itself remains intact.

Correlate timestamps with AI-agent logs, shell auditing, and system auditing before attributing an event to an LLM.

## Important limitations

### Detection, not prevention

Inotify reports activity; it does not deny it. A reader may obtain ciphertext before an alert is handled. The random key remains necessary for confidentiality.

### No process attribution

Inotify supplies no PID, UID, executable name, model name, or command line. For process attribution, use operating-system auditing. On Linux, an administrator can evaluate rules such as:

```sh
auditctl -w /safe/vault -p rwa -k gemseal_tripwire
ausearch -k gemseal_tripwire -i
```

Those commands require appropriate privileges and an audit policy review. They are examples, not actions performed by this package.

### Same-user and root attackers

An AI running with your permissions may be able to stop the watcher, delete the vault, alter logs, or access your keys. Root or kernel control defeats this design. Use a separate account, protected keyring, restricted VM, and remote or otherwise tamper-resistant logging for stronger boundaries.

### Coverage gaps

- Events that occurred before the watcher started are absent.
- Merely enumerating names may not produce a file-open event for every entry.
- Hard links, bind mounts, snapshots, backup readers, raw-disk access, and alternate namespaces may bypass path-based monitoring.
- Network filesystems and FUSE drivers vary in inotify support and semantics.
- A host watcher does not see file-level accesses inside an isolated VM unless an agent watches from within that VM.
- Queue overflows are logged when possible but indicate lost events.
- Moving directories or replacing watched trees can complicate path attribution.
- Obfuscating a filename does not change any of these limitations.

### Log confidentiality and integrity

Paths themselves can be sensitive. Protect audit logs accordingly. The local JSONL file is not append-only or cryptographically signed. A same-privilege attacker can edit it. Forward events to a protected log service or use a separately privileged logging account for production use.

## Recommended deployment for AI workloads

1. Run the model in a disposable VM or restricted sandbox with no general home-directory mount.
2. Keep the vault key in a separate account, hardware-backed store, or keyring unavailable to the model.
3. Run the watcher under a separate logging identity and forward records off-machine when practical.
4. Mount only a curated, read-only, nonsensitive dataset for routine model use.
5. Release sensitive plaintext through an explicit user-approved broker, one file at a time.
6. Disable or tightly control network access from the model environment.
7. Destroy the disposable environment and released plaintext after the task.

For production confidentiality, prefer an audited encryption tool such as `age` over experimental GEMSEAL. The tripwire concept can monitor any encrypted-vault directory regardless of the encryption tool.

## Forensic integration

For the proposed Cerotto evidence model, agent-session correlation, chain-of-custody controls, response playbook, and delivery phases, see [the formal forensic integration plan](CEROTTO_FORENSIC_PLAN.md).

## Tests

Run all encryption, cracker, and tripwire tests:

```sh
python3 -m unittest discover -s tests -v
```

The tripwire tests cover encrypted-canary creation, external-key enforcement, invalid canary names, log-location enforcement, and a real inotify open event with JSON output and clean single-event shutdown.
