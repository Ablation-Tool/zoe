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

from .field import _canonical
from .pentomino import COLORS, HEIGHT, PIECE_NAMES, WIDTH, PentominoGame, benchmark_budgets, oriented_cells


def channels(color):
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


class PentominoCanvas(Gtk.DrawingArea):
    def __init__(self, game, action):
        super().__init__()
        self.game = game
        self.action = action
        self.set_size_request(430, 760)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Zoe Pentomino board")
        self.get_accessible().set_description("Six columns, ten rows, and five staging rows. Arrow keys move, R rotates, F reflects, Space drops, and Return places the current piece.")

    def layout(self):
        cell = min(self.get_allocated_width() / (WIDTH + 1), self.get_allocated_height() / (HEIGHT + 6))
        return cell, (self.get_allocated_width() - WIDTH * cell) / 2, 24

    def cell(self, context, x, y, color, alpha=1):
        cell, left, top = self.layout()
        if not 0 <= y < HEIGHT + 5:
            return
        context.set_source_rgba(*channels(color), alpha)
        context.rectangle(left + x * cell + 2, top + y * cell + 2, cell - 4, cell - 4)
        context.fill_preserve()
        context.set_source_rgba(.9, .95, 1, .45)
        context.set_line_width(1)
        context.stroke()

    def do_draw(self, context):
        cell, left, top = self.layout()
        context.set_source_rgb(.031, .067, .122)
        context.paint()
        context.select_font_face("sans-serif")
        context.set_font_size(14)
        context.set_source_rgb(.62, .72, .84)
        context.move_to(left, 17)
        context.show_text("STAGING · orient before entering the board")
        for y in range(HEIGHT + 1):
            for x in range(WIDTH):
                self.cell(context, x, y + 5, "#101b2b")
        context.set_source_rgba(.3, .55, .7, .5)
        context.set_line_width(2)
        context.rectangle(left, top + 5 * cell, WIDTH * cell, HEIGHT * cell)
        context.stroke()
        for (x, y), name in self.game.fixed.items():
            self.cell(context, x, y + 5, COLORS[name])
        current = self.game.current
        if current:
            for dx, dy in oriented_cells(current["name"], current["rotation"], current["reflected"]):
                self.cell(context, current["x"] + dx, current["y"] + dy + 5, COLORS[current["name"]], .72)
        context.set_font_size(16)
        context.set_source_rgb(.8, .88, .95)
        context.move_to(left, top + (HEIGHT + 5) * cell + 25)
        context.show_text("Arrows move · R rotate · F flip · Space drop")
        return False

    def on_button(self, _widget, _event):
        self.grab_focus()
        return True

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        actions = {
            "Left": ("move", -1, 0), "Right": ("move", 1, 0),
            "Up": ("move", 0, -1), "Down": ("move", 0, 1),
            "r": ("rotate", 1), "R": ("rotate", 1), "f": ("flip",), "F": ("flip",),
            "space": ("drop",), "Return": ("place",), "KP_Enter": ("place",),
        }
        if key not in actions:
            return False
        self.action(*actions[key])
        return True


