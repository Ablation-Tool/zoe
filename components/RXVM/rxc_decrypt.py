#!/usr/bin/env python3
"""
Amazon rxc= Cookie Decryptor

The rxc cookie stores accumulated behavioral metrics from RXVM,
encrypted with RC4. The key is derived from hash(userAgent + sessionId)
and shipped in cleartext inside the cookie itself.

Cookie wire format (after base64 decode):
  byte 0:     fnpv (version, currently 0)
  bytes 1-4:  fnpb (RC4 key, 4 bytes — derived from custom hash of UA+SID)
  bytes 5+:   RC4 ciphertext

Plaintext format (after RC4 decrypt):
  bytes 0-3:  unix timestamp (uint32 LE) — when ep4 was called
  bytes 4+:   metric stream — serialized by E(v)

Metric stream format:
  Sequence of [metric_id, ...data_bytes] pairs.
  E() serializes as: Object.keys(v).forEach(n => { t.push(parseInt(n)); t = t.concat(v[n]) })

Known metric IDs:
  16 (0x10) = bot fingerprint bitmask (payload [4])
  32 (0x20) = mouse click timing stats (payload [5])
  33 (0x21) = mouse movement / acceleration stats (payload [6])
  34 (0x22) = scroll velocity stats (payload [7])
  35 (0x23) = paint / navigation timing (payload [8])
  48 (0x30) = neural network score (payload [11])

Usage:
  rxc_decrypt.py <cookie_value>
  rxc_decrypt.py --file <cookies.txt>
"""

import base64
import struct
import sys
import json
from datetime import datetime, timezone


# ─── RC4 ───────────────────────────────────────────────────────────────────

def rc4(key: bytes, data: bytes) -> bytes:
    """Standard RC4 stream cipher — matches fn@433 in payload [0]."""
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) & 0xFF
        S[i], S[j] = S[j], S[i]

    out = []
    i = j = 0
    for byte in data:
        i = (i + 1) & 0xFF
        j = (j + S[i]) & 0xFF
        S[i], S[j] = S[j], S[i]
        out.append(byte ^ S[(S[i] + S[j]) & 0xFF])
    return bytes(out)


# ─── Base64 ───────────────────────────────────────────────────────────────

def b64_decode_amazon(s: str) -> bytes:
    """Amazon's custom base64 — standard alphabet, no padding."""
    missing = len(s) % 4
    if missing:
        s += '=' * (4 - missing)
    return base64.b64decode(s)


# ─── Timestamp ─────────────────────────────────────────────────────────────

def format_timestamp(ts):
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OSError, ValueError, OverflowError):
        return f'invalid ({ts})'


# ─── Metric IDs ────────────────────────────────────────────────────────────

KNOWN_METRICS = {
    16: 'bot fingerprint bitmask',
    31: 'scroll position hash',
    32: 'mouse click timing (count/mean/sum)',
    33: 'mouse movement + acceleration (6 stats)',
    34: 'scroll velocity (count/mean/sum)',
    35: 'paint / navigation timing',
    48: 'neural network score (float16)',
}


# ─── Decryption ────────────────────────────────────────────────────────────

def decrypt_rxc(cookie_value: str) -> dict:
    """Decrypt an rxc= cookie value."""
    # Strip prefix
    if cookie_value.startswith('rxc='):
        cookie_value = cookie_value[4:]
    cookie_value = cookie_value.split(';')[0].strip()

    raw = b64_decode_amazon(cookie_value)

    if len(raw) < 6:
        raise ValueError(f"Cookie too short: {len(raw)} bytes (need >= 6)")

    version = raw[0]
    key = raw[1:5]
    ciphertext = raw[5:]

    plaintext = rc4(key, ciphertext)

    # First 4 bytes = unix timestamp (LE uint32)
    timestamp = None
    metrics_start = 0
    if len(plaintext) >= 4:
        timestamp = struct.unpack('<I', plaintext[:4])[0]
        metrics_start = 4

    metric_bytes = plaintext[metrics_start:]

    return {
        'version': version,
        'key_hex': key.hex(),
        'key_bytes': list(key),
        'ciphertext_len': len(ciphertext),
        'plaintext_len': len(plaintext),
        'timestamp': timestamp,
        'timestamp_human': format_timestamp(timestamp) if timestamp else None,
        'plaintext_hex': plaintext.hex(),
        'plaintext_bytes': list(plaintext),
        'metric_bytes': list(metric_bytes),
        'metrics': parse_metrics(metric_bytes),
    }


# ─── Metric Parsing ───────────────────────────────────────────────────────

