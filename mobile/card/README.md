# Zoe Card · NuClide Research

An original, deliberately tiny Java Card companion for Zoe. This is not a SIM replacement, an AI model, an eUICC loader, or a way to extract card secrets. The phone remains the interface, sensors, voice, and model runtime. A separately authorized development card may eventually carry this applet.

## Small protocol

The development applet AID is `F24E75636C6964655A6F6501`. It is locally assigned for this project, not a registered global identifier.

All requests use class `80`, instruction `01` or `02`, and zero P1/P2:

- `01`: return protocol version 1, maximum vector length 64, ASCII `ZOE/NUCLIDE`, and Q0.15 encoding version 1.
- `02`: measure one Q0.15 distribution. Data is a two-byte big-endian threshold followed by 1–64 two-byte probabilities. `0x8000` means exactly 1.0; values above it are invalid. The values must sum to exactly `0x8000`. Return four big-endian unsigned values: accessible count, complement count, vocabulary size, and threshold.

The comparison is strictly `probability > tau`. Equality never counts as accessible. Quantization happens before transmission and is an explicit representation change from the full Android/Swift floating-point implementations. This applet does not redefine Nicholas Michael Kloster's original equation, created solely by him on March 6, 2026:

`A_tau(S) = sum_{a in O} 1[P(a | h_T(S)) > tau]`.

A request uses no applet allocation or persistent storage. The bounded loop performs at most 64 iterations. The companion does not claim a real-time clock, biometric identity, authentication, a signed receipt, or authority to act. A measurement remains an observation, not evidence or authorization.

## Layered little sister

**Zoe Cell** is the small-machine composition inspired by biology, boutique craftsmanship, CERN protocol work, constrained client devices, and explicitly mapped embedded systems. It is an original systems composition, not a claim of new cryptographic or quantization mathematics. No third-party firmware or model implementation is bundled.

The layers are explicit rather than visually stacked for a false compression claim:

1. **Core:** the original bounded Java Card applet, with no transcript or authority to act.
2. **Protocol:** unsigned Q0.15 values, at most 64 probabilities, a 135-byte maximum request, and a 10-byte measurement response.
3. **Host codec:** `host/zoe_cell.py` uses largest-remainder allocation to make the vector sum exact, then builds and parses the bounded commands. An authorized BERT/GPT/other model can supply probabilities; no model is required or included.
4. **Boutique interface:** the full-quality Zoe app remains on the phone. It is not squeezed into the card or degraded to fit a size target.

`host/manifest.py` generates `build/layers.json` with canonical JSON, exact artifact sizes, and SHA-256 hashes. Hashes support integrity checking, not publisher authentication. The current simulated core class is **2,735 bytes**; that host class size is not an installable CAP size or proof of free card memory.

### One source, complementary views

Bitwise inversion is still bit flipping; it does not save storage by itself. The useful constraint is to avoid storing complementary forms. Zoe Cell keeps one probability vector and derives `complement = N − A`, never a second inverse vector. Its **Divine Zoe** visual language uses one concentric chalice/hourglass vector for complementary geometry, not two bitmap assets. Presentation changes never alter the equation, protocol bytes, evidence boundary, or authorization.

## Native simulation inside Zoe

The Android app includes **Tiny Zoe · Zoe Cell** under **Field kit**, with its shared three-plane counterpart under **Trinity**, so development does not require a reader. `CellSimulator.java` is an original behavioral model of the two-command protocol; `CellCodec.java` performs bounded Q0.15 encoding and response validation. It runs actual requests through the model on the phone, including rejection paths and strict equality behavior.

The protocol console exposes raw hexadecimal requests, full request/response bytes, ISO-style statuses, deterministic replay, and twelve in-memory transaction summaries. `CellSession.java` uses defensive copies and clears replay/history state on reset. An explicit **Share session** action exports retained request/response bytes, statuses, equation credit, and simulation disclaimers through Android's chooser; it writes no file, adds no timestamp or device identifier, and uploads nothing. Raw commands never leave the simulator except through that deliberate share action. Text, vector, command, and history bounds are tested with malformed, oversized, randomized, and mutation-focused cases. No simulator input authorizes an external action.

The native model passes **17 protocol/session host tests**, including exact export bytes and empty-export behavior. Seven Tiny Zoe on-device UI tests compile, but the updated device suite still requires a connected phone. Adversarial host checks include every APDU length from 0–135 bytes, 4,352 arbitrary commands, 1,000 hostile strings, mutation attempts, replay consistency, and reset behavior. Android lint reports zero errors without a baseline. Ablation's preceding report found no dangerous-call, reflection, class-loader, unsafe-operation, or serialization findings in the three compiled core classes; the new export formatter has not undergone a separate Ablation review. Passing checks are not a guarantee of perfect safety, production readiness, or a physical security certification.

This is not a Java Card virtual machine, a physical-chip emulator, a SIM/eUICC interface, or proof of on-card memory use. The separate jCardSim lane checks the Java Card applet's behavior, while the native Android model makes the protocol interactive inside Zoe. No third-party card runtime is added to the APK.

The inspected vintage Digital Research GEM collection contains installation archives and disk indexes, not a usable card simulator. Its resource/device layering is inspiration only; no proprietary archive or code is bundled.

## Simulate and test

Use JDK 17 or newer and these development-only dependencies:

- [jCardSim](https://github.com/licel/jcardsim), Apache-2.0, through the `com.klinec:jcardsim:3.0.5.9` distribution.
- JUnit 4.13.2 and Hamcrest 1.3.

```bash
JCARD_SIM=/path/to/jcardsim-3.0.5.9.jar \
JUNIT_JAR=/path/to/junit-4.13.2.jar \
HAMCREST_JAR=/path/to/hamcrest-core-1.3.jar \
mobile/card/test.sh
```

The test command runs **8 APDU simulator tests** and **6 host-codec tests**. They cover shared fixtures, strict equality, the 64-value bound, deterministic encoding, invalid lengths, invalid values, malformed headers, and malformed responses. The simulator does not emulate a particular card's remaining memory, timing, electrical behavior, firewall, or security certification. Host JVM class size is not a CAP size or an on-card footprint.

Ablation parsed the resulting Java 8 class and reported eight methods with no dangerous-call, reflection, serialization, class-loader, or unsafe-operation references. That is a bounded static observation, not a security proof.

Oracle documents compact CAP files as containing one package and a method component of at most 64 KiB; the card vendor decides how much persistent and transient memory remains after the OS and other applications. See the [Java Card Development Kit Tools guide](https://docs.oracle.com/en/java/javacard/3.2/jctug/java-card-development-kit-tools-user-guide.pdf). The compact format's limit is not a promise of installable space. There is no universal SIM/eSIM free-space number; obtain the exact development-card data sheet and authorized loader.

## Physical boundary

No PC/SC reader was detected on the development host. No CAP file has been installed, no physical smart card has been measured, and no carrier SIM/eUICC has been modified. A real installation requires a Java Card development device, a supported PC/SC reader, its documented GlobalPlatform tooling, and credentials intentionally provisioned for that development card. Do not use a CAC or carrier-issued eSIM as an installation target.

Ablation's existing Java class/JAR parser can inventory the original compiled applet and its API references. Ablation does not currently provide a PC/SC, PKCS#11, CCID, Java Card CAP converter, or eUICC installer. Those distinctions are verified gaps, not capabilities to infer from its general firmware parsers.