class PentominoWindow(Gtk.Window):
    def __init__(self, game=None):
        super().__init__(title="Zoe Pentomino · timed spatial practice")
        self.game = game or PentominoGame()
        self.timer = None
        self.set_default_size(1120, 860)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        self.add(outer)
        header = Gtk.Label(xalign=0)
        header.set_markup("<span size='xx-large' color='#0e7490'>Zoe Pentomino</span>\n<span color='#475569'>Twelve free pentominoes · finite space · inspectable time</span>")
        outer.pack_start(header, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.set_position(490)
        outer.pack_start(panes, True, True, 0)
        self.canvas = PentominoCanvas(self.game, self.action)
        panes.pack1(self.canvas, True, True)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        panes.pack2(side, False, True)
        self.seed = Gtk.Entry(text="zoe-practice", max_length=128)
        side.pack_start(self.labeled("Practice seed", self.seed), False, False, 0)
        self.mode = Gtk.ComboBoxText()
        self.mode.append("practice", "Reproducible practice · preview visible")
        self.mode.append("masked", "Masked order · next piece hidden")
        self.mode.set_active_id("practice" if self.game.mode == "practice" else "masked")
        side.pack_start(self.labeled("Piece order", self.mode), False, False, 0)
        self.seconds = Gtk.SpinButton.new_with_range(1, 3600, 1)
        self.seconds.set_value(self.game.seconds)
        side.pack_start(self.labeled("Seconds", self.seconds), False, False, 0)
        self.interval = Gtk.SpinButton.new_with_range(.05, 3600, .05)
        self.interval.set_digits(2)
        self.interval.set_value(self.game.interval)
        side.pack_start(self.labeled("Gravity interval", self.interval), False, False, 0)
        self.new_button = Gtk.Button(label="Start a new mutually agreed challenge")
        self.new_button.connect("clicked", self.start)
        side.pack_start(self.new_button, False, False, 0)
        controls = Gtk.Grid(column_spacing=6, row_spacing=6)
        for label, action, column, row in (
            ("←", ("move", -1, 0), 0, 1), ("↓", ("move", 0, 1), 1, 1), ("→", ("move", 1, 0), 2, 1),
            ("↑", ("move", 0, -1), 1, 0), ("Rotate", ("rotate", 1), 0, 2),
            ("Flip", ("flip",), 1, 2), ("Drop", ("drop",), 2, 2), ("Place", ("place",), 1, 3),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", lambda _button, value=action: self.action(*value))
            controls.attach(button, column, row, 1, 1)
        side.pack_start(controls, False, False, 0)
        for label, callback in (
            ("Save session JSON", self.save_dialog), ("Open and verify completed replay", self.open_dialog),
            ("Export SVG", lambda *_args: self.export_dialog("svg")),
            ("Export PNG", lambda *_args: self.export_dialog("png")),
            ("Export GEM VDI", lambda *_args: self.export_dialog("gem")),
            ("Compare 1 / 5 / 20 / 300 second budgets", self.compare_dialog),
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
        self.resume()

    def labeled(self, text, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=text, xalign=0)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)
        box.pack_end(widget, False, False, 0)
        return box

    def resume(self):
        if self.timer is None and self.game.status == "playing":
            self.timer = GLib.timeout_add(100, self.on_tick)

    def stop(self):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def on_destroy(self, *_args):
        self.stop()

    def on_tick(self):
        try:
            self.game.tick()
            self.update_summary()
            self.canvas.queue_draw()
        except ValueError as error:
            self.status.set_text(str(error))
            self.timer = None
            return False
        if self.game.status != "playing":
            self.timer = None
            return False
        return True

    def start(self, *_args):
        self.stop()
        try:
            self.game = PentominoGame(
                seed=self.seed.get_text(), mode=self.mode.get_active_id(),
                seconds=self.seconds.get_value(), interval=self.interval.get_value(),
            )
            self.canvas.game = self.game
            self.canvas.grab_focus()
            self.status.set_text("A new challenge started. No move is executed automatically; only gravity and the agreed clock advance.")
            self.update_summary()
            self.resume()
        except ValueError as error:
            self.status.set_text(str(error))
            self.resume()

    def action(self, name, *arguments):
        try:
            accepted = getattr(self.game, name)(*arguments)
            self.status.set_text(f"{name}: {'accepted' if accepted else 'not available from this position'}")
            self.update_summary()
            self.canvas.queue_draw()
            return accepted
        except ValueError as error:
            self.status.set_text(str(error))
            return False

    def update_summary(self):
        values = self.game.measurements()
        next_piece = self.game.next_piece or ("masked" if self.game.mode == "masked" and self.game.status == "playing" else "end of game")
        self.summary.set_text(
            f"Time remaining: {values['remaining']:.1f} seconds\n"
            f"Pieces placed: {values['pieces_placed']} / 12\n"
            f"Filled cells: {values['filled_cells']} / 60\n"
            f"Full rows: {values['full_row_count']} (counted, not cleared)\n"
            f"Holes below occupied cells: {values['holes']}\n"
            f"Current: {self.game.current['name'] if self.game.current else 'none'} · Next: {next_piece}\n"
            f"Status: {self.game.status.replace('_', ' ')}\n"
            f"Recorded events: {len(self.game.events)}\n\n"
            "Attempt value = immediate reward + information gained + future skill + enjoyment − expected cost of failure.\n\n"
            "This is a decision lens, not a biological equation. A completed board is a puzzle result, not a measure of intelligence. No universal perfect timing is assumed."
        )

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
        path = self.choose_path("Save Pentomino session", Gtk.FileChooserAction.SAVE, "pentomino.json")
        if path:
            try:
                self.game.save(path)
                self.status.set_text(f"Saved {path}. Active saves hide seed material and future order.")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Save failed: {error}")

    def open_dialog(self, *_args):
        path = self.choose_path("Open completed Pentomino replay", Gtk.FileChooserAction.OPEN, "pentomino.json")
        if path:
            try:
                game = PentominoGame.replay(path)
                self.stop()
                self.game = game
                self.canvas.game = game
                self.update_summary()
                self.canvas.queue_draw()
                self.status.set_text("Replay verified: seed, event chain, actions, and final board agree.")
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.status.set_text(f"Replay rejected: {error}")

    def export_dialog(self, kind):
        path = self.choose_path(f"Export Pentomino {kind.upper()}", Gtk.FileChooserAction.SAVE, f"pentomino.{kind}")
        if path:
            try:
                self.game.export(path, kind)
                self.status.set_text(f"Exported {path}")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Export failed: {error}")

    def compare_dialog(self, *_args):
        path = self.choose_path("Save controlled budget comparison", Gtk.FileChooserAction.SAVE, "pentomino-budgets.json")
        if path:
            try:
                if path.suffix.lower() != ".json" or not path.parent.is_dir():
                    raise ValueError("choose a new .json path in an existing directory")
                report = benchmark_budgets(seed=self.seed.get_text() or "zoe-time-study")
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(_canonical(report) + "\n")
                self.status.set_text(f"Saved {path}. Identical synthetic strategy only; no human optimum is inferred.")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Comparison failed: {error}")


def launch_pentomino(game=None):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Pentomino requires a GTK display; use --output for headless export")
    window = PentominoWindow(game)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="pentomino", description="Zoe Pentomino timed spatial practice")
    result.add_argument("input", nargs="?", help="completed session JSON to verify and replay")
    result.add_argument("--seed", default="zoe-time-study", help="reproducible practice seed")
    result.add_argument("--masked", action="store_true", help="use a secret shuffled order and hide the next piece during play")
    result.add_argument("--seconds", type=float, default=300, help="finite time budget, up to 3600 seconds")
    result.add_argument("--gravity", type=float, default=.8, help="gravity interval in seconds")
    result.add_argument("--output", help="write a new .json, .svg, .png, or .gem artifact instead of opening GTK")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1200)
    result.add_argument("--compare", nargs="?", const="1,5,20,300", help="compare comma-separated budgets with one deterministic strategy")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.compare is not None:
            budgets = [float(value) for value in arguments.compare.split(",")]
            if not 1 <= len(budgets) <= 32:
                raise ValueError("choose 1-32 time budgets")
            report = benchmark_budgets(budgets, seed=arguments.seed)
            if arguments.output:
                output = Path(arguments.output)
                if output.suffix.lower() != ".json" or not output.parent.is_dir():
                    raise ValueError("comparison output must be a .json path in an existing directory")
                with output.open("x", encoding="utf-8") as stream:
                    stream.write(_canonical(report) + "\n")
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        game = PentominoGame.replay(arguments.input) if arguments.input else PentominoGame(arguments.seed, "masked" if arguments.masked else "practice", arguments.seconds, arguments.gravity)
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            output = game.save(arguments.output) if kind == "json" else game.export(arguments.output, kind, arguments.width)
            print(json.dumps({"instrument": "zoe-pentomino", "status": game.status, "output": str(output), "bytes": output.stat().st_size, "replay_verified": game.replay_verified}, sort_keys=True))
            return 0
        launch_pentomino(game)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"pentomino: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