def parse_metrics(data: bytes) -> list:
    """
    Parse the decrypted metric stream.

    The metrics are serialized by E(v):
      Object.keys(v).forEach(n => { t.push(parseInt(n)); t = t.concat(v[n]) })

    Each metric entry from rx.pc(id, data):
      v[id & 0xFF] = data

    Known metric payload sizes (from disassembly):
      - ID 16: variable (bitmask + hdl count)
      - ID 32: 6 bytes (3x uint16 LE — count, mean, sum for clicks)
      - ID 33: 6 bytes (3x uint16 LE — count, mean, sum for movement)
                + 6 bytes (3x uint16 LE — count, mean, sum for acceleration)
      - ID 34: 6 bytes (3x uint16 LE — count, mean, sum for scroll)
      - ID 35: 2 bytes (float16 encoded)
      - ID 48: 2 bytes (float16 neural net score) + 1 byte (model ID)
    """
    metrics = []
    if not data:
        return metrics

    # Heuristic parse: try to identify metric boundaries
    # by matching known IDs and their expected sizes
    i = 0
    while i < len(data):
        metric_id = data[i]
        i += 1

        # Try to determine payload size from known IDs
        if metric_id in KNOWN_METRICS:
            label = KNOWN_METRICS[metric_id]
        else:
            label = f'unknown (0x{metric_id:02x})'

        # Collect bytes until next plausible metric ID or end
        value_bytes = []
        while i < len(data):
            # Peek: if this byte is a known metric ID and we have at least 1 byte,
            # it might be the start of the next metric
            if data[i] in KNOWN_METRICS and len(value_bytes) >= 2:
                break
            value_bytes.append(data[i])
            i += 1

        entry = {
            'id': metric_id,
            'label': label,
            'raw': value_bytes,
            'hex': bytes(value_bytes).hex() if value_bytes else '',
        }

        # Decode float16 values if this looks like a 2-byte metric
        if len(value_bytes) == 2:
            entry['float16'] = decode_float16(value_bytes[0], value_bytes[1])

        # Decode as uint16 LE pairs if divisible by 2
        if len(value_bytes) >= 2 and len(value_bytes) % 2 == 0:
            uint16s = []
            for j in range(0, len(value_bytes), 2):
                uint16s.append(value_bytes[j] | (value_bytes[j + 1] << 8))
            entry['uint16_le'] = uint16s

        metrics.append(entry)

    return metrics


def decode_float16(lo, hi):
    """Decode Amazon's float16 format (matches rx.df16)."""
    v = (hi << 8) | lo
    sign = -1 if (v & 0x8000) else 1
    exp = (v >> 10) & 0x1F
    mant = v & 0x3FF

    if exp == 31:
        return float('nan')
    if exp == 0:
        return sign * (mant / 1024) * (2 ** -14)
    return sign * (1 + mant / 1024) * (2 ** (exp - 15))


# ─── Output Formatting ────────────────────────────────────────────────────

def format_output(result: dict) -> str:
    lines = []
    lines.append(f"{'=' * 64}")
    lines.append(f"rxc= COOKIE DECRYPTION")
    lines.append(f"{'=' * 64}")
    lines.append(f"")
    lines.append(f"Version:         {result['version']}")
    lines.append(f"RC4 Key:         {result['key_hex']} ({result['key_bytes']})")
    lines.append(f"Ciphertext:      {result['ciphertext_len']} bytes")
    lines.append(f"Plaintext:       {result['plaintext_len']} bytes")
    if result.get('timestamp'):
        lines.append(f"Timestamp:       {result['timestamp']} ({result['timestamp_human']})")
    lines.append(f"Metric entries:  {len(result.get('metrics', []))}")
    lines.append(f"")

    # Hex dump
    lines.append(f"{'─' * 64}")
    lines.append(f"DECRYPTED BYTES")
    lines.append(f"{'─' * 64}")
    data = result['plaintext_bytes']
    for offset in range(0, len(data), 16):
        chunk = data[offset:offset + 16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  {offset:04x}:  {hex_part:<48s}  {ascii_part}")

    # Parsed metrics
    lines.append(f"")
    lines.append(f"{'─' * 64}")
    lines.append(f"PARSED METRICS")
    lines.append(f"{'─' * 64}")
    for m in result['metrics']:
        lines.append(f"  [{m['id']:3d}] {m['label']}")
        lines.append(f"        hex: {m['hex']}")
        if 'float16' in m:
            lines.append(f"        float16: {m['float16']:.6f}")
        if 'uint16_le' in m:
            lines.append(f"        uint16 LE: {m['uint16_le']}")
        lines.append(f"        raw ({len(m['raw'])} bytes): {m['raw'][:32]}{'...' if len(m['raw']) > 32 else ''}")

    return '\n'.join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Amazon rxc= Cookie Decryptor")
        print()
        print("Usage:")
        print("  rxc_decrypt.py <cookie_value>")
        print("  rxc_decrypt.py --file <cookies.txt>")
        print("  rxc_decrypt.py --json <cookie_value>    (JSON output)")
        print()
        print("Cookie value is the rxc= value from Amazon,")
        print("with or without the 'rxc=' prefix.")
        sys.exit(1)

    json_mode = '--json' in sys.argv
    if json_mode:
        sys.argv.remove('--json')

    if sys.argv[1] == '--file':
        with open(sys.argv[2]) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if 'rxc=' in line:
                    for part in line.split(';'):
                        part = part.strip()
                        if part.startswith('rxc='):
                            line = part[4:]
                            break
                try:
                    result = decrypt_rxc(line)
                    if json_mode:
                        print(json.dumps(result, indent=2))
                    else:
                        print(format_output(result))
                except Exception as ex:
                    print(f"FAILED: {ex}")
                print()
    else:
        cookie = sys.argv[1]
        try:
            result = decrypt_rxc(cookie)
            if json_mode:
                print(json.dumps(result, indent=2))
            else:
                print(format_output(result))
                print(f"\n{'─' * 64}")
                print("JSON:")
                print(json.dumps(result, indent=2))
        except Exception as ex:
            print(f"FAILED: {ex}")
            sys.exit(1)


if __name__ == '__main__':
    main()
