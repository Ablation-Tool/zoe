#!/usr/bin/env python3
"""Independent Verifier & Spectrogram + Chladni Cymatics Plate Renderer for Zoe Voice Choral Composer (#8)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guiai-lab"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from guiai.gem.zoe_choral_composer import SR, compose_kloster_choral_nocturne


def render_choral_cymatics_plate(report: dict, stereo: np.ndarray, plates: list, out_path: Path) -> None:
    plt.rcParams.update({
        "figure.facecolor": "#060A14",
        "axes.facecolor": "#0B1324",
        "axes.edgecolor": "#243652",
        "axes.labelcolor": "#DCE7F7",
        "xtick.color": "#9DB2D1",
        "ytick.color": "#9DB2D1",
        "text.color": "#EEF5FF",
        "font.family": "DejaVu Sans",
        "grid.color": "#1A2840",
        "grid.alpha": 0.65,
    })

    fig = plt.figure(figsize=(18.0, 10.6), dpi=220)
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.27, left=0.055, right=0.975, top=0.89, bottom=0.075)

    fig.suptitle(
        "Zoe Native Voice & Choral Intelligence :: 3-Part Formant Choir x Kloster Tension x Chladni Cymatics",
        fontsize=15.5, fontweight="bold", color="#F4F8FF", y=0.96,
    )
    fig.text(
        0.5, 0.923,
        f"Pure 44.1 kHz Stereo DSP (0 PyTorch · 0 Cloud Tokens)  |  Duration: {report['wav']['duration_sec']}s  |  Stereo Corr: {report['acoustics']['stereo_correlation']}  |  SHA-256: {report['evidence_sha256'][:16]}",
        ha="center", fontsize=9.8, color="#7CE8FF",
    )

    mono = 0.5 * (stereo[:, 0] + stereo[:, 1])

    # Panel A: Full-Piece Stereo Waveform Envelope
    ax_a = fig.add_subplot(gs[0, 0])
    stride = max(1, len(mono) // 2500)
    t_ax = np.arange(0, len(mono), stride) / SR
    ax_a.plot(t_ax, stereo[::stride, 0], color="#00E5FF", alpha=0.75, linewidth=0.9, label="Left Channel (Soprano-lead)")
    ax_a.plot(t_ax, stereo[::stride, 1] * 0.95, color="#FFB84D", alpha=0.58, linewidth=0.8, label="Right Channel (Alto-lead)")
    ax_a.set_xlabel("Time (seconds)", fontsize=9)
    ax_a.set_ylabel("Amplitude", fontsize=9)
    ax_a.set_title("A. 3-Part Choral Stereo Waveform + 3:2 Chimes", fontsize=10.8, fontweight="bold", color="#7CE8FF", pad=8)
    ax_a.grid(True, linestyle="--", linewidth=0.6)
    ax_a.legend(loc="upper right", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panel B: High-Resolution Vocal Formant Spectrogram (0..4500 Hz)
    ax_b = fig.add_subplot(gs[0, 1])
    freqs, times, sxx = signal.spectrogram(mono, fs=SR, nperseg=2048, noverlap=1536)
    f_mask = freqs <= 4500.0
    db = 10.0 * np.log10(sxx[f_mask] + 1e-12)
    im_b = ax_b.pcolormesh(times, freqs[f_mask], db, shading="gouraud", cmap="magma", vmin=float(np.percentile(db, 15)))
    ax_b.set_xlabel("Time (seconds)", fontsize=9)
    ax_b.set_ylabel("Frequency (Hz)", fontsize=9)
    ax_b.set_title("B. Formant Cascade + Aspiration Spectrogram", fontsize=10.8, fontweight="bold", color="#FFB84D", pad=8)
    cb_b = fig.colorbar(im_b, ax=ax_b, fraction=0.046, pad=0.03)
    cb_b.set_label("Power (dB)", fontsize=8.0)

    # Panel C: #5 Kloster Renyi H_2 Harmonic Tension Arc Driving Vibrato & Breath
    ax_c = fig.add_subplot(gs[0, 2])
    bars_x = np.arange(1, len(report["kloster_tension_h2_arc"]) + 1)
    h2_arc = report["kloster_tension_h2_arc"]
    a10_arc = report["kloster_a010_arc"]
    ax_c.plot(bars_x, h2_arc, color="#00E5FF", marker="o", linewidth=2.4, markersize=7, label="Kloster Renyi H_2 Tension")
    ax_c.fill_between(bars_x, 0, h2_arc, color="#00E5FF", alpha=0.14)
    ax_c2 = ax_c.twinx()
    ax_c2.bar(bars_x, a10_arc, width=0.35, color="#FFB84D", alpha=0.45, label="Accessible Chord Modes A_0.10")
    ax_c.set_xlabel("Phrase Measure (D Lydian Nocturne)", fontsize=9)
    ax_c.set_ylabel("Kloster Harmonic Tension H_2 (nats)", fontsize=9, color="#00E5FF")
    ax_c2.set_ylabel("Accessible Volume A_0.10", fontsize=9, color="#FFB84D")
    ax_c.set_ylim(0, max(h2_arc) * 1.3)
    ax_c2.set_ylim(0, max(a10_arc) + 2.5)
    ax_c.set_title("C. Kloster Tension Arc (#5 x #11 x #8)", fontsize=10.8, fontweight="bold", color="#63F5B5", pad=8)
    ax_c.grid(True, linestyle="--", linewidth=0.6)
    ax_c.legend(loc="upper left", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")
    ax_c2.legend(loc="upper right", fontsize=7.6, framealpha=0.88, facecolor="#09101E", edgecolor="#284066")

    # Panels D, E, F: Coupled Chladni Acoustic Nodal Resonance Plates at Opening, Peak Tension & Resolution
    plate_titles = [
        "D. Opening Tonic Chladni Plate (/OW/)",
        "E. Peak Tension Chladni Plate (/AA/)",
        "F. Home Resolution Chladni Plate (/AA/)",
    ]
    cmaps = ["cividis", "plasma", "viridis"]
    for idx, pl in enumerate(plates[:3]):
        ax = fig.add_subplot(gs[1, idx])
        fld = np.abs(pl["nodal_grid"])
        # Highlight bright sand lines along zero-amplitude Chladni nodal curves!
        sand = np.exp(-6.5 * (fld / max(1e-6, float(np.max(fld)))))
        ax.imshow(sand, cmap=cmaps[idx], origin="lower", aspect="equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(
            f"{plate_titles[idx]}  [H2={pl['kloster_h2']:.2f}]",
            fontsize=10.3, fontweight="bold", color="#7CE8FF" if idx == 0 else ("#FFB84D" if idx == 1 else "#63F5B5"), pad=8,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    wav_path = Path("/tmp/zoe_kloster_choral_nocturne.wav")
    report = compose_kloster_choral_nocturne(wav_path)
    stereo = report.pop("_stereo")
    plates = report.pop("_chladni_plates")

    ev_path = ROOT / "evidence/voice-choral/zoe-choral-composer-report.json"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    fig_path = ROOT / "components/agent-logging-system/docs/images/zoe-voice-choral-cymatics.png"
    render_choral_cymatics_plate(report, stereo, plates, fig_path)

    checks = list(report["checks"].items()) + [("choral_plate_generated", fig_path.is_file() and fig_path.stat().st_size > 40_000)]
    passed = sum(1 for _, ok in checks if ok)
    for k, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {k}")
    print(f"\nTOTAL: {passed}/{len(checks)} PASS | SHA-256={report['evidence_sha256'][:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
