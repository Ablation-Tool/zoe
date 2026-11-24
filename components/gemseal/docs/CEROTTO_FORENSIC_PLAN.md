# Native Cerotto Vault Tripwire for Forensic Analysis of Agentic LLM Attacks

## Technical and Operational Plan

**Prepared for:** A forensic LLM analyst developing Cerotto, a tool focused on the digital forensics of LLM and AI-agent attacks  
**Document status:** Native Cerotto implementation and operating plan based on a working GEMSEAL 0.3.0 reference prototype  
**Integration model:** Built into Cerotto core; no plugin, adapter process, or required JSONL handoff  
**Security posture:** Detection and evidence support, not a standalone prevention boundary

## 1. Executive summary

Agentic LLM systems can inherit broad filesystem access through the user, tools, containers, or host accounts under which they run. Their file activity may therefore appear authorized even when the agent is indexing, copying, modifying, or staging information outside the user's intended scope. Ordinary application logs often show that an agent was active without showing every file it touched.

Cerotto will implement the vault tripwire directly. Selected data is placed inside encrypted containers, and Cerotto monitors those containers as high-value forensic objects. Encryption limits what an unauthorized reader can learn. Cerotto's native sensor records interactions with the encrypted object and places those events directly into its own evidence model and agent-centric incident timeline.

The intended result is not a claim that “the AI cannot touch the file.” It is a more defensible outcome:

1. An unauthorized reader obtains ciphertext rather than plaintext when the key is unavailable.
2. Supported access attempts generate timestamped forensic telemetry inside Cerotto.
3. Cerotto correlates that telemetry with agent sessions, tool calls, processes, network connections, and user approvals.
4. Analysts can distinguish ciphertext contact, approved plaintext release, monitoring gaps, and possible key compromise.

The GEMSEAL reference work also demonstrates four useful container properties:

- Preventing casual inspection of file contents.
- Making resource files appear as high-entropy binary data.
- Providing a proprietary container around application data.
- Supporting research into layered formats and key handling.

These properties are optional inputs to the design. Cerotto need not import the GEMSEAL Python package or depend on its command-line tools. It may implement compatible functionality internally or monitor another encrypted-vault format. Obfuscation is not access control, and a proprietary format is not a security guarantee.

## 2. Reference prototype versus native Cerotto deliverable

### Available in the GEMSEAL reference prototype

- GEMSEAL version 1 authenticated-encryption containers.
- Raw 32-byte key generation, encryption, and full-container verified decryption.
- ChaCha20-Poly1305 with HKDF-SHA256 per-file key derivation.
- Detection of wrong keys, modification, reordering, truncation, and trailing data.
- Atomic, no-overwrite publication after complete verification.
- An offline PIN, wordlist, and reduced-key test harness.
- Encrypted-canary vault initialization with keys stored outside the vault.
- Linux inotify monitoring for open, read, modification, metadata, creation, deletion, and rename events.
- JSONL event output outside the watched vault, immediate stderr alerts, duplicate suppression, and event `fsync`.
- Nineteen automated tests, including a real inotify access-event test.

The prototype's JSONL is reference output for comparison and testing only. It is not the intended Cerotto integration mechanism.

### To be built directly into Cerotto

- A native vault sensor supporting inotify initially and OS-audit sources where process attribution is required.
- Cerotto-owned vault configuration, watcher sessions, event sequences, and health records.
- A versioned Cerotto evidence record written directly to Cerotto's native evidence store.
- Immutable preservation of raw source details alongside structured evidence fields.
- Host, boot, vault, event, agent-session, tool-call, process, network, and consent correlation.
- Protected evidence replication and native watcher-health monitoring.
- An explicit per-file release broker with approval and plaintext-lifetime records.
- Native case dashboards, response actions, exports, and acceptance tests.

All of these components belong in Cerotto's repository and runtime. No GEMSEAL plugin, external normalization service, or separate ingestion adapter is part of the design. Cerotto's actual internal evidence schema and service boundaries will be used directly; unavailable fields must remain `null` or `unknown`, never inferred.

## 3. Threat model and objectives

### Scenario

An LLM agent is legitimately installed on a workstation or server and can navigate selected directories. It may have shell, file, browser, MCP, or other tool access. The user sees high-level activity but not necessarily every file access. Sensitive material may be copied during background indexing, prompt construction, embedding generation, tool execution, or attempted exfiltration.

### Primary objectives

- Reduce plaintext exposure to unauthorized file readers.
- Create reliable native Cerotto telemetry for interactions with selected sensitive containers.
- Preserve raw source details and structured evidence for later reconstruction.
- Associate vault activity with agent identity and tool-call context where independent evidence permits.
- Detect destructive actions, monitoring failures, and unauthorized plaintext release.
- Provide an operational response path that does not depend on interpreting model intent.

