from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from .cicada import CicadaClock
from .render import draw_cairo


class CicadaCanvas(Gtk.DrawingArea):
    def __init__(self, game, action):
        super().__init__()
        self.game = game
        self.action = action
        self.set_size_request(740, 680)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Cicada internal clock")
        self.get_accessible().set_description("Daily phase and four-year developmental gates. Space toggles Act, Right advances one year, and R resets the configured clock.")

    def do_draw(self, context):
        draw_cairo(context, self.game.scene(), self.get_allocated_width(), self.get_allocated_height())
        return False

    def on_button(self, _widget, _event):
        self.grab_focus()
        return True

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "space":
            self.action("act")
            return True
        if key == "Right":
            self.action("step")
            return True
        if key in {"r", "R"}:
            self.action("reset")
            return True
        return False


class CicadaWindow(Gtk.Window):
    def __init__(self, game=None, clock=time.monotonic):
        super().__init__(title="Zoetic Research · Zoe Internal Clock")
        self.game = game or CicadaClock(initial_cycles=8)
        self.clock = clock
        if not callable(self.clock):
            raise ValueError("clock must be callable")
        self.timer = None
        self.last_tick = None
        self.set_default_size(1240, 850)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        self.add(outer)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        logo_path = Path(__file__).resolve().parents[1] / "icons/zoetic-research.svg"
        self.logo = None
        if logo_path.is_file():
            try:
                self.logo = Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(logo_path), 330, 115, True))
                header.pack_start(self.logo, False, False, 0)
            except (OSError, ValueError):
                self.logo = None
        title = Gtk.Label(xalign=0)
        title.set_markup("<span size='xx-large' color='#0e7490'>Zoe Internal Clock</span>\n<span color='#475569'>CERN phase discipline · cicada timing hypotheses · local action without a reasoning loop</span>")
        header.pack_start(title, True, True, 0)
        outer.pack_start(header, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.set_position(760)
        outer.pack_start(panes, True, True, 0)
        self.canvas = CicadaCanvas(self.game, self.action)
        panes.pack1(self.canvas, True, True)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(440, 630)
        scrolled.add(side)
        panes.pack2(scrolled, False, True)
        self.cycle = Gtk.ComboBoxText()
        self.cycle.append("13", "13-year gate")
        self.cycle.append("17", "17-year gate")
        self.cycle.set_active_id(str(self.game.cycle_years))
        side.pack_start(self.labeled("Developmental model", self.cycle), False, False, 0)
        self.host_rate = Gtk.ComboBoxText()
        self.host_rate.append("1", "1 host cycle / calendar year")
        self.host_rate.append("2", "2 host cycles / calendar year")
        self.host_rate.set_active_id(str(self.game.host_rate))
        side.pack_start(self.labeled("Host entrainment", self.host_rate), False, False, 0)
        self.initial = Gtk.SpinButton.new_with_range(0, 24, 1)
        self.initial.set_value(float(self.game.initial_cycles))
        side.pack_start(self.labeled("Initial host cycles", self.initial), False, False, 0)
        self.speed = Gtk.SpinButton.new_with_range(0.05, 4, 0.05)
        self.speed.set_digits(2)
        self.speed.set_value(float(self.game.years_per_second))
        side.pack_start(self.labeled("Simulated years / second", self.speed), False, False, 0)
        self.daily = Gtk.SpinButton.new_with_range(1, 120, 1)
        self.daily.set_value(self.game.daily_period_seconds)
        side.pack_start(self.labeled("Toy daily period · seconds", self.daily), False, False, 0)
        self.entrainment = Gtk.SpinButton.new_with_range(0, 0.25, 0.01)
        self.entrainment.set_digits(2)
        self.entrainment.set_value(self.game.entrainment_strength)
        side.pack_start(self.labeled("Phase entrainment", self.entrainment), False, False, 0)
        self.temperature = Gtk.SpinButton.new_with_range(-20, 50, 0.1)
        self.temperature.set_digits(1)
        self.temperature.set_value(self.game.soil_temp_c)
        side.pack_start(self.labeled("Synthetic soil temperature · °C", self.temperature), False, False, 0)
        self.sunset = Gtk.CheckButton(label="After sunset · synthetic release cue")
        self.sunset.set_active(self.game.after_sunset)
        side.pack_start(self.sunset, False, False, 0)
        self.act_button = Gtk.Button(label="Act · start local event timer")
        self.act_button.connect("clicked", self.act)
        side.pack_start(self.act_button, False, False, 0)
        for label, callback in (
            ("Advance one simulated year", self.step_year),
            ("Apply configuration as a new clock", self.start),
            ("Save and verify replay", self.save_dialog),
            ("Open and verify replay", self.open_dialog),
            ("Export SVG", lambda *_args: self.export_dialog("svg")),
            ("Export PNG", lambda *_args: self.export_dialog("png")),
            ("Export GEM VDI", lambda *_args: self.export_dialog("gem")),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            side.pack_start(button, False, False, 0)
        self.summary = Gtk.Label(xalign=0)
        self.summary.set_line_wrap(True)
        self.summary.set_selectable(True)
        side.pack_start(self.summary, True, True, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        outer.pack_end(self.status, False, False, 0)
        self.update_summary()

    def labeled(self, text, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=text, xalign=0)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)
        box.pack_end(widget, False, False, 0)
        return box

    def update_summary(self):
        values = self.game.measurements()
        self.summary.set_text(
            f"Host cycles: {values['host_cycles']}\n"
            f"Calendar age: {values['calendar_age']}\n"
            f"Growth / critical weight: {values['growth_ratio']:.3f} / 1.000\n"
            f"Gate: {self.game.gate_cycle} · Emergence: {self.game.emergence_cycle}\n"
            f"Daily phase: {self.game.phase:.3f}\n"
            f"Events: {len(self.game.events)} / 256\n"
            f"Last actions: {', '.join(self.game.last_actions)}\n\n"
            "Act advances only local visual/replay events. No AI calls, hardware access, biological measurement, or external actuator."
        )

    def refresh(self):
        self.update_summary()
        self.canvas.queue_draw()

    def action(self, name, *_args):
        if name == "act":
            return self.act()
        if name == "step":
            return self.step_year()
        if name == "reset":
            return self.start()
        return False

    def act(self, *_args):
        if self.timer is not None:
            self.stop()
            self.status.set_text("Act stopped. Recorded events remain available for replay.")
            return False
        if len(self.game.events) >= 256:
            self.status.set_text("Event bound reached. Start a new clock or open a new replay.")
            return False
        self.last_tick = self.clock()
        self.timer = GLib.timeout_add(100, self.on_tick)
        self.act_button.set_label("Stop local event timer")
        self.status.set_text("Acting locally without a reasoning loop. Stop at any time; no external action is executed.")
        return True

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.last_tick = None
        self.act_button.set_label("Act · start local event timer")

    def on_destroy(self, *_args):
        self.stop()

    def on_tick(self):
        try:
            now = self.clock()
            elapsed = now - self.last_tick
            if elapsed < 0:
                raise ValueError("clock cannot move backward")
            self.last_tick = now
            if elapsed == 0:
                return True
            elapsed = min(0.25, elapsed)
            self.game.step(elapsed, self.temperature.get_value(), self.sunset.get_active(), (now % self.game.daily_period_seconds) / self.game.daily_period_seconds)
            self.refresh()
            if len(self.game.events) >= 256:
                self.stop()
                self.status.set_text("Event bound reached; the local timer stopped cleanly.")
                return False
            return True
        except (OSError, ValueError) as error:
            self.stop()
            self.status.set_text(str(error))
            return False

    def step_year(self, *_args):
        try:
            self.game.step(1, self.temperature.get_value(), self.sunset.get_active(), 0.0)
            self.refresh()
            return True
        except ValueError as error:
            self.status.set_text(str(error))
            return False

    def start(self, *_args):
        self.stop()
        try:
            self.game = CicadaClock(
                cycle_years=int(self.cycle.get_active_id()), host_rate=int(self.host_rate.get_active_id()),
                initial_cycles=self.initial.get_value(), growth_multiplier=1,
                daily_period_seconds=self.daily.get_value(), entrainment_strength=self.entrainment.get_value(),
                years_per_second=self.speed.get_value(),
            )
            self.canvas.game = self.game
            self.status.set_text("New clock configured. Act remains disarmed until you start it.")
            self.canvas.grab_focus()
            self.refresh()
        except ValueError as error:
            self.status.set_text(str(error))

    def choose_path(self, title, action, filename):
        dialog = Gtk.FileChooserDialog(title=title, transient_for=self, action=action)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button(title, Gtk.ResponseType.OK)
        if action == Gtk.FileChooserAction.SAVE:
            dialog.set_current_name(filename)
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                return Path(dialog.get_filename())
            return None
        finally:
            dialog.destroy()

    def save_dialog(self, *_args):
        path = self.choose_path("Save cicada replay", Gtk.FileChooserAction.SAVE, "cicada.json")
        if path:
            try:
                self.game.save(path)
                self.status.set_text(f"Saved and verified {path}")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Save failed: {error}")

    def load_path(self, path):
        try:
            game = CicadaClock.replay(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.status.set_text(f"Replay rejected: {error}")
            return False
        self.stop()
        self.game = game
        self.canvas.game = game
        self.status.set_text("Replay verified: configuration, events, and final state agree.")
        self.refresh()
        return True

    def open_dialog(self, *_args):
        path = self.choose_path("Open cicada replay", Gtk.FileChooserAction.OPEN, "cicada.json")
        if path:
            self.load_path(path)

    def export_current(self, path, kind=None):
        return self.game.export(path, kind)

    def export_dialog(self, kind):
        path = self.choose_path(f"Export cicada {kind.upper()}", Gtk.FileChooserAction.SAVE, f"cicada.{kind}")
        if path:
            try:
                self.export_current(path, kind)
                self.status.set_text(f"Exported {path}")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Export failed: {error}")


def launch_cicada(game=None, act=False):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Internal Clock requires a GTK display; use --output for headless export")
    window = CicadaWindow(game)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    if act:
        window.act()
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="cicada", description="Zoe Internal Clock · CERN ticks and cicada timing hypotheses")
    result.add_argument("input", nargs="?", help="saved cicada replay to verify")
    result.add_argument("--cycle", type=int, choices=(13, 17), default=13)
    result.add_argument("--host-rate", type=int, choices=(1, 2), default=1)
    result.add_argument("--start", type=float, default=0, help="initial host seasonal cycles, not necessarily calendar age")
    result.add_argument("--age", type=float, help="initial calendar age; default: initial host cycles")
    result.add_argument("--years", type=float, help="advance this many simulated calendar years before export")
    result.add_argument("--growth", type=float, default=1, help="growth-rate multiplier from 0.125 to 4")
    result.add_argument("--daily-period", type=float, default=24, help="toy daily phase period in seconds")
    result.add_argument("--entrainment", type=float, default=.03, help="phase entrainment from 0 to 0.25")
    result.add_argument("--speed", type=float, default=1, help="simulated years per reference second")
    result.add_argument("--phase", type=float, default=0, help="initial daily phase from 0 to less than 1")
    result.add_argument("--host-phase", type=float, default=0, help="host phase for each explicit step")
    result.add_argument("--temp", type=float, default=18, help="synthetic soil temperature in Celsius")
    result.add_argument("--day", action="store_true", help="withhold the after-sunset release cue")
    result.add_argument("--act", action="store_true", help="arm the local timer after opening the native window")
    result.add_argument("--output", help="new .json, .svg, .png, or .gem artifact instead of opening GTK")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def _print(document):
    print(json.dumps(document, ensure_ascii=False, sort_keys=True))


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        game = CicadaClock.replay(arguments.input) if arguments.input else CicadaClock(
            cycle_years=arguments.cycle, host_rate=arguments.host_rate,
            initial_cycles=arguments.start, initial_calendar_age=arguments.age,
            growth_multiplier=arguments.growth, daily_period_seconds=arguments.daily_period,
            entrainment_strength=arguments.entrainment, years_per_second=arguments.speed,
            initial_phase=arguments.phase,
        )
        if arguments.years is not None:
            game.step(arguments.years, arguments.temp, not arguments.day, arguments.host_phase)
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            output = game.save(arguments.output) if kind == "json" else game.export(arguments.output, kind, arguments.width)
            _print({"instrument": "zoe-cicada-internal-clock", "output": str(output), "measurements": game.measurements(), "external_actions_executed": False})
            return 0
        launch_cicada(game, arguments.act)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"cicada: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
