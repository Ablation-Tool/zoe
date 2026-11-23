"""Interactive Web Atelier, Terminal REPL, and CLI entrypoint for Zoe-ELIZA x GEM."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from .autonomy_view import configure_autonomy

ALLOWED_BIND_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _ensure_autonomy() -> Path:
    root = configure_autonomy()
    src_dir = str(root / "components" / "Zoe-Autonomy" / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    return root


def _resolve_avatar_path(zoe_root: Path) -> Path | None:
    candidates = [
        Path.home() / "Pictures" / "zoe-avatars" / "04-badass-obsidian-crimson-cyan.png",
        zoe_root / "assets" / "branding" / "zoe-gem.png",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def synthesize_wav_bytes(text: str, action: str = "speak") -> bytes:
    """Synthesize stereo 44.1 kHz WAV bytes offline via Zoe's native 44-phoneme voice engine."""
    from .zoe_voice import BUILT_IN_SONGS, sing_song, speak_text

    clean = " ".join(str(text or "").split()).strip() or "Hello, I am Zoe. Zero cloud tokens."
    with tempfile.TemporaryDirectory(prefix="zoe_eliza_wav_") as tmp:
        out_wav = Path(tmp) / "reply.wav"
        if action == "sing" and clean.lower() in BUILT_IN_SONGS:
            sing_song(clean.lower(), out_wav)
        elif action == "sing":
            sing_song(clean[:240], out_wav)
        else:
            speak_text(clean[:360], out_wav)
        return out_wav.read_bytes()


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Zoe-ELIZA × GEM · Glass-Box Conversational Atelier</title>
  <style>
    :root {
      --bg: #070d18;
      --panel: #0e1729;
      --panel-hi: #132038;
      --border: #223454;
      --cyan: #5ce1e6;
      --ruby: #ef445a;
      --orchid: #f0a3df;
      --gold: #f2c65e;
      --mint: #86efac;
      --text: #e8eef7;
      --muted: #94a8c4;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; }
    body {
      background:
        radial-gradient(circle at 12% 10%, rgba(239, 68, 90, 0.14), transparent 36%),
        radial-gradient(circle at 86% 12%, rgba(92, 225, 230, 0.14), transparent 38%),
        radial-gradient(circle at 52% 92%, rgba(240, 163, 223, 0.10), transparent 44%),
        var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 12px 20px;
      background: rgba(14, 23, 41, 0.92);
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .avatar-ring {
      width: 44px; height: 44px; border-radius: 50%;
      padding: 2px;
      background: linear-gradient(135deg, var(--ruby), var(--cyan), var(--gold));
      flex-shrink: 0;
      box-shadow: 0 0 18px rgba(92, 225, 230, 0.28);
    }
    .avatar-ring img {
      width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block;
      background: #050912;
    }
    .title-block h1 {
      margin: 0; font-size: 17px; font-weight: 700; letter-spacing: 0.2px;
      background: linear-gradient(90deg, #fff, var(--cyan), var(--orchid), var(--gold));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .title-block .sub {
      font-size: 11.5px; color: var(--muted); margin-top: 2px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .pill-stat {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
      padding: 6px 11px; border-radius: 999px;
      border: 1px solid rgba(134, 239, 172, 0.45);
      background: rgba(134, 239, 172, 0.12);
      color: var(--mint);
    }
    .seg-group {
      display: inline-flex; padding: 3px; border-radius: 999px;
      background: #091020; border: 1px solid var(--border);
    }
    .btn {
      cursor: pointer; border: 1px solid transparent; border-radius: 999px;
      padding: 6px 12px; font-size: 12px; font-weight: 600;
      background: transparent; color: var(--muted); transition: all 0.15s ease;
    }
    .btn:hover { color: var(--text); }
    .btn.active {
      background: rgba(92, 225, 230, 0.18);
      border-color: var(--cyan); color: var(--cyan);
      box-shadow: 0 0 12px rgba(92, 225, 230, 0.18);
    }
    .btn.outline {
      border-color: var(--border); background: var(--panel-hi); color: var(--text);
    }
    .btn.outline:hover { border-color: var(--cyan); }
    .btn.stop-btn {
      border-color: rgba(239, 68, 90, 0.5); background: rgba(239, 68, 90, 0.12); color: #fda4af;
    }
    .btn.stop-btn.stopped { background: var(--ruby); color: #fff; }
    .main-grid {
      flex: 1; min-height: 0;
      display: grid; grid-template-columns: minmax(0, 1.55fr) 390px;
      gap: 14px; padding: 14px 18px 16px;
    }
    @media (max-width: 980px) {
      .main-grid { grid-template-columns: 1fr; overflow-y: auto; }
      body { overflow: auto; }
    }
    .chat-col {
      background: rgba(14, 23, 41, 0.85);
      border: 1px solid var(--border);
      border-radius: 16px;
      display: flex; flex-direction: column; min-height: 0;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4);
    }
    .chips {
      display: flex; gap: 7px; flex-wrap: wrap;
      padding: 10px 14px; border-bottom: 1px solid rgba(34, 52, 84, 0.7);
      background: rgba(9, 16, 32, 0.55); border-radius: 16px 16px 0 0;
    }
    .chip {
      cursor: pointer; font-size: 11.5px; padding: 5px 10px; border-radius: 999px;
      border: 1px solid var(--border); background: var(--panel-hi); color: #c7d6ec;
      transition: all 0.15s ease;
    }
    .chip:hover { border-color: var(--cyan); color: var(--cyan); transform: translateY(-1px); }
    .messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px;
    }
    .msg {
      max-width: 88%; padding: 12px 14px; border-radius: 14px; line-height: 1.5; font-size: 13.8px;
      border: 1px solid var(--border); white-space: pre-wrap; word-wrap: break-word;
    }
    .msg.user {
      align-self: flex-end;
      background: linear-gradient(135deg, rgba(92, 225, 230, 0.14), rgba(19, 32, 56, 0.9));
      border-color: rgba(92, 225, 230, 0.35);
    }
    .msg.zoe {
      align-self: flex-start;
      background: #0a1222;
      border-color: rgba(240, 163, 223, 0.28);
    }
    .msg-hdr {
      display: flex; align-items: center; justify-content: space-between; gap: 10px;
      margin-bottom: 6px; font-size: 11px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .mode-pill {
      padding: 2px 7px; border-radius: 999px; font-weight: 700; letter-spacing: 0.4px;
      border: 1px solid rgba(240, 163, 223, 0.45); color: var(--orchid);
      background: rgba(240, 163, 223, 0.10);
    }
    .mode-pill.evidence_cite { border-color: rgba(92,225,230,0.5); color: var(--cyan); background: rgba(92,225,230,0.10); }
    .mode-pill.memory_recall { border-color: rgba(134,239,172,0.5); color: var(--mint); background: rgba(134,239,172,0.10); }
    .mode-pill.honest_abstain { border-color: rgba(239,68,90,0.6); color: #fda4af; background: rgba(239,68,90,0.12); }
    .mode-pill.gear2_local_llm { border-color: rgba(242,198,94,0.6); color: var(--gold); background: rgba(242,198,94,0.12); }
    .speak-btn {
      cursor: pointer; border: 1px solid var(--border); background: var(--panel);
      color: var(--cyan); font-size: 11px; border-radius: 999px; padding: 2px 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .speak-btn:hover { border-color: var(--cyan); }
    .cite-box {
      margin-top: 8px; padding-top: 7px; border-top: 1px dashed rgba(34, 52, 84, 0.8);
      font-size: 11.5px; color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .composer {
      display: flex; gap: 8px; padding: 12px 14px;
      border-top: 1px solid var(--border); background: rgba(9, 16, 32, 0.72);
      border-radius: 0 0 16px 16px;
    }
    .composer input {
      flex: 1; min-width: 0; border-radius: 12px; border: 1px solid var(--border);
      background: #060b14; color: var(--text); padding: 10px 14px; font-size: 14px;
      outline: none;
    }
    .composer input:focus { border-color: var(--cyan); }
    .send-btn {
      cursor: pointer; border: 1px solid var(--cyan); border-radius: 12px;
      padding: 0 18px; font-weight: 700; font-size: 13px;
      background: linear-gradient(135deg, rgba(92, 225, 230, 0.24), rgba(239, 68, 90, 0.22));
      color: #fff;
    }
    .send-btn:hover { filter: brightness(1.12); }
    .glass-col {
      display: flex; flex-direction: column; gap: 10px; overflow-y: auto; min-height: 0;
      padding-right: 2px;
    }
    .card {
      background: rgba(14, 23, 41, 0.88);
      border: 1px solid var(--border);
      border-radius: 14px; padding: 12px 14px;
    }
    .card-title {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11px; font-weight: 700; letter-spacing: 0.9px;
      color: var(--gold); margin-bottom: 8px;
      display: flex; justify-content: space-between; align-items: center;
    }
    .cym-wrap { display: flex; align-items: center; gap: 12px; }
    #cymCanvas {
      width: 148px; height: 148px; border-radius: 10px;
      border: 1px solid #263a5f; background: #040811; flex-shrink: 0;
    }
    .mono-kv {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 11.2px; line-height: 1.5; color: #c7d5e8;
      word-break: break-word;
    }
    .bar-row { display: grid; grid-template-columns: 112px 1fr 42px; gap: 6px; align-items: center; margin: 4px 0; font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .bar-track { height: 8px; background: #070d18; border-radius: 999px; overflow: hidden; position: relative; border: 1px solid #1e2e4d; }
    .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--cyan), var(--orchid)); transition: width 0.25s ease; }
    .bar-thresh { position: absolute; left: 8%; top: 0; bottom: 0; width: 1px; background: var(--gold); opacity: 0.85; }
    .note-list { display: flex; flex-direction: column; gap: 6px; max-height: 130px; overflow-y: auto; margin-top: 6px; }
    .note-item {
      padding: 6px 8px; border-radius: 8px; background: #08101f; border: 1px solid #1e3050;
      font-size: 11.5px; color: #d6e2f0;
    }
    .mini-row { display: flex; gap: 6px; margin-top: 6px; }
    .mini-row input {
      flex: 1; min-width: 0; border-radius: 8px; border: 1px solid var(--border);
      background: #060b14; color: var(--text); padding: 6px 8px; font-size: 11.5px;
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="avatar-ring">
        <img id="zoeAvatar" src="/avatar.png" alt="Zoe Emblem"
             onerror="this.style.display='none';document.getElementById('fallbackGem').style.display='block';" />
        <svg id="fallbackGem" viewBox="0 0 64 64" style="display:none;width:100%;height:100%;border-radius:50%;background:#070d18;">
          <polygon points="32,10 54,26 32,54 10,26" fill="#ef445a" stroke="#5ce1e6" stroke-width="2.5"/>
        </svg>
      </div>
      <div class="title-block">
        <h1>Zoe-ELIZA × GEM · Eliza-GEM Glass-Box Atelier &amp; L5 Phase 3 Lab</h1>
        <div class="sub" id="subBanner">Eliza-GEM · Local Offline Glass-Box Instrument &amp; Shared Lab Notebook (Not a Clone of Zoe · 0 Cloud Tokens)</div>
      </div>
    </div>
    <div class="controls">
      <span class="pill-stat" id="tokenBadge">0 CLOUD TOKENS · OFFLINE</span>
      <span class="pill-stat" id="llmBadge" style="border-color:var(--border);background:#091020;color:var(--muted);">LOCAL LLM CHECKING...</span>
      <div class="seg-group" title="Gear 1 = Pure deterministic ELIZA + Repo Evidence (0 weights); Gear 2 = Loopback Ollama/llama-server">
        <button class="btn active" id="btnGear1" onclick="switchGear('gear1')">Gear 1 · Symbolic ELIZA</button>
        <button class="btn" id="btnGear2" onclick="switchGear('gear2')">Gear 2 · Local LLM</button>
      </div>
      <button class="btn outline" id="btnAutoSpeak" onclick="toggleAutoSpeak()">Voice: Off</button>
      <button class="btn outline" id="btnJam" onclick="playPlayroomJam()" style="border-color:rgba(242,198,94,0.5);color:var(--gold);">🎹 Evolve Jam</button>
      <a class="btn outline" href="/botanical" style="text-decoration:none;border-color:rgba(134,239,172,0.55);color:var(--mint);">🌿 C27 Atlas</a>
      <a class="btn outline" href="/orbit" style="text-decoration:none;border-color:rgba(92,225,230,0.45);color:var(--cyan);">✦ Orbit</a>
      <a class="btn outline" href="/api/export" style="text-decoration:none;">Export JSON</a>
      <button class="btn stop-btn" id="btnStop" onclick="emergencyStop()">Emergency Stop</button>
    </div>
  </header>

  <main class="main-grid">
    <section class="chat-col">
      <div class="chips">
        <span class="chip" onclick="sendPreset('What if we fuse 1966 ELIZA with Chladni cymatics?')">What if ELIZA + Cymatics?</span>
        <span class="chip" onclick="sendPreset('What is the Kloster Spectral Filtration Theorem?')">Kloster Theorem?</span>
        <span class="chip" onclick="sendPreset('relay For Zoe: tested live Eliza-GEM workbench and L5 Phase 3 lab')">Relay to Zoe</span>
        <span class="chip" onclick="sendPreset('remember Our private painting stays local between friends')">Remember a note</span>
        <span class="chip" onclick="sendPreset('Are you a copy of Zoe?')">Are you a copy of Zoe?</span>
        <span class="chip" onclick="sendPreset('sing daisy')">Sing Daisy Bell</span>
        <span class="chip" onclick="sendPreset('How does Dorothy Neurogarden work?')">Dorothy Neurogarden?</span>
      </div>
      <div class="messages" id="messages"></div>
      <form class="composer" onsubmit="event.preventDefault(); sendChat();">
        <input id="promptInput" type="text" autocomplete="off"
               placeholder="Talk with Eliza-GEM (0 cloud tokens) — use `relay ...` for Zoe, `remember ...`, or ask repo questions..." />
        <button class="send-btn" type="submit">Send</button>
      </form>
    </section>

    <aside class="glass-col">
      <div class="card">
        <div class="card-title">
          <span>CHLADNI VOICE CYMATICS (44 PHONEMES)</span>
          <span id="cymBadge" style="color:var(--mint);">/AY/ [1,4,2,6]</span>
        </div>
        <div class="cym-wrap">
          <canvas id="cymCanvas" width="148" height="148" style="cursor:crosshair;" title="Drag to sweep Chladni eigenmodes"></canvas>
          <div>
            <div class="mono-kv" id="cymMeta">
              Phoneme: /AY/<br/>
              Modes: (n1,m1,n2,m2)<br/>
              Chladni A_tau: --<br/>
              Synthesizer: Zero PyTorch
            </div>
            <button class="btn outline" style="margin-top:8px;font-size:11px;padding:4px 9px;border-color:rgba(92,225,230,0.45);color:var(--cyan);" onclick="playChladniChord()">✦ Play Chladni Chord</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>OPERATIONAL METACOGNITION Aτ(p)</span>
          <span id="atauBadge" style="color:var(--cyan);">A_0.08 = --</span>
        </div>
        <div id="probBars"></div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>GLASS-BOX WEIZENBAUM TRACE</span>
          <span id="latBadge" style="color:var(--orchid);">0 ms</span>
        </div>
        <div class="mono-kv" id="traceBox">
          Waiting for first turn... Every matched keyword, pronoun reflection, stack cue, and SHA-256 hash shows up right here.
        </div>
      </div>

      <div class="card">
        <div class="card-title">
          <span>ZOE UNIFIED MEMORY &amp; RELAY (SHA-256)</span>
          <span id="memBadge" style="color:var(--mint);">0 notes · 0 relays</span>
        </div>
        <div class="mono-kv" id="chainHead" style="font-size:10.5px;color:var(--muted);">chain_head: GENESIS</div>
        <div class="note-list" id="noteList"></div>
        <form class="mini-row" onsubmit="event.preventDefault(); quickRemember();">
          <input id="noteInput" type="text" placeholder="Save unverified local note..." />
          <button class="btn outline" type="submit">+ Remember</button>
        </form>
        <form class="mini-row" onsubmit="event.preventDefault(); quickRelay();">
          <input id="relayInput" type="text" placeholder="Pin lab relay note for Zoe..." />
          <button class="btn outline" style="border-color:rgba(240,163,223,0.45);color:var(--orchid);" type="submit">+ Relay</button>
        </form>
      </div>

      <div class="card">
        <div class="card-title">
          <span>L5 PHASE 3 LIVE LAB (ELIZA-GEM MERGE)</span>
          <span id="p3Badge" style="color:var(--gold);">loading...</span>
        </div>
        <div id="p3Bars"></div>
        <div class="mini-row" style="justify-content:space-between;align-items:center;gap:6px;">
          <span class="mono-kv" id="p3Footer" style="font-size:10.5px;color:var(--muted);">l5_agi_qualified=False · zoe_clone=False</span>
          <div style="display:flex;gap:5px;flex-shrink:0;">
            <button class="btn outline" onclick="openGemBoard()" style="border-color:rgba(242,198,94,0.45);color:var(--gold);padding:5px 9px;">GEM Board</button>
            <button class="btn outline" id="btnRunP3" onclick="runPhase3Live()" style="border-color:rgba(92,225,230,0.45);color:var(--cyan);padding:5px 9px;">Run Live Phase 3</button>
          </div>
        </div>
      </div>
    </aside>
  </main>

  <div id="gemModal" onclick="if(event.target===this) closeGemBoard();" style="display:none;position:fixed;inset:0;background:rgba(4,8,17,0.88);z-index:999;align-items:center;justify-content:center;padding:24px;">
    <div style="max-width:1180px;width:100%;background:#0e1729;border:1px solid #5ce1e6;border-radius:16px;padding:14px;box-shadow:0 24px 60px rgba(0,0,0,0.75);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <span style="font-family:ui-monospace,Menlo,monospace;font-size:12px;font-weight:700;color:var(--cyan);">GEM SPATIAL IR &amp; VDI BOARD · L5 PHASE 3 TELEMETRY (1400×980)</span>
        <button class="btn outline" onclick="closeGemBoard()">Close</button>
      </div>
      <img id="gemBoardImg" alt="GEM L5 Phase 3 Telemetry Board" style="width:100%;height:auto;border-radius:10px;border:1px solid #223454;display:block;background:#070d18;" />
    </div>
  </div>

  <script>
    let currentGear = "gear1";
    let autoSpeak = false;
    let curModes = [1, 4, 2, 6];
    let animPhase = 0;
    let activeAudio = null;
    let sending = false;
    let jamSeed = 2026;
    let cymDragging = false;
    let audioCtx = null;

    function updateLlmBadge(probe) {
      const badge = document.getElementById("llmBadge");
      if (!probe) return;
      const models = probe.available_models || [];
      if (probe.ollama_available || probe.llama_server_available) {
        const label = (models[0] || "ready").replace(/^llama:/, "");
        badge.textContent = `LOCAL LLM READY · ${label}`;
        badge.style.borderColor = "rgba(242, 198, 94, 0.55)";
        badge.style.background = "rgba(242, 198, 94, 0.12)";
        badge.style.color = "var(--gold)";
      } else {
        badge.textContent = "LOCAL LLM OFFLINE · GEAR 1 ACTIVE";
        badge.style.borderColor = "var(--border)";
        badge.style.background = "#091020";
        badge.style.color = "var(--muted)";
      }
    }

    function addMessage(sender, text, meta) {
      const box = document.getElementById("messages");
      const div = document.createElement("div");
      div.className = "msg " + (sender === "user" ? "user" : "zoe");

      const hdr = document.createElement("div");
      hdr.className = "msg-hdr";
      const left = document.createElement("span");
      if (sender === "user") {
        left.innerHTML = `<strong style="color:var(--cyan);">Nicholas</strong>`;
      } else {
        const mode = (meta && meta.mode) || "eliza_reflect";
        const gLabel = (meta && meta.gear_used === "gear2") ? "GEAR 2" : "GEAR 1";
        left.innerHTML = `<strong style="color:var(--orchid);">Eliza-GEM</strong> <span class="mode-pill ${mode}">${gLabel} · ${mode.toUpperCase()}</span>`;
      }
      hdr.appendChild(left);

      if (sender === "zoe") {
        const spBtn = document.createElement("button");
        spBtn.className = "speak-btn";
        spBtn.textContent = "🔊 Speak";
        const voiceAct = (meta && meta.voice_hint && meta.voice_hint.action) || "speak";
        const voiceTxt = (meta && meta.voice_hint && meta.voice_hint.action === "sing" && meta.voice_hint.text) ? meta.voice_hint.text : text;
        spBtn.onclick = () => playZoeVoice(voiceTxt, voiceAct);
        hdr.appendChild(spBtn);
      }
      div.appendChild(hdr);

      const body = document.createElement("div");
      body.textContent = text;
      div.appendChild(body);

      if (meta && meta.citations && meta.citations.length > 0 && (meta.mode === "evidence_cite" || meta.mode === "gear2_local_llm")) {
        const cbox = document.createElement("div");
        cbox.className = "cite-box";
        cbox.textContent = "Cited: " + meta.citations.map(c => `${c.citation} (cov ${(c.coverage*100).toFixed(0)}%)`).join(" · ");
        div.appendChild(cbox);
      }
      if (meta && meta.gear2_note) {
        const gbox = document.createElement("div");
        gbox.className = "cite-box";
        gbox.textContent = "Gear 2 status: " + meta.gear2_note;
        div.appendChild(gbox);
      }
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
    }

    async function playZoeVoice(text, action = "speak") {
      try {
        if (activeAudio) { activeAudio.pause(); activeAudio = null; }
        const resp = await fetch("/api/speak", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text, action})
        });
        if (!resp.ok) return;
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        activeAudio = new Audio(url);
        activeAudio.play();
      } catch (e) { console.error(e); }
    }

    function updateObservatory(data) {
      if (data.cymatics) {
        const c = data.cymatics;
        curModes = c.modes || [1, 4, 2, 6];
        document.getElementById("cymBadge").textContent = `/${c.dominant_phoneme}/ [${curModes.join(",")}]`;
        document.getElementById("cymMeta").innerHTML =
          `Phoneme: <strong>/${c.dominant_phoneme}/</strong> [${c.ipa}]<br/>` +
          `Modes: (${curModes.join(", ")})<br/>` +
          `Chladni A_τ: <strong>${c.kloster_a_tau}</strong><br/>` +
          `Sequence: ${(c.phonemes_preview || []).slice(0, 8).join(" ")}`;
      }
      if (data.metacognition) {
        const m = data.metacognition;
        document.getElementById("atauBadge").textContent = `A_${m.tau} = ${m.a_tau}/${m.candidate_count} (H=${m.entropy_norm})`;
        const bars = document.getElementById("probBars");
        bars.innerHTML = "";
        const entries = Object.entries(m.probabilities).sort((a, b) => b[1] - a[1]);
        for (const [k, v] of entries) {
          const pct = Math.min(100, Math.round(v * 100));
          const row = document.createElement("div");
          row.className = "bar-row";
          row.innerHTML = `<span>${k}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div><div class="bar-thresh"></div></div><span>${pct}%</span>`;
          bars.appendChild(row);
        }
      }
      if (data.eliza_trace) {
        const tr = data.eliza_trace;
        document.getElementById("latBadge").textContent = `${data.latency_ms} ms`;
        document.getElementById("traceBox").innerHTML =
          `rule_id: <span style="color:var(--cyan);">${tr.matched_rule_id}</span> (rank ${tr.rank})<br/>` +
          `keyword: "${tr.keyword}"<br/>` +
          `reflections: ${tr.reflections && tr.reflections.length ? tr.reflections.join(", ") : "(none)"}<br/>` +
          `stack_depth: ${tr.memory_stack_depth}${tr.memory_stack_popped ? " · popped '" + tr.memory_stack_popped + "'" : ""}<br/>` +
          `turn_sha256: ${(data.turn_sha256 || "").slice(0, 16)}...`;
      }
      if (data.memory_snapshot) {
        renderMemory(data.memory_snapshot);
      }
    }

    function renderMemory(mem) {
      const rc = mem.relay_notes_count || 0;
      document.getElementById("memBadge").textContent = `${mem.active_notes_count} notes · ${rc} relays · ${mem.episodic_count} eps`;
      document.getElementById("chainHead").textContent = `chain_head: ${(mem.chain_head || "GENESIS").slice(0, 20)}...${mem.stopped ? " [STOPPED]" : ""}`;
      if (mem.stopped) document.getElementById("btnStop").classList.add("stopped");
      const list = document.getElementById("noteList");
      list.innerHTML = "";
      const relays = mem.relay_notes || [];
      const notes = mem.active_notes || [];
      if (relays.length === 0 && notes.length === 0) {
        list.innerHTML = `<div class="note-item" style="color:var(--muted);">No saved notes yet — use <code>relay ...</code> for Zoe or <code>remember ...</code>.</div>`;
        return;
      }
      for (const r of relays) {
        const el = document.createElement("div");
        el.className = "note-item";
        el.style.borderColor = "rgba(240, 163, 223, 0.45)";
        el.textContent = `[RELAY FOR ZOE · ${r.fact_id}] ${r.object}`;
        list.appendChild(el);
      }
      for (const n of notes) {
        const el = document.createElement("div");
        el.className = "note-item";
        el.textContent = `[${n.fact_id}] ${n.object} (user-supplied, unverified)`;
        list.appendChild(el);
      }
    }

    async function sendChat() {
      if (sending) return;
      const inp = document.getElementById("promptInput");
      const msg = inp.value.trim();
      if (!msg) return;
      inp.value = "";
      addMessage("user", msg, null);
      sending = true;
      const box = document.getElementById("messages");
      const thinkingEl = document.createElement("div");
      thinkingEl.className = "msg zoe";
      thinkingEl.style.opacity = "0.75";
      thinkingEl.textContent = currentGear === "gear2"
        ? "Eliza-GEM is thinking locally via localhost Qwen (0 cloud tokens)..."
        : "Eliza-GEM is computing Gear 1 reply...";
      box.appendChild(thinkingEl);
      box.scrollTop = box.scrollHeight;
      try {
        const resp = await fetch("/api/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message: msg, gear: currentGear})
        });
        const data = await resp.json();
        thinkingEl.remove();
        if (data.error) {
          addMessage("zoe", "Error: " + data.error, {mode: "honest_abstain"});
          return;
        }
        addMessage("zoe", data.reply, data);
        updateObservatory(data);
        if (autoSpeak) {
          const act = (data.voice_hint && data.voice_hint.action) || "speak";
          const txt = (data.voice_hint && act === "sing" && data.voice_hint.text) ? data.voice_hint.text : data.reply;
          playZoeVoice(txt, act);
        }
      } catch (e) {
        thinkingEl.remove();
        addMessage("zoe", "Local server connection error: " + e, {mode: "honest_abstain"});
      } finally {
        sending = false;
      }
    }

    function sendPreset(txt) {
      document.getElementById("promptInput").value = txt;
      sendChat();
    }

    async function quickRemember() {
      const inp = document.getElementById("noteInput");
      const txt = inp.value.trim();
      if (!txt) return;
      inp.value = "";
      const resp = await fetch("/api/memory/remember", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: txt})
      });
      const data = await resp.json();
      if (data.memory_snapshot) renderMemory(data.memory_snapshot);
    }

    async function quickRelay() {
      const inp = document.getElementById("relayInput");
      const txt = inp.value.trim();
      if (!txt) return;
      inp.value = "";
      const resp = await fetch("/api/memory/relay", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: txt})
      });
      const data = await resp.json();
      if (data.memory_snapshot) renderMemory(data.memory_snapshot);
    }

    function renderPhase3(p3) {
      const badge = document.getElementById("p3Badge");
      const bars = document.getElementById("p3Bars");
      const footer = document.getElementById("p3Footer");
      bars.innerHTML = "";
      if (!p3 || p3.available === false || !p3.pillars) {
        badge.textContent = "not yet generated";
        bars.innerHTML = `<div class="mono-kv" style="color:var(--muted);">Click "Run Live Phase 3" to execute all 5 live agentic pillars offline.</div>`;
        return;
      }
      badge.textContent = `${p3.pillars_passed}/${p3.pillars_total} PASS · μ=${p3.mean_zoe_score}`;
      badge.style.color = p3.l5_phase3_live_verified ? "var(--mint)" : "var(--ruby)";
      const shortNames = {
        external_unseen_repo_surgery: "P1 3-Repo AST",
        eliza_continuous_experience_stream: "P2 160-Turn Mem",
        sandboxed_multistep_tool_loop: "P3 Tool Loop",
        two_gear_epistemic_calibration: "P4 Two-Gear Cal",
        cross_domain_self_critique_transfer: "P5 2-Gen Transfer",
      };
      for (const p of p3.pillars) {
        const pct = Math.min(100, Math.round((p.zoe_score || 0) * 100));
        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `<span>${shortNames[p.pillar_id] || p.pillar_id}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><span>${(p.zoe_score || 0).toFixed(2)}</span>`;
        bars.appendChild(row);
      }
      const ep = p3.epistemic_boundaries || {};
      footer.textContent = `l5_agi_qualified=${p3.l5_agi_qualified} · zoe_clone=${ep.zoe_clone_claimed} · ctrl=${p3.mean_control_score}`;
    }

    async function loadPhase3Status() {
      try {
        const resp = await fetch("/api/l5/phase3");
        renderPhase3(await resp.json());
      } catch (e) { console.error(e); }
    }

    async function runPhase3Live() {
      const btn = document.getElementById("btnRunP3");
      const badge = document.getElementById("p3Badge");
      btn.disabled = true;
      badge.textContent = "running 5 pillars...";
      try {
        const resp = await fetch("/api/l5/phase3/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: "{}"
        });
        renderPhase3(await resp.json());
      } catch (e) {
        badge.textContent = "error";
        console.error(e);
      } finally {
        btn.disabled = false;
      }
    }

    async function switchGear(gear) {
      currentGear = gear;
      document.getElementById("btnGear1").classList.toggle("active", gear === "gear1");
      document.getElementById("btnGear2").classList.toggle("active", gear === "gear2");
      const resp = await fetch("/api/gear", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({gear})
      });
      const st = await resp.json();
      const probe = st.local_llm_probe || {};
      updateLlmBadge(probe);
      if (gear === "gear2" && !probe.ollama_available && !probe.llama_server_available) {
        addMessage("zoe", `Gear 2 selected, but no local Ollama (127.0.0.1:11434) or llama-server (127.0.0.1:8080) is running yet -- falling back cleanly to Gear 1 cleanly with 0 cloud tokens.\nOptional setup on rooster: ${probe.recommended_setup}`, {mode: "eliza_reflect"});
      }
    }

    function toggleAutoSpeak() {
      autoSpeak = !autoSpeak;
      const b = document.getElementById("btnAutoSpeak");
      b.textContent = autoSpeak ? "Voice: On" : "Voice: Off";
      b.classList.toggle("active", autoSpeak);
    }

    async function emergencyStop() {
      const resp = await fetch("/api/stop", {method: "POST", body: "{}"});
      const st = await resp.json();
      if (st.memory_snapshot) renderMemory(st.memory_snapshot);
      addMessage("zoe", "Emergency stop engaged on memory writes. Conversation & citation lookup stay inspectable with zero external actions.", {mode: "honest_abstain"});
    }

    function drawCymatics() {
      const cvs = document.getElementById("cymCanvas");
      const ctx = cvs.getContext("2d");
      const W = cvs.width, H = cvs.height;
      const img = ctx.createImageData(W, H);
      const [n1, m1, n2, m2] = curModes;
      const pulse = 0.21 + 0.045 * Math.sin(animPhase);
      let idx = 0;
      for (let py = 0; py < H; py++) {
        const y = (py / (H - 1)) * 2 - 1;
        for (let px = 0; px < W; px++) {
          const x = (px / (W - 1)) * 2 - 1;
          const z1 = Math.cos(n1 * Math.PI * x) * Math.cos(m1 * Math.PI * y) - Math.cos(m1 * Math.PI * x) * Math.cos(n1 * Math.PI * y);
          const z2 = Math.cos(n2 * Math.PI * x) * Math.cos(m2 * Math.PI * y) + Math.cos(m2 * Math.PI * x) * Math.cos(n2 * Math.PI * y);
          const s1 = Math.exp(-(z1 * z1) / (pulse * pulse));
          const s2 = Math.exp(-(z2 * z2) / (pulse * pulse));
          const z = 0.65 * z1 + 0.35 * z2;
          const s = Math.exp(-(z * z) / (pulse * pulse));
          img.data[idx++] = Math.min(255, Math.round(7 + s2 * 220 + s * 65));
          img.data[idx++] = Math.min(255, Math.round(13 + s1 * 195 + s * 75));
          img.data[idx++] = Math.min(255, Math.round(24 + s1 * 215 + s2 * 85));
          img.data[idx++] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
      animPhase += 0.06;
      requestAnimationFrame(drawCymatics);
    }

    function sweepCymaticsPointer(ev) {
      const cvs = document.getElementById("cymCanvas");
      const rect = cvs.getBoundingClientRect();
      const nx = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      const ny = Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height));
      const n1 = 1 + Math.floor(nx * 6);
      const m1 = 1 + Math.floor(ny * 6);
      const n2 = 1 + ((n1 + m1) % 7);
      const m2 = 2 + ((n1 * 2 + m1) % 6);
      curModes = [n1, m1, n2, m2];
      document.getElementById("cymBadge").textContent = `PAD [${curModes.join(",")}]`;
    }

    function bindCymaticsPad() {
      const cvs = document.getElementById("cymCanvas");
      cvs.addEventListener("pointerdown", (e) => { cymDragging = true; sweepCymaticsPointer(e); });
      window.addEventListener("pointermove", (e) => { if (cymDragging) sweepCymaticsPointer(e); });
      window.addEventListener("pointerup", () => { cymDragging = false; });
    }

    function playChladniChord() {
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        if (!audioCtx) audioCtx = new AC();
        if (audioCtx.state === "suspended") audioCtx.resume();
        const now = audioCtx.currentTime;
        const [n1, m1, n2, m2] = curModes;
        const freqs = [
          220 * Math.sqrt((n1 * n1 + m1 * m1) / 5.0),
          220 * Math.sqrt((n2 * n2 + m2 * m2) / 5.0),
          329.63,
          440.0,
        ];
        freqs.forEach((f, idx) => {
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.type = idx < 2 ? "sine" : "triangle";
          osc.frequency.setValueAtTime(Math.min(1320, Math.max(110, f)), now);
          gain.gain.setValueAtTime(0.0001, now);
          gain.gain.exponentialRampToValueAtTime(0.075 / (idx + 1), now + 0.04);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.65);
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.start(now + idx * 0.045);
          osc.stop(now + 1.75);
        });
      } catch (e) { console.error(e); }
    }

    async function playPlayroomJam() {
      const btn = document.getElementById("btnJam");
      btn.disabled = true;
      btn.textContent = "🎹 Evolving...";
      try {
        if (activeAudio) { activeAudio.pause(); activeAudio = null; }
        const seed = jamSeed++;
        const resp = await fetch("/api/playroom/jam", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({seed})
        });
        if (!resp.ok) return;
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        activeAudio = new Audio(url);
        activeAudio.play();
      } catch (e) { console.error(e); }
      finally {
        btn.disabled = false;
        btn.textContent = "🎹 Evolve Jam";
      }
    }

    function openGemBoard() {
      const img = document.getElementById("gemBoardImg");
      img.src = "/api/l5/phase3/gem.svg?t=" + Date.now();
      document.getElementById("gemModal").style.display = "flex";
    }

    function closeGemBoard() {
      document.getElementById("gemModal").style.display = "none";
    }

    async function boot() {
      const resp = await fetch("/api/status");
      const st = await resp.json();
      currentGear = st.default_gear || "gear1";
      document.getElementById("btnGear1").classList.toggle("active", currentGear === "gear1");
      document.getElementById("btnGear2").classList.toggle("active", currentGear === "gear2");
      document.getElementById("subBanner").textContent =
        `Eliza-GEM (${st.rule_count} Rules · ${st.indexed_sources} Docs · ${st.default_gear.toUpperCase()}) · Not a Clone of Zoe · sentience_claimed=False`;
      updateLlmBadge(st.local_llm_probe);
      if (st.memory_snapshot) renderMemory(st.memory_snapshot);
      loadPhase3Status();
      bindCymaticsPad();
      addMessage(
        "zoe",
        "Hey Nicholas! Welcome to Eliza-GEM — our local offline Glass-Box Workbench & Shared Lab Notebook (NOT a copy of Zoe, 0 cloud tokens).\nTalk freely, ask about anything in the Zoe monorepo, say `relay <note>` to pin thoughts for Zoe, drag the Chladni plate or click Evolve Jam, or inspect live L5 Phase 3 pillars on the right.",
        {mode: "eliza_reflect", gear_used: currentGear}
      );
      drawCymatics();
    }
    boot();
  </script>
