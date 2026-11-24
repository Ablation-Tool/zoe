# Deployment

## Requirements

- Python 3.12 or newer
- ffmpeg 4.x or newer (ships both `ffmpeg` and `ffprobe` binaries)

The service validates at startup that both binaries are on PATH and that the temp directory is writable. It will refuse to start if either check fails.

---

## Docker

The Dockerfile bakes in ffmpeg and runs the service as an unprivileged user (uid 10001). The base image is pinned to a specific SHA256 digest so builds are reproducible.

```bash
docker build -t dba .
docker run --rm -p 8000:8000 dba
```

To override configuration:

```bash
docker run --rm -p 8000:8000 \
  -e MD_MAX_UPLOAD_BYTES=52428800 \
  -e MD_MAX_CONCURRENT=5 \
  -e MD_TEMP_DIR=/data/tmp \
  -v /data:/data \
  dba
```

Mount a volume for `MD_TEMP_DIR` when the caller needs to retrieve sanitized files by path. The default is the container's system temp directory, which is ephemeral.

---

## Local

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

For production, add `--workers N` to run multiple Uvicorn processes. Each worker maintains its own semaphore, so `MD_MAX_CONCURRENT` applies per worker.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MD_TEMP_DIR` | system temp | Absolute path for upload staging and sanitized output. Must be writable by the service user. |
| `MD_MAX_UPLOAD_BYTES` | `209715200` | Maximum upload size in bytes (200 MiB). Enforced at the middleware layer before the body is spooled, so the reverse proxy does not need a matching limit (though adding one is good practice). |
| `MD_FFPROBE_TIMEOUT` | `30` | Seconds before an ffprobe call is killed. Files that cause ffprobe to hang (rare but possible with malformed containers) are rejected with 422. |
| `MD_FFMPEG_TIMEOUT` | `120` | Seconds before an ffmpeg re-mux is killed. Increase for very large files or slow storage. |
| `MD_SANITIZED_TTL` | `300` | Seconds before sanitized output files are swept. The sweep runs at startup and then periodically. Set to 0 to disable sweeping (not recommended in production). |
| `MD_MAX_CONCURRENT` | `10` | Maximum simultaneous ffprobe + ffmpeg subprocess pairs. Requests that would exceed this limit wait on an asyncio semaphore. |

---

## Reverse proxy

dBA handles upload size enforcement in middleware, but adding a limit at the reverse proxy reduces unnecessary body transmission before the service rejects the request.

**nginx example:**

```nginx
client_max_body_size 201m;

location /analyze-and-sanitize-audio {
    proxy_pass http://localhost:8000;
    proxy_request_buffering off;
    proxy_read_timeout 180;
}
```

Set `proxy_read_timeout` higher than `MD_FFMPEG_TIMEOUT` so nginx does not close the connection before ffmpeg finishes.

---

## Kubernetes

Run dBA as a Deployment with a single container. Use a `PersistentVolumeClaim` for `MD_TEMP_DIR` when callers retrieve sanitized files by path.

```yaml
env:
  - name: MD_TEMP_DIR
    value: /data/dba-tmp
  - name: MD_MAX_CONCURRENT
    value: "5"
volumeMounts:
  - name: tmp-vol
    mountPath: /data/dba-tmp
```

The `HEALTHCHECK` baked into the Dockerfile translates directly to a Kubernetes liveness probe:

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
```

---

## Sanitized file retrieval

`sanitized_file_path` in the response is a local filesystem path. Three deployment patterns:

**Shared volume**: mount the same `MD_TEMP_DIR` into both the dBA container and the caller. The caller reads the path directly and is responsible for deleting it. dBA sweeps orphans older than `MD_SANITIZED_TTL` as a safety net.

**Sidecar**: run dBA as a sidecar container in the same pod as the ASR service. Both containers share an `emptyDir` volume at `MD_TEMP_DIR`.

**API gateway with file proxy**: expose a separate download endpoint in a gateway (e.g., nginx `alias` or a thin proxy) that serves files from `MD_TEMP_DIR` and then deletes them. dBA's own TTL sweep handles any files the gateway misses.

---

## Extending the indicator set

Add entries to `SUSPICIOUS_PATTERNS` in `main.py`:

```python
{"id": "TAG_MY_MARKER", "severity": "high", "regex": r"<MY_MARKER>", "mask": False},
```

- `id`: stable string, used by SIEM/SOAR to key on findings. Never reuse a retired ID.
- `severity`: `"low"` (10), `"medium"` (25), or `"high"` (40).
- `mask`: set to `True` for credentials or PII where even a truncated snippet should not appear in the response.

Add a paired test in `tests/test_policy.py` that asserts the indicator fires and its severity weight is correct. The CI pipeline requires all tests to pass before merge.

---

## Allowing specific tags through

By default no free-form tag survives into `sanitized_metadata.tags`. To allow specific keys:

```python
ALLOWED_TAG_KEYS: set[str] = {"language"}
```

Only the exact key names listed here pass through. Values are still scanned for indicators before passing. If a value matches any indicator, the tag is dropped from sanitized output entirely rather than passed through — the indicator still fires and reports the match.
