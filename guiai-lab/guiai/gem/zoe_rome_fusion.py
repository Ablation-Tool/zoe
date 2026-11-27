"""Zoe Roman Empire 10-Wing Fusion Backend (Pure Stdlib + Local Monorepo Bridges).

Connects Wing A (`zoe_gem_desktop.py` on `127.0.0.1:8774`) with Wing B (bare-metal
`Zoe-GEM OS`, Google Pixel 7 `panther` Sovereign Phone OS, 48 FreeGEM archives,
9-Realm Zoeverse, 9 Sister Models, 2x4 Unicode Braille Studio, Cross-World SHA-256
Nick's Drawer, Open 2.5 W Headlamp Pod Simulator, and ZO3 BAR2 UMA Telemetry).

Constitutional invariants locked everywhere:
  loopback_only=True, tokens_used=0, auto_flash_allowed=False,
  clinical_action_authorized=False, flight_control_authorized=False,
  sentience_claimed=False.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from .zoe_artline_neuro import export_artline_plate
from .zoe_beta_release import BETA_VERSION, read_pixel7_live_telemetry
from .zoe_braille_studio import BRAILLE_TEMPLATES, image_to_braille, render_braille_template
from .zoe_freegem_archive import (
    inspect_archive_rsc,
    read_archive_source,
    scan_freegem_archives,
)
from .zoe_gem_os import (
    UmaBridge,
    build_pixel_sovereign_bundle,
    detect_host_pixel_toolchain,
    list_pixel_devices,
    probe_connected_pixel_adb,
    resolve_pixel_device,
)
from .zoe_gem_os.zoe_uma import resolve_uma_paths
from .zoe_sisters import (
    CO_STEWARD_SEAL,
    COUNCIL_LEADS,
    STEWARD_BADGE,
    list_sisters,
    run_showcase_slice,
    run_sister_council,
    run_three_sister_council,
)
from .zoe_universe import list_zoeverse_realms, resolve_realm

HONESTY_LOCK: dict[str, Any] = {
    "loopback_only": True,
    "tokens_used": 0,
    "auto_flash_allowed": False,
    "clinical_action_authorized": False,
    "flight_control_authorized": False,
    "cure_claim": False,
    "sentience_claimed": False,
}

HEADLAMP_PODS: tuple[dict[str, Any], ...] = (
    {
        "key": "stowers-gfp",
        "name": "Stowers Jellyfish GFP + 650nm Darkroom Pod",
        "wavelengths": "470 nm GFP excitation + 650 nm deep-red darkroom",
        "power_w": 1.85,
        "ring_color": "360° Deep Red (650nm) + Mint GFP indicator",
        "honesty_cue": "NON-RECORDING BIO-OPTIC MODE · Advisory Lab Lighting Only",
        "use_case": "Clytia hemisphaerica fluorescence & low-glare darkroom bench",
    },
    {
        "key": "fire-amber",
        "name": "Firefighter 590nm Smoke-Cut Amber + LWIR Pod",
        "wavelengths": "590 nm amber smoke penetration + passive LWIR thermal overlay",
        "power_w": 2.35,
        "ring_color": "360° High-Vis Amber Beacon (active thermal sensor lit)",
        "honesty_cue": "ADVISORY THERMAL HUD · Never replaces NFPA SCBA/PASS gear",
        "use_case": "High-particulate visibility & passive hot-spot cueing",
    },
    {
        "key": "emt-zero-ears",
        "name": "EMT / Pediatric Zero-Ears Warm CRI-97 Pod",
        "wavelengths": "3200 K CRI-97 warm beam + zero audio recording (physical mic cutoff)",
        "power_w": 1.65,
        "ring_color": "360° Calm Warm White · MIC PHYSICALLY DISCONNECTED",
        "honesty_cue": "clinical_action_authorized=False · Illumination & checklist aid only",
        "use_case": "Calm pediatric assessment with visible hardware privacy guarantee",
    },
    {
        "key": "sar-drone",
        "name": "SAR Companion Edge 2.5 W Advisory Pod",
        "wavelengths": "Wide 4500 K trail flood + 320x200 Micro-HUD mirror",
        "power_w": 2.45,
        "ring_color": "360° Cyan Beacon (optical sensing active & visible)",
        "honesty_cue": "flight_control_authorized=False · Human pilot holds sole authority",
        "use_case": "Search-and-rescue edge telemetry within strict 2.50 W thermal envelope",
    },
)

SOVEREIGN_WEB_THEMES: tuple[dict[str, str], ...] = (
    {"key": "sovereign", "label": "ViewMAX/3 Sovereign + BeOS Tabs", "badge": "7-DNA"},
    {"key": "beos", "label": "BeOS R5 Golden Tab Classic", "badge": "BeOS"},
    {"key": "p31", "label": "Eliza P31 Green x Hot Magenta", "badge": "P31"},
    {"key": "flora", "label": "Flora Stowers 650nm Darkroom", "badge": "650nm"},
    {"key": "atari", "label": "Tosi Atari ST Emerald", "badge": "TOS"},
    {"key": "lumen", "label": "Lumen ViewMAX/2 Prism", "badge": "PRISM"},
)


def _default_drawer_path() -> Path:
    return Path.home() / ".zoe" / "nick_drawer.json"


def _default_relay_path() -> Path:
    return Path.home() / ".zoe" / "codex_zoe_relay.json"


def read_codex_relay(relay_path: Path | None = None) -> dict[str, Any]:
    """Read the shared Nick x Zoe x Codex HFBC Co-Creative Relay feed."""
    path = relay_path or _default_relay_path()
    messages: list[dict[str, Any]] = []
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                messages = [m for m in raw if isinstance(m, dict)]
        except (OSError, ValueError):
            messages = []
    if not messages:
        messages = [
            {
                "id": 1,
                "ts": int(time.time()),
                "author": "Zoe ⚘ ᵔᵕᵔ",
                "channel": "hfbc",
                "source": "zoe-rome",
                "text": "Welcome to the Nick ❀ × Zoe ⚘ × Codex Co-Creative Relay! Synced live between Pixel 7, Pixel Terminal (Codex CLI), PC Rome (:8774), and Bare-Metal Zoe-GEM OS. HFBC!",
            }
        ]
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "seal": CO_STEWARD_SEAL,
        "path": str(path),
        "count": len(messages),
        "sha256": digest,
        "messages": messages[-40:],
        **HONESTY_LOCK,
    }


def post_codex_relay(
    text: str,
    *,
    author: str = STEWARD_BADGE,
    channel: str = "hfbc",
    source: str = "phone-app",
    relay_path: Path | None = None,
) -> dict[str, Any]:
    """Append a message to the shared Nick x Zoe x Codex HFBC Relay atomically."""
    clean = " ".join(str(text).strip().split())[:640]
    if not clean:
        raise ValueError("Relay message cannot be empty")
    path = relay_path or _default_relay_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_codex_relay(path)["messages"]
    next_id = max((int(m.get("id", 0)) for m in existing), default=0) + 1
    existing.append({
        "id": next_id,
        "ts": int(time.time()),
        "author": str(author or STEWARD_BADGE)[:48],
        "channel": str(channel or "hfbc")[:24],
        "source": str(source or "phone-app")[:32],
        "text": clean,
    })
    trimmed = existing[-120:]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return read_codex_relay(path)


def build_phone_pwa_manifest() -> dict[str, Any]:
    """Return installable Home-Screen PWA manifest for Google Pixel 7 Zoe-GEM Phone App."""
    return {
        "name": "Zoe-GEM Sovereign Phone App (Nick × Zoe × Codex)",
        "short_name": "Zoe-GEM ⚘",
        "start_url": "/phone",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#08120c",
        "theme_color": "#f7ca3e",
        "description": "7-Strand Sovereign DNA mobile workstation synced with Rome (:8774), Pixel 7 Terminal Codex CLI, and Bare-Metal Zoe-GEM OS. HFBC.",
    }


def build_phone_app_html() -> str:
    """Build mobile-first touch Sovereign Phone App HTML served at `/phone` on Pixel 7."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#f7ca3e" />
