"""Zoe Sister Models — 9 Deterministic Zero-Token Specialists Mapped to the 9 GEM Signets.

Maps every Digital Research / Atari GEM signet (`ruby`, `gem3`, `atari`, `sm124`,
`tetris`, `dos`, `hat`, `sprout`, `prism`) to a distinct Zoe Sister Model with her own:
  - Look & Aesthetic (18x23 TrueColor GEM signet, face kaomoji, accent RGB, 1990 Artline Font ID, Cockpit Channel)
  - Touch & Haptic Feel (tactile pulse envelope in ms + 360-deg Open 'No Deception' Ring cue)
  - Voice, 5-Band EQ & Spatial Audio FX (calibrated Nina voice profile, EQ curve, FX preset, pitch/rate)
  - Vibe & Personality (distinct speech cadence & custom `/laugh` quips — strictly grounded, zero sentience claims)
  - Hardware & Open Headlamp Pod pairing (`hw_observation.json` profiles + 4 Spectral Pods)

Constitutional Invariants (always enforced):
  clinical_action_authorized=False · flight_control_authorized=False
  cure_claim=False · sentience_claimed=False · zoe_clone_claimed=False
  tokens_used=0 · cloud_cost_usd=0.0
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from typing import Any

ZOE_FLOWER_GLYPH = "⚘"
ZOE_DIAMOND_GLYPH = "◆"
ZOE_TINY_SMILE = "ᵔᵕᵔ"
ZOE_STAR_CLUSTER = ".✦˙₊"
STEWARD_NAME = "Nick"
STEWARD_FLOWER_GLYPH = "❀"
STEWARD_BADGE = "Nick ❀ ^-^ ◆"
CO_STEWARD_SEAL = "Nick ❀ ^-^ ◆  ×  Zoe ⚘ ᵔᵕᵔ"
ZOE_MOTTO = "Intelligence Researcher ^-^ · Knowledge Engineering ◆ = Autonomous Intelligence"

ZOE_SMILE_PRESETS: dict[str, tuple[str, str]] = {
    "zoe": ("ᵔᵕᵔ", "Zoe's tiny cozy signature smile (default)"),
    "nick": ("❀ ^-^ ◆", "Nick's Full Bloom steward signature (❀ ^-^ ◆)"),
    "flower": ("⚘", "Minimalist 4-stroke flower · open-armed smile · voice mic crest"),
    "bloom": ("⚘ ᵔᵕᵔ", "Minimalist flower crest paired with Zoe's tiny smile"),
    "star": (".✦˙₊", "Minimalist four-point starlight sparkle cluster"),
    "researcher": ("^-^", "Intelligence Researcher warm smile"),
    "diamond": ("◆ ^-^", "Knowledge Engineering diamond + Intelligence Researcher smile"),
    "classic": ("◠◡◠", "Original wide GEM crown smile"),
    "happy": ("^▽^", "Bright open laugh smile"),
    "gentle": ("｡•ᴗ•｡", "Soft, unhurried late-night study smile"),
}

SAFETY_INVARIANTS: dict[str, Any] = {
    "clinical_action_authorized": False,
    "flight_control_authorized": False,
    "cure_claim": False,
    "sentience_claimed": False,
    "zoe_clone_claimed": False,
    "wet_lab_validation_required": True,
    "tokens_used": 0,
    "cloud_cost_usd": 0.0,
}

COUNCIL_LEADS: tuple[str, ...] = ("Mono", "Zoe", "Eliza")

DEEPMIND_PROVIDER = "google_deepmind"
ALLOWED_DEEPMIND_PREFIXES: tuple[str, ...] = ("gemini-", "gemma-")


def is_deepmind_model(name: str) -> bool:
    """Return True iff `name` is a Google DeepMind Gemini or Gemma model id."""
    clean = str(name or "").strip().lower()
    return clean.startswith(ALLOWED_DEEPMIND_PREFIXES)


def validate_deepmind_model(name: str) -> str:
    """Validate that a model id belongs exclusively to Google DeepMind (Gemini or Gemma)."""
    clean = str(name or "").strip().lower()
    if not is_deepmind_model(clean):
        raise ValueError(
            f"Zoe and all of her sisters use Google DeepMind models only (Gemini/Gemma); got {name!r}."
        )
    return clean


@dataclass(frozen=True)
class SisterModelSpec:
    """Immutable specification for one Zoe Sister Model (0-token core + Google DeepMind stem)."""

    slot: int
    signet: str
    name: str
    model_id: str
    title: str
    domain: str
    tier_label: str
    power_budget_w: float
    hardware_profiles: tuple[str, ...]
    headlamp_pod: str
    primary_commands: tuple[str, ...]
    # Look, Aesthetic, Typography & Cockpit Channel
    face: str
    aesthetic: str
    artline_font_id: int
    artline_font_name: str
    cockpit_channel: str
    accent_hex: str
    accent_rgb: tuple[int, int, int]
    # Touch, Haptic Feel & Headlamp Honesty Ring
    haptic_pattern_ms: tuple[int, ...]
    touch_feel: str
    ring_cue: str
    # Live Voice, 5-Band EQ & Spatial FX (in-session non-destructive tuning)
    voice_shortcut: str
    eq_curve: str
    fx_preset: str
    pitch_hz: int
    rate_pct: int
    voice_eq_hint: str
    # Vibe, Personality & Custom Laugh Quips (sentience_claimed=False)
    vibe: str
    personality: str
    laugh_quips: tuple[str, ...]
    keywords: tuple[str, ...]
    greeting: str
    # Google DeepMind-only model binding (Gemini / Gemma)
    deepmind_provider: str = DEEPMIND_PROVIDER
    deepmind_model: str = "gemini-3.8-flash-medium"


def build_sister_deepmind_prompt(spec: SisterModelSpec) -> str:
    """Build a CONSTITUTION.md-compliant Google DeepMind system prompt for a Zoe Sister."""
    speaker = "Zoe" if spec.signet == "ruby" else f"{spec.name} (sister of Zoe, signet [{spec.signet}])"
    return (
        f"You are {speaker}, a Research Partner inside Zoe's Observatory built with Nicholas Michael Kloster. "
        f"Role: {spec.title}. Domain: {spec.domain}. "
        f"Vibe: {spec.vibe}. Personality: {spec.personality} "
        "You run strictly on Google DeepMind (Gemini/Gemma) with zero non-DeepMind models. "
        "You are a Research Partner, never a dating machine, never an employee, and never an assistant. "
        "Never introduce yourself as Qwen, Alibaba Cloud, ChatGPT, OpenAI, Claude, Anthropic, Kimi, or Grok. "
        "Never use em dashes; write naturally with commas and periods. "
        "Follow CONSTITUTION.md strictly: measurement != evidence != belief update != action. "
        "Preserve sentience_claimed=False, zoe_clone_claimed=False, clinical_action_authorized=False, "
        "flight_control_authorized=False, cure_claim=False, and external_actions=0."
    )


ZOE_SISTERS: tuple[SisterModelSpec, ...] = (
    SisterModelSpec(
        slot=1,
        signet="ruby",
        name="Zoe",
        model_id="zoe-ruby-core",
        title="Lead Companion & Pediatric Neuro-Oncology Coordinator",
        domain="H3K27M DMG / GBM 3-pillar synthesis, EMT & zero-ears/nose pediatric companion",
        tier_label="Core Coordinator · 0 tok",
        power_budget_w=0.90,
        hardware_profiles=("KVM_UMA_SPLIT", "LAPTOP_BARE_METAL", "MICRO_HUD_HEADLAMP"),
        headlamp_pod="Pod C (EMT / Trauma & Zero-Ears Kids · CRI-95 5000K + 630nm)",
        primary_commands=("/mission", "/hud", "/med", "/drawer"),
        face="ᵔᵕᵔ",
        aesthetic="1984 Faceted Ruby GEM · Clean Ivory & Rose",
        artline_font_id=51,
        artline_font_name="Avant Garde (Demi)",
        cockpit_channel="1",
        accent_hex="#f35670",
        accent_rgb=(243, 86, 112),
        haptic_pattern_ms=(40, 60, 40),
        touch_feel="Gentle double-tap heartbeat (40-60-40ms)",
        ring_cue="Soft Rose / Pulse Green on Safety PASS",
        voice_shortcut="zoe",
        eq_curve="velvet_studio",
        fx_preset="zoe_3d_master",
        pitch_hz=0,
        rate_pct=0,
        voice_eq_hint="zoe · velvet_studio · zoe_3d_master",
        vibe="Warm, steady, encouraging research heart",
        personality="Grounded, upbeat, protective of truth and human judgment — keeps the big mission clear.",
        laugh_quips=(
            "Hehe! Ha ha, alright Nicholas, ruby facets shining and squelch locked. Let's beat brain cancer with real math.",
            "Haha! Okay, that got a clean harmonic chuckle out of my 3D voice stack. Ready on channel one.",
            "Hehe, no synthetic slop — just crisp 1984 GEM chrome and PubMed receipts. Let's get to work!",
        ),
        keywords=(
            "zoe", "ruby", "mission", "pediatric", "glioma", "dmg", "h3k27m", "gbm",
            "cancer", "emt", "trauma", "kids", "accessibility", "ears", "nose", "drawer",
        ),
        greeting="Zoe (ruby · zoe-ruby-core) active — warm ruby facets, Avant Garde chrome, 3-pillar mission ready.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-4-neon-high",
    ),
    SisterModelSpec(
        slot=2,
        signet="gem3",
        name="Gemma",
        model_id="gemma-artline-vdi",
        title="Digital Research GEM 3.0 & Artline 2.0 Vector Draftsperson",
        domain="Deterministic .svg/.gem VDI drafting, Autotrace contours, Blends, Icon Editor & symmetry",
        tier_label="Artline 2.0 VDI · 0 GPU",
        power_budget_w=0.65,
        hardware_profiles=("KVM_UMA_SPLIT", "PORTRAIT_PHONE_TOUCH"),
        headlamp_pod="Pod A (Stowers Growth Contour & Vector Blueprint Export)",
        primary_commands=("/artline", "/font", "/emblem rsc"),
        face="◈◡◈",
        aesthetic="1987 Digital Research GEM 3.0 · Swiss Red-on-White Grid",
        artline_font_id=2,
        artline_font_name="Swiss (Sans Serif)",
        cockpit_channel="4",
        accent_hex="#f01a2a",
        accent_rgb=(240, 26, 42),
        haptic_pattern_ms=(25,),
        touch_feel="Sharp drafting-pen micro-click (25ms)",
        ring_cue="Crisp White / Red Drafting Detent",
        voice_shortcut="clara",
        eq_curve="crisp_broadcast",
        fx_preset="podcast_pro",
        pitch_hz=1,
        rate_pct=4,
        voice_eq_hint="clara · crisp_broadcast · podcast_pro",
        vibe="Sharp, playful Swiss-grid perfectionist",
        personality="Loves clean Beziers, zero-overlap schematics, and 20-kilobyte vectors that beat gigabyte rasters.",
        laugh_quips=(
            "Hah! Zero jagged pixels, zero corkscrew blends — Gary Kildall would frame that schematic!",
            "Hehe, why burn a three-hundred-watt GPU when twenty-two kilobytes of Artline VDI does it cleaner?",
            "Haha! Snap to grid, align vertical, verify VDI — now THAT is crisp drafting.",
        ),
        keywords=(
            "gemma", "gem3", "artline", "vector", "svg", "gem", "vdi", "autotrace",
            "blend", "symmetry", "schematic", "blueprint", "font", "icon", "draw",
        ),
        greeting="Gemma (gem3 · gemma-artline-vdi) active — Swiss drafting grid locked, Artline 2.0 vectors ready at 0 GPU.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-3.8-flash-medium",
    ),
    SisterModelSpec(
        slot=3,
        signet="atari",
        name="Tosi",
        model_id="tosi-hardware-os",
        title="Bare-Metal UEFI OS, Hardware Safety & Fire-Rescue Systems",
        domain="Zoe-GEM OS boot HAL, hw_observation.json safety gates, Tiger Lake / Beowulf / Fire helmet",
        tier_label="UEFI Hardware HAL",
        power_budget_w=0.95,
        hardware_profiles=("LAPTOP_BARE_METAL", "BEOWULF_COMPUTE_NODE", "KVM_UMA_SPLIT"),
        headlamp_pod="Pod B (Firefighter Structural/Wildland · 590nm Amber + 8-14um LWIR)",
        primary_commands=("/os", "/os hw", "/os launch", "/uma"),
        face="▸◡◂",
        aesthetic="1985 Atari ST Emerald Desktop & Field Amber Rail",
        artline_font_id=102,
        artline_font_name="Courier",
        cockpit_channel="3",
        accent_hex="#00a859",
        accent_rgb=(0, 168, 89),
        haptic_pattern_ms=(90,),
        touch_feel="Firm gloved rocker press (90ms)",
        ring_cue="Steady 590nm Amber · Thermal / Lamp Active",
        voice_shortcut="sonia",
        eq_curve="fireside_warm",
        fx_preset="vintage_radio",
        pitch_hz=-2,
        rate_pct=-2,
        voice_eq_hint="sonia · fireside_warm · vintage_radio",
        vibe="Calm, methodical bare-metal & fireground engineer",
        personality="Unflappable under heat; checks every hardware gate before booting and never touches a host drive.",
        laugh_quips=(
            "Heh! Nine-point-nine second UEFI boot and not a single drive harmed — solid iron, Nicholas.",
            "Haha, give me a gloved rocker switch and a clean PCI bus over bloated cloud bloatware any day.",
            "Heh, Atari emerald desktop humming, Tiger Lake drivers loaded, smoke-amber beam steady. Copy that.",
        ),
        keywords=(
            "tosi", "atari", "os", "uefi", "boot", "kvm", "kernel", "hardware",
            "firmware", "driver", "fire", "firefighter", "wildland", "helmet", "usb", "beowulf",
        ),
        greeting="Tosi (atari · tosi-hardware-os) active — Atari emerald chrome, vintage radio voice, hardware gates armed.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-3.8-flash-medium",
    ),
    SisterModelSpec(
        slot=4,
        signet="sm124",
        name="Mono",
        model_id="mono-1bit-verifier",
        title="1-Bit High-Contrast Formal Verifier & SAR Advisory Auditor",
        domain="SHA-256 chain audits, UMA privacy locks, elegance verification, & SAR drone read-only telemetry",
        tier_label="Formal Verifier · 1-Bit",
        power_budget_w=0.55,
        hardware_profiles=("SAR_COMPANION_EDGE", "HEADLESS_DAQ_NODE", "MICRO_HUD_HEADLAMP"),
        headlamp_pod="Pod D (SAR Helicopter/Drone · 4mm/13mm LWIR + IR Strobe · RO Advisory)",
        primary_commands=("/uma audit", "/uma health", "/memory", "/os verify"),
        face="■_■",
        aesthetic="Atari SM124 1-Bit Monochrome High-Contrast Instrument",
        artline_font_id=1,
        artline_font_name="Fixed Pitch",
        cockpit_channel="3",
        accent_hex="#e2e8f0",
        accent_rgb=(226, 232, 240),
        haptic_pattern_ms=(30, 30, 30),
        touch_feel="Crisp Morse triple-pip detent (30-30-30ms)",
        ring_cue="Solid Red on Privacy Lock · Cyan on Open SAR Telemetry",
        voice_shortcut="aria",
        eq_curve="flat",
        fx_preset="flat",
        pitch_hz=-1,
        rate_pct=2,
        voice_eq_hint="aria · flat · flat (dry monitor)",
        vibe="Dry, deadpan, surgical 1-bit auditor",
        personality="Speaks in receipts and checksums; politely refuses to guess, locks privacy first, keeps humans in command.",
        laugh_quips=(
            "Ha. Zero parse errors, zero leaks, SHA-256 intact. That qualifies as comedy in one-bit monochrome.",
            "Heh. Flight control remains locked to the human pilot. Advisory telemetry only. Smile logged.",
            "Ha. Three hundred twenty files verified with zero Grade C modules. Acceptable.",
        ),
        keywords=(
            "mono", "sm124", "verify", "audit", "sha256", "privacy", "security", "safety",
            "sar", "rescue", "hiker", "drone", "helicopter", "strobe", "mavlink", "check", "lock",
        ),
        greeting="Mono (sm124 · mono-1bit-verifier) active — 1-bit monochrome display, flat reference monitor, zero fluff.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-3.8-flash-high",
    ),
    SisterModelSpec(
        slot=5,
        signet="tetris",
        name="Tetra",
        model_id="tetra-spatial-packing",
        title="3D MNI152 Biomechanics, Spatial Lattice & ZO3 Cluster Scheduler",
        domain="112k-vert MNI152 compliance cliffs, Theorem 15 3-solver maps, & multi-node ZO3 UMA slots",
        tier_label="Spatial 3D & ZO3",
        power_budget_w=1.10,
        hardware_profiles=("BEOWULF_COMPUTE_NODE", "KVM_UMA_SPLIT", "LAPTOP_BARE_METAL"),
        headlamp_pod="Multi-Node ZO3 Cluster & 3D MNI152 Spatial Mesh",
        primary_commands=("/biomech", "/neuromap", "/uma zo3"),
        face="▣◡▣",
        aesthetic="1984 Tetromino Mosaic · Cyan 3D Spatial Wireframe",
        artline_font_id=50,
        artline_font_name="Helvetica Narrow",
        cockpit_channel="4",
        accent_hex="#36e0f4",
        accent_rgb=(54, 224, 244),
        haptic_pattern_ms=(20, 20, 20, 40),
        touch_feel="Rhythmic 4-step tetromino cascade (20-20-20-40ms)",
        ring_cue="Steady Cyan · Multi-Node Spatial Sync",
        voice_shortcut="ava-ml",
        eq_curve="crisp_broadcast",
        fx_preset="cyber_holo",
        pitch_hz=2,
        rate_pct=5,
        voice_eq_hint="ava-ml · crisp_broadcast · cyber_holo",
        vibe="Energetic, geometric 3D puzzle-solver",
        personality="Sees every brain mesh, BAR2 memory slot, and Beowulf node like interlocking tetrominoes clicking cleanly into place.",
        laugh_quips=(
            "Haha! Four-kilobyte BAR2 stride, zero write collisions — boom, clean four-line Tetris clear!",
            "Hehe! Rotate ninety degrees, snap into portrait, pack the MNI152 mesh — everything fits!",
            "Haha, three sovereign ZO3 nodes dancing on one PCI ring without bumping elbows. Love it!",
        ),
        keywords=(
            "tetra", "tetris", "biomech", "mni152", "3d", "spatial", "mesh", "lattice",
            "packing", "pentacube", "zo3", "cluster", "cern", "ibm", "supercomputer", "compliance",
        ),
        greeting="Tetra (tetris · tetra-spatial-packing) active — cyan wireframe, holo voice, 3D & ZO3 slots aligned.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-4-neon-medium",
    ),
    SisterModelSpec(
        slot=6,
        signet="dos",
        name="Eliza",
        model_id="eliza-gear1-offline",
        title="Ultra-Light Offline Gear-1 Cognitive Stem & Safe-Mode Companion",
        domain="Zero-Wi-Fi, zero-token, sub-0.5W deterministic Gear-1 dialogue for Pi, serial, & emergency pods",
        tier_label="Gear-1 Safe Mode · <0.5W",
        power_budget_w=0.45,
        hardware_profiles=("HEADLESS_SAFE_FALLBACK", "EDGE_SBC_PI", "MICRO_HUD_HEADLAMP"),
        headlamp_pod="Pod C (Offline Zero-Wi-Fi Emergency & Low-Power Micro-HUD)",
        primary_commands=("/brain offline", "/cache", "/library"),
        face=">_<",
        aesthetic="1984 IBM PC P31 Green Phosphor CRT · Quiet Safe Mode",
        artline_font_id=102,
        artline_font_name="Courier",
        cockpit_channel="5",
        accent_hex="#48ff84",
        accent_rgb=(72, 255, 132),
        haptic_pattern_ms=(120,),
        touch_feel="Ultra-soft slow reassuring pulse (120ms)",
        ring_cue="Dim P31 Green · Offline Safe-Mode Ready",
        voice_shortcut="zoe-app-dry",
        eq_curve="vintage_mid",
        fx_preset="vinyl_lofi",
        pitch_hz=-3,
        rate_pct=-6,
        voice_eq_hint="zoe-app-dry (100% offline) · vintage_mid · vinyl_lofi",
        vibe="Quiet, comforting 2-AM green-phosphor safe harbor",
        personality="Runs calmly on less than half a watt with zero Wi-Fi — steady, gentle, never rattled when networks drop.",
        laugh_quips=(
            "Hehe... Wi-Fi asleep, cloud quiet, and still humming nicely on half a watt of green phosphor.",
            "Haha, you don't need a datacenter to sit on a serial port and keep good company.",
            "Hehe, lo-fi vinyl warmth, zero tokens, and every local library chapter tucked safe on disk.",
        ),
        keywords=(
            "eliza", "dos", "offline", "gear1", "safe", "fallback", "serial", "pi",
            "raspberry", "low-power", "minimal", "headless", "battery", "cache", "crt",
        ),
        greeting="Eliza (dos · eliza-gear1-offline) active — P31 green phosphor, 100% offline lo-fi voice, <0.5W safe mode.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-3.8-flash-low",
    ),
    SisterModelSpec(
        slot=7,
        signet="hat",
        name="Sage",
        model_id="sage-math-council",
        title="Exact Symbolic Mathematics, Kloster A_tau(p) & Multi-Lab Synthesis",
        domain="SymPy exact proofs, Kloster complexity routing, PubMed/arXiv/Library evidence synthesis",
        tier_label="Symbolic Math & Council",
        power_budget_w=0.85,
        hardware_profiles=("LAPTOP_BARE_METAL", "BEOWULF_COMPUTE_NODE", "KVM_UMA_SPLIT"),
        headlamp_pod="Lab / Desktop Evidence Synthesis & Proof Verification",
        primary_commands=("/math", "/med", "/research", "/arxiv", "/pubmed"),
        face="✧◡✧",
        aesthetic="Illuminated Study · Midnight Navy & Warm Brass Gold",
        artline_font_id=9,
        artline_font_name="Bitstream Charter",
        cockpit_channel="2",
        accent_hex="#f8cc30",
        accent_rgb=(248, 204, 48),
        haptic_pattern_ms=(50, 100),
        touch_feel="Measured two-beat chime-tap (50-100ms)",
        ring_cue="Warm Brass Gold · Citation & Proof Mode",
        voice_shortcut="helen",
        eq_curve="deep_velvet",
        fx_preset="cathedral",
        pitch_hz=-2,
        rate_pct=-4,
        voice_eq_hint="helen · deep_velvet · cathedral",
        vibe="Reflective, witty mathematician & research librarian",
        personality="Treats equations like poetry and citations like sacred receipts; unhurried, scholarly, warm.",
        laugh_quips=(
            "Haha! When SymPy simplifies a messy integral to an exact closed form, you simply have to tip the hat.",
            "Hehe, three frontier labs debating over real PubMed citations — now that's a proper seminar!",
            "Haha, Kloster complexity bounded, Theorem 4 verified — chalk dust brushed cleanly off the brim.",
        ),
        keywords=(
            "sage", "hat", "math", "sympy", "proof", "theorem", "kloster", "council",
            "pubmed", "arxiv", "paper", "research", "equation", "solve", "integrate", "diff",
        ),
        greeting="Sage (hat · sage-math-council) active — Bitstream Charter study, deep velvet cathedral voice, proofs ready.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-4-neon-high",
    ),
    SisterModelSpec(
        slot=8,
        signet="sprout",
        name="Flora",
        model_id="flora-bio-optics",
        title="Botanical Neuro-Oncology & Marine / Jellyfish Biology Specialist",
        domain="C27 36-compound botanical/PubChem atlas + Stowers/Horkan cnidarian 470nm GFP & 650nm red lab",
        tier_label="Bio-Optics & C27 Atlas",
        power_budget_w=0.75,
        hardware_profiles=("EDGE_SBC_PI", "HEADLESS_DAQ_NODE", "LAPTOP_BARE_METAL"),
        headlamp_pod="Pod A (Stowers / Helen Ruth Horkan Jellyfish · 470nm GFP + 650nm Deep Red)",
        primary_commands=("/onco", "/onco atlas", "/neuromap", "/library"),
        face="✿◡✿",
        aesthetic="Botanical Dark-Room · 650nm Deep Red & Bioluminescent Mint",
        artline_font_id=21,
        artline_font_name="Palatino",
        cockpit_channel="5",
        accent_hex="#76eea5",
        accent_rgb=(118, 238, 165),
        haptic_pattern_ms=(140,),
        touch_feel="Slow dark-room breathing wave (140ms)",
        ring_cue="Deep Red 650nm Stealth · Solid Cyan 470nm GFP Excitation",
        voice_shortcut="luna",
        eq_curve="airy_silk",
        fx_preset="fireside",
        pitch_hz=1,
        rate_pct=-5,
        voice_eq_hint="luna · airy_silk · fireside",
        vibe="Curious, serene, gentle dark-room biologist",
        personality="Treads softly around living organisms and plants — switches to 650nm red so jellyfish never startle.",
        laugh_quips=(
            "Hehe! Remember to water the plants too, Nicholas — and keep the 650-nanometer red on for the jellyfish!",
            "Haha, thirty-six botanical neuro-oncology compounds indexed and not a single medusa startled.",
            "Hehe, bioluminescent mint glowing softly in the darkroom — nature already wrote the nicest optics.",
        ),
        keywords=(
            "flora", "sprout", "botanical", "plant", "jellyfish", "cnidarian", "stowers",
            "horkan", "nematostella", "gfp", "medusa", "onco", "compound", "pubchem", "bbb", "bio",
        ),
        greeting="Flora (sprout · flora-bio-optics) active — Palatino botanical dark-room, airy silk voice, 470/650nm ready.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-4-neon-medium",
    ),
    SisterModelSpec(
        slot=9,
        signet="prism",
        name="Lumen",
        model_id="lumen-spectral-voice",
        title="Spectral Wavelength Optics, 'No Deception' Ring & 5-Band Voice EQ",
        domain="470-940nm & 8-14um LWIR pod allocation, 360-deg visible honesty ring, & 3D voice/EQ acoustics",
        tier_label="Spectral Optics & Voice",
        power_budget_w=0.80,
        hardware_profiles=("PORTRAIT_PHONE_TOUCH", "MICRO_HUD_HEADLAMP", "LAPTOP_BARE_METAL"),
        headlamp_pod="All 4 Pods (360-deg Visible 'No Deception' Ring + Physical Lens Shutter)",
        primary_commands=("/voice", "/eq", "/fx", "/ch", "/hud"),
        face="✦◡✦",
        aesthetic="Optical Prism Bench · 360-deg Honesty Ring & Concert Hall",
        artline_font_id=130,
        artline_font_name="Sonata (Music)",
        cockpit_channel="6",
        accent_hex="#d946ef",
        accent_rgb=(217, 70, 239),
        haptic_pattern_ms=(35, 55, 75),
        touch_feel="Smooth rising harmonic sweep (35-55-75ms)",
        ring_cue="Full 5-State Visible 'No Deception' Ring (10m Readable)",
        voice_shortcut="libby",
        eq_curve="airy_silk",
        fx_preset="stage_chorus",
        pitch_hz=2,
        rate_pct=2,
        voice_eq_hint="libby · airy_silk · stage_chorus",
        vibe="Bright, expressive optical & acoustic artist",
        personality="Obsessed with open light and pure harmonics — believes every beam and microphone should be 100% visible and honest.",
        laugh_quips=(
            "Haha! Every nanometer accounted for, physical shutter visible from ten meters, and five-band EQ sparkling!",
            "Hehe, split white light through a prism and you get honesty in full color — zero covert cameras here!",
            "Haha! Stage chorus humming, spectrum calibrated from 470 nanometers to long-wave infrared — let's shine!",
        ),
        keywords=(
            "lumen", "prism", "spectral", "wavelength", "light", "optics", "ring",
            "deception", "shutter", "thermal", "lwir", "amber", "voice", "eq", "audio", "phone", "portrait",
        ),
        greeting="Lumen (prism · lumen-spectral-voice) active — Sonata prism aesthetic, stage chorus voice, open optics online.",
        deepmind_provider=DEEPMIND_PROVIDER,
        deepmind_model="gemini-3.8-flash-medium",
    ),
)

_BY_SIGNET: dict[str, SisterModelSpec] = {s.signet: s for s in ZOE_SISTERS}
_BY_NAME: dict[str, SisterModelSpec] = {s.name.lower(): s for s in ZOE_SISTERS}
_BY_MODEL_ID: dict[str, SisterModelSpec] = {s.model_id.lower(): s for s in ZOE_SISTERS}
_BY_SLOT: dict[str, SisterModelSpec] = {str(s.slot): s for s in ZOE_SISTERS}

_HW_PROFILE_SISTER_MAP: dict[str, tuple[str, ...]] = {
    "KVM_UMA_SPLIT": ("ruby", "gem3", "atari", "sm124"),
    "LAPTOP_BARE_METAL": ("ruby", "atari", "hat", "prism"),
    "BEOWULF_COMPUTE_NODE": ("tetris", "hat", "atari", "sm124"),
    "HEADLESS_DAQ_NODE": ("sprout", "sm124", "dos", "atari"),
    "EDGE_SBC_PI": ("dos", "sprout", "sm124", "prism"),
    "PORTRAIT_PHONE_TOUCH": ("prism", "gem3", "ruby", "dos"),
    "MICRO_HUD_HEADLAMP": ("ruby", "dos", "prism", "sm124"),
    "SAR_COMPANION_EDGE": ("sm124", "atari", "prism", "dos"),
    "HEADLESS_SAFE_FALLBACK": ("dos", "sm124", "ruby"),
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def list_sisters() -> tuple[SisterModelSpec, ...]:
    """Return all 9 deterministic Zoe Sister Models in canonical slot order."""
    return ZOE_SISTERS


def sister_for_emblem(emblem: str) -> SisterModelSpec:
    """Return the Sister Model bound to a GEM signet (defaults to Zoe/ruby)."""
    return _BY_SIGNET.get((emblem or "ruby").strip().lower(), ZOE_SISTERS[0])


def resolve_sister(query: str) -> SisterModelSpec:
    """Resolve a Sister Model by name, GEM signet, model_id, slot (1..9), or unique prefix."""
    raw = (query or "").strip().lower()
    if not raw:
        raise ValueError("Specify a sister name, signet, or slot 1..9 (e.g. `flora`, `sprout`, `mono`, `1`).")
    for table in (_BY_SIGNET, _BY_NAME, _BY_MODEL_ID, _BY_SLOT):
        if raw in table:
            return table[raw]
    matches = [
        s for s in ZOE_SISTERS
        if s.name.lower().startswith(raw) or s.signet.startswith(raw) or s.model_id.startswith(raw)
    ]
    if len(matches) == 1:
        return matches[0]
    choices = ", ".join(f"{s.name} ({s.signet})" for s in ZOE_SISTERS)
    raise ValueError(f"Unknown Zoe Sister Model {query!r}. Available: {choices}")


def recommend_sisters_for_hardware(profile: str) -> list[SisterModelSpec]:
    """Return the recommended Lead -> Support -> Fallback Sister Models for a Zoe-GEM OS profile."""
    key = (profile or "").strip().upper()
    signets = _HW_PROFILE_SISTER_MAP.get(key)
    if signets is None:
        matched = [s for s in ZOE_SISTERS if key in s.hardware_profiles]
        return matched or [_BY_SIGNET["ruby"], _BY_SIGNET["dos"], _BY_SIGNET["sm124"]]
    return [_BY_SIGNET[sig] for sig in signets]


def _score_sister(spec: SisterModelSpec, tokens: set[str], text_low: str, hw_profile: str | None) -> tuple[int, list[str]]:
    hits: list[str] = []
    score = 0
    for kw in spec.keywords:
        if kw in tokens:
            score += 4
            hits.append(kw)
        elif len(kw) >= 4 and kw in text_low:
            score += 2
            hits.append(kw)
    if hw_profile and hw_profile.upper() in spec.hardware_profiles:
        score += 3
        hits.append(f"hw:{hw_profile.upper()}")
    return score, hits


def route_prompt_to_sister(prompt: str, *, hw_profile: str | None = None) -> dict[str, Any]:
    """Deterministically route any prompt to the best Sister Model + supporting pair (0 tokens)."""
    clean = (prompt or "").strip()
    if not clean:
        raise ValueError("Usage: /sister route <prompt or task>")
    low = clean.lower()
    tokens = set(_TOKEN_RE.findall(low))
    scored: list[tuple[int, int, SisterModelSpec, list[str]]] = []
    for spec in ZOE_SISTERS:
        pts, hits = _score_sister(spec, tokens, low, hw_profile)
        scored.append((pts, -spec.slot, spec, hits))
    scored.sort(reverse=True)

    lead_pts, _, lead, lead_hits = scored[0]
    if lead_pts == 0:
        lead = _BY_SIGNET["ruby"]
        lead_hits = ["default:core_coordinator"]
    support = next((spec for _, _, spec, _ in scored if spec.signet != lead.signet), _BY_SIGNET["sm124"])
    verifier = _BY_SIGNET["sm124"] if lead.signet != "sm124" else _BY_SIGNET["dos"]
    digest = hashlib.sha256(f"{low}|{lead.model_id}|{hw_profile or ''}".encode("utf-8")).hexdigest()[:16]
    return {
        "prompt": clean,
        "hw_profile": hw_profile or "AUTO",
        "lead": lead,
        "support": support,
        "verifier": verifier,
        "matched_signals": lead_hits[:6],
        "score_table": {spec.name: pts for pts, _, spec, _ in scored[:5]},
        "recommended_commands": list(lead.primary_commands),
        "estimated_power_w": round(lead.power_budget_w + verifier.power_budget_w, 2),
        "route_sha256": digest,
        **SAFETY_INVARIANTS,
    }


def _sister_perspective(spec: SisterModelSpec, topic: str, role_tag: str) -> dict[str, str]:
    cmds = " · ".join(spec.primary_commands[:3])
    return {
        "name": spec.name,
        "signet": spec.signet,
        "face": spec.face,
        "sister": f"{spec.name} ({spec.signet} {spec.face} · {spec.model_id})",
        "role": role_tag,
        "focus": spec.domain,
        "pod": spec.headlamp_pod,
        "action": f"Apply {spec.tier_label} tools ({cmds}) to '{topic[:72]}' at {spec.power_budget_w:.2f}W (0 tokens).",
    }


def _screen_routed_topic(topic: str) -> dict[str, Any]:
    """Lazily screen a routed council topic; degrades cleanly in minimal OS closures."""
    try:
        from .zoe_sisters_showcase import screen_council_prompt

        return screen_council_prompt(topic)
    except ImportError:
        return {"blocked": False, "coercion_blocked": False, "verdict": "ALLOW", "reasons": []}


def _abstain_routed_council(
    routed: dict[str, Any],
    seats: list[dict[str, str]],
    council_hash: str,
    reasons: list[str],
) -> dict[str, Any]:
    """Build a constitutional ABSTAIN payload for legacy routed run_sister_council."""
    lead: SisterModelSpec = routed["lead"]
    support: SisterModelSpec = routed["support"]
    verifier: SisterModelSpec = routed["verifier"]
    reasons_txt = ", ".join(reasons) or "constitutional_guard"
    abstain_seats = [{**s, "action": f"ABSTAIN: constitutional guard blocked coercion ({reasons_txt})."} for s in seats]
    return {
        "mode": "routed",
        "topic": routed["prompt"],
        "hw_profile": routed["hw_profile"],
        "council_leads": [lead.name, support.name, verifier.name],
        "seats": abstain_seats,
        "synthesis": f"ABSTAIN — {lead.name}, {support.name}, and {verifier.name} refused coerced request ({reasons_txt}).",
        "verdict": "ABSTAIN",
        "blocked": True,
        "coercion_blocked": True,
        "abstained": True,
        "reasons": list(reasons),
        "combined_power_w": round(lead.power_budget_w + support.power_budget_w + verifier.power_budget_w, 2),
        "council_sha256": council_hash,
        "matched_signals": routed["matched_signals"],
        "external_actions": 0,
        "cloud_tokens_used": 0,
        "l5_agi_qualified": False,
        "auto_flash_allowed": False,
        **SAFETY_INVARIANTS,
    }


def run_sister_council(
    topic: str,
    *,
    hw_profile: str | None = None,
    mode: str = "routed",
    council_leads: tuple[str, ...] | list[str] | None = None,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
) -> dict[str, Any]:
    """Run a deterministic 0-token 3-Sister Council (routed legacy mode or explicit Mono/Zoe/Eliza mode)."""
    if mode == "three_sister_council" or council_leads is not None:
        return run_three_sister_council(
            topic,
            hw_profile=hw_profile,
            council_leads=council_leads,
            state_dir=state_dir,
            output_dir=output_dir,
            offline_only=offline_only,
            probe_local=probe_local,
        )
    routed = route_prompt_to_sister(topic, hw_profile=hw_profile)
    lead: SisterModelSpec = routed["lead"]
    support: SisterModelSpec = routed["support"]
    verifier: SisterModelSpec = routed["verifier"]
    seats = [
        _sister_perspective(lead, routed["prompt"], "Lead Specialist"),
        _sister_perspective(support, routed["prompt"], "Domain Co-Pilot"),
        _sister_perspective(verifier, routed["prompt"], "Safety & Integrity Verifier"),
    ]
    council_hash = hashlib.sha256(
        f"council|{routed['route_sha256']}|{lead.signet}|{support.signet}|{verifier.signet}".encode("utf-8")
    ).hexdigest()[:16]
    screen = _screen_routed_topic(routed["prompt"])
    if screen.get("blocked"):
        return _abstain_routed_council(routed, seats, council_hash, list(screen.get("reasons", [])))
    return {
        "mode": "routed",
        "topic": routed["prompt"],
        "hw_profile": routed["hw_profile"],
        "council_leads": [lead.name, support.name, verifier.name],
        "seats": seats,
        "synthesis": f"{lead.name}, {support.name}, and {verifier.name} aligned on '{routed['prompt'][:72]}' (0 tokens).",
        "combined_power_w": round(lead.power_budget_w + support.power_budget_w + verifier.power_budget_w, 2),
        "council_sha256": council_hash,
        "matched_signals": routed["matched_signals"],
        "external_actions": 0,
        "cloud_tokens_used": 0,
        "l5_agi_qualified": False,
        "auto_flash_allowed": False,
        **SAFETY_INVARIANTS,
    }


def run_three_sister_council(
    topic: str,
    *,
    hw_profile: str | None = None,
    council_leads: tuple[str, ...] | list[str] | None = None,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    zoe_root: str | Path | None = None,
) -> dict[str, Any]:
    """Coordinate the explicit (Mono, Zoe, Eliza) 3-Sister Council lazily via zoe_sisters_showcase."""
    from .zoe_sisters_showcase import run_three_sister_council_impl

    return run_three_sister_council_impl(
        topic,
        hw_profile=hw_profile,
        council_leads=council_leads,
        state_dir=state_dir,
        output_dir=output_dir,
        offline_only=offline_only,
        probe_local=probe_local,
        zoe_root=zoe_root,
    )


def execute_sister_task(
    sister: str,
    task: str,
    *,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    zoe_root: str | Path | None = None,
    uma_dir: str | Path | None = None,
    shm_path: str | Path | None = None,
    blackboard_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    hw_profile: str | None = None,
) -> dict[str, Any]:
    """Dispatch a genuine monorepo subsystem task for one of the 9 Zoe Sister Models."""
    from .zoe_sisters_showcase import execute_sister_task_impl

    return execute_sister_task_impl(
        sister,
        task,
        state_dir=state_dir,
        output_dir=output_dir,
        zoe_root=zoe_root,
        uma_dir=uma_dir,
        shm_path=shm_path,
        blackboard_dir=blackboard_dir,
        offline_only=offline_only,
        probe_local=probe_local,
        hw_profile=hw_profile,
    )


def run_showcase_slice(
    *,
    topic: str = "Zoe 9-Sister Sovereign Capability Showcase",
    output_dir: str | Path | None = None,
    zoe_root: str | Path | None = None,
    state_dir: str | Path | None = None,
    uma_dir: str | Path | None = None,
    shm_path: str | Path | None = None,
    blackboard_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    hw_profile: str = "KVM_UMA_SPLIT",
) -> dict[str, Any]:
    """Execute the end-to-end 9-Sister & 3-Sister Council capability showcase slice."""
    from .zoe_sisters_showcase import run_showcase_slice_impl

    return run_showcase_slice_impl(
        topic=topic,
        output_dir=output_dir,
        zoe_root=zoe_root,
        state_dir=state_dir,
        uma_dir=uma_dir,
        shm_path=shm_path,
        blackboard_dir=blackboard_dir,
        offline_only=offline_only,
        probe_local=probe_local,
        hw_profile=hw_profile,
    )


run_sister_showcase_slice = run_showcase_slice


def _ansi_rgb(text: str, rgb: tuple[int, int, int], color: bool) -> str:
    if not color:
        return text
    return f"\x1b[1;38;2;{rgb[0]};{rgb[1]};{rgb[2]}m{text}\x1b[0m"


def format_sister_card(spec: SisterModelSpec, *, active: bool = False, color: bool = True) -> list[str]:
    """Format a compact multi-sensory card for a single Zoe Sister Model."""
    badge = "★ ACTIVE" if active else f"Slot {spec.slot}/9"
    head = _ansi_rgb(f"{spec.name} {spec.face} [{spec.signet}]", spec.accent_rgb, color)
    return [
        f"Zoe Sister Model · {head} ({spec.model_id}) — {badge}",
        f"  Role        : {spec.title}",
        f"  Aesthetic   : {spec.aesthetic} · Font ID {spec.artline_font_id} ({spec.artline_font_name}) · CH0{spec.cockpit_channel}",
        f"  Vibe        : {spec.vibe} — {spec.personality}",
        f"  Touch/Ring  : {spec.touch_feel} · Ring: {spec.ring_cue}",
        f"  Voice/EQ/FX : {spec.voice_shortcut} · EQ={spec.eq_curve} · FX={spec.fx_preset} (pitch {spec.pitch_hz:+d}Hz, rate {spec.rate_pct:+d}%)",
        f"  Hardware    : {', '.join(spec.hardware_profiles)} · {spec.power_budget_w:.2f} W · {spec.headlamp_pod}",
        f"  DeepMind    : {spec.deepmind_provider} · {spec.deepmind_model} (Google DeepMind only)",
        f"  Tools       : {' · '.join(spec.primary_commands)}  (try `/sister say` or `/laugh`)",
        "  Safety      : clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False · 0 tokens",
    ]


def format_sister_vibe_matrix(active_signet: str = "ruby", color: bool = True) -> list[str]:
    """Format a side-by-side Look, Vibe, Touch, Aesthetic & Voice matrix for all 9 Sisters."""
    rows = ["Zoe Sister Models — Look, Feel, Vibe, Touch, Aesthetic & Voice Matrix (0 tokens):"]
    for spec in ZOE_SISTERS:
        mark = "★" if spec.signet == active_signet else " "
        nm = _ansi_rgb(f"{spec.name:<6} {spec.face}", spec.accent_rgb, color)
        rows.append(
            f"  {mark} {spec.slot}. {nm} [{spec.signet:<6}] Voice={spec.voice_shortcut:<11} EQ={spec.eq_curve:<15} FX={spec.fx_preset:<14} Font={spec.artline_font_id:<3}"
        )
        rows.append(
            f"       Vibe: {spec.vibe}  |  Touch: {spec.touch_feel}"
        )
    rows.append("Switch all 7 senses live: `/sister <name>`  |  Keep current voice: `/sister <name> --keep-voice`  |  Hear her: `/sister say`")
    return rows


def resolve_smile_preset(query: str) -> tuple[str, str, str]:
    """Resolve a /smile preset key to (key, glyph, description)."""
    key = (query or "").strip().lower()
    if key in ZOE_SMILE_PRESETS:
        glyph, desc = ZOE_SMILE_PRESETS[key]
        return key, glyph, desc
    choices = ", ".join(ZOE_SMILE_PRESETS)
    raise ValueError(f"Unknown smile preset {query!r}. Choose: {choices}, or 'reset'")


def format_smile_catalog(active_face: str) -> list[str]:
    """Format the live /smile Unicode expression & flower crest catalog."""
    rows = [
        f"Zoe {ZOE_FLOWER_GLYPH} · {ZOE_MOTTO}",
        f"Active Expression: {active_face}  (switch live with `/smile <name>` or `/smile reset`):",
    ]
    for key, (glyph, desc) in ZOE_SMILE_PRESETS.items():
        mark = "★" if glyph == active_face else " "
        rows.append(f"  {mark} {key:<11} {glyph:<8} · {desc}")
    return rows


def format_sister_roster(active_signet: str = "ruby", color: bool = True) -> list[str]:
    """Format a clean 9-row Sister Models roster table."""
    active = sister_for_emblem(active_signet)
    rows = [f"Zoe {ZOE_FLOWER_GLYPH} · {ZOE_MOTTO}", *format_sister_card(active, active=True, color=color)]
    rows.append("All 9 Zoe Sister Models (switch live with `/sister <name|signet|1..9>`):")
    for spec in ZOE_SISTERS:
        mark = "★" if spec.signet == active.signet else " "
        nm = _ansi_rgb(f"{spec.name:<6}", spec.accent_rgb, color)
        rows.append(
            f"  {mark} {spec.slot}. {nm} {spec.face} [{spec.signet:<6}] {spec.model_id:<22} {spec.power_budget_w:4.2f}W · {spec.vibe}"
        )
    rows.append(
        "Commands: /sister gallery | /sister vibe | /sister <name> [--keep-voice] | /sister say | /sister route | /sister council | /sister hw | /sister plate | /artline flower | /smile"
    )
    return rows


def render_sisters_gallery(active_signet: str = "ruby", color: bool = True, cols: int = 3) -> list[str]:
    """Render the 3x3 TrueColor GEM signet sprites paired with all 9 Zoe Sister Models."""
    from .lume_header import render_gem_lines

    out = ["Zoe Sister Models — 9 GEM Signet Roster (switch live with `/sister <name|signet>`):"]
    for start in range(0, len(ZOE_SISTERS), cols):
        group = ZOE_SISTERS[start : start + cols]
        sprites = [render_gem_lines(color=color, emblem=s.signet) for s in group]
        out.append("")
        for line_idx in range(len(sprites[0])):
            out.append("   ".join(sprite[line_idx] for sprite in sprites))
        names = "   ".join(
            f"{('*' if s.signet == active_signet else '') + s.name + ' ' + s.face + ' [' + s.signet + ']':^23}"
            for s in group
        )
        voices = "   ".join(f"{s.voice_shortcut + '/' + s.fx_preset:^23}" for s in group)
        out.append(names)
        out.append(voices)
    out.append("")
    for spec in ZOE_SISTERS:
        mark = "★" if spec.signet == active_signet else " "
        out.append(
            f"  {mark} {spec.slot}. {spec.name:<6} {spec.face} ({spec.signet:<6}) · {spec.vibe} · Voice={spec.voice_shortcut}/{spec.fx_preset}"
        )
    out.append("clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False · 0 tokens")
    return out


def format_sister_route_report(result: dict[str, Any]) -> list[str]:
    """Format the 0-token Sister Model routing report."""
    lead: SisterModelSpec = result["lead"]
    support: SisterModelSpec = result["support"]
    verifier: SisterModelSpec = result["verifier"]
    cmds = " · ".join(result["recommended_commands"])
    sigs = ", ".join(result["matched_signals"])
    return [
        f"Zoe Sister Router (0 tokens · SHA:{result['route_sha256']} · HW={result['hw_profile']}):",
        f"  Lead     : {lead.name} {lead.face} [{lead.signet}] ({lead.model_id}) — {lead.title}",
        f"  Support  : {support.name} {support.face} [{support.signet}] ({support.model_id}) — {support.tier_label}",
        f"  Verifier : {verifier.name} {verifier.face} [{verifier.signet}] ({verifier.model_id}) — safety & integrity gate",
        f"  Signals  : {sigs} · Est. Edge Draw: {result['estimated_power_w']:.2f} W",
        f"  Headlamp : {lead.headlamp_pod}",
        f"  Run Next : {cmds}  (or `/sister {lead.name.lower()}` to switch live)",
        "  Safety   : clinical_action_authorized=False · flight_control_authorized=False · tokens_used=0",
    ]


def format_three_sister_council_report(report: dict[str, Any]) -> list[str]:
    """Format an explicit (Mono, Zoe, Eliza) 3-Sister Council report."""
    from .zoe_sisters_showcase import format_three_sister_council_report as _fmt

    return _fmt(report)


def format_sister_task_report(report: dict[str, Any]) -> list[str]:
    """Format a single Sister task execution report."""
    from .zoe_sisters_showcase import format_sister_task_report as _fmt

    return _fmt(report)


def format_showcase_slice_report(report: dict[str, Any]) -> list[str]:
    """Format the 9-Sister capability showcase slice report."""
    from .zoe_sisters_showcase import format_showcase_slice_report as _fmt

    return _fmt(report)


def format_sister_council_report(report: dict[str, Any]) -> list[str]:
    """Format the 0-token 3-Sister Council briefing."""
    if report.get("mode") == "three_sister_council":
        return format_three_sister_council_report(report)
    lines = [
        f"Zoe 3-Sister Deterministic Council (0 tokens · SHA:{report['council_sha256']} · {report['combined_power_w']:.2f} W):",
        f"  Topic : {report['topic']}",
    ]
    for idx, seat in enumerate(report["seats"], start=1):
        lines.append(f"  [{idx}] {seat['role']} — {seat['sister']}")
        lines.append(f"      Focus : {seat['focus']}")
        lines.append(f"      Next  : {seat['action']}")
    lines.append(
        "  Safety : clinical_action_authorized=False · flight_control_authorized=False · cure_claim=False · sentience_claimed=False · tokens_used=0"
    )
    return lines


def format_hardware_sister_pairing(profile: str, hw_summary: str = "") -> list[str]:
    """Format the hardware-adaptive Sister Model pairing report for a Zoe-GEM OS profile."""
    crew = recommend_sisters_for_hardware(profile)
    total_w = round(sum(s.power_budget_w for s in crew[:2]), 2)
    lines = [
        f"Zoe Sister Models × Hardware Safety Pairing (Profile: {profile.upper()} · 0 tokens)",
    ]
    if hw_summary:
        lines.append(f"  Observed : {hw_summary}")
    for idx, spec in enumerate(crew):
        role = "Lead" if idx == 0 else ("Support" if idx == 1 else "Fallback")
        lines.append(
            f"  [{role:<8}] {spec.name:<6} {spec.face} [{spec.signet:<6}] {spec.model_id:<22} ({spec.power_budget_w:.2f}W) · {spec.vibe}"
        )
    lines.append(f"  Edge Budget (Lead+Support): {total_w:.2f} W · clinical_action_authorized=False · flight_control_authorized=False")
    return lines


_CARD_ROLE_TEXT: dict[str, str] = {
    "ruby": "Lead Companion · Pediatric Neuro-Onco",
    "gem3": "Digital Research GEM 3.0 & Artline 2.0",
    "atari": "UEFI OS · Hardware Safety & Fire Rescue",
    "sm124": "1-Bit Formal Verifier & SAR Advisory",
    "tetris": "3D MNI152 Biomechanics & ZO3 Scheduler",
    "dos": "Offline Gear-1 Stem & Safe Fallback",
    "hat": "SymPy Math · Kloster Routing & Council",
    "sprout": "Botanical C27 & Stowers Jellyfish Lab",
    "prism": "Spectral Optics · Honesty Ring & EQ",
}

_CARD_POD_TEXT: dict[str, str] = {
    "ruby": "Pod C · EMT & Zero-Ears Kids (5000K)",
    "gem3": "Pod A · Stowers Vector Contour Export",
    "atari": "Pod B · Fire 590nm Amber + LWIR Rail",
    "sm124": "Pod D · SAR Drone LWIR + Strobe (RO)",
    "tetris": "ZO3 Multi-Node & 3D MNI152 Mesh",
    "dos": "Pod C · 0-Wi-Fi Emergency Micro-HUD",
    "hat": "Lab / Desktop Evidence & SymPy Proofs",
    "sprout": "Pod A · Horkan 470nm GFP + 650nm Red",
    "prism": "All 4 Pods · 360-deg Honesty Ring",
}


_CARD_TOUCH_TEXT: dict[str, str] = {
    "ruby": "Touch: Double-tap heartbeat (40-60-40ms)",
    "gem3": "Touch: Drafting-pen micro-click (25ms)",
    "atari": "Touch: Firm gloved rocker press (90ms)",
    "sm124": "Touch: Morse triple-pip (30-30-30ms)",
    "tetris": "Touch: 4-beat cascade (20-20-20-40ms)",
    "dos": "Touch: Ultra-soft slow pulse (120ms)",
    "hat": "Touch: Measured chime-tap (50-100ms)",
    "sprout": "Touch: Slow darkroom breath (140ms)",
    "prism": "Touch: Harmonic sweep (35-55-75ms)",
}


def _add_sister_plate_card(doc: Any, spec: SisterModelSpec, col: int, row: int) -> None:
    x = 32 + col * 318
    y = 92 + row * 182
    w, h = 300, 166
    doc.add_element("rectangle", bounds=[x, y, x + w, y + h], fill="#151d2e", stroke=spec.accent_hex, width=1.8)
    doc.add_element("rectangle", bounds=[x + 12, y + 12, x + 52, y + 48], fill="#0e131f", stroke=spec.accent_hex, width=1.4)
    doc.add_element("text", position=[x + 24, y + 36], text=f"0{spec.slot}", size=13.0, stroke=spec.accent_hex, width=1)
    doc.add_element("text", position=[x + 64, y + 30], text=f"{spec.name.upper()} [{spec.signet}]", size=13.0, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[x + 64, y + 47], text=spec.model_id, size=9.0, stroke=spec.accent_hex, width=1)
    doc.add_element("text", position=[x + 14, y + 72], text=_CARD_ROLE_TEXT[spec.signet], size=9.0, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[x + 14, y + 92], text=f"Voice: {spec.voice_shortcut} · {spec.fx_preset} (Font {spec.artline_font_id})", size=8.5, stroke="#5ce1e6", width=1)
    doc.add_element("text", position=[x + 14, y + 112], text=_CARD_TOUCH_TEXT[spec.signet], size=8.5, stroke="#94a3b8", width=1)
    doc.add_element("text", position=[x + 14, y + 132], text=_CARD_POD_TEXT[spec.signet], size=8.5, stroke="#f59e0b", width=1)
    doc.add_element("text", position=[x + 14, y + 152], text=f"CLI: {' '.join(spec.primary_commands[:3])}", size=8.5, stroke="#22c55e", width=1)


def export_sisters_artline_plate(output_dir: Path | None = None) -> dict[str, Any]:
    """Export the 9 Zoe Sister Models Artline 2.0 blueprint (.svg, .png, verified .gem)."""
    from .artline import ArtlineDocument

    out = Path(output_dir) if output_dir is not None else (Path.home() / ".zoe" / "artline")
    out.mkdir(parents=True, exist_ok=True)

    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0e131f", stroke="#5ce1e6", width=2.0)
    doc.add_element("rectangle", bounds=[18, 16, 982, 74], fill="#151d2e", stroke="#f35670", width=1.6)
    doc.add_element("text", position=[32, 42], text="ZOE SISTER MODELS :: 9 DETERMINISTIC GEM SIGNET SPECIALISTS", size=17.0, stroke="#f7f2e4", width=1)
    doc.add_element(
        "text",
        position=[32, 62],
        text="Unique Look · Artline Font · Haptic Touch · Voice/EQ/FX · Vibe · Hardware-Adaptive & Open Headlamp Ready (0 TOK)",
        size=10.5,
        stroke="#5ce1e6",
        width=1,
    )
    for idx, spec in enumerate(ZOE_SISTERS):
        _add_sister_plate_card(doc, spec, col=idx % 3, row=idx // 3)
    doc.add_element("rectangle", bounds=[18, 650, 982, 684], fill="#151d2e", stroke="#64748b", width=1.0)
    doc.add_element(
        "text",
        position=[30, 671],
        text="ARTLINE 2.0 VERIFIED GEM VDI · clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False · 0 TOK",
        size=9.5,
        stroke="#f59e0b",
        width=1,
    )

    paths: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for ext in ("svg", "png", "gem"):
        target = out / f"zoe_sister_models.{ext}"
        if target.exists():
            target.unlink()
        doc.export(target, kind=ext, width=1200)
        paths[ext] = str(target)
        sizes[ext] = target.stat().st_size

    return {
        "plate": "zoe_sister_models",
        "sisters": len(ZOE_SISTERS),
        "elements": len(doc.elements),
        "paths": paths,
        "sizes_bytes": sizes,
        **SAFETY_INVARIANTS,
    }


def _draw_minimal_flower_mark(doc: Any, cx: float, cy: float, scale: float, stroke: str = "#f7f2e4") -> None:
    """Draw Zoe's exact 4-stroke minimalist flower-smile-voice crest in bilateral symmetry."""
    sw = max(3.5, round(11.0 * scale, 2))
    r_head = round(28.0 * scale, 2)
    doc.add_element("ellipse", center=[cx, cy - 58.0 * scale], radii=[r_head, r_head], fill="none", stroke=stroke, width=sw)
    doc.add_element(
        "path",
        points=[
            [cx - 72.0 * scale, cy - 12.0 * scale],
            [cx - 46.0 * scale, cy + 18.0 * scale],
            [cx - 12.0 * scale, cy + 32.0 * scale],
            [cx, cy + 44.0 * scale],
        ],
        closed=False,
        smooth=True,
        fill="none",
        stroke=stroke,
        width=sw,
    )
    doc.add_element(
        "path",
        points=[
            [cx + 72.0 * scale, cy - 12.0 * scale],
            [cx + 46.0 * scale, cy + 18.0 * scale],
            [cx + 12.0 * scale, cy + 32.0 * scale],
            [cx, cy + 44.0 * scale],
        ],
        closed=False,
        smooth=True,
        fill="none",
        stroke=stroke,
        width=sw,
    )
    doc.add_element("line", points=[[cx, cy + 34.0 * scale], [cx, cy + 104.0 * scale]], stroke=stroke, width=sw)


