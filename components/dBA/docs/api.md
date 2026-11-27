# API Reference

## Base URL

All paths are relative to the server root. No versioning prefix.

---

## POST `/analyze-and-sanitize-audio`

The full firewall endpoint. Runs the complete pipeline: ingest, probe, analyze, score, decide, strip.

### Query parameters

| Parameter | Type | Default | Values |
|-----------|------|---------|--------|
| `mode` | string | `strict` | `strict`, `lenient`, `audit` |

### Request body

`multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | binary | yes |

### Response

**200 OK** — disposition is `allow` or `quarantine`:

```json
{
  "sanitized_metadata": {
    "duration": 0.5,
    "bit_rate": 256000,
    "sample_rate": 16000,
    "channels": 1,
    "codec_name": "pcm_s16le",
    "container_format": "wav",
    "tags": {}
  },
  "indicators": [],
  "risk_score": 0,
  "disposition": "allow",
  "sanitized_file_path": "/tmp/sanitized_abc123.wav"
}
```

**422 Unprocessable Entity** — disposition is `reject`:

Same body shape as above. `sanitized_file_path` is always `null`. The file is not sanitized or forwarded.

**400 Bad Request** — invalid `mode` value, or empty upload.

**413 Request Entity Too Large** — `Content-Length` exceeds `MD_MAX_UPLOAD_BYTES`.

**415 Unsupported Media Type** — ffprobe recognized the file but the container is not in the output format allowlist.

### Response headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | 12-character hex correlation ID, server-generated |
| `X-dBA-Version` | dBA service version |
| `X-Content-Type-Options` | `nosniff` |
| `Cache-Control` | `no-store` |
| `Content-Security-Policy` | `default-src 'none'` |
| `X-Frame-Options` | `DENY` |

---

## POST `/sanitize-audio`

Legacy endpoint. Strips metadata and returns alerts. No scoring, no disposition, no reject path.

### Request body

`multipart/form-data`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file` | binary | required | Audio file |
| `strip` | boolean | `true` | If false, analyze only and skip ffmpeg re-mux |

### Response

**200 OK**:

```json
{
  "sanitized_metadata": {
    "duration": 0.01,
    "bit_rate": null,
    "sample_rate": 16000,
    "channels": 1,
    "codec_name": "pcm_s16le",
    "container_format": "wav",
    "tags": {}
  },
  "alerts": [
    {
      "key": "encoder",
      "pattern": "\\[VIPER\\]",
      "value": "[VIPER] <SEIZURE_SHORT> OP=<OPERATION_I***"
    }
  ],
  "sanitized_file_path": "/tmp/sanitized_def456.wav"
}
```

`alert.value` is truncated to 80 characters. Secret matches (AWS keys, private keys, email addresses) have the matched span replaced with `***`.

When `strip=false`, `sanitized_file_path` is `null`.

---

## GET `/healthz`

Liveness check. Returns 200 immediately without touching any subprocess.

```json
{"status": "ok"}
```

---

## Indicator reference

### Content indicators

Fired when a pattern matches a tag key or tag value. Every field except `detail` is populated.

| ID | Severity | Pattern | Masked |
|----|----------|---------|--------|
| `TAG_VIPER` | high | `\[VIPER\]` | no |
| `TAG_SEIZURE_MARKER` | high | `<SEIZURE_SHORT>` | no |
| `TAG_OPERATION_ID` | high | `<OP_ID>\|<OPERATION_ID>` | no |
| `TAG_POTENTIAL_SHELL` | high | `;\s*curl\b\|\bwget\b\|\bbash\s+-i` | no |
| `TAG_CMD_SUBSTITUTION` | high | `\$\(\|`` ` `` | no |
| `TAG_AWS_KEY` | high | `\b(?:AKIA\|ASIA)[0-9A-Z]{16}\b` | yes |
| `TAG_PRIVATE_KEY` | high | `-----BEGIN [A-Z ]*PRIVATE KEY-----` | yes |
| `TAG_HTML_SCRIPT` | medium | `<script\b` | no |
| `TAG_DEBUG_FLAG` | low | `-dbug\b` | no |
| `TAG_GENERIC_URL` | low | `\bhttps?://\S+` | no |
| `TAG_EMAIL_PII` | low | email address pattern | yes |

"Masked" means the matched span in `value_snippet` (and `Alert.value`) is replaced with `***`. The tag is dropped from the sanitized output regardless.

Keys are scanned as well as values. Vorbis field names and ID3 TXXX description fields are attacker-controlled, so a payload placed in the key rather than the value is still detected.

### Structural indicators

Fired by file-shape checks independent of tag content. Only `detail` is populated; `key`, `pattern`, and `value_snippet` are null.

| ID | Severity | Description |
|----|----------|-------------|
| `NO_AUDIO_STREAM` | high | File has no audio stream. ASR has nothing to process. |
| `UNUSUAL_DURATION` | medium | Duration < 0.1s and file size > 1 MB. Classic shape for data hidden in a blip. |
| `TRAILING_DATA` | medium | On-disk size far exceeds what the audio stream's own data rate and duration account for. Possible appended payload. Uses stream `bit_rate`, not format `bit_rate` (which is circular). |
| `UNEXPECTED_CODEC` | medium | Codec is not on the ASR pipeline allowlist. |
| `MULTIPLE_AUDIO_STREAMS` | medium | More than one audio stream. ASR expects one. |
| `EMBEDDED_NONAUDIO_STREAM` | medium | Cover art, video, or data stream embedded in an audio upload. |

---

## Scoring

Base score is the sum of severity weights for all indicators, capped at 100:

| Severity | Weight |
|----------|--------|
| high | 40 |
| medium | 25 |
| low | 10 |

Mode adjustments are applied after the sum:

| Mode | Adjustment |
|------|-----------|
| `strict` | +10 if any indicator present |
| `lenient` | -10 (floored at 0) |
| `audit` | none |

Duplicate indicators (same ID, same key, same snippet) are deduplicated before scoring so the same payload in multiple streams does not compound the score.

---

## Disposition thresholds

`mode` defaults to `strict` when the parameter is omitted. Any unrecognised value returns 400.

| Mode | allow | quarantine | reject |
|------|-------|------------|--------|
| `strict` | score < 10 | score < 40 | score >= 40 |
| `lenient` | score < 30 | score < 80 | score >= 80 |
| `audit` | always | never | never |

---

## Output format allowlist

dBA re-muxes into the format ffprobe detected from the file content, not from the upload filename. Only these containers are supported:

| Detected token | Output extension | ffmpeg muxer |
|----------------|-----------------|--------------|
| `wav` | `.wav` | `wav` |
| `mp3` | `.mp3` | `mp3` |
| `flac` | `.flac` | `flac` |
| `ogg` | `.ogg` | `ogg` |
| `m4a` | `.m4a` | `ipod` |
| `mp4` | `.m4a` | `ipod` |
| `aac` | `.aac` | `adts` |

Files in other containers return 415.

---

## Sanitized file path

`sanitized_file_path` is an absolute local filesystem path. It is valid only when the caller and service share a filesystem (local deployment, shared volume). In a fully remote deployment, expose a download endpoint in front of dBA or mount the temp directory as a shared volume.

The file is deleted automatically after `MD_SANITIZED_TTL` seconds (default 300). Retrieve it before the TTL expires.
