from __future__ import annotations

from gi.repository import Gtk


PHI = (1 + 5 ** 0.5) / 2
SPACE = (4, 6, 10, 16, 26, 42)
PALETTE = (
    "#67e8f9", "#fde68a", "#f0abfc", "#86efac", "#fda4af",
    "#93c5fd", "#fdba74", "#c4b5fd", "#a7f3d0", "#f9a8d4",
    "#d9f99d", "#e7d6ad", "#fef08a", "#facc15", "#a5f3fc",
)

CSS = b"""
.zoe-root, .zoe-root viewport, .zoe-root flowbox, .zoe-root list {
    background-color: #080d18;
    color: #d8e2ee;
}
.zoe-root headerbar {
    background-color: #0e1828;
    color: #e2e8f0;
    border-bottom: 1px solid #243449;
}
.zoe-title {
    color: #67e8f9;
    font-size: 24px;
    font-weight: 500;
}
.zoe-subtitle, .zoe-muted {
    color: #9fb1c8;
    font-size: 12px;
}
.zoe-panel, .zoe-card, .zoe-agent {
    background-color: #101b2b;
    border: 1px solid #243449;
    border-radius: 10px;
}
.zoe-panel {
    padding: 16px;
}
.zoe-card {
    color: #d8e2ee;
    padding: 14px;
    margin: 5px;
    transition: background-color 150ms ease-in-out, border-color 150ms ease-in-out;
}
.zoe-card:hover, .zoe-card:focus {
    background-color: #14263c;
    border-color: #67e8f9;
}
.zoe-card:active, .zoe-selected {
    background-color: #19304a;
    border-color: #86efac;
}
.zoe-action {
    color: #e2e8f0;
    background-color: #14263c;
    border: 1px solid #35506b;
    border-radius: 8px;
    padding: 8px 12px;
}
.zoe-action:hover, .zoe-action:focus {
    border-color: #86efac;
    background-color: #19304a;
}
.zoe-action:disabled {
    color: #64748b;
    background-color: #101b2b;
    border-color: #243449;
}
.zoe-status {
    color: #a7f3d0;
    font-family: monospace;
    font-size: 11px;
}
.zoe-agent {
    padding: 16px;
}
.zoe-root entry, .zoe-root textview, .zoe-root terminal {
    background-color: #0e1828;
    color: #e2e8f0;
    border: 1px solid #35506b;
    border-radius: 6px;
}
.zoe-root button, .zoe-root button:hover, .zoe-root button:focus,
.zoe-root button:active, .zoe-root button:disabled {
    background-image: none;
}
.zoe-root separator {
    background-color: #243449;
}
"""


def apply_theme(window):
    window.get_style_context().add_class("zoe-root")
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        window.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