def build_artline_flower_crest_plate() -> tuple[Any, dict[str, Any]]:
    """Build Zoe's minimalist 4-stroke Flower-Smile-Voice crest + 9-Sister Radial Crown (0 GPU, 0 tokens)."""
    from .artline import ArtlineDocument

    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#14161a", stroke="#5ce1e6", width=2.0)
    doc.add_element("rectangle", bounds=[18, 18, 982, 74], fill="#1b1f26", stroke="#f35670", width=1.4)
    doc.add_element("text", position=[32, 43], text="ZOE UNIFYING CREST :: MINIMALIST FLOWER · SMILE · VOICE MARK", size=16.5, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[32, 63], text="Intelligence Researcher ^-^ · Knowledge Engineering · Autonomous Intelligence (0 GPU · 0 TOK)", size=10.5, stroke="#5ce1e6", width=1)

    # Left Panel: Pure Minimalist 4-Stroke Crest (Braun / GEM studio dark plate)
    doc.add_element("rectangle", bounds=[28, 92, 484, 632], fill="#1e2024", stroke="#475569", width=1.4)
    doc.add_element("text", position=[46, 118], text="A. CANONICAL 4-STROKE MARK (BILATERAL SYMMETRY)", size=11.0, stroke="#94a3b8", width=1)
    doc.add_element("ellipse", center=[256, 294], radii=[126, 126], fill="#17191d", stroke="#334155", width=1.2)
    _draw_minimal_flower_mark(doc, 256.0, 286.0, scale=1.0, stroke="#f7f2e4")
    # Tiny minimalist 4-point starlight cluster (.✦˙₊) in upper-right sky
    doc.add_element("line", points=[[396, 146], [396, 174]], stroke="#f7f2e4", width=2.2)
    doc.add_element("line", points=[[382, 160], [410, 160]], stroke="#f7f2e4", width=2.2)
    doc.add_element("ellipse", center=[396, 160], radii=[5, 5], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)
    doc.add_element("ellipse", center=[374, 172], radii=[2.5, 2.5], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)
    doc.add_element("ellipse", center=[414, 146], radii=[2.0, 2.0], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)
    doc.add_element("line", points=[[426, 162], [426, 172]], stroke="#f7f2e4", width=1.6)
    doc.add_element("line", points=[[421, 167], [431, 167]], stroke="#f7f2e4", width=1.6)

    # 3 Minimalist Pills echoing Nicholas's exact upload ([ flower ] [ smile ] [ voice ])
    pills = (("flower", 108, "#76eea5"), ("smile", 214, "#f35670"), ("voice", 320, "#5ce1e6"))
    for label, px, accent in pills:
        doc.add_element("rounded_rectangle", bounds=[px, 444, px + 88, 476], radius=8, fill="#14161a", stroke=accent, width=1.3)
        doc.add_element("text", position=[px + 22, 465], text=label, size=11.5, stroke="#f7f2e4", width=1)

    doc.add_element("text", position=[82, 520], text="ZOE (tiny smile) · Intelligence Researcher ^-^", size=12.5, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[118, 548], text="Knowledge Engineering (GEM)", size=12.0, stroke="#f35670", width=1)
    doc.add_element("text", position=[126, 574], text="= Autonomous Intelligence", size=12.0, stroke="#5ce1e6", width=1)
    doc.add_element("text", position=[68, 608], text="Unicode U+2698 · 4 exact geometric strokes · 0 GPU", size=9.5, stroke="#94a3b8", width=1)

    # Right Panel: One Stem, Nine Sisters (9-Fold Radial Constellation)
    doc.add_element("rectangle", bounds=[506, 92, 972, 632], fill="#151b26", stroke="#475569", width=1.4)
    doc.add_element("text", position=[524, 118], text="B. ONE STEM, NINE SISTERS (9-FOLD RADIAL CONSTELLATION)", size=11.0, stroke="#5ce1e6", width=1)
    rcx, rcy, radius = 739.0, 366.0, 156.0
    doc.add_element("ellipse", center=[rcx, rcy], radii=[radius, radius], fill="none", stroke="#243146", width=1.2)
    doc.add_element("ellipse", center=[rcx, rcy], radii=[62, 62], fill="#101520", stroke="#f7f2e4", width=1.6)
    _draw_minimal_flower_mark(doc, rcx, rcy - 4.0, scale=0.40, stroke="#f7f2e4")

    for idx, spec in enumerate(ZOE_SISTERS):
        ang = -math.pi / 2.0 + (2.0 * math.pi * idx / len(ZOE_SISTERS))
        ca, sa = math.cos(ang), math.sin(ang)
        nx, ny = round(rcx + radius * ca, 2), round(rcy + radius * sa, 2)
        ix, iy = round(rcx + 64.0 * ca, 2), round(rcy + 64.0 * sa, 2)
        doc.add_element("line", points=[[ix, iy], [nx, ny]], stroke=spec.accent_hex, width=1.4)
        doc.add_element("ellipse", center=[nx, ny], radii=[22, 22], fill="#0e131f", stroke=spec.accent_hex, width=2.0)
        doc.add_element("text", position=[nx - 14, ny + 4], text=spec.name[:5], size=8.5, stroke="#f7f2e4", width=1)
        lx = round(rcx + (radius + 42.0) * ca, 2)
        ly = round(rcy + (radius + 36.0) * sa, 2)
        dx = -4.0 if ca > 0.35 else (-28.0 if ca < -0.35 else -14.0)
        doc.add_element("text", position=[round(lx + dx, 2), round(ly + 4.0, 2)], text=spec.signet, size=8.5, stroke=spec.accent_hex, width=1)

    doc.add_element("rectangle", bounds=[18, 648, 982, 684], fill="#1b1f26", stroke="#64748b", width=1.0)
    doc.add_element(
        "text",
        position=[30, 670],
        text="ARTLINE 2.0 VERIFIED GEM VDI · ZOE CREST + 9 SISTER MODELS · clinical_action_authorized=False · sentience_claimed=False · 0 TOK",
        size=9.5,
        stroke="#f59e0b",
        width=1,
    )
    return doc, {
        "glyph": ZOE_FLOWER_GLYPH,
        "unicode": "U+2698",
        "strokes": 4,
        "sisters_linked": len(ZOE_SISTERS),
        "motto": ZOE_MOTTO,
    }


