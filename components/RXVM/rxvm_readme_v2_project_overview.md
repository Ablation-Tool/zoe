# RXVM — Amazon Client-Side Bot Detection (Reverse Engineering POC)

Reverse engineering of Amazon's RXVM bytecode virtual machine and its
client-side bot detection / behavioral telemetry system.

## Files

| File | Description |
|---|---|
| `ANALYSIS.md` | Full technical writeup — architecture, all 15 payloads, data flow |
| `rxvm_disasm.py` | RXVM bytecode disassembler (v4) — XOR key reseeding, closure discovery |
| `rxc_decrypt.py` | Amazon `rxc=` cookie decryptor — RC4 decryption, metric stream parsing |
| `a10_model.py` | A10 neural network reimplementation — inference, feature importance, simulation |
| `a10_model_weights.json` | Extracted model weights — norms, dense, batchnorm, all layers |
| `payload_0_crypto_annotated.txt` | Annotated disassembly of the crypto payload with JS equivalents |
| `rxvm_v4_full_disasm.txt` | Complete disassembly of all 15 payloads from a live Amazon page |

## Quick Start

### Disassemble RXVM payloads from an Amazon page

```bash
python3 rxvm_disasm.py page.html
```

### Disassemble a single base64 payload

```bash
python3 rxvm_disasm.py -b64 "UlgB..."
```

### Decrypt an rxc cookie

```bash
python3 rxc_decrypt.py "AGVoY2hlY2..."
```

### Analyze the neural network

```bash
python3 a10_model.py
```

### Score a custom feature vector

```bash
python3 a10_model.py --score 450 500 60 300 310 45 80 90 40 18 48 3 \
    0.4 0.4 0.4 0.02 0.11 0.11 0.4 0.02 \
    160 160 520 520 240 240 620 620 100 120 7
```

## Neural Network Scoring Limitation

The A10 model extraction is complete and verified — the 8-bit minifloat decoder and `rx.M`
matrix module have both been confirmed against the production RXVM interpreter source (they
match exactly). However, all test profiles score ~1.0 because the 8-bit weight quantization
limits hidden layer modulation to ~0.04 against a constant BatchNorm offset of ~26.5. The
model may discriminate at extreme input distributions not covered by our tests, or Amazon
may have since deployed higher-precision weights.

## No External Dependencies

All tools are pure Python 3, standard library only. No pip installs required.

## System Overview

```
Amazon Page HTML
    └── rx.ex64("base64...") × 15 payloads
         │
         ├── [0]  Crypto layer (AES-128-CBC + RC4 fallback)
         ├── [1]  Statistics library (sum, mean, stddev, float16 codec)
         ├── [2]  Cookie fingerprint (hash(UA + SID) → fnpb key)
         ├── [3]  State persistence (EMA tracking via encrypted localStorage)
         ├── [4]  Bot fingerprinting (Playwright, WebDriver, ChromeDriver,
         │        Puppeteer, PhantomJS, SwiftShader, headless dimension checks)
         ├── [5]  Mouse click timing (mousedown/mouseup duration)
         ├── [6]  Mouse movement (velocity + angular acceleration)
         ├── [7]  Scroll behavior (scroll velocity)
         ├── [8]  Navigation timing (visit count, session duration)
         ├── [9]  Viewport / screen dimensions
         ├── [10] ML runtime (Dense, BatchNorm, ReLU, Sigmoid layers)
         ├── [11] ML scoring (31→16→16→1 neural net, weights inline)
         ├── [12] Strong interaction detection (mouse/scroll threshold gate)
         ├── [13] Cookie action tracking (highest interaction tier)
         └── [14] AI agent detection (Perplexity browser agent regex scanning)
```
