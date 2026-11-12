from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GLib, Gtk

from .life import Life, PATTERNS
from .render import draw_cairo


class LifeCanvas(Gtk.DrawingArea):
    def __init__(self, game, action):
        super().__init__()
        self.game = game
        self.action = action
        self.set_size_request(900, 610)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Conway's Game of Life grid")
        self.get_accessible().set_description("Click cells to toggle them. Space toggles play, Right advances one generation, R resets the pattern, and C clears the grid.")

    def do_draw(self, context):
        draw_cairo(context, self.game.scene(), self.get_allocated_width(), self.get_allocated_height())
        return False

    def on_button(self, _widget, event):
        self.grab_focus()
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        scale = min(width / 1100, height / 740)
        offset_x = (width - 1100 * scale) / 2
        offset_y = (height - 740 * scale) / 2
        x = (event.x - offset_x) / scale
        y = (event.y - offset_y) / scale
        if 40 <= x < 40 + self.game.width * 20 and 132 <= y < 132 + self.game.height * 20:
            self.action("toggle", int((x - 40) // 20), int((y - 132) // 20))
        return True

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key == "space":
            self.action("play")
        elif key == "Right":
            self.action("step")
        elif key in {"r", "R"}:
            self.action("reset")
        elif key in {"c", "C"}:
            self.action("clear")
        else:
            return False
        return True


class LifeWindow(Gtk.Window):
    def __init__(self, game=None):
        super().__init__(title="Zoe Life · Conway's Game of Life")
        self.game = game or Life.from_pattern("glider")
        self.pattern = "glider"
        self.timer = None
        self.set_default_size(1120, 830)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=8)
        self.add(outer)
        self.canvas = LifeCanvas(self.game, self.action)
        outer.pack_start(self.canvas, True, True, 0)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        outer.pack_start(controls, False, False, 0)
        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.play)
        controls.pack_start(self.play_button, False, False, 0)
        for label, callback in (("Step", self.step), ("Reset", self.reset), ("Clear", self.clear)):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            controls.pack_start(button, False, False, 0)
        self.patterns = Gtk.ComboBoxText()
        for name in PATTERNS:
            self.patterns.append(name, name)
        self.patterns.set_active_id(self.pattern)
        controls.pack_start(self.patterns, False, False, 0)
        apply_button = Gtk.Button(label="Apply pattern")
        apply_button.connect("clicked", self.apply_pattern)
        controls.pack_start(apply_button, False, False, 0)
        for kind in ("svg", "png", "gem", "json"):
            button = Gtk.Button(label=f"Export {kind.upper()}")
            button.connect("clicked", self.export_dialog, kind)
            controls.pack_end(button, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        outer.pack_end(self.status, False, False, 0)
        self.refresh()

    def refresh(self):
        document = self.game.document()
        self.status.set_text(
            f"Generation {document['generation']} · Population {document['population']} · "
            f"{document['state_sha256'][:20]} · {self.game.width}×{self.game.height} finite B3/S23 grid"
        )
        self.canvas.queue_draw()

    def action(self, name, *arguments):
        if name == "toggle":
            self.game.toggle(*arguments)
            self.refresh()
            return True
        if name == "play":
            return self.play()
        if name == "step":
            return self.step()
        if name == "reset":
            return self.reset()
        if name == "clear":
            return self.clear()
        return False

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.play_button.set_label("Play")
        return False

    def play(self, *_args):
        if self.timer is not None:
            return self.stop()
        self.timer = GLib.timeout_add(150, self.on_tick)
        self.play_button.set_label("Pause")
        return False

    def on_tick(self):
        self.game.step()
        self.refresh()
        return True

    def step(self, *_args):
        self.stop()
        self.game.step()
        self.refresh()
        return False

    def apply_pattern(self, *_args):
        self.stop()
        self.pattern = self.patterns.get_active_id()
        self.game = Life.from_pattern(self.pattern, self.game.width, self.game.height)
        self.canvas.game = self.game
        self.refresh()
        return False

    def reset(self, *_args):
        self.stop()
        self.game = Life.from_pattern(self.pattern, self.game.width, self.game.height)
        self.canvas.game = self.game
        self.refresh()
        return False

    def clear(self, *_args):
        self.stop()
        self.game.clear()
        self.refresh()
        return False

    def export_dialog(self, _button, kind):
        dialog = Gtk.FileChooserDialog(
            title=f"Export Life {kind.upper()}", transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Export", Gtk.ResponseType.OK)
        dialog.set_current_name(f"life-generation-{self.game.generation}.{kind}")
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                path = Path(dialog.get_filename())
                try:
                    self.game.export(path, kind)
                    self.status.set_text(f"Exported {path}")
                except (OSError, ValueError) as error:
                    self.status.set_text(f"Export failed: {error}")
        finally:
            dialog.destroy()

    def on_destroy(self, *_args):
        self.stop()


def launch_life(game=None, play=False):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Life requires a GTK display; use --output for headless export")
    window = LifeWindow(game)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    if play:
        window.play()
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="zoe life", description="Conway's Game of Life through Zoe/GEM")
    result.add_argument("--pattern", choices=tuple(PATTERNS), default="glider")
    result.add_argument("--steps", type=int, default=0, help="generations to advance before export (0–10000)")
    result.add_argument("--play", action="store_true", help="start the native generation timer")
    result.add_argument("--output", help="new .json, .svg, .png, or .gem export instead of opening GTK")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400, help="SVG/PNG width in pixels")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        game = Life.from_pattern(arguments.pattern).advance(arguments.steps)
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            output = game.export(arguments.output, kind, arguments.width)
            print(json.dumps({
                "instrument": "zoe-life", "pattern": arguments.pattern,
                "generation": game.generation, "population": game.population,
                "state_sha256": game.digest(), "output": str(output),
                "bytes": output.stat().st_size, "biological_life_created": False,
            }, indent=2, sort_keys=True))
            return 0
        launch_life(game, arguments.play)
        return 0
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        print(f"zoe life: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
