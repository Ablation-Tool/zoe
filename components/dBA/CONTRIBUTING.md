# Contributing

## Setup

```bash
git clone <repo>
cd dBA
pip install -r requirements-dev.txt
```

ffmpeg and ffprobe must be on PATH for the integration tests to run. On Debian/Ubuntu:

```bash
sudo apt-get install ffmpeg
```

On macOS:

```bash
brew install ffmpeg
```

---

## Running tests

```bash
pytest
```

`tests/test_policy.py` runs without ffmpeg. It exercises `analyze_metadata` as a pure function over synthetic ffprobe dicts. `tests/test_endpoints.py` requires ffmpeg and is skipped automatically when it is absent.

Run both suites with verbosity to see which tests skipped:

```bash
pytest -v
```

---

## Quality gates

All three gates must pass before a PR can merge. CI runs them automatically.

**Tests:**
```bash
pytest
```

**SAST (bandit at MEDIUM+ severity):**
```bash
bandit -r main.py -ll
```

Zero MEDIUM or HIGH findings are required. The six LOW findings from subprocess calls are expected and are excluded by the `-ll` flag.

**Dependency vulnerability scan:**
```bash
pip-audit -r requirements.txt --strict
```

---

## Adding an indicator

Indicators live in `SUSPICIOUS_PATTERNS` in `main.py`. Each entry needs four fields:

```python
{"id": "TAG_MY_MARKER", "severity": "high", "regex": r"<MY_MARKER>", "mask": False},
```

**id**: a stable string. SIEM and SOAR tools key on this value. Never reuse a retired ID. Prefix with `TAG_` for content indicators.

**severity**: `"low"` (adds 10 to risk score), `"medium"` (25), or `"high"` (40). Use `"high"` only for patterns that indicate active exploitation or credential exposure.

**regex**: a Python regular expression. It is compiled once with `re.IGNORECASE` so casing variants do not evade detection. Keep it specific enough to have a low false-positive rate against benign audio metadata.

**mask**: set to `True` when the matched text should not appear in the response even truncated. Use this for credentials and PII. dBA replaces the matched span with `***` in `value_snippet` and `Alert.value`.

After adding the entry, add a test in `tests/test_policy.py`:

```python
def test_my_marker_detected():
    r = raw(fmt={"format_name": "wav", "tags": {"comment": "<MY_MARKER>"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "TAG_MY_MARKER" in ids(inds)
```

If `mask=True`, add a masking test:

```python
def test_my_marker_is_masked():
    r = raw(fmt={"format_name": "wav", "tags": {"comment": "prefix <MY_MARKER> suffix"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    ind = next(i for i in inds if i.id == "TAG_MY_MARKER")
    assert "<MY_MARKER>" not in ind.value_snippet
    assert "***" in ind.value_snippet
```

---

## Adding a structural indicator

Structural indicators live in `_structural_indicators` in `main.py`. They fire on file-shape properties from the ffprobe JSON, independent of tag content. Follow the pattern of the existing checks: append an `Indicator` to `out` when the condition fires, use `detail` to describe the anomaly, and set `key`, `pattern`, and `value_snippet` to `None`.

Add a test in `tests/test_policy.py` that constructs a synthetic ffprobe dict that triggers the condition.

---

## Changing score weights or thresholds

`SEVERITY_WEIGHT` maps severity strings to score increments. `_decide_disposition` contains the per-mode threshold table. Both are in `main.py`.

`tests/test_policy.py` pins the exact numeric values in `test_severity_weights_in_audit_mode` and `test_disposition_*`. Update those tests when you change the numbers so the intent is documented.

---

## Pull request checklist

- All three quality gates pass locally.
- New behavior has a test that fails without the change.
- `SUSPICIOUS_PATTERNS` changes include a paired test.
- No em dashes, parenthetical feature lists, or filler words in commit messages or documentation prose.
- `SEVERITY_WEIGHT` or threshold changes update the corresponding test assertions.
