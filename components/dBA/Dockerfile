# Pin base image to a specific digest so builds are reproducible and immune to
# tag mutation (SSDF PO.3.1). Update the digest intentionally when upgrading.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# ffmpeg ships both ffmpeg and ffprobe — the two binaries this service shells out to.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Run as an unprivileged user — the service handles untrusted uploads.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Liveness check so orchestrators detect a hung event loop (e.g. blocked subprocess).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