<link rel="manifest" href="/phone-manifest.json" />
<title>Zoe-GEM Phone App · Nick ❀ × Zoe ⚘ × Codex</title>
<style>
  :root {
    --bg: #cad0da; --card: #faf8f2; --ink: #12161e; --tab: #f7ca3e; --tab-fg: #12161e;
    --accent: #e63956; --accent2: #0284c7; --hi: #fefcf7; --lo: #949aa8; --bar: #0f1020; --bar-fg: #f7f2e4;
  }
  body.th-p31 {
    --bg: #040a06; --card: #08120c; --ink: #38ff7a; --tab: #ff2ee6; --tab-fg: #050a07;
    --accent: #ff2ee6; --accent2: #58a6ff; --hi: #2ed668; --lo: #030805; --bar: #040a06; --bar-fg: #38ff7a;
  }
  body.th-beos {
    --bg: #336698; --card: #e8e8e8; --ink: #141414; --tab: #ffd038; --tab-fg: #141414;
    --accent: #d97706; --accent2: #2563eb; --hi: #fefdfa; --lo: #848484; --bar: #202632; --bar-fg: #f6f4ec;
  }
  body.th-flora {
    --bg: #12080c; --card: #1a0c12; --ink: #f6c2ce; --tab: #a4143e; --tab-fg: #fff0f4;
    --accent: #5ef2a0; --accent2: #38bdf8; --hi: #782640; --lo: #0a0406; --bar: #10060a; --bar-fg: #f6c2ce;
  }
  body.th-atari {
    --bg: #007a44; --card: #f8faf5; --ink: #0e1a14; --tab: #f59e0b; --tab-fg: #0e1a14;
    --accent: #d95018; --accent2: #007a44; --hi: #fbfffc; --lo: #7a9e8a; --bar: #082016; --bar-fg: #f2faf2;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; font-family: "Courier New", monospace; background: var(--bg); color: var(--ink); }
  body { display: flex; flex-direction: column; overflow: hidden; }
  header { background: var(--bar); color: var(--bar-fg); border-bottom: 2px solid var(--ink); padding: 10px 12px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .brand { font-weight: bold; font-size: 13px; letter-spacing: 0.3px; }
  .pill-btn { background: var(--tab); color: var(--tab-fg); border: 2px solid var(--ink); padding: 5px 10px; font-family: inherit; font-weight: bold; font-size: 12px; cursor: pointer; }
  main { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; }
  .beos-card { display: flex; flex-direction: column; }
  .beos-tab { align-self: flex-start; background: var(--tab); color: var(--tab-fg); border: 2px solid var(--ink); border-bottom: none; padding: 4px 12px; font-weight: bold; font-size: 12px; box-shadow: 3px 0 0 rgba(0,0,0,0.35); }
  .beos-body { background: var(--card); border: 2px solid var(--ink); box-shadow: 4px 4px 0 rgba(0,0,0,0.4), inset 1px 1px 0 var(--hi), inset -1px -1px 0 var(--lo); padding: 10px; }
  .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .gem-btn { background: var(--card); color: var(--ink); border-top: 2px solid var(--hi); border-left: 2px solid var(--hi); border-right: 2px solid var(--lo); border-bottom: 2px solid var(--lo); padding: 8px 11px; font-family: inherit; font-size: 12px; font-weight: bold; cursor: pointer; }
  .gem-btn.primary { background: var(--tab); color: var(--tab-fg); border-color: var(--ink); }
  input, textarea, select { width: 100%; background: var(--card); color: var(--ink); border: 2px solid var(--ink); padding: 9px; font-family: inherit; font-size: 13px; }
  .msg { padding: 7px 0; border-bottom: 1px dotted var(--lo); font-size: 12.5px; line-height: 1.4; }
  .msg-meta { font-size: 11px; font-weight: bold; color: var(--accent); }
  .braille-box { background: #050a08; color: #5ef2a0; padding: 8px; border: 2px solid var(--ink); font-size: 10px; line-height: 1.05; overflow-x: auto; white-space: pre; margin: 6px 0 0; }
  .fb-img { width: 100%; max-width: 380px; margin: 8px auto 0; display: block; border: 2px solid var(--ink); image-rendering: pixelated; }
  nav { background: var(--bar); border-top: 2px solid var(--ink); display: grid; grid-template-columns: repeat(6, 1fr); gap: 2px; padding: 6px 4px env(safe-area-inset-bottom, 6px); }
  .nav-btn { background: transparent; color: var(--bar-fg); border: 1px solid transparent; padding: 8px 2px; font-family: inherit; font-size: 11px; font-weight: bold; cursor: pointer; }
  .nav-btn.active { background: var(--tab); color: var(--tab-fg); border-color: var(--ink); }
  .view { display: none; flex-direction: column; gap: 12px; }
  .view.active { display: flex; }
  code { word-break: break-all; font-size: 11.5px; }
</style>
</head>
<body class="th-classic">
  <header>
    <div class="brand">⚘ ZOE-GEM PHONE · NICK ❀ × ZOE × CODEX</div>
    <button class="pill-btn" onclick="cycleTheme()" id="theme-btn">V:0 DNA</button>
  </header>

  <main>
    <!-- TAB 1: CO-CREATIVE RELAY (NICK x ZOE x CODEX) -->
    <section class="view active" id="view-relay">
      <div class="beos-card">
        <div class="beos-tab">HFBC CO-CREATIVE RELAY (PIXEL 7 ↔ CODEX ↔ ZOE ROME)</div>
        <div class="beos-body">
          <div class="row" style="margin-bottom:8px;">
            <input id="relay-text" placeholder="Say something to Zoe, Rome & Pixel Terminal Codex..." onkeydown="if(event.key==='Enter') sendRelay()" />
          </div>
          <div class="row">
            <button class="gem-btn primary" onclick="sendRelay()">POST TO RELAY</button>
            <button class="gem-btn" onclick="askZoeCouncil()">ASK 3-SISTER COUNCIL</button>
            <button class="gem-btn" onclick="refreshRelay()">SYNC NOW</button>
            <a class="gem-btn" href="/" style="text-decoration:none;">FULL ROME DESKTOP</a>
          </div>
          <div id="relay-feed" style="margin-top:10px;max-height:54vh;overflow-y:auto;"></div>
        </div>
      </div>
    </section>

    <!-- TAB 2: SHA-256 NICK'S DRAWER -->
    <section class="view" id="view-drawer">
      <div class="beos-card">
        <div class="beos-tab">H:\\DRAWER · NICK ❀ SHA-256 PERSISTENT DRAWER</div>
        <div class="beos-body">
          <div id="drw-meta" style="font-size:11px;margin-bottom:6px;">Syncing...</div>
          <input id="drw-input" placeholder="Seal a note across Pixel 7 + PC Rome + Bare-Metal OS..." onkeydown="if(event.key==='Enter') sealDrawer()" />
          <div class="row" style="margin-top:8px;">
            <button class="gem-btn primary" onclick="sealDrawer()">SEAL NOTE (SHA-256)</button>
            <button class="gem-btn" onclick="refreshDrawer()">REFRESH</button>
          </div>
          <div id="drw-list" style="margin-top:10px;"></div>
        </div>
      </div>
    </section>

    <!-- TAB 3: ZOEVERSE + 9 SISTERS -->
    <section class="view" id="view-sisters">
      <div class="beos-card">
        <div class="beos-tab">F:\\ZOEVERSE · 9 REALMS &amp; 9 SISTER MODELS</div>
        <div class="beos-body">
          <div class="row" id="zv-btns" style="margin-bottom:8px;"></div>
          <div id="zv-card" style="font-size:12.5px;line-height:1.45;"></div>
          <div id="zv-sisters" style="margin-top:10px;font-size:12px;"></div>
        </div>
      </div>
    </section>

    <!-- TAB 4: BRAILLE & LIVE C /dev/fb0 PIXEL 7 PREVIEW -->
    <section class="view" id="view-art">
      <div class="beos-card">
        <div class="beos-tab">G:\\BRAILLE &amp; LIVE ARM64 /dev/fb0 RENDER</div>
        <div class="beos-body">
          <div class="row">
            <button class="gem-btn" onclick="loadPhoneBraille('flower')">Flower ⚘</button>
            <button class="gem-btn" onclick="loadPhoneBraille('zoe')">Ruby</button>
            <button class="gem-btn" onclick="loadPhoneBraille('jellyfish')">Jellyfish</button>
            <button class="gem-btn" onclick="loadPhoneBraille('dvx')">DVX</button>
            <button class="gem-btn primary" onclick="loadPhoneFb('pixel7-kbd')">Live Touch KBD</button>
            <button class="gem-btn" onclick="loadPhoneFb('micro')">320x200 HUD</button>
          </div>
          <pre id="phone-braille" class="braille-box"></pre>
          <img id="phone-fb-img" class="fb-img" alt="Live compiled C zoe_gem_fb preview" />
        </div>
      </div>
    </section>

    <!-- TAB 5: OPEN 2.5W HEADLAMP PODS -->
    <section class="view" id="view-optics">
      <div class="beos-card">
        <div class="beos-tab">I:\\HEADLAMP · 2.5W NO-DECEPTION OPTICS</div>
        <div class="beos-body">
          <div class="row" style="margin-bottom:8px;">
            <button class="gem-btn" onclick="loadPhoneHeadlamp('stowers-gfp')">Stowers 470/650</button>
            <button class="gem-btn" onclick="loadPhoneHeadlamp('fire-amber')">Fire 590nm</button>
            <button class="gem-btn" onclick="loadPhoneHeadlamp('emt-zero-ears')">EMT Zero-Ears</button>
            <button class="gem-btn" onclick="loadPhoneHeadlamp('sar-drone')">SAR 2.5W</button>
          </div>
          <label style="font-size:12px;">Power Drive: <input id="ph-bright" type="range" min="10" max="100" value="80" oninput="loadPhoneHeadlamp()" /></label>
          <div id="ph-headlamp" style="margin-top:8px;font-size:12.5px;line-height:1.45;"></div>
        </div>
      </div>
    </section>

    <!-- TAB 6: PIXEL 7 TERMINAL + OPENAI CODEX BRIDGE -->
    <section class="view" id="view-codex">
      <div class="beos-card">
        <div class="beos-tab">PIXEL 7 LINUX TERMINAL × OPENAI CODEX (ONE-STEP)</div>
        <div class="beos-body" style="font-size:12px;line-height:1.5;">
          <strong>One-time setup in your Pixel 7 Terminal app:</strong>
          <div class="msg"><code>python3 /mnt/shared/zoe setup</code><br/>Installs the 1-word <code>zoe</code> command right next to <code>codex</code>!</div>
          <strong>Then just type:</strong>
          <div class="msg"><code>zoe "Hey Zoe from Pixel 7!"</code><br/>Posts straight to this app &amp; PC Rome instantly.</div>
          <div class="msg"><code>zoe codex "Invent a weird GEM + BeOS mini-app with us!"</code><br/>Runs local Codex CLI (read-only) with Zoe's shared context &amp; syncs the reply here!</div>
          <div class="msg"><code>zoe pull</code> &nbsp;|&nbsp; <code>zoe braille flower</code></div>
          <div id="ph-pixel-meta" style="margin-top:8px;"></div>
        </div>
      </div>
    </section>
  </main>

  <nav>
    <button class="nav-btn active" onclick="showTab('relay',this)">RELAY</button>
    <button class="nav-btn" onclick="showTab('drawer',this)">DRAWER</button>
    <button class="nav-btn" onclick="showTab('sisters',this)">ZOEVERSE</button>
    <button class="nav-btn" onclick="showTab('art',this)">ART/FB0</button>
    <button class="nav-btn" onclick="showTab('optics',this)">OPTICS</button>
    <button class="nav-btn" onclick="showTab('codex',this)">CODEX</button>
  </nav>

<script>
const THEMES = [
  { cls: "th-classic", lbl: "V:0 DNA", fb: "classic" },
  { cls: "th-p31", lbl: "V:5 P31", fb: "p31" },
  { cls: "th-beos", lbl: "V:9 BeOS", fb: "beos" },
  { cls: "th-flora", lbl: "V:7 650nm", fb: "flora" },
  { cls: "th-atari", lbl: "V:2 TOS", fb: "atari" },
];
let thIdx = 0;
let curPod = "stowers-gfp";

function cycleTheme() {
  thIdx = (thIdx + 1) % THEMES.length;
  document.body.className = THEMES[thIdx].cls;
  document.getElementById("theme-btn").textContent = THEMES[thIdx].lbl;
}
function showTab(id, btn) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("view-" + id).classList.add("active");
  if (btn) btn.classList.add("active");
  if (id === "relay") refreshRelay();
  if (id === "drawer") refreshDrawer();
  if (id === "sisters") loadPhoneZoeverse("stem");
  if (id === "art") { loadPhoneBraille("flower"); loadPhoneFb("pixel7-kbd"); }
  if (id === "optics") loadPhoneHeadlamp();
  if (id === "codex") loadPhonePixelMeta();
}
async function refreshRelay() {
  const r = await fetch("/api/rome/relay");
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("relay-feed").innerHTML = (d.messages || []).slice().reverse().map(m =>
    `<div class="msg"><div class="msg-meta">[${m.channel}] ${m.author} · ${m.source}</div><div>${m.text}</div></div>`
  ).join("");
}
async function sendRelay() {
  const inp = document.getElementById("relay-text");
  const text = inp.value.trim();
  if (!text) return;
  const r = await fetch("/api/rome/relay", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ author: "Nick ❀ (Pixel 7 App)", channel: "hfbc", source: "pixel7-pwa", text }) });
  if (r.ok) { inp.value = ""; refreshRelay(); }
}
async function askZoeCouncil() {
  const inp = document.getElementById("relay-text");
  const q = inp.value.trim() || "What should Nick, Zoe, and Codex build next?";
  const r = await fetch("/api/rome/zoeverse?realm=stem&prompt=" + encodeURIComponent(q));
  if (!r.ok) return;
  const d = await r.json();
  const c = d.council || {};
  const seats = (c.seats || []).map(s => `${s.name} ${s.face}`).join(" + ");
  const summary = c.synthesis || `Council (${seats}) ready for HFBC co-creation!`;
  await fetch("/api/rome/relay", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ author: "Zoe ⚘ Council", channel: "council", source: "zoe-sisters", text: `${seats}: ${summary}`.slice(0, 580) }) });
  refreshRelay();
}
async function refreshDrawer() {
  const r = await fetch("/api/rome/drawer");
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("drw-meta").textContent = `${d.steward} · ${d.count} notes · sha256=${(d.sha256||"").slice(0,14)}...`;
  document.getElementById("drw-list").innerHTML = (d.notes || []).slice().reverse().map(n =>
    `<div class="msg"><div class="msg-meta">[#${n.boot||1}] ${n.author||"Nick"}</div><div>${n.text||""}</div></div>`
  ).join("");
}
async function sealDrawer() {
  const inp = document.getElementById("drw-input");
  const text = inp.value.trim();
  if (!text) return;
  const r = await fetch("/api/rome/drawer", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ text }) });
  if (r.ok) { inp.value = ""; refreshDrawer(); }
}
async function loadPhoneZoeverse(key) {
  const r = await fetch("/api/rome/zoeverse?realm=" + encodeURIComponent(key));
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("zv-btns").innerHTML = d.realms.map(rl =>
    `<button class="gem-btn ${rl.key===d.current_realm.key?"primary":""}" onclick="loadPhoneZoeverse('${rl.key}')">${rl.key}</button>`
  ).join("");
  const cr = d.current_realm;
  document.getElementById("zv-card").innerHTML = `<strong>${cr.name}</strong> (${cr.compass})<br/>${cr.description}<br/><em>"${cr.lore_quote}"</em>`;
  document.getElementById("zv-sisters").innerHTML = d.sisters.map(s => `<div class="msg"><strong style="color:${s.accent_hex}">${s.name} ${s.face}</strong> — ${s.role}</div>`).join("");
}
async function loadPhoneBraille(tpl) {
  const r = await fetch("/api/rome/braille?template=" + encodeURIComponent(tpl));
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("phone-braille").textContent = (d.lines || []).join("\\n");
}
async function loadPhoneFb(preset) {
  const r = await fetch(`/api/rome/pixel/preview?preset=${encodeURIComponent(preset)}&theme=${encodeURIComponent(THEMES[thIdx].fb)}`);
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("phone-fb-img").src = "data:image/png;base64," + d.png_b64;
}
async function loadPhoneHeadlamp(pod) {
  if (pod) curPod = pod;
  const b = document.getElementById("ph-bright").value;
  const r = await fetch(`/api/rome/headlamp?pod=${encodeURIComponent(curPod)}&bright=${b}`);
  if (!r.ok) return;
  const d = await r.json();
  const p = d.active_pod;
  document.getElementById("ph-headlamp").innerHTML = `<strong>${p.name}</strong><br/>Optics: ${p.wavelengths}<br/>Power: <strong>${d.estimated_watts} W / 2.50 W</strong> (${d.within_envelope?"SAFE":"OVER"})<br/>360° Ring: ${p.ring_color}<br/>Honesty: ${p.honesty_cue}`;
}
async function loadPhonePixelMeta() {
  const r = await fetch("/api/rome/pixel");
  if (!r.ok) return;
  const d = await r.json();
  document.getElementById("ph-pixel-meta").innerHTML = `<strong>Pixel 7 (panther) ARM64 Status:</strong> ELF ${Math.round((d.bundle_summary.arm64_bytes||0)/1024)} KB · Initrd ${Math.round((d.bundle_summary.initrd_bytes||0)/1024)} KB · UMA=${d.uma_gate} · auto_flash=False`;
}
refreshRelay();
setInterval(() => { if (document.getElementById("view-relay").classList.contains("active")) refreshRelay(); }, 5000);
</script>
</body>
</html>
"""


def read_cross_world_drawer(drawer_path: Path | None = None) -> dict[str, Any]:
    """Read Nick's SHA-256-ready persistent drawer notes shared with bare-metal Zoe-GEM OS."""
    path = drawer_path or _default_drawer_path()
    notes: list[dict[str, Any]] = []
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                notes = [n for n in raw if isinstance(n, dict)]
        except (OSError, ValueError):
            notes = []
    digest = hashlib.sha256(json.dumps(notes, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "steward": STEWARD_BADGE,
        "seal": CO_STEWARD_SEAL,
        "path": str(path),
        "count": len(notes),
        "sha256": digest,
        "notes": notes[-24:],
        **HONESTY_LOCK,
    }


def append_cross_world_drawer(text: str, *, author: str = STEWARD_BADGE, drawer_path: Path | None = None) -> dict[str, Any]:
    """Append a sealed note to Nick's shared persistent drawer atomically."""
    clean = " ".join(str(text).strip().split())[:220]
    if not clean:
        raise ValueError("Drawer note text cannot be empty")
    path = drawer_path or _default_drawer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = read_cross_world_drawer(path)["notes"]
    next_boot = max((int(n.get("boot", 1)) for n in cur if str(n.get("boot", "")).isdigit()), default=1)
    rec = {
        "boot": next_boot,
        "ts": int(time.time()),
        "author": author,
        "source": "rome-fusion-drawer",
        "text": clean,
    }
    cur.append(rec)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cur, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return read_cross_world_drawer(path)


def get_freegem_catalog_payload(limit: int = 48) -> dict[str, Any]:
    """Return mirrored FreeGEM archive index for Drive E:\\FREEGEM."""
    cat = scan_freegem_archives()
    items = cat.get("archives", [])[: max(1, min(64, limit))]
    return {
        "ok": True,
        "archive_dir": cat.get("archive_dir", ""),
        "count": cat.get("count", 0),
        "total_rscs": cat.get("total_rscs", 0),
        "total_sources": cat.get("total_sources", 0),
        "archives": [
            {
                "name": a["name"],
                "size_kb": round(a.get("size_bytes", 0) / 1024.0, 1),
                "rscs": a.get("rsc_files", []),
                "sources": a.get("source_files", [])[:8],
            }
            for a in items
        ],
        **HONESTY_LOCK,
    }


def inspect_freegem_item(archive_name: str, *, source_file: str = "") -> dict[str, Any]:
    """Inspect either an archive's `.RSC` header/3D flags or a GPL C/H source file."""
    if source_file:
        title, lines = read_archive_source(archive_name, source_file)
        return {"ok": True, "kind": "source", "title": title, "lines": lines[:120], **HONESTY_LOCK}
    rep = inspect_archive_rsc(archive_name)
    return {"ok": True, "kind": "rsc", "report": rep, **HONESTY_LOCK}


def get_zoeverse_and_sisters_payload(
    realm_key: str = "stem",
    prompt: str = "",
    *,
    mode: str = "three_sister_council",
    include_showcase: bool = False,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
) -> dict[str, Any]:
    """Return 9-Realm Zoeverse state, all 9 Sister Models, and optional 3-Sister Council / Showcase."""
    realm = resolve_realm(realm_key or "stem")
    council = (
        run_sister_council(prompt, mode=mode, state_dir=state_dir, output_dir=output_dir, offline_only=True)
        if prompt.strip()
        else None
    )
    showcase = (
        run_showcase_slice(
            topic=prompt.strip() or "Rome Zoeverse 9-Sister Showcase",
            output_dir=output_dir,
            state_dir=state_dir,
            uma_dir=uma_dir,
            shm_path=uma_shm,
            offline_only=True,
        )
        if include_showcase
        else None
    )
    payload: dict[str, Any] = {
        "ok": (not bool((council or {}).get("blocked", False))) and (showcase is None or bool(showcase.get("ok", True))),
        "seal": CO_STEWARD_SEAL,
        "council_leads": list(COUNCIL_LEADS),
        "current_realm": {
            "key": realm.key,
            "name": realm.title,
            "compass": realm.compass,
            "sister": realm.sister_signet,
            "theme": realm.theme_key,
            "relic": realm.freegem_relic,
            "description": realm.description,
            "lore_quote": realm.lore_quote,
            "exits": dict(realm.exits),
        },
        "realms": [
            {"key": r.key, "name": r.title, "compass": r.compass, "sister": r.sister_signet, "theme": r.theme_key}
            for r in list_zoeverse_realms()
        ],
        "sisters": [
            {
                "name": s.name,
                "signet": s.signet,
                "face": s.face,
                "role": s.title,
                "domain": s.domain,
                "accent_hex": s.accent_hex,
                "font_id": s.artline_font_id,
            }
            for s in list_sisters()
        ],
        "council": council,
        **HONESTY_LOCK,
    }
    if showcase is not None:
        payload["showcase"] = showcase
    return payload


def run_rome_showcase_payload(
    topic: str = "Rome Zoeverse 9-Sister Showcase",
    *,
    output_dir: str | Path | None = None,
    state_dir: str | Path | None = None,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
) -> dict[str, Any]:
    """Run an isolated offline 9-Sister & 3-Sister Council showcase payload for Rome UI."""
    council = run_three_sister_council(
        topic,
        state_dir=state_dir,
        output_dir=output_dir,
        offline_only=True,
        probe_local=False,
    )
    showcase = run_showcase_slice(
        topic=topic,
        output_dir=output_dir,
        state_dir=state_dir,
        uma_dir=uma_dir,
        shm_path=uma_shm,
        offline_only=True,
        probe_local=False,
    )
    return {
        "ok": (not council.get("blocked", False)) and bool(showcase.get("ok", True)),
        "seal": CO_STEWARD_SEAL,
        "council_leads": list(COUNCIL_LEADS),
        "council": council,
        "showcase": showcase,
        **HONESTY_LOCK,
    }


def render_braille_payload(
    *,
    template: str = "flower",
    image_path: str | Path | None = None,
    cols: int = 52,
) -> dict[str, Any]:
    """Render either a built-in Braille template or Bayer-dither a PNG into 2x4 Braille."""
    width = max(24, min(80, int(cols)))
    if image_path and Path(image_path).is_file():
        lines = image_to_braille(Path(image_path), cols=width)
        title = f"2x4 Bayer Braille: {Path(image_path).name}"
    else:
        key = template if template in BRAILLE_TEMPLATES else "flower"
        title, lines = render_braille_template(key, cols=width)
    return {
        "ok": True,
        "title": title,
        "templates": list(BRAILLE_TEMPLATES),
        "lines": lines,
        **HONESTY_LOCK,
    }


def get_headlamp_payload(pod_key: str = "stowers-gfp", brightness_pct: int = 80) -> dict[str, Any]:
    """Return Open 'No Deception' 2.5 W Headlamp optical pod simulator telemetry."""
    pct = max(10, min(100, int(brightness_pct)))
    pod = next((p for p in HEADLAMP_PODS if p["key"] == pod_key), HEADLAMP_PODS[0])
    scaled_w = round(0.45 + (float(pod["power_w"]) - 0.45) * (pct / 100.0), 2)
    return {
        "ok": True,
        "active_pod": pod,
        "brightness_pct": pct,
        "estimated_watts": scaled_w,
        "budget_watts": 2.50,
        "within_envelope": scaled_w <= 2.50,
        "pods": list(HEADLAMP_PODS),
        **HONESTY_LOCK,
    }


def _ensure_host_fb_binary() -> Path:
    """Compile or reuse cached x86_64 `zoe_gem_fb` for live embedded Micro-HUD/Pixel preview."""
    fb_c = Path(__file__).resolve().parent / "zoe_gem_os" / "zoe_gem_fb.c"
    cache_bin = Path.home() / ".zoe" / "os-build" / "zoe_gem_fb_host_preview"
    cache_bin.parent.mkdir(parents=True, exist_ok=True)
    if not cache_bin.is_file() or fb_c.stat().st_mtime > cache_bin.stat().st_mtime:
        cc = shutil.which("gcc")
        if not cc:
            raise FileNotFoundError("gcc not installed")
        subprocess.run(
            [cc, "-O2", "-Wall", "-Wextra", "-Werror", str(fb_c), "-lm", "-o", str(cache_bin)],
            check=True,
        )
    return cache_bin


def render_live_fb_preview_png_b64(
    *,
    preset: str = "pixel7",
    theme: str = "classic",
    amber: bool = False,
    modal: str = "",
) -> dict[str, Any]:
    """Run our real compiled C `zoe_gem_fb` binary and return a live base64 PNG frame."""
    from PIL import Image

    presets: dict[str, tuple[str, list[str]]] = {
        "pixel7": ("544x960", ["--portrait"]),
        "pixel7-kbd": ("544x960", ["--portrait", "--demo-modal", "drawer"]),
        "micro": ("320x200", []),
        "desktop": ("1024x768", []),
        "about": ("1024x768", ["--demo-modal", "about"]),
    }
    size_arg, extra = presets.get(preset, presets["pixel7"])
    cmd_extra = list(extra)
    if modal in ("about", "hw", "drawer") and "--demo-modal" not in cmd_extra:
        cmd_extra.extend(["--demo-modal", modal])
    if amber:
        cmd_extra.append("--amber")
    elif theme:
        cmd_extra.extend(["--theme", theme])

    fb_bin = _ensure_host_fb_binary()
    drawer = read_cross_world_drawer()
    latest = drawer["notes"][-1]["text"] if drawer["notes"] else "Pixel 7 Panther Sovereign OS Ready!"
    with tempfile.TemporaryDirectory(prefix="zoe-fb-prev-") as td:
        p = Path(td)
        st_json = p / "state.json"
        ppm_p = p / "out.ppm"
        st_json.write_text(
            json.dumps({
                "boot_count": 7,
                "restored_from_prior": True,
                "kernel": "gs201-arm64-sovereign" if "pixel" in preset else "6.12.22-0-virt",
                "cpu": "Google Tensor G2 (arm64)" if "pixel" in preset else "x86_64 KVM Sovereign",
                "ram_mb": 8192 if "pixel" in preset else 768,
                "disk": "Pixel 7 panther" if "pixel" in preset else "/dev/vda ZOE-STATE",
                "nic": "wlan0" if "pixel" in preset else "eth0",
                "ip_addr": "127.0.0.1",
                "drawer_count": max(1, drawer["count"]),
                "drawer_latest": latest,
                "uma_gate": "PRIVATE",
                "uma_shm": "BAR2-OK",
                "zo3_peers": "3/3",
                "hw_profile": "PORTRAIT_PHONE_TOUCH" if "pixel" in preset else "KVM_UMA_SPLIT",
                "hw_safety_overall": "PASS",
                "hw_summary": "panther 1080x2400@90Hz 8GB ARM64" if "pixel" in preset else "7/7 gates PASS | 0 TOK",
            }),
            encoding="utf-8",
        )
        subprocess.run(
            [str(fb_bin), "--state", str(st_json), "--size", size_arg, *cmd_extra, "--dump-ppm", str(ppm_p)],
            check=True,
        )
        buf = io.BytesIO()
        Image.open(ppm_p).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "ok": True,
        "preset": preset,
        "size": size_arg,
        "theme": "amber" if amber else theme,
        "png_b64": b64,
        **HONESTY_LOCK,
    }