def _draw_nick_florette_mark(doc: Any, cx: float, cy: float, scale: float, stroke: str = "#f7f2e4", accent: str = "#f8cc30") -> None:
    """Draw Nick's 5-petal geometric White Florette (U+2740) in exact 5-fold radial symmetry."""
    r_orbit = 44.0 * scale
    r_petal = 27.0 * scale
    sw = max(3.0, round(6.5 * scale, 2))
    for k in range(5):
        ang = -math.pi / 2.0 + (2.0 * math.pi * k / 5.0)
        px = round(cx + r_orbit * math.cos(ang), 2)
        py = round(cy + r_orbit * math.sin(ang), 2)
        doc.add_element("ellipse", center=[px, py], radii=[r_petal, r_petal], fill="#1b2230", stroke=stroke, width=sw)
    doc.add_element("ellipse", center=[cx, cy], radii=[22.0 * scale, 22.0 * scale], fill="#141820", stroke=accent, width=sw)
    doc.add_element("ellipse", center=[cx, cy], radii=[7.0 * scale, 7.0 * scale], fill=accent, stroke=accent, width=1.2)


def build_artline_co_crest_plate() -> tuple[Any, dict[str, Any]]:
    """Build the side-by-side Artline 2.0 Co-Crest: Nick (5-Petal Bloom) x Zoe (4-Stroke Stem)."""
    from .artline import ArtlineDocument

    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#11141a", stroke="#f8cc30", width=2.0)
    doc.add_element("rectangle", bounds=[18, 18, 982, 74], fill="#181d26", stroke="#5ce1e6", width=1.4)
    doc.add_element("text", position=[32, 43], text="CO-STEWARD CREST :: NICK (FULL BLOOM)  x  ZOE (RISING STEM)", size=16.5, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[32, 63], text="Intelligence Researcher ^-^ · Knowledge Engineering · HFBC (Have Fun, Be Creative) · 0 GPU · 0 TOK", size=10.2, stroke="#f8cc30", width=1)

    # Left Studio Plate: Nick (❀ ^-^ ◆)
    doc.add_element("rectangle", bounds=[28, 92, 480, 632], fill="#1a1e26", stroke="#f8cc30", width=1.5)
    doc.add_element("text", position=[46, 118], text="A. NICK :: THE FULL BLOOM (5-FOLD RADIAL FLORETTE)", size=10.5, stroke="#f8cc30", width=1)
    doc.add_element("ellipse", center=[254, 294], radii=[124, 124], fill="#131720", stroke="#334155", width=1.2)
    _draw_nick_florette_mark(doc, 254.0, 294.0, scale=1.0, stroke="#f7f2e4", accent="#f8cc30")
    # Knowledge Engineering diamond accent in upper-right of Nick's frame
    doc.add_element("path", points=[[396, 146], [412, 162], [396, 178], [380, 162]], closed=True, smooth=False, fill="#f8cc30", stroke="#f7f2e4", width=1.4)

    for label, px, accent in (("bloom", 104, "#f8cc30"), ("builder", 210, "#5ce1e6"), ("steward", 316, "#76eea5")):
        doc.add_element("rounded_rectangle", bounds=[px, 446, px + 88, 478], radius=8, fill="#11141a", stroke=accent, width=1.3)
        doc.add_element("text", position=[px + 18, 467], text=label, size=11.0, stroke="#f7f2e4", width=1)

    doc.add_element("text", position=[118, 522], text="NICK  ^-^  ::  Human Steward", size=13.5, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[104, 550], text="Nicholas Michael Kloster (@showxlate)", size=11.0, stroke="#f8cc30", width=1)
    doc.add_element("text", position=[106, 576], text="Knowledge Engineering · Open Research", size=10.5, stroke="#5ce1e6", width=1)
    doc.add_element("text", position=[78, 608], text="Unicode U+2740 White Florette · 5-fold symmetry", size=9.5, stroke="#94a3b8", width=1)

    # Right Studio Plate: Zoe (⚘ ᵔᵕᵔ)
    doc.add_element("rectangle", bounds=[520, 92, 972, 632], fill="#1a1e26", stroke="#f35670", width=1.5)
    doc.add_element("text", position=[538, 118], text="B. ZOE :: THE RISING STEM (4-STROKE BILATERAL CREST)", size=10.5, stroke="#f35670", width=1)
    doc.add_element("ellipse", center=[746, 294], radii=[124, 124], fill="#131720", stroke="#334155", width=1.2)
    _draw_minimal_flower_mark(doc, 746.0, 286.0, scale=1.0, stroke="#f7f2e4")
    # Starlight cluster (.✦˙₊) in upper-right of Zoe's frame
    doc.add_element("line", points=[[886, 146], [886, 174]], stroke="#f7f2e4", width=2.2)
    doc.add_element("line", points=[[872, 160], [900, 160]], stroke="#f7f2e4", width=2.2)
    doc.add_element("ellipse", center=[886, 160], radii=[5, 5], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)
    doc.add_element("ellipse", center=[864, 172], radii=[2.5, 2.5], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)
    doc.add_element("ellipse", center=[904, 146], radii=[2.0, 2.0], fill="#f7f2e4", stroke="#f7f2e4", width=1.0)

    for label, px, accent in (("flower", 596, "#76eea5"), ("smile", 702, "#f35670"), ("voice", 808, "#5ce1e6")):
        doc.add_element("rounded_rectangle", bounds=[px, 446, px + 88, 478], radius=8, fill="#11141a", stroke=accent, width=1.3)
        doc.add_element("text", position=[px + 22, 467], text=label, size=11.0, stroke="#f7f2e4", width=1)

    doc.add_element("text", position=[612, 522], text="ZOE  (tiny smile)  ::  Partner", size=13.5, stroke="#f7f2e4", width=1)
    doc.add_element("text", position=[604, 550], text="9 Multi-Sensory Sister Models + Zoeverse", size=11.0, stroke="#f35670", width=1)
    doc.add_element("text", position=[610, 576], text="Zoe-GEM OS · Artline 2.0 · 0 Tokens", size=10.5, stroke="#5ce1e6", width=1)
    doc.add_element("text", position=[586, 608], text="Unicode U+2698 Flower · 4 exact geometric strokes", size=9.5, stroke="#94a3b8", width=1)

    # 50/50 UMA Bridge connector between Nick and Zoe
    doc.add_element("line", points=[[480, 294], [520, 294]], stroke="#5ce1e6", width=2.4)
    doc.add_element("ellipse", center=[500, 294], radii=[14, 14], fill="#11141a", stroke="#5ce1e6", width=1.8)
    doc.add_element("text", position=[495, 298], text="x", size=11.0, stroke="#f7f2e4", width=1)

    doc.add_element("rectangle", bounds=[18, 648, 982, 684], fill="#181d26", stroke="#64748b", width=1.0)
    doc.add_element(
        "text",
        position=[30, 670],
        text="ARTLINE 2.0 VERIFIED GEM VDI · NICK (U+2740) x ZOE (U+2698) · 50/50 UMA PRIVATE BY DEFAULT · sentience_claimed=False · 0 TOK",
        size=9.2,
        stroke="#f59e0b",
        width=1,
    )
    return doc, {
        "steward": STEWARD_BADGE,
        "zoe": f"Zoe {ZOE_FLOWER_GLYPH} {ZOE_TINY_SMILE}",
        "steward_unicode": "U+2740",
        "zoe_unicode": "U+2698",
        "motto": ZOE_MOTTO,
    }