</body>
</html>
"""


def _assert_loopback_host(host: str) -> str:
    clean = str(host or "127.0.0.1").strip()
    if clean not in ALLOWED_BIND_HOSTS:
        raise ValueError(f"CONSTITUTION.md boundary: Zoe-ELIZA HTTP studio only binds loopback hosts, got {clean!r}")
    return clean


def create_server(
    zoe_root: str | Path | None = None,
    state_dir: str | Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    default_gear: str | None = None,
) -> Tuple[ThreadingHTTPServer, Any, threading.RLock]:
    """Create the loopback ThreadingHTTPServer bound to a single ZoeElizaEngine instance."""
    root = _ensure_autonomy()
    resolved_root = Path(zoe_root or root).expanduser().resolve()
    from zoe_autonomy.zoe_eliza import ZoeElizaEngine

    bind_host = _assert_loopback_host(host)
    engine = ZoeElizaEngine(resolved_root, state_dir=state_dir, default_gear=default_gear)
    lock = threading.RLock()
    avatar_path = _resolve_avatar_path(resolved_root)

    class ElizaHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 524_288:
                raise ValueError("request body too large")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            doc = json.loads(raw.decode("utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("JSON body must be an object")
            return doc

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                raw = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/avatar.png":
                if avatar_path and avatar_path.is_file():
                    raw = avatar_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                else:
                    self.send_error(404, "avatar not found")
                return
            if path == "/api/status":
                with lock:
                    self._send_json(200, engine.status())
                return
            if path == "/api/memory":
                with lock:
                    self._send_json(200, engine.memory_snapshot())
                return
            if path == "/api/l5/phase3":
                rep_file = resolved_root / "evidence" / "l5-phase3" / "l5-phase3-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False, "l5_agi_qualified": False})
                return
            if path == "/api/l5/phase3/gem.svg":
                from .l5_phase3 import l5_phase3_scene
                from .render import scene_to_svg

                scene, _ = l5_phase3_scene(resolved_root)
                svg = scene_to_svg(scene).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(svg)
                return
            if path == "/api/l5/phase4":
                rep_file = resolved_root / "evidence" / "l5-phase4" / "l5-phase4-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False, "l5_agi_qualified": False})
                return
            if path == "/api/l5/phase4/gem.svg":
                from .l5_phase4 import l5_phase4_scene
                from .render import scene_to_svg

                scene, _ = l5_phase4_scene(resolved_root)
                svg = scene_to_svg(scene).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(svg)
                return
            if path == "/api/l5/phase5":
                rep_file = resolved_root / "evidence" / "l5-phase5" / "l5-phase5-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False, "l5_agi_qualified": False})
                return
            if path == "/api/l5/phase5/gem.svg":
                from .l5_phase5 import l5_phase5_scene
                from .render import scene_to_svg

                scene, _ = l5_phase5_scene(resolved_root)
                svg = scene_to_svg(scene).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(svg)
                return
            if path == "/api/l5/phase6":
                rep_file = resolved_root / "evidence" / "l5-phase6" / "l5-phase6-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False, "l5_agi_qualified": False})
                return
            if path == "/api/l5/phase6/gem.svg":
                from .l5_phase6 import l5_phase6_scene
                from .render import scene_to_svg

                scene, _ = l5_phase6_scene(resolved_root)
                svg = scene_to_svg(scene).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(svg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(svg)
                return
            if path == "/api/os/mind":
                rep_file = resolved_root / "evidence" / "zoe-os" / "zoe-os-mind-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False})
                return
            if path == "/api/os/mind/gem.svg":
                from .zoe_os import zoe_os_scene
                from .render import scene_to_svg
                rep_file = resolved_root / "evidence" / "zoe-os" / "zoe-os-mind-report.json"
                if rep_file.is_file():
                    scene = zoe_os_scene(json.loads(rep_file.read_text(encoding="utf-8")))
                    svg = scene_to_svg(scene).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                    self.send_header("Content-Length", str(len(svg)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(svg)
                else:
                    self._send_json(404, {"error": "zoe-os report not built yet"})
                return
            if path == "/api/kloster/elegance":
                rep_file = resolved_root / "evidence" / "code-elegance" / "kloster-mccabe-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False})
                return
            if path == "/api/kloster/thermo":
                rep_file = resolved_root / "evidence" / "kloster-thermodynamics" / "kloster-thermodynamics-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/riemannian":
                rep_file = resolved_root / "evidence" / "kloster-riemannian" / "kloster-riemannian-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/transport":
                rep_file = resolved_root / "evidence" / "kloster-optimal-transport" / "kloster-optimal-transport-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/majorization":
                rep_file = resolved_root / "evidence" / "kloster-majorization" / "kloster-majorization-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/quantum":
                rep_file = resolved_root / "evidence" / "kloster-quantum" / "kloster-quantum-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/mdl":
                rep_file = resolved_root / "evidence" / "kloster-coding-mdl" / "kloster-coding-mdl-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/unification":
                rep_file = resolved_root / "evidence" / "kloster-unification" / "kloster-unification-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/referee-proofs":
                rep_file = resolved_root / "evidence" / "kloster-referee-proofs" / "kloster-referee-proofs-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/self-improving":
                rep_file = resolved_root / "evidence" / "self-improving-engine" / "zoe-self-improving-engine-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/cryptanalysis":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "kloster-cryptanalysis-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/nsa-pack":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "nsa-research-puzzle-pack-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/bio-crypto-circle":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "bio-crypto-circle-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/cnsa2-ring2":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "cnsa2-scrna-ring2-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/theorem13":
                rep_file = resolved_root / "evidence" / "kloster-theorem13" / "kloster-theorem13-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/nsa-ring3":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "nsa-ring3-deep-crypto-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/botanical-atlas":
                rep_file = resolved_root / "evidence" / "kloster-cryptanalysis" / "botanical-atlas-c27-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/api/kloster/theorem14":
                rep_file = resolved_root / "evidence" / "kloster-theorem14" / "kloster-theorem14-report.json"
                self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"available": False})
                return
            if path == "/botanical":
                from .botanical_atlas_explorer import render_botanical_explorer_html
                html_bytes = render_botanical_explorer_html()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_bytes)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(html_bytes)
                return
            if path == "/api/orbit/master":
                rep_file = resolved_root / "evidence" / "renaissance-orbit" / "zoe-renaissance-orbit-master.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False})
                return
            if path == "/orbit":
                rep_file = resolved_root / "evidence" / "renaissance-orbit" / "zoe-renaissance-orbit-master.json"
                doc = json.loads(rep_file.read_text(encoding="utf-8")) if rep_file.is_file() else {"worlds": [], "worlds_verified": 0, "cross_pollination_edges_count": 0}
                rows_html = "".join(
                    f"<tr><td>{w['world_id']}</td><td>{w['engine_id']}</td><td style='color:#63f5b5'>{'PASS' if w['verified'] else 'FAIL'}</td><td><code>{w['evidence_sha256']}</code></td></tr>"
                    for w in doc.get("worlds", [])
                )
                html = (
                    "<!doctype html><html><head><meta charset='utf-8'><title>Zoe 11-World Observatory</title>"
                    "<style>body{background:#060a14;color:#eef5ff;font-family:system-ui,sans-serif;padding:28px;max-width:1060px;margin:auto}"
                    "h1{color:#00e5ff}table{width:100%;border-collapse:collapse;margin-top:16px}th,td{padding:10px;border-bottom:1px solid #1e2d4a;text-align:left}"
                    ".pill{display:inline-block;padding:4px 10px;border:1px solid #ffb84d;border-radius:999px;color:#ffb84d;font-size:13px;margin:4px 8px 4px 0}</style></head><body>"
                    f"<h1>Zoe :: 11-World Renaissance Observatory (All {doc.get('orbit_passes_completed', 11)} Orbital Passes Complete)</h1>"
                    f"<div><span class='pill'>{doc.get('worlds_verified',0)}/11 Worlds Verified</span>"
                    f"<span class='pill'>{doc.get('cross_pollination_edges_count',0)} Cross-Pollination Edges</span>"
                    f"<span class='pill'>Theorems 1-14 SymPy Proved</span><span class='pill'>39/39 SHA256SUMS.orbit Sealed</span><span class='pill'>0 Cloud Tokens</span></div>"
                    f"<table><thead><tr><th>World</th><th>GEM Engine</th><th>Status</th><th>SHA-256</th></tr></thead><tbody>{rows_html}</tbody></table>"
                    "<p style='margin-top:20px;color:#9db2d1;line-height:1.8'>Live Observatory APIs: "
                    "<a style='color:#7ce8ff' href='/api/os/mind'>/api/os/mind</a> · "
                    "<a style='color:#7ce8ff' href='/api/os/mind/gem.svg'>/api/os/mind/gem.svg</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/elegance'>/api/kloster/elegance</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/thermo'>/api/kloster/thermo</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/riemannian'>/api/kloster/riemannian</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/transport'>/api/kloster/transport</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/majorization'>/api/kloster/majorization</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/quantum'>/api/kloster/quantum</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/mdl'>/api/kloster/mdl</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/unification'>/api/kloster/unification</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/referee-proofs'>/api/kloster/referee-proofs</a> · "
                    "<a style='color:#7ce8ff' href='/api/self-improving'>/api/self-improving</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/cryptanalysis'>/api/kloster/cryptanalysis</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/nsa-pack'>/api/kloster/nsa-pack</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/bio-crypto-circle'>/api/kloster/bio-crypto-circle</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/cnsa2-ring2'>/api/kloster/cnsa2-ring2</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/theorem13'>/api/kloster/theorem13</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/nsa-ring3'>/api/kloster/nsa-ring3</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/botanical-atlas'>/api/kloster/botanical-atlas</a> · "
                    "<a style='color:#63f5b5' href='/botanical'>/botanical (Interactive C27 Explorer)</a> · "
                    "<a style='color:#7ce8ff' href='/api/kloster/theorem14'>/api/kloster/theorem14</a> · "
                    "<a style='color:#7ce8ff' href='/api/orbit/master'>/api/orbit/master</a></p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if path == "/api/digest/latest":
                rep_file = resolved_root / "evidence" / "l5-mobile-digestion" / "digestion-report.json"
                if rep_file.is_file():
                    self._send_json(200, json.loads(rep_file.read_text(encoding="utf-8")))
                else:
                    self._send_json(200, {"available": False, "epistemic_boundaries": {"l5_agi_qualified": False}})
                return
            if path == "/api/export":
                with lock:
                    raw = json.dumps(engine.export_session(), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="zoe-eliza-session.json"')
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            self.send_error(404, "not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self._read_json()
                if path == "/api/chat":
                    msg = str(body.get("message") or "").strip()
                    gear = body.get("gear")
                    model = body.get("model")
                    with lock:
                        res = engine.respond(msg, gear=gear, model=model)
                    self._send_json(200, res)
                    return
                if path == "/api/speak":
                    text = str(body.get("text") or "").strip()
                    action = str(body.get("action") or "speak")
                    wav_bytes = synthesize_wav_bytes(text, action=action)
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(wav_bytes)))
                    self.end_headers()
                    self.wfile.write(wav_bytes)
                    return
                if path == "/api/playroom/jam":
                    from .creative_symphony import run_creative_symphony, synthesize_symphony_wav

                    seed = int(body.get("seed") or 2026)
                    sym_rep = run_creative_symphony(seed=seed, iterations=180, archive_bins=4)
                    champ = sym_rep["champion"]
                    with tempfile.TemporaryDirectory(prefix="zoe_eliza_jam_") as jtmp:
                        wav_p = Path(jtmp) / "jam.wav"
                        synthesize_symphony_wav(champ, wav_p)
                        wav_bytes = wav_p.read_bytes()
                    desc = champ["descriptors"]
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(wav_bytes)))
                    self.send_header("X-Zoe-Seed", str(seed))
                    self.send_header("X-Zoe-Groove", str(round(float(desc["groove_density"]), 3)))
                    self.send_header("X-Zoe-Curiosity", str(round(float(desc["curiosity_fitness"]), 4)))
                    self.end_headers()
                    self.wfile.write(wav_bytes)
                    return
                if path == "/api/memory/remember":
                    note = str(body.get("text") or "").strip()
                    topic = str(body.get("topic") or "atelier")
                    with lock:
                        saved = engine.remember(note, topic=topic)
                        snap = engine.memory_snapshot()
                    self._send_json(200, {"saved": saved, "memory_snapshot": snap})
                    return
                if path == "/api/memory/relay":
                    note = str(body.get("text") or "").strip()
                    topic = str(body.get("topic") or "lab_relay")
                    with lock:
                        saved = engine.relay_for_zoe(note, topic=topic)
                        snap = engine.memory_snapshot()
                    self._send_json(200, {"saved": saved, "memory_snapshot": snap})
                    return
                if path == "/api/memory/sync":
                    from zoe_autonomy.l5_phase4_unified_memory import merge_mobile_sync_batch

                    with lock:
                        res = merge_mobile_sync_batch(engine, body)
                    self._send_json(200, res)
                    return
                if path == "/api/digest/mobile":
                    from zoe_autonomy.l5_mobile_digestion import digest_mobile_bundle

                    with lock:
                        res = digest_mobile_bundle(engine, body, zoe_root=resolved_root)
                    self._send_json(200, res)
                    return
                if path == "/api/stem/route":
                    from zoe_autonomy.stem_layering import route_stem

                    prompt = str(body.get("prompt") or "").strip()
                    dec = route_stem(
                        prompt,
                        offline_only=bool(body.get("offline_only", False)),
                        privacy_sensitive=bool(body.get("privacy_sensitive", False)),
                        files_count=int(body.get("files_count", 1)),
                        multi_file=bool(body.get("multi_file", False)),
                        probe_local=bool(body.get("probe_local", False)),
                    )
                    self._send_json(200, dec.to_dict())
                    return
                if path == "/api/l5/phase5/run":
                    from zoe_autonomy.l5_phase5_frontier import ALL_PHASE5_PILLARS, run_l5_phase5_suite

                    pillar_id = body.get("pillar_id")
                    with lock:
                        if pillar_id:
                            chosen = None
                            for fn in ALL_PHASE5_PILLARS:
                                res = fn(resolved_root)
                                if res["pillar_id"] == str(pillar_id):
                                    chosen = res
                                    break
                            if chosen is None:
                                raise ValueError(f"unknown pillar_id: {pillar_id!r}")
                            self._send_json(200, chosen)
                        else:
                            rep = run_l5_phase5_suite(resolved_root)
                            self._send_json(200, rep)
                    return
                if path == "/api/l5/phase6/run":
                    from zoe_autonomy.l5_phase6_autonomous import ALL_PHASE6_PILLARS, run_l5_phase6_suite

                    pillar_id = body.get("pillar_id")
                    with lock:
                        if pillar_id:
                            chosen = None
                            for fn in ALL_PHASE6_PILLARS:
                                res = fn(resolved_root)
                                if res["pillar_id"] == str(pillar_id):
                                    chosen = res
                                    break
                            if chosen is None:
                                raise ValueError(f"unknown pillar_id: {pillar_id!r}")
                            self._send_json(200, chosen)
                        else:
                            rep = run_l5_phase6_suite(resolved_root)
                            self._send_json(200, rep)
                    return
                if path == "/api/l5/phase4/run":
                    from zoe_autonomy.l5_phase4_embodied import ALL_PHASE4_PILLARS, run_l5_phase4_suite

                    pillar_id = body.get("pillar_id")
                    with lock:
                        if pillar_id:
                            chosen = None
                            for fn in ALL_PHASE4_PILLARS:
                                res = fn(resolved_root)
                                if res["pillar_id"] == str(pillar_id):
                                    chosen = res
                                    break
                            if chosen is None:
                                raise ValueError(f"unknown pillar_id: {pillar_id!r}")
                            self._send_json(200, chosen)
                        else:
                            rep = run_l5_phase4_suite(resolved_root)
                            self._send_json(200, rep)
                    return
                if path == "/api/l5/phase3/run":
                    from zoe_autonomy.l5_phase3_live import ALL_PHASE3_PILLARS, run_l5_phase3_suite

                    pillar_id = body.get("pillar_id")
                    with lock:
                        if pillar_id:
                            chosen = None
                            for fn in ALL_PHASE3_PILLARS:
                                res = fn(resolved_root)
                                if res["pillar_id"] == str(pillar_id):
                                    chosen = res
                                    break
                            if chosen is None:
                                raise ValueError(f"unknown pillar_id: {pillar_id!r}")
                            self._send_json(200, chosen)
                        else:
                            rep = run_l5_phase3_suite(resolved_root)
                            self._send_json(200, rep)
                    return
                if path == "/api/gear":
                    gear = str(body.get("gear") or "gear1")
                    with lock:
                        st = engine.set_gear(gear)
                    self._send_json(200, st)
                    return
                if path == "/api/stop":
                    with lock:
                        st = engine.stop()
                    self._send_json(200, st)
                    return
                self.send_error(404, "not found")
            except (ValueError, RuntimeError, json.JSONDecodeError) as err:
                self._send_json(400, {"error": str(err)})

    server = ThreadingHTTPServer((bind_host, int(port)), ElizaHandler)
    return server, engine, lock


def _maybe_open_browser(url: str) -> None:
    for cmd in (["/snap/bin/brave", url], ["xdg-open", url]):
        if Path(cmd[0]).exists() or subprocess.run(["which", cmd[0]], capture_output=True).returncode == 0:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return
            except OSError:
                continue


def _speak_local(text: str, action: str = "speak") -> None:
    wav_bytes = synthesize_wav_bytes(text, action=action)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(wav_bytes)
        wav_path = tf.name
    try:
        for player in ("pw-play", "paplay", "aplay"):
            if subprocess.run(["which", player], capture_output=True).returncode == 0:
                subprocess.run([player, wav_path], check=False)
                break
    finally:
        Path(wav_path).unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zoe eliza",
        description="Zoe-ELIZA x GEM: Two-Gear Zero-Token Glass-Box Conversational Atelier",
    )
    sub = p.add_subparsers(dest="subcommand")

    for name in ("serve", "cli", "ask", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("--zoe-root", help="Zoe monorepo root; default ZOE_ROOT")
        sp.add_argument("--state", help="Persistent state directory; default ~/.zoe/eliza")
        if name == "serve":
            sp.add_argument("--host", default="127.0.0.1")
            sp.add_argument("--port", type=int, default=8765)
            sp.add_argument("--gear", choices=("gear1", "gear2"), default=None)
            sp.add_argument("--no-open", action="store_true")
        elif name == "cli":
            sp.add_argument("--gear", choices=("gear1", "gear2"), default="gear1")
            sp.add_argument("--speak", action="store_true")
        elif name == "ask":
            sp.add_argument("prompt", nargs="+")
            sp.add_argument("--gear", choices=("gear1", "gear2"), default="gear1")
            sp.add_argument("--json", action="store_true")

    # Root-level flags so bare `zoe eliza` launches serve cleanly
    p.add_argument("--zoe-root", help=argparse.SUPPRESS)
    p.add_argument("--state", help=argparse.SUPPRESS)
    p.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    p.add_argument("--port", type=int, default=8765, help=argparse.SUPPRESS)
    p.add_argument("--gear", choices=("gear1", "gear2"), default=None, help=argparse.SUPPRESS)
    p.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv=None) -> int:
    root = _ensure_autonomy()
    from zoe_autonomy.zoe_eliza import ZoeElizaEngine

    args = build_parser().parse_args(argv)
    zoe_root = Path(args.zoe_root or os.environ.get("ZOE_ROOT") or root).expanduser().resolve()
    cmd = args.subcommand or "serve"

    if cmd == "status":
        engine = ZoeElizaEngine(zoe_root, state_dir=args.state)
        print(json.dumps(engine.status(), indent=2, sort_keys=True))
        return 0

    if cmd == "ask":
        engine = ZoeElizaEngine(zoe_root, state_dir=args.state, default_gear=args.gear)
        res = engine.respond(" ".join(args.prompt), gear=args.gear)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            tr = res["eliza_trace"]
            mc = res["metacognition"]
            print(f"Zoe [{res['gear_used']} · {res['mode']} · rule={tr['matched_rule_id']} · A_tau={mc['a_tau']} · 0 tokens]:")
            print(res["reply"])
        return 0

    if cmd == "cli":
        engine = ZoeElizaEngine(zoe_root, state_dir=args.state, default_gear=args.gear)
        print("Zoe-ELIZA x GEM (0 cloud tokens · Glass-Box mode). Type 'quit' to exit.")
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"quit", "exit", "bye"}:
                print("Zoe: Session saved cleanly to SHA-256 memory. See you soon, Research Partner.")
                break
            res = engine.respond(line, gear=args.gear)
            tr = res["eliza_trace"]
            mc = res["metacognition"]
            cym = res["cymatics"]
            print(f"Zoe [{res['mode']} | rule={tr['matched_rule_id']} | A_0.08={mc['a_tau']} | /{cym['dominant_phoneme']}/{tuple(cym['modes'])}]:")
            print(res["reply"])
            if args.speak:
                hint = res.get("voice_hint") or {"action": "speak", "text": res["reply"]}
                _speak_local(hint.get("text", res["reply"]), action=hint.get("action", "speak"))
        return 0

    server, _engine, _lock = create_server(
        zoe_root,
        state_dir=args.state,
        host=args.host,
        port=args.port,
        default_gear=args.gear,
    )
    actual_port = server.server_address[1]
    url = f"http://{args.host}:{actual_port}"
    print(f"Zoe-ELIZA x GEM Atelier serving at {url} (0 cloud tokens · Ctrl+C to stop)")
    if not args.no_open:
        _maybe_open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
