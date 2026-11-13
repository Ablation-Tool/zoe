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

from .brain_life import BrainLife
from .render import draw_cairo


class BrainLifeCanvas(Gtk.DrawingArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.set_size_request(1000, 650)
        self.set_can_focus(True)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Three-dimensional Brain Life volume")
        self.get_accessible().set_description("Space toggles play, Right advances one generation, brackets rotate the volume, R resets, and C clears.")

    def do_draw(self, context):
        draw_cairo(context, self.window.game.scene(self.window.yaw), self.get_allocated_width(), self.get_allocated_height())
        return False

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        actions = {"space": self.window.play, "Right": self.window.step, "bracketleft": self.window.rotate_left, "bracketright": self.window.rotate_right, "r": self.window.reset, "R": self.window.reset, "c": self.window.clear, "C": self.window.clear}
        if key not in actions:
            return False
        actions[key]()
        return True


class BrainLifeWindow(Gtk.Window):
    def __init__(self, game=None, yaw=35):
        super().__init__(title="Zoe Brain Life · 3D cellular automaton")
        self.game = game or BrainLife.from_brain()
        self.yaw = yaw
        self.timer = None
        self.set_default_size(1140, 830)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=8)
        self.add(outer)
        self.canvas = BrainLifeCanvas(self)
        outer.pack_start(self.canvas, True, True, 0)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        outer.pack_start(controls, False, False, 0)
        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.play)
        controls.pack_start(self.play_button, False, False, 0)
        for label, callback in (("Step", self.step), ("Rotate left", self.rotate_left), ("Rotate right", self.rotate_right), ("Reset", self.reset), ("Clear", self.clear)):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            controls.pack_start(button, False, False, 0)
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
        self.status.set_text(f"Generation {document['generation']} · Population {document['population']} · Yaw {self.yaw:g}° · {document['state_sha256'][:20]} · illustrative voxels, not anatomy")
        self.canvas.queue_draw()

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        self.play_button.set_label("Play")
        return False

    def play(self, *_args):
        if self.timer is not None:
            return self.stop()
        self.timer = GLib.timeout_add(200, self.on_tick)
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

    def rotate_left(self, *_args):
        self.yaw = (self.yaw - 15) % 360
        self.refresh()
        return False

    def rotate_right(self, *_args):
        self.yaw = (self.yaw + 15) % 360
        self.refresh()
        return False

    def reset(self, *_args):
        self.stop()
        self.game = BrainLife.from_brain(self.game.size)
        self.refresh()
        return False

    def clear(self, *_args):
        self.stop()
        self.game.clear()
        self.refresh()
        return False

    def export_dialog(self, _button, kind):
        dialog = Gtk.FileChooserDialog(title=f"Export Brain Life {kind.upper()}", transient_for=self, action=Gtk.FileChooserAction.SAVE)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Export", Gtk.ResponseType.OK)
        dialog.set_current_name(f"brain-life-generation-{self.game.generation}.{kind}")
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                path = Path(dialog.get_filename())
                try:
                    self.game.export(path, kind, yaw=self.yaw)
                    self.status.set_text(f"Exported {path}")
                except (OSError, ValueError) as error:
                    self.status.set_text(f"Export failed: {error}")
        finally:
            dialog.destroy()

    def on_destroy(self, *_args):
        self.stop()


def launch_brain_life(game=None, play=False, yaw=35):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Brain Life requires a GTK display; use --output for headless export")
    window = BrainLifeWindow(game, yaw)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    if play:
        window.play()
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="zoe life --3d", description="Three-dimensional Brain Life through Zoe/GEM")
    result.add_argument("--brain", action="store_true", help="use the illustrative brain-shaped seed (the default)")
    result.add_argument("--steps", type=int, default=0, help="generations to advance before export (0–1000)")
    result.add_argument("--yaw", type=float, default=35, help="view rotation in degrees")
    result.add_argument("--play", action="store_true", help="start the native generation timer")
    result.add_argument("--output", help="new .json, .svg, .png, or .gem export instead of opening GTK")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        game = BrainLife.from_brain().advance(arguments.steps)
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            output = game.export(arguments.output, kind, arguments.width, arguments.yaw)
            print(json.dumps({
                "instrument": "zoe-brain-life", "generation": game.generation,
                "population": game.population, "state_sha256": game.digest(),
                "output": str(output), "bytes": output.stat().st_size,
                "anatomical_brain": False, "biological_life_created": False,
            }, indent=2, sort_keys=True))
            return 0
        launch_brain_life(game, arguments.play, arguments.yaw)
        return 0
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        print(f"zoe brain-life: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
