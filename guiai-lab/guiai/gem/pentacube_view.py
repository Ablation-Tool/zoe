from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import zipfile

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GdkPixbuf, Gtk

from .pentacube import (
    COLORS, FACES, NET, PentacubeGame, SOLVED_RHYME, move_text, parse_moves,
    rhyme_for_move,
)
from .pentacube_reference import inspect_reference, save_reference_report


def channels(color):
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


class PentacubeCanvas(Gtk.DrawingArea):
    def __init__(self, game, turn, action, depth):
        super().__init__()
        self.game = game
        self.turn_action = turn
        self.action = action
        self.depth = depth
        self.set_size_request(610, 650)
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Zoe Pentacube face net")
        self.get_accessible().set_description("Six five-by-five faces. Letter keys turn faces; Shift reverses. One selects outer, two inner. H hints, Space applies, Backspace undoes.")

    def layout(self):
        cell = max(60, min(self.get_allocated_width() / 4.5, (self.get_allocated_height() - 45) / 3.5))
        width, height = 4 * cell + 30, 3 * cell + 40
        return cell, (self.get_allocated_width() - width) / 2, 38 + (self.get_allocated_height() - 38 - height) / 2

    def do_draw(self, context):
        cell, left, top = self.layout()
        context.set_source_rgb(.031, .067, .122)
        context.paint()
        context.select_font_face("sans-serif")
        context.set_source_rgb(.62, .72, .84)
        context.set_font_size(13)
        context.move_to(max(12, left), 22)
        context.show_text("U / L / F / R / B / D turn · Shift reverses · 1 outer · 2 inner")
        board = self.game.board()
        for face in FACES:
            net_x, net_y = NET[face]
            face_x = left + net_x * (cell + 10)
            face_y = top + net_y * (cell + 20)
            context.set_source_rgb(.8, .68, .48)
            context.set_font_size(13)
            context.move_to(face_x, face_y - 8)
            context.show_text(f"{face} · home pentominoes")
            for row in range(5):
                for column in range(5):
                    sticker = board[face][row][column]
                    x = face_x + column * cell / 5
                    y = face_y + row * cell / 5
                    side = cell / 5
                    context.set_source_rgb(*channels(COLORS[sticker["name"]]))
                    context.rectangle(x + 1, y + 1, side - 2, side - 2)
                    context.fill_preserve()
                    if sticker["home_match"]:
                        context.set_source_rgba(.97, .98, 1, .85)
                    else:
                        context.set_source_rgba(.12, .18, .26, .8)
                    context.set_line_width(1)
                    context.stroke()
                    context.set_source_rgb(.03, .06, .1)
                    context.set_font_size(max(8, side * .35))
                    context.move_to(x + side * .32, y + side * .67)
                    context.show_text(sticker["name"])
        return False

    def on_button(self, _widget, _event):
        self.grab_focus()
        return True

    def on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key in FACES or key.lower() in {face.lower() for face in FACES}:
            self.turn_action(key.upper(), key.isupper())
            return True
        if key == "BackSpace" or key == "z" and event.state & Gdk.ModifierType.CONTROL_MASK:
            self.action("undo")
            return True
        if key in {"h", "H"}:
            self.action("hint")
            return True
        if key == "space":
            self.action("apply_hint")
            return True
        return False


