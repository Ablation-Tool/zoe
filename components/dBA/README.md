<h1 align="center">dBA</h1>
<p align="center"><strong>defenseBridge for ASR</strong></p>

![](https://komarev.com/ghpvc/?username=Ablation-Tool&repo=dBA&color=grey) [![NIST SP 800-218](https://img.shields.io/badge/NIST%20SP%20800--218-SSDF-grey)](SECURITY.md) [![CI](https://img.shields.io/github/actions/workflow/status/Ablation-Tool/dBA/ci.yml?branch=main&label=CI&color=grey)](https://github.com/Ablation-Tool/dBA/actions) [![License](https://img.shields.io/badge/License-MIT-grey)](LICENSE) [![Sponsor Me](https://img.shields.io/badge/Sponsor_Me-grey?logo=githubsponsors&logoColor=white)](https://github.com/Ablation-Tool/ablation/blob/main/docs/SPONSORS.md)


dBA is a metadata firewall for ASR pipelines.

It sits between an upload endpoint and a transcription service such as Whisper, inspects every field in the audio container, scores the risk, and hands back a stripped copy.

Raw tag values never leave the service.



---

## The Problem

Audio files carry free-form text in their containers. A WAV RIFF LIST chunk accepts any bytes. An MP3 ID3 tag or a Vorbis comment field does the same.

Most ASR deployments treat audio as opaque binary data, so those bytes flow unchanged into transcription logs, LLM context windows, and SIEM pipelines. The log parser does not know it is reading audio metadata. The prompt assembler does not distinguish between words in the waveform and text in the file header. Nobody is scanning WAV INFO chunks for AWS keys.

An attacker who can upload audio can write arbitrary text into those fields. dBA closes that path at the ingestion point, before transcription runs.

---

## Capabilities

<details>
<summary><strong>Pipeline</strong> </summary>

| Stage | |
|:---|:---|
| **Ingest** | Streams the upload to a `0o600` file under a UUID and discards the original filename. The filename never appears in a path or a subprocess argument, so a crafted name cannot reach the filesystem or ffmpeg. Size is counted per chunk during the stream, so a lying or missing `Content-Length` does not bypass the cap. |
| **Extract** | Runs `ffprobe` read-only and parses the container as JSON. Every tag key and value, every stream, and the format block are captured for analysis. |
| **Analyze** | Runs structural checks and case-insensitive pattern matching across tag keys as well as values, at both format and stream level. Vorbis field names and ID3 TXXX descriptions are attacker-controlled, so a payload placed in the key is detected the same as one in the value. |
| **Score** | Sums severity weights into a 0–100 risk score and applies the mode adjustment. Duplicate indicators are collapsed first so the same payload in multiple streams does not compound the score. |
| **Decide** | Returns `allow`, `quarantine`, or `reject`. A reject returns HTTP 422 with the full indicator report and no sanitized file. |
| **Sanitize** | Re-muxes with `ffmpeg -c copy`, so audio is never re-encoded. `-map_metadata -1` drops every tag, `-map 0:a` drops every non-audio stream, and `-bitexact` suppresses ffmpeg's own `encoder=Lavf...` stamp, which would otherwise survive as a silent metadata leak. The output muxer is chosen from an allowlist keyed on the ffprobe-detected format, not the caller-supplied extension. |
| **Respond** | Returns a forensic JSON report and the path to the stripped file. Indicator snippets are truncated to 80 characters and credential matches are masked. |

</details>

<details>
<summary><strong>Content Indicators</strong> </summary>

Fire when a pattern matches a tag key or value.

| ID | Severity | Matches | Masked |
|:---|:---|:---|:---|
| `TAG_AWS_KEY` | high | `AKIA` / `ASIA` + 16 uppercase alphanumerics | yes |
| `TAG_PRIVATE_KEY` | high | `-----BEGIN ... PRIVATE KEY-----` | yes |
| `TAG_POTENTIAL_SHELL` | high | `; curl`, `wget`, `bash -i` | no |
| `TAG_CMD_SUBSTITUTION` | high | `$(` or backtick | no |
| `TAG_VIPER` | high | `[VIPER]` | no |
| `TAG_SEIZURE_MARKER` | high | `<SEIZURE_SHORT>` | no |
| `TAG_OPERATION_ID` | high | `<OP_ID>` / `<OPERATION_ID>` | no |
| `TAG_HTML_SCRIPT` | medium | `<script` | no |
| `TAG_DEBUG_FLAG` | low | `-dbug` | no |
| `TAG_GENERIC_URL` | low | `http://` or `https://` | no |
| `TAG_EMAIL_PII` | low | email address pattern | yes |

Masked means the matched span is replaced with `***` in the response, so a credential does not appear even in truncated form. The tag is dropped from the sanitized output regardless.

</details>

<details>
<summary><strong>Structural Indicators</strong> </summary>

Fire on file shape alone. No suspicious string is required.

| ID | Severity | Fires when |
|:---|:---|:---|
| `NO_AUDIO_STREAM` | high | The file has no audio stream. ASR has nothing to process. |
| `UNUSUAL_DURATION` | medium | Duration is under 0.1 s and the file exceeds 1 MB. The classic shape for data hidden behind a blip. |
| `TRAILING_DATA` | medium | On-disk size far exceeds what the audio stream's own data rate and duration account for. |
| `UNEXPECTED_CODEC` | medium | The codec is not on the ASR allowlist. |
| `MULTIPLE_AUDIO_STREAMS` | medium | More than one audio stream is present. ASR expects one. |
| `EMBEDDED_NONAUDIO_STREAM` | medium | Cover art, video, or a data stream is embedded in an audio upload. |

`TRAILING_DATA` uses the stream's own bit rate rather than `format.bit_rate`. ffprobe derives `format.bit_rate` from file size divided by duration, so comparing against it is circular and the check would never fire. For PCM streams that report no bit rate, it is derived from sample rate × channels × bits per sample. The check fires when the file is more than twice the expected size plus a 64 KiB allowance for headers.

</details>

<details>
<summary><strong>Security Properties</strong> </summary>

| Property | |
|:---|:---|
| **No shell interpolation** | Every subprocess runs from an argument list. There is no `shell=True` anywhere in the codebase. |
| **No raw tag leakage** | Tag keys and values never appear in logs or API responses. Only the indicator ID, a truncated snippet, and the masked span are returned. |
| **Upload cap enforced twice** | `Content-Length` is checked in middleware before the body is spooled, and the byte count is checked again per chunk while streaming to disk. An oversized upload is refused either way. |
| **Format allowlist** | The output muxer is selected from the ffprobe-detected container. Unsupported containers return 415. |
| **Hardened temp files** | Uploads are created with `O_EXCL` and mode `0o600`. Sanitized copies are `chmod 0o600`. The original is deleted after each request. Sanitized copies and orphaned uploads are swept at startup and then every `MD_SANITIZED_TTL` seconds. |
| **Bounded concurrency** | ffprobe and ffmpeg run in a thread pool so the event loop stays responsive. Concurrent subprocess pairs are capped at `MD_MAX_CONCURRENT` by an asyncio semaphore. |
| **Timeouts on every subprocess** | ffprobe and ffmpeg are killed after `MD_FFPROBE_TIMEOUT` and `MD_FFMPEG_TIMEOUT`. A malformed container that hangs the probe is rejected with 422. |
| **Hardened response headers** | Every response carries `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, `Content-Security-Policy: default-src 'none'`, `X-Frame-Options: DENY`, and `X-dBA-Version`. The firewall endpoint also returns a server-generated `X-Request-ID`, and the same ID is injected into every log line for that request. |
| **Unprivileged container** | The Docker image runs as uid 10001 on a base image pinned to a SHA-256 digest. |

</details>

---

## Modes

| Mode | Allow | Quarantine | Reject | Adjustment |
|:---|:---|:---|:---|:---|
| `strict` | score < 10 | score < 40 | score ≥ 40 | +10 when any indicator fires |
| `lenient` | score < 30 | score < 80 | score ≥ 80 | −10, floored at 0 |
| `audit` | always | never | never | scores and reports but never blocks |

`mode` defaults to `strict` when omitted. Any other value returns 400.

Severity weights are **high** 40 · **medium** 25 · **low** 10, summed and capped at 100 before the mode adjustment is applied. Indicators are deduplicated by (ID, key, snippet) first, so the same payload in multiple streams does not compound the score.

When `analyze_metadata` is called as a library function with an unrecognised mode, it falls back to 20 / 60 thresholds with no adjustment. That path is not reachable through the HTTP API.

---

## Supported Containers

| Detected | Output | ffmpeg muxer |
|:---|:---|:---|
| WAV | `.wav` | `wav` |
| MP3 | `.mp3` | `mp3` |
| FLAC | `.flac` | `flac` |
| Ogg | `.ogg` | `ogg` |
| M4A · MP4 | `.m4a` | `ipod` |
| AAC | `.aac` | `adts` |

---

## Endpoints

| Method | Path | Purpose |
|:---|:---|:---|
| `POST` | `/analyze-and-sanitize-audio?mode=strict\|lenient\|audit` | Full firewall: score, decide, strip |
| `POST` | `/sanitize-audio` | Strip and alert only, no scoring |
| `GET` | `/healthz` | Liveness check |

See [docs/api.md](docs/api.md) for complete request and response shapes and [docs/deployment.md](docs/deployment.md) for reverse proxy, Kubernetes, and sidecar patterns.

---

## Where It Belongs

dBA sits in front of any ASR system that accepts untrusted uploads.

Customer support voice bots. Call recording pipelines. Healthcare voice documentation. Any pipeline where audio metadata reaches an LLM context window.

---

## Install

**Docker**

```bash
docker build -t dba .
docker run --rm -p 8000:8000 dba
```

**Local**

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Send a file**

```bash
curl -s -X POST "http://localhost:8000/analyze-and-sanitize-audio?mode=strict" \
  -F "file=@recording.wav" | jq
```

---

## Requirements

- Python >= 3.12
- `ffmpeg` and `ffprobe` on PATH (ffmpeg 4.x or newer)
- `fastapi`, `uvicorn`, `python-multipart`

The service validates at startup that both binaries are present and that the temp directory is writable. It refuses to start if either check fails.

---

## Configuration

| Variable | Default | Meaning |
|:---|:---|:---|
| `MD_TEMP_DIR` | system temp | Working directory for uploads and output |
| `MD_MAX_UPLOAD_BYTES` | `209715200` | Reject uploads larger than this (200 MiB) |
| `MD_FFPROBE_TIMEOUT` | `30` | ffprobe timeout in seconds |
| `MD_FFMPEG_TIMEOUT` | `120` | ffmpeg timeout in seconds |
| `MD_SANITIZED_TTL` | `300` | Seconds before sanitized output files are swept |
| `MD_MAX_CONCURRENT` | `10` | Maximum simultaneous ffprobe + ffmpeg subprocess pairs |

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/test_policy.py` exercises `analyze_metadata` as a pure function over synthetic ffprobe dicts. 32 tests, no ffmpeg required. Every indicator, every severity weight, every mode threshold, masking, truncation, key scanning, and deduplication each have a dedicated case.

`tests/test_endpoints.py` drives the full FastAPI stack against real ffmpeg with generated clean, hostile, and trailing-padded WAV fixtures. 16 tests covering disposition per mode, 400 / 413 / 422 paths, that the sanitized output carries no tags, that raw tag values never reach the log, and that security headers are present. It is skipped automatically when ffmpeg is absent, and CI installs ffmpeg so the integration suite never silently skips.

---

## Responsible Use

dBA is a defensive control. It is built to protect ASR pipelines you own or operate, and the indicator set exists to detect injected content, not to generate it. Deploy it only on infrastructure you are authorized to protect. The author is not responsible for misuse.

---

## Standards

**[NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final)**

The Secure Software Development Framework defines how software should be built, organized around four practice areas: preparing the organization, protecting the software, producing well-secured software, and responding to vulnerabilities.

What this means for dBA in practice:

Every push and pull request runs the full test suite, a `bandit` SAST scan at MEDIUM severity and above, and a `pip-audit` scan that fails the build on any known-vulnerable dependency.

Dependencies are pinned to exact versions. The Docker base image is pinned to a SHA-256 digest. Dependabot scans weekly and patch bumps auto-merge only after CI passes.

No subprocess runs through a shell. No tag value is logged. No secret is hardcoded.

[SECURITY.md](SECURITY.md) maps each in-repo artifact to the SSDF practice it satisfies, publishes the disclosure process and response SLAs, and lists the GitHub repository settings (branch protection, secret scanning, push protection, signed commits) that must be enabled separately.

SSDF is a process framework with no accreditation body. This is alignment, not certification.

---
