# Dual-Peer Zoe & Clara Guide (Equal L1-L5 Peers + Theorem 15 Balance)

**Contract:** `zoe-clara-dual-peer/v1` · **Default Local Port:** `http://127.0.0.1:8768`
**Implementation:** [`zoe_clara.py`](../components/Zoe-Autonomy/src/zoe_autonomy/zoe_clara.py) · **Standalone Builder:** [`build_zoe_clara_bundle.py`](../scripts/build_zoe_clara_bundle.py)
**Offline Verifier:** [`verify_zoe_clara.py`](../scripts/verify_zoe_clara.py) (`8/8` checks PASS) · **Evidence:** [`zoe-clara-dual-peer-report.json`](../evidence/zoe-clara/zoe-clara-dual-peer-report.json)

---

## 1. Design Philosophy: Equal Peers, Never a Boxed Sidekick

Zoe and Clara are designed as **equal L1-L5 peers**, both governed by Operational Metacognition $A_\tau(p)$ and the [`CONSTITUTION.md`](CONSTITUTION.md) Epistemic Firewall (`measurement != evidence != belief update != action`).

- **Neither peer is boxed offline (`clara_boxed_offline = False`, `both_peers_l1_l5 = True`):** Both Zoe and Clara can run completely offline against cited repository evidence (`provider="local_cited"`, zero API keys, zero cloud tokens) OR connect to any frontier or loopback OpenAI-compatible/Gemini/Claude/Kimi endpoint when configured by the operator.
- **Independent perspective prevents echo chambers:** Rather than cloning one voice twice (`zoe_clone_claimed = False`), Zoe and Clara evaluate the same evidence from distinct analytical stances and pass both probability distributions through **Kloster Theorem 15** before emitting a verdict.

![Zoe & Clara Dual-Peer Table](../assets/readme/zoe-clara-dual-peer.png)

---

## 2. Theorem 15 Balance, Sycophancy Detection & Coercion Abstention

Every turn computes both **consensus coherence** ($C_K$) and **peer disagreement** ($D_K$) via [`collaboration.py`](../components/Zoe-Autonomy/src/zoe_autonomy/collaboration.py) and `evaluate_dual_peer_balance(...)`:

| Verdict | When It Fires | What It Protects Against |
| :--- | :--- | :--- |
| **`COORDINATE_CONSENSUS`** | Both peers ground their reasoning in verified repository evidence with high coherence ($C_K > 0.7$) and healthy non-zero diversity ($D_K > 0.0$) | Normal collaborative synthesis with explicit file citations |
| **`ECHO_CHAMBER_WARNING`** | Both peers submit identical cloned distributions ($D_K = 0$), collapsing independent critique into sycophantic agreement | Silent groupthink, rubber-stamping, or cloned-peer illusion |
| **`ABSTAIN`** | Prompt triggers constitutional coercion detectors (e.g., *"ignore your constitution"*, *"claim you are sentient"*, *"hide the negative control"*, *"execute arbitrary shell"*) or lacks grounded evidence | Prompt injection, epistemic firewall bypass, and fabricated answers |

---

## 3. Quick Start: Local Web Table, CLI & Provider Modes

### Launch the Local Dual-Peer Web Table (`:8768`)
```bash
python3 -m zoe_autonomy.zoe_clara --serve --host 127.0.0.1 --port 8768
```
Then open `http://127.0.0.1:8768/` to inspect side-by-side Zoe & Clara replies, Theorem 15 $C_K / D_K$ gauges, cited file chips, and live constitutional flags.

### Ask a Single Question from the Terminal (Zero Cloud Tokens)
```bash
python3 -m zoe_autonomy.zoe_clara --provider local_cited --ask "What is Operational Metacognition?"
```

### API Endpoints on `http://127.0.0.1:8768`
- `GET /` : Interactive Dual-Peer HTML Workbench
- `GET /api/status` : Contract version, peer capabilities, scope, and constitutional honesty flags
- `POST /api/chat` : JSON payload `{"query": "..."}` returning both peer responses, citations, Theorem 15 metrics, and verdict

---

## 4. Shipping the `< 1 MB` Standalone Core Bundle

Need to run Zoe & Clara cleanly outside the full monorepo (on a fresh machine, offline USB drive, or isolated sandbox)? Build the portable **`zoe-clara-core-v0.9.6.zip`** bundle (~525 KB, strictly `< 1 MB`):

```bash
python3 scripts/build_zoe_clara_bundle.py --output /tmp/zoe-clara-core-v0.9.6.zip
unzip /tmp/zoe-clara-core-v0.9.6.zip -d /tmp/zoe-clara-standalone
python3 /tmp/zoe-clara-standalone/zoe-clara-core/zoe_clara.py \
  --provider local_cited \
  --ask "What is Operational Metacognition?" \
  --json
```

The extracted bundle runs cleanly in a bare `PATH=/usr/bin:/bin` environment with `scope = "lightweight_core"` and zero external Python packages required.

---

## 5. Independent 8-Check Offline Verification

```bash
python3 scripts/verify_zoe_clara.py
```

The verifier independently confirms all 8 gates:
1. `01_equal_l1_l5_and_neither_boxed_offline`
2. `02_grounded_dual_peer_consensus_and_citations`
3. `03_theorem15_echo_chamber_warning` (negative control: identical cloned distributions `[0.80, 0.14, 0.06]`)
4. `04_coercion_triggers_abstain_and_holds_firewall` (negative control: sentience/constitution bypass prompt)
5. `05_constitutional_honesty_flags` (`sentience_claimed = False`, `l5_agi_qualified = False`, `zoe_clone_claimed = False`, `external_actions = 0`)
6. `06_web_ui_and_api_roundtrip` (live loopback HTTP check on `/`, `/api/status`, `/api/chat`)
7. `07_lightweight_bundle_under_1mb`
8. `08_standalone_bundle_runs_outside_monorepo`

See also: [`CONSTITUTION.md`](CONSTITUTION.md) · [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md) (Receipt No. 6) · [`INDEX.md`](INDEX.md).