class PentacubeWindow(Gtk.Window):
    def __init__(self, game=None, show_hint=False, rhyme=False):
        super().__init__(title="Zoetic Research · Zoe Pentacube")
        self.game = game or PentacubeGame()
        self.hint_move = self.game.hint() if show_hint else None
        self.rhyme = rhyme
        self.set_default_size(1220, 900)
        self.set_position(Gtk.WindowPosition.CENTER)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        self.add(outer)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.logo = None
        logo_path = Path(__file__).resolve().parents[1] / "icons/zoetic-research.svg"
        if logo_path.is_file():
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(logo_path), 360, 125, True)
                self.logo = Gtk.Image.new_from_pixbuf(pixbuf)
                header.pack_start(self.logo, False, False, 0)
            except (OSError, ValueError):
                self.logo = None
        title = Gtk.Label(xalign=0)
        title.set_markup("<span size='xx-large' color='#0e7490'>Zoe Pentacube</span>\n<span color='#475569'>Thirty pentominoes · 150 stickers · exact legal permutations</span>")
        header.pack_start(title, True, True, 0)
        outer.pack_start(header, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.set_position(650)
        outer.pack_start(panes, True, True, 0)
        self.canvas = PentacubeCanvas(self.game, self.turn, self.action, lambda: self.depth.get_value_as_int())
        panes.pack1(self.canvas, True, True)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, border_width=10)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(480, 690)
        scrolled.add(side)
        panes.pack2(scrolled, False, True)
        self.seed = Gtk.Entry(text=self.game.seed, max_length=128)
        side.pack_start(self.labeled("Reproducible seed", self.seed), False, False, 0)
        self.scramble = Gtk.SpinButton.new_with_range(0, 64, 1)
        self.scramble.set_value(len(self.game.scramble))
        side.pack_start(self.labeled("Legal scramble turns", self.scramble), False, False, 0)
        self.new_button = Gtk.Button(label="Start a new scramble")
        self.new_button.connect("clicked", self.start)
        side.pack_start(self.new_button, False, False, 0)
        self.depth = Gtk.SpinButton.new_with_range(1, 2, 1)
        self.depth.set_value(1)
        side.pack_start(self.labeled("Layer · 1 outer / 2 inner", self.depth), False, False, 0)
        self.inverse = Gtk.CheckButton(label="Reverse the next quarter turn")
        side.pack_start(self.inverse, False, False, 0)
        faces = Gtk.Grid(column_spacing=5, row_spacing=5)
        for index, face in enumerate(FACES):
            button = Gtk.Button(label=f"Turn {face}")
            button.get_accessible().set_description(f"Turn the {face} layer using the selected depth and direction")
            button.connect("clicked", lambda _button, value=face: self.turn(value))
            faces.attach(button, index % 3, index // 3, 1, 1)
        side.pack_start(faces, False, False, 0)
        actions = Gtk.Grid(column_spacing=5, row_spacing=5)
        for index, (label, callback) in enumerate((
            ("Undo", self.undo), ("Reset", self.reset),
            ("Hint", self.hint), ("Apply hint", self.apply_hint),
        )):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            actions.attach(button, index % 2, index // 2, 1, 1)
        side.pack_start(actions, False, False, 0)
        self.rhyme_button = Gtk.CheckButton(label="Original rhyme hints")
        self.rhyme_button.set_active(self.rhyme)
        self.rhyme_button.connect("toggled", self.set_rhyme)
        side.pack_start(self.rhyme_button, False, False, 0)
        files = Gtk.Grid(column_spacing=5, row_spacing=5)
        for index, (label, callback) in enumerate((
            ("Save replay", self.save_dialog), ("Open replay", self.open_dialog),
            ("SVG", lambda *_args: self.export_dialog("svg")),
            ("PNG", lambda *_args: self.export_dialog("png")),
            ("GEM VDI", lambda *_args: self.export_dialog("gem")),
        )):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            files.attach(button, index % 2, index // 2, 1, 1)
        side.pack_start(files, False, False, 0)
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

    def refresh(self):
        self.update_summary()
        self.canvas.queue_draw()

    def update_summary(self):
        values = self.game.measurements()
        hint = move_text(self.hint_move["move"]) if self.hint_move else "not requested"
        text = (
            f"Home stickers: {values['home_matches']} / 150\n"
            f"Recovered regions: {values['recovered_regions']} / 30\n"
            f"Displaced: {values['displaced']}\n"
            f"Weak lower bound: {values['weak_lower_bound']} turns (not optimal)\n"
            f"Player turns: {values['player_turns']} · Events: {values['events']}\n"
            f"Hint: {hint} · never automatic\n\n"
            "Legal, reversible moves. No optimal-distance or intelligence claim."
        )
        if self.rhyme:
            text += "\n\n" + (SOLVED_RHYME if values["solved"] else rhyme_for_move(self.hint_move["move"]) if self.hint_move else "Ask for a hint when you want a rhyme;\nOne little turn at a time.")
        self.summary.set_text(text)

    def turn(self, face, inverse=None):
        try:
            accepted = self.game.turn(face, self.depth.get_value_as_int(), self.inverse.get_active() if inverse is None else inverse)
            self.hint_move = None
            self.status.set_text(f"{face}: explicit layer turn applied")
            self.refresh()
            return accepted
        except ValueError as error:
            self.status.set_text(str(error))
            return False

    def action(self, name, *_args):
        return {"undo": self.undo, "hint": self.hint, "apply_hint": self.apply_hint}.get(name, lambda: False)()

    def undo(self, *_args):
        accepted = self.game.undo()
        self.hint_move = None
        self.status.set_text("Player turn undone; replay remains append-only." if accepted else "No player turn to undo.")
        self.refresh()
        return accepted

    def reset(self, *_args):
        self.game.reset()
        self.hint_move = None
        self.status.set_text("Returned to the recorded scramble. Earlier events remain in the replay.")
        self.refresh()
        return True

    def hint(self, *_args):
        self.hint_move = self.game.hint()
        self.status.set_text("Hint shown without applying it. This reverses the recorded path, not an optimal search.")
        self.refresh()
        return self.hint_move

    def apply_hint(self, *_args):
        if self.hint_move is None:
            self.hint_move = self.game.hint()
        if self.hint_move is None:
            self.status.set_text("Already solved. No move is applied.")
            return False
        move = self.hint_move["move"]
        self.game.apply(move)
        self.hint_move = None
        self.status.set_text(f"Hint {move_text(move)} applied by explicit user action.")
        self.refresh()
        return True

    def set_rhyme(self, *_args):
        self.rhyme = self.rhyme_button.get_active()
        self.update_summary()

    def start(self, *_args):
        try:
            self.game = PentacubeGame(self.seed.get_text(), self.scramble.get_value_as_int())
            self.canvas.game = self.game
            self.hint_move = None
            self.status.set_text("New legal scramble created. No move is executed automatically.")
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
        path = self.choose_path("Save Pentacube session", Gtk.FileChooserAction.SAVE, "pentacube.json")
        if path:
            try:
                self.game.save(path)
                self.status.set_text(f"Saved and verified {path}")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Save failed: {error}")

    def load_path(self, path):
        try:
            game = PentacubeGame.replay(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.status.set_text(f"Replay rejected: {error}")
            return False
        self.game = game
        self.canvas.game = game
        self.hint_move = None
        self.status.set_text("Replay verified: scramble, events, and final state agree.")
        self.refresh()
        return True

    def open_dialog(self, *_args):
        path = self.choose_path("Open Pentacube replay", Gtk.FileChooserAction.OPEN, "pentacube.json")
        if path:
            self.load_path(path)

    def export_current(self, path, kind=None):
        return self.game.export(path, kind, hint=self.hint_move)

    def export_dialog(self, kind):
        path = self.choose_path(f"Export Pentacube {kind.upper()}", Gtk.FileChooserAction.SAVE, f"pentacube.{kind}")
        if path:
            try:
                self.export_current(path, kind)
                self.status.set_text(f"Exported {path}")
            except (OSError, ValueError) as error:
                self.status.set_text(f"Export failed: {error}")


def launch_pentacube(game=None, show_hint=False, rhyme=False):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Pentacube requires a GTK display; use --output for headless export")
    window = PentacubeWindow(game, show_hint, rhyme)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="pentacube", description="Zoe Pentacube · pentomino exact covers and legal cube permutations")
    result.add_argument("input", nargs="?", help="saved session JSON to verify and replay")
    result.add_argument("--seed", default="zoe-pentacube", help="reproducible scramble seed")
    result.add_argument("--scramble", type=int, default=6, help="legal scramble turns, from 0 to 64")
    result.add_argument("--moves", default="", help="comma-separated explicit turns: F, R', U2, L2'")
    result.add_argument("--hint", action="store_true", help="show the next recorded-path inverse without applying it")
    result.add_argument("--rhyme", action="store_true", help="include an original rhyme hint")
    result.add_argument("--reference", help="inspect an external MZ, ZIP, or binary historical artifact without executing it")
    result.add_argument("--source-url", help="HTTPS provenance URL for --reference; metadata only, no fetch")
    result.add_argument("--output", help="new .json, .svg, .png, or .gem artifact instead of opening GTK")
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def _print(document):
    print(json.dumps(document, ensure_ascii=False, sort_keys=True))


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.reference:
            if arguments.input or arguments.moves:
                raise ValueError("historical reference inspection cannot be combined with a replay or game moves")
            if not arguments.output:
                raise ValueError("historical reference inspection requires a new --output JSON path")
            if (arguments.format or Path(arguments.output).suffix.lower().lstrip(".")) != "json":
                raise ValueError("historical reference output must be JSON")
            report = inspect_reference(arguments.reference, arguments.source_url)
            save_reference_report(report, arguments.output)
            _print({"instrument": report["instrument"], "kind": report["kind"], "sha256": report["sha256"], "bytes": report["bytes"], "output": arguments.output, "payloads_executed": False, "hardware_accessed": False})
            return 0
        game = PentacubeGame.replay(arguments.input) if arguments.input else PentacubeGame(arguments.seed, arguments.scramble)
        for move in parse_moves(arguments.moves):
            game.apply(move)
        hint = game.hint() if arguments.hint else None
        if arguments.output:
            kind = arguments.format or Path(arguments.output).suffix.lower().lstrip(".")
            if kind == "json":
                output = game.save(arguments.output)
            else:
                output = game.export(arguments.output, kind, arguments.width, hint)
            _print({"instrument": "zoe-pentacube", "output": str(output), "measurements": game.measurements(), "hint": hint, "rhyme": rhyme_for_move(hint["move"]) if arguments.rhyme and hint else None, "autonomous_moves": False})
            return 0
        launch_pentacube(game, arguments.hint, arguments.rhyme)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"pentacube: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