### Non-goals

- Preventing every read, copy, deletion, or rename.
- Proving that a particular event was initiated by an LLM rather than another process.
- Defending against root, kernel, hypervisor, firmware, or physical compromise.
- Protecting plaintext after an authorized release.
- Guaranteeing detection of directory enumeration, alternate mount paths, or all VM and network-filesystem activity.
- Treating filename obfuscation as a reliable hiding mechanism.
- Replacing established encryption, backup, endpoint-security, or incident-response systems.

## 4. Native Cerotto architecture

```text
                         Separate key authority
                    +--------------------------+
                    | Random key               |
                    | Separate account/keyring |
                    | No AI access             |
                    +-------------+------------+
                                  |
                                  v
+---------------+       +---------+-----------+       +----------------------+
| Encrypted     |       | Cerotto native      |       | Approved plaintext   |
| vault and     |------>| release broker      |------>| release area         |
| canaries      |       | and consent record  |       | Short-lived, scoped  |
+-------+-------+       +---------------------+       +----------------------+
        |
        | File access attempts
        v
+---------------------------------------------------------------+
| Cerotto native vault sensor                                   |
| - inotify events                                              |
| - optional OS-audit attribution                               |
| - watcher session, sequence, and health                       |
+----------------------------+----------------------------------+
                             |
                             v
+---------------------------------------------------------------+
| Cerotto native evidence store                                 |
| - immutable source details                                    |
| - structured evidence fields                                  |
| - protected replication and retention policy                  |
+----------------------------+----------------------------------+
                             |
                             v
+---------------------------------------------------------------+
| Cerotto correlation and case engine                           |
| - agent sessions and tool calls                               |
| - processes, network, consent, and vault baselines            |
| - timelines, confidence labels, alerts, and response          |
+---------------------------------------------------------------+
```

### Ownership and trust boundaries

1. **Code ownership:** the sensor, evidence schema, correlation logic, release broker, interface, and tests are Cerotto code.
2. **Ciphertext boundary:** the vault may be visible to the agent; plaintext keys must not be.
3. **Monitoring boundary:** Cerotto's sensor should run under an identity the agent cannot terminate.
4. **Evidence boundary:** Cerotto's evidence store and replicas must be protected from agent modification.
5. **Release boundary:** only an explicit trusted Cerotto action should create plaintext in a separate release area.
6. **Attribution boundary:** inotify events alone do not identify process or intent; Cerotto must preserve that uncertainty.

## 5. Operational workflow

### 5.1 Preparation

- Select a small, explicit set of sensitive containers rather than encrypting the whole host indiscriminately.
- Use a native, permission-enforcing filesystem for keys, vaults, and plaintext releases.
- Generate a random key through Cerotto's native key-management flow; do not use a manually derived password key.
- Store the key in a separate account, keyring, or hardware-backed store unavailable to the agent.
- Create an encrypted canary containing no sensitive information.
- Start Cerotto's native sensor before starting the agent and record startup, host, vault, and clock-synchronization state.
- For production confidentiality, use an audited encryption implementation such as `age`; Cerotto's monitoring and correlation model is independent of the container format.

### 5.2 Baseline capture

- Record the vault manifest, container hashes, key custodian, approved agent accounts, expected backup/indexing schedules, and approved release directories.
- Record Cerotto sensor identity, start time, software version, configuration, and watched paths.
- Preserve the initial manifest separately from the vault.
- Establish normal activity so backups and administrative reads are not automatically treated as hostile.

### 5.3 Native monitoring

- Write source-event details directly into Cerotto's evidence store with a Cerotto event ID and watcher sequence.
- Retain duplicate events when forensic completeness matters; use deduplication only for alert presentation.
- Monitor sensor termination, evidence-write failure, queue overflow, clock changes, and unexpected configuration changes.
- Replicate evidence to protected storage as part of Cerotto's normal evidence pipeline.
- Add OS auditing for PID, UID, executable, syscall, and parent-process context where process attribution is required.

### 5.4 Plaintext release

The reference prototype uses a manual release command. Cerotto's native release broker will additionally record:

- Requesting user, agent session, and tool call if known.
- Exact container and content hash.
- Reason and explicit approval decision.
- Release destination and permitted agent identity.
- Release and expiration times.
- Cleanup result and any residual temporary-file condition.

A release changes the evidence interpretation: later plaintext access is expected only within the approved scope. Encryption cannot protect information after an authorized reader or destination is compromised.

### 5.5 Native correlation and case handling

Cerotto will join vault events to its existing independent evidence using time, host, canonical path, account, process tree, agent session, tool-call identifier, and network destination when available.

Analysts should be able to answer:

- Was the object touched only as ciphertext, or was plaintext released?
- Was there a matching user approval?
- Which agent session and tool invocation overlapped the event?
- Did a process associated with the agent open the object, or was it an unrelated service?
- Was there subsequent network activity consistent with staging or exfiltration?
- Was the object modified, renamed, copied, or deleted?
- Were there monitoring gaps that limit the conclusion?

## 6. Native forensic event and evidence model

### Reference prototype output

The current GEMSEAL prototype supplies this reference subset:

```json
{
  "timestamp": "UTC timestamp from the prototype watcher",
  "events": ["open"],
  "mask": "0x00000020",
  "path": "/safe/vault/project_notes.gemseal"
}
```

This format is useful for prototype comparisons but is not a required Cerotto input format.

### Cerotto native evidence record

The following illustrates fields to implement using Cerotto's own schema and storage conventions:

```json
{
  "schema_version": "1.0",
  "event_id": "Cerotto-generated event identifier",
  "source": "cerotto.vault",
  "event_type": "file.open",
  "observed_utc": "sensor observation timestamp",
  "recorded_utc": "native evidence-store commit timestamp",
  "monotonic_ns": null,
  "host_id": "protected host identifier",
  "boot_id": null,
  "watcher_session": "Cerotto sensor startup identifier",
  "sequence": 1,
  "vault_id": "case-specific vault identifier",
  "path": "/safe/vault/project_notes.gemseal",
  "source_detail": {
    "api": "inotify",
    "mask": "0x00000020"
  },
  "process": null,
  "agent_session": null,
  "tool_call": null,
  "consent": "unknown",
  "plaintext_state": "ciphertext",
  "attribution": "unresolved"
}
```

Native evidence rules:

- Preserve original source details with the structured record.
- Never invent a PID, agent session, user approval, or plaintext state.
- Distinguish sensor observation time, evidence-commit time, and case-analysis time.
- Preserve unknown and unavailable values explicitly.
- Version evidence and correlation rules for reproducibility.
- Treat paths as sensitive evidence and restrict their disclosure.

### Evidence integrity and chain of custody

- Use Cerotto's native protected evidence pipeline and replicate raw records to remote or otherwise tamper-resistant storage.
- Use append-only storage, signed batches, hash chaining, or platform audit facilities where appropriate; these are proposed Cerotto controls, not current reference-prototype features.
- Record evidence custodian, observation time, commit time, export time, evidence hashes, storage location, and every analyst access.
- Use synchronized clocks and retain clock-adjustment events.
- Do not describe the reference JSONL or an agent-writable Cerotto database as tamper-proof.

## 7. Detection and analysis use cases

These are investigative hypotheses, not automatic proof of malicious intent.

### Unexpected ciphertext contact

An encrypted canary is opened during an agent session without a corresponding approved purpose. Cerotto should raise a reviewable event and look for matching process and tool-call evidence.

### Canary contact followed by network activity

A canary open, subsequent read, and an outbound connection associated with the same agent or process may indicate reconnaissance or staging. The sequence warrants higher priority but still requires corroboration.

### Unauthorized plaintext release

A release event without consent, or access to a released file outside the approved identity or time window, suggests key misuse, policy violation, or control compromise.

### Destructive vault activity

Modification, deletion, rename, or replacement of encrypted resources may indicate destructive behavior, anti-forensics, or an attempted rollback. Preserve pre-incident container hashes and copies.

### Monitoring degradation

Sensor termination, queue overflow, disabled auditing, evidence-store truncation, and clock changes are forensic signals in their own right. They should produce native Cerotto health alerts rather than silently reducing coverage.

### Benign alternatives

Backups, antivirus, indexing, administrative inspection, synchronization, and user-approved jobs can produce identical path events. Baseline schedules and process evidence are necessary to avoid false attribution.

## 8. Response playbook

When Cerotto raises a high-priority vault alert:

1. Preserve native vault, audit, agent, tool-call, process, and network evidence before taking destructive action.
2. Record the case time, analyst, host, vault, sensor state, and initial evidence hashes.
3. Isolate the agent environment or suspend its tools according to policy; disable networking if exfiltration is a concern.
4. Avoid decrypting the container merely to inspect it during the initial response.
5. Determine whether the event involved ciphertext only or an approved plaintext release.
6. Check for key-file, keyring, broker, and release-directory access.
7. If key exposure is plausible, rotate the key and re-encrypt affected material after preserving required evidence.
8. Document monitoring gaps and alternate explanations in the case record.
9. Restore the environment only after the access path and policy failure are understood.

## 9. Validation and acceptance plan

### Reference validation

The GEMSEAL repository has 19 passing tests covering encryption, corruption rejection, atomic publication, offline key recovery, vault initialization, key/log placement, and live inotify detection. Source and wheel builds and all three installed commands have been exercised. These tests validate the reference behavior, not Cerotto itself.

### Native Cerotto tests