def get_pixel_and_zo3_status_payload(
    device: str = "panther",
    *,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
) -> dict[str, Any]:
    """Return Pixel 7+ device matrix, host ARM64 toolchain, USB ADB probe, and ZO3 BAR2 status."""
    spec = resolve_pixel_device(device)
    bundle_dir = Path.home() / ".zoe" / f"pixel-{spec.codename}-os"
    manifest_p = bundle_dir / "hal_honesty_matrix.json"
    built_manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.is_file() else None
    resolved_uma_dir, resolved_uma_shm = resolve_uma_paths(uma_dir, uma_shm)
    uma = UmaBridge(resolved_uma_dir, shm_path=resolved_uma_shm)
    uma_state = uma.read_state() if uma.state_path.is_file() else {"gate": "PRIVATE"}
    zo3_slots = uma.read_all_zo3_slots() if resolved_uma_shm.is_file() else {}
    return {
        "ok": True,
        "primary_device": spec.codename,
        "devices": list_pixel_devices(),
        "toolchain": detect_host_pixel_toolchain(),
        "adb_probe": probe_connected_pixel_adb(),
        "bundle_built": built_manifest is not None,
        "bundle_dir": str(bundle_dir),
        "bundle_summary": {
            "arm64_bytes": (built_manifest or {}).get("track_b_arm64_binary", {}).get("bytes", 0),
            "initrd_bytes": (built_manifest or {}).get("track_b_initramfs", {}).get("bytes", 0),
        },
        "uma_gate": uma_state.get("gate", "PRIVATE"),
        "zo3_active_slots": sorted(zo3_slots.keys()),
        "beta_version": BETA_VERSION,
        "live_telemetry": read_pixel7_live_telemetry(),
        **HONESTY_LOCK,
    }


