# Design and implementation review

## Scope and evidence

The review began with *Programmer's Guide to GEM* by Balma and Fitler. It then processed all 75 other PDF books in the local GEM collection:

- 57 had usable embedded text and were searched for encryption, password, message, raster, resource, byte-order, and file-format material.
- 18 were image-only or nearly textless.
- Full OCR completed for the GEM DOS 1.0 specification, GEM Resource Construction Set, and February 1985 *Introduction to GEM Programming*.
- Targeted OCR covered the AES 4.0 supplement's contents and new-message sections, plus introductory/file sections of the Atari GEMDOS Reference Manual and GEMDOS Technical Specifications.
- Relevant sections were read in the official DRI AES and VDI guides, Atari's 1989 AES/VDI guides, Atari Compendium, COMPUTE's VDI/AES references, GSX documentation, Prochnow's handbook, and other text-bearing manuals.

This was a targeted design review, not a cover-to-cover read of every page. Some remaining image-only books were not fully OCRed; several have duplicate text-bearing editions in the collection. No claim is made that the review proves the absence of every possible GEM-related encryption idea.

## What the books establish

### AES is not encryption

GEM's Application Environment Services manages applications, events, windows, objects, resources, menus, and forms. The reviewed manuals do not define a native cryptographic cipher. A reference to the Falcon DSP supporting encryption is generic hardware capability, not a GEM encryption algorithm.

The FreeMiNT `Dsetkey` Blowfish interface found elsewhere in the online reference belongs to FreeMiNT 1.15.4 and later. It must not be attributed to classic PC GEM, ViewMAX, Atari AES, or GEMDOS generally.

### The 16-byte message inspiration is accurate

The official GEM 2.0 AES Reference and Atari AES guide describe FIFO message pipes and predefined messages with a common layout:

- Word 0: message type.
- Word 1: sender application identifier.
- Word 2: message length beyond the predefined 16 bytes.
- Words 3–7: message-specific data.

GEMSEAL's sealed-body length therefore follows a real GEM structural convention. Its suite field replaces the sender identifier, and its remaining fields are new. GEMSEAL records are not valid GEM AES messages.

The AES 4.0 supplement adds window, shell, shutdown, and predefined message behavior; it does not change this into a cryptographic protocol.

### VDI XOR is only a design motif

The VDI references define raster logic mode 6 as `D' = S XOR D`. Other writing modes use a mode number 3 for XOR. These are pixel operations, and their mode numbers are not interchangeable with an encryption suite identifier.

ChaCha20 also combines plaintext with a keystream using XOR, but the similarity ends there. Security comes from the cryptographic key, nonce, cipher, and authentication—not from GEM raster code or the Dungeon game's reversible text obfuscation.

### Portability requires an explicit new encoding

Balma and Fitler document that the Intel 8086 stores the low-order byte first while the Motorola 68000 stores the high-order byte first. Other manuals contain Intel-format and Motorola-format structures. GEMSEAL therefore fixes its own little-endian fields rather than reading or writing native C structures.

This does not make GEMSEAL an RSC or metafile format. It only borrows the idea of a self-describing, portable container.

### Historical size limits must not become file-size limits

The Atari Compendium describes original RSC 16-bit offsets and their 64 KiB limitation, followed by an extensible format with larger fields. GEMSEAL's 16-bit sealed-body length limits each record, not the whole file. Streaming records and a 32-bit record index avoid imposing the old RSC file-size ceiling.

## Implementation flaws found and fixed

### Partial plaintext was published before whole-file verification

The initial decryption loop wrote each authenticated DATA chunk directly to the final destination before validating the END record. A late failure normally removed the file, but a crash or kill could leave partial plaintext. Another process could also read the destination while validation was still underway.

**Resolution:** key generation, encryption, and decryption now write to temporary files. The destination appears only after complete success and file `fsync`, using an atomic hard-link publication step.

### Interruption and no-overwrite behavior needed stronger handling

The original `except Exception` cleanup did not cover `KeyboardInterrupt`. A pre-existing destination check alone would also leave a race between checking and publishing.

**Resolution:** temporary-file cleanup now runs in `finally`, including `KeyboardInterrupt` and other exceptions. Publication uses `os.link`, which fails if the destination already exists instead of replacing it. An early existence check avoids unnecessary work, while the link operation closes the publication race.

### Permission promises depended on the filesystem

The code requested `0600`, and this worked on the native Linux home filesystem. The research mount is `fuseblk` and reported `0660` even after an explicit `chmod(0600)` attempt.

**Resolution:** documentation now requires a permission-enforcing filesystem for sensitive keys and plaintext. No claim is made that the program can override mount-specific permission behavior.

## Remaining limitations and risks