- Generate a vault event through Cerotto's own sensor and verify direct persistence in its evidence store.
- Verify that no plugin, adapter service, or JSONL import is required.
- Verify that unknown process and consent fields remain unresolved.
- Correlate a synthetic agent session only when independent correlation evidence exists.
- Preserve observation, evidence-commit, and case-analysis timestamps separately.
- Reproduce a structured event and timeline from retained native evidence.
- Verify that Cerotto can run its vault workflow without the GEMSEAL Python package installed.

### Controlled acceptance scenarios

- Perform 20 local open attempts on a supported filesystem and verify all expected events, documenting duplicates.
- Confirm that reading an unrelated file creates no vault event.
- Test create, modify, rename, delete, and queue-overflow behavior.
- Stop the native sensor and verify that supervision reports the monitoring gap.
- Restart with clock drift and verify timeline uncertainty is retained.
- Test containers and host bind mounts; test VMs with an in-guest Cerotto sensor.
- Exercise network and FUSE filesystems and record unsupported behavior rather than assuming coverage.
- Attempt evidence modification from the agent identity and verify that protected storage denies or detects it.
- Release one file with approval and verify that its plaintext event is distinguished from ciphertext-only access.
- Attempt a release without approval and verify denial and evidence capture.

### Operational metrics

- Native sensor and evidence-replication uptime.
- Event commit and replication latency and queue-loss count.
- Percentage of events with independent process attribution.
- False-positive rate after baseline tuning.
- Number of unapproved plaintext releases.
- Time from event to Cerotto correlation and analyst triage.
- Evidence exports that reproduce the same hashes and native timelines.

## 10. Delivery phases

### Phase 1: Native Cerotto vault sensor

- Implement inotify monitoring inside Cerotto.
- Add the Cerotto evidence record, watcher session, sequence, boot identifier, and health events.
- Add supervised startup, configuration capture, and direct native evidence persistence.
- Define behavior for restarts, moved directories, and event backlog.

**Exit condition:** Cerotto generates and stores vault evidence without the GEMSEAL package, a plugin, or an external handoff.

### Phase 2: Native evidence and case integration

- Map vault records directly into Cerotto's actual evidence schema and case model.
- Implement immutable source details, schema versions, and correlation-confidence labels.
- Build native vault timelines, case views, and evidence exports.

**Exit condition:** analysts can reproduce vault timelines from native Cerotto evidence without unsupported attribution.

### Phase 3: Attribution and evidence protection

- Add optional OS-audit sources and protected evidence replication.
- Add sensor-health alerts and baseline management.
- Separate agent, key, sensor, and evidence-store identities.

**Exit condition:** supported events include corroborating process evidence, and agent-level evidence tampering is denied or detected.

### Phase 4: Native release broker and pilot

- Implement explicit approval, scoped plaintext release, expiration, and cleanup records inside Cerotto.
- Pilot with synthetic canaries and nonsensitive data before protecting real material.
- Tune benign-activity baselines and response procedures.

**Exit condition:** Cerotto demonstrates ciphertext-only monitoring, approved release, incident response, and defensible evidence export end to end.

## 11. Principal risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Key is available to the agent | Plaintext compromise | Separate key identity, keyring, hardware backing, no unattended agent access |
| Sensor or evidence store is agent-writable | Evidence suppression | Separate identities, protected replication, health alerts |
| Inotify lacks process identity | Misattribution | OS audit correlation and explicit unresolved state |
| Plaintext is released too broadly | Loss of confidentiality | Per-file consent, short lifetime, separate release area |
| Alternate paths or unsupported filesystems | Monitoring gaps | Coverage testing, in-guest Cerotto sensors, documented unsupported paths |
| Obfuscation is treated as security | False assurance | Random keys, access control, monitored release, clear threat model |
| Alert volume and benign indexing | Analyst fatigue | Baselines, deduplicated presentation, raw-source retention |
| GEMSEAL implementation is experimental | Unknown implementation risk | Independent review; use `age` for production confidentiality |
| Paths reveal sensitive metadata | Secondary information exposure | Restrict evidence access and apply retention controls |

## 12. Recommendation

Build the capability directly into Cerotto as a native forensic feature. Do not create a GEMSEAL plugin or require a separate adapter.

The useful combination is **encrypted sensitive objects, Cerotto-native access monitoring, protected evidence collection, explicit plaintext release, and native Cerotto correlation**. The GEMSEAL repository provides reference behavior and test cases; Cerotto will own the production sensor, evidence model, correlation, interface, response, and tests.

Proceed with a limited forensic pilot, not a claim of complete AI containment. The feature should be presented as an additional detection and evidence layer whose value can be tested objectively. It should not be presented as hiding files reliably from an LLM, proving malicious intent from an open event, or preventing a privileged agent from reaching data after keys or plaintext become available.