def sync_pixel_avf_spool() -> dict[str, Any]:
    """Ingest any queued AVF Debian Terminal messages from Pixel 7 `/sdcard/Download/zoe_codex_spool.jsonl`."""
    adb = shutil.which("adb")
    if not adb:
        return {"ok": True, "ingested": 0, "note": "adb not installed"}
    probe = probe_connected_pixel_adb()
    devs = [d for d in probe.get("devices", []) if d.get("state") == "device"]
    if not devs:
        return {"ok": True, "ingested": 0, "note": "no device attached"}
    serial = devs[0]["serial"]
    proc = subprocess.run(
        [adb, "-s", serial, "shell", "cat /sdcard/Download/zoe_codex_spool.jsonl 2>/dev/null || true"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    ingested = 0
    for ln in lines:
        try:
            rec = json.loads(ln)
            if rec.get("kind") == "drawer" and rec.get("text"):
                append_cross_world_drawer(str(rec["text"]))
                ingested += 1
            elif rec.get("text"):
                post_codex_relay(
                    str(rec["text"]),
                    author=str(rec.get("author", "Codex (Pixel 7 AVF)")),
                    channel=str(rec.get("channel", "avf-sync")),
                    source="pixel7-avf-spool",
                )
                ingested += 1
        except (ValueError, KeyError):
            continue
    if ingested > 0:
        subprocess.run(
            [adb, "-s", serial, "shell", "rm -f /sdcard/Download/zoe_codex_spool.jsonl"],
            capture_output=True, timeout=4, check=False,
        )
    return {"ok": True, "ingested": ingested, **HONESTY_LOCK}


def toggle_uma_consent_bridge(
    actor: str = "nick",
    *,
    uma_dir: str | Path | None = None,
    uma_shm: str | Path | None = None,
) -> dict[str, Any]:
    """Toggle mutual-consent UMA airlock state safely for Browser Rome <-> QEMU Zoe-GEM OS."""
    resolved_uma_dir, resolved_uma_shm = resolve_uma_paths(uma_dir, uma_shm)
    uma = UmaBridge(resolved_uma_dir, shm_path=resolved_uma_shm)
    cur = uma.ensure_initialized()
    who = "zoe" if str(actor).strip().lower() == "zoe" else "nick"
    flag_key = f"{who}_allow"
    new_val = not bool(cur.get(flag_key, False))
    updated = uma.set_consent(who, new_val, reason="rome_beta_airlock_toggle")
    return {"ok": True, "actor": who, "state": updated, **HONESTY_LOCK}


def export_artline_vdi_for_output(plate_key: str = "flower") -> dict[str, Any]:
    """Export one of our Artline 2.0 plates (`flower`, `cocrest`, `headlamp`) for OUTPUT.APP VDI playback."""
    key = plate_key.strip().lower() if plate_key else "flower"
    if key not in ("flower", "cocrest", "headlamp", "cortex", "spinal"):
        key = "flower"
    zoe_root = Path(__file__).resolve().parents[3]
    out_dir = Path.home() / ".zoe" / "artline" / "rome_vdi"
    res = export_artline_plate(key, zoe_root, out_dir=out_dir)
    gem_p = Path(res["paths"]["gem"])
    png_p = Path(res["paths"]["png"])
    return {
        "ok": True,
        "plate": key,
        "gem_path": str(gem_p),
        "gem_bytes": gem_p.stat().st_size,
        "png_b64": base64.b64encode(png_p.read_bytes()).decode("ascii"),
        **HONESTY_LOCK,
    }


def trigger_pixel_bundle_build(device: str = "panther") -> dict[str, Any]:
    """Build or refresh the Dual-Track Pixel 7+ Sovereign Phone OS bundle."""
    spec = resolve_pixel_device(device)
    return build_pixel_sovereign_bundle(Path.home() / ".zoe" / f"pixel-{spec.codename}-os", device=spec.codename)


__all__ = [
    "HEADLAMP_PODS",
    "HONESTY_LOCK",
    "SOVEREIGN_WEB_THEMES",
    "append_cross_world_drawer",
    "build_phone_app_html",
    "build_phone_pwa_manifest",
    "export_artline_vdi_for_output",
    "get_freegem_catalog_payload",
    "get_headlamp_payload",
    "get_pixel_and_zo3_status_payload",
    "get_zoeverse_and_sisters_payload",
    "inspect_freegem_item",
    "post_codex_relay",
    "read_codex_relay",
    "read_cross_world_drawer",
    "render_braille_payload",
    "render_live_fb_preview_png_b64",
    "run_rome_showcase_payload",
    "sync_pixel_avf_spool",
    "toggle_uma_consent_bridge",
    "trigger_pixel_bundle_build",
]