- **Independent assurance:** the primitives are established, but the custom container and implementation have not been independently audited or cryptanalyzed.
- **Key management:** security depends on a random 32-byte key remaining secret and available. Manually derived or predictable keys enable offline guessing. HKDF does not strengthen passwords.
- **No password KDF:** password support would need a separately specified memory-hard function such as Argon2id and new format parameters.
- **Shared-key authentication:** anyone with the master key can decrypt or forge files. This is not a digital signature or proof of sender identity.
- **Metadata exposure:** magic bytes, approximate plaintext size, chunk size, record count, filenames chosen by the user, access times, and I/O patterns are not concealed.
- **Endpoint and memory attacks:** Python does not guarantee key or plaintext erasure. Malware and compromised machines are outside the security boundary.
- **Crash residue:** atomic publication prevents partial output at the final pathname, but `SIGKILL` or power loss can leave hidden temporary files containing plaintext or ciphertext. Their permissions remain filesystem-dependent.
- **Hard-link dependency:** atomic no-overwrite publication fails on filesystems that do not support hard links. There is deliberately no unsafe fallback.
- **Durability:** file `fsync` is used, but directory-entry durability and storage-media behavior can vary. Atomic publication is not a backup strategy.
- **Sequential format:** previous-tag chaining intentionally prevents arbitrary record reordering and does not provide independent random-access decryption.
- **Noncanonical short DATA records:** the decoder can accept authenticated short chunks before the final DATA record. Encoders must emit canonical full chunks except possibly at the end.
- **Denial of service:** an attacker can supply very large valid or invalid inputs and consume time and storage. The 16-bit body length bounds each individual record read, not total work.

## Cryptographic checks

No key- or nonce-reuse flaw was found in the normal version 1 construction:

- A 128-bit random salt feeds HKDF to produce per-file keys.
- Each record uses a unique 32-bit index with the file's nonce prefix.
- Across files, nonce safety does not depend solely on the 64-bit prefix; the random salt also changes the file key.
- File and record headers are authenticated as AAD.
- The previous tag and consecutive index authenticate ordering.
- The authenticated END record and trailing-data check authenticate completion.

These are design checks, not a security proof. Standard cryptographic primitives do not compensate for every possible implementation or deployment error.

## Offline key-search harness

`gemseal_crack.py` independently parses the public file header and first record, derives candidate file keys, and uses the first Poly1305 tag as an offline candidate oracle. It supports binary wordlists, numeric PIN searches, and deliberately reduced raw-key prefixes. Candidate transforms are SHA-256, zero-padding, or exact raw 32-byte keys. An optional output path invokes full-container verification and atomic decryption after recovery.

This demonstrates the practical weakness of predictable manually derived keys and measures local candidate throughput. It is not a generic attack against ChaCha20-Poly1305 and cannot make an exhaustive random 256-bit key search feasible. A successful first-record match is followed by full verification when `--output` is used; without that option, later records are not checked.

The harness is intended for the user's own containers and controlled security experiments. Candidate displays and recovered plaintext should be handled as sensitive output.

## Tripwire implementation review

`gemseal_tripwire.py` adds an encrypted-canary initializer and Linux inotify watcher. Keys and audit logs must be outside the vault. Events are appended as JSON and `fsync`ed after each record. The watcher handles nested directories, duplicate-event suppression, queue-overflow reporting, recursive watches, and clean signal shutdown.

The first implementation created a key's parent directory before checking whether that key was inside the vault. A regression test caught the resulting artifact after rejection; validation now occurs before directory creation. A real inotify integration test confirms that opening the encrypted canary publishes a JSON event.

This is a detection aid, not an access-control mechanism. Inotify cannot identify the accessing process or reliably reveal intent, block reads, guarantee directory-listing detection, observe every network/virtual-machine access path, or resist a privileged attacker. Local JSON logs are not tamper-proof. Production deployments need separate privileges, protected or remote logging, and OS auditing when process attribution is required. Obfuscation does not change these limits.

## Verification status

The standard-library suite contains 19 tests covering empty, multi-record, and exact-chunk files; wrong keys; ciphertext modification; truncation; record reordering; trailing data; existing destinations; temporary-file cleanup; `KeyboardInterrupt`; atomic publication; deterministic vectors; PIN and wordlist recovery; empty END-record challenges; reduced raw-key searches; skipped candidates; candidate limits; vault initialization; key/log placement; and live inotify access detection.

The implementation has also been exercised for randomized containers and operation on both available filesystems. Package validation builds source and wheel distributions, installs the wheel into a fresh virtual environment, and exercises all three installed commands.

The installed Bandit environment could not scan the module under Python 3.14 because Bandit raised `AttributeError: 'Constant' object has no attribute 's'` on a bytes constant. No successful Bandit result is claimed; manual review and executable checks are not represented as a replacement for an independent security audit.
