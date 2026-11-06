from __future__ import annotations

import argparse
from copy import deepcopy
import math
import os
from pathlib import Path

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GLib, Gtk

from .artline import ArtlineDocument, CANVAS, element_bounds, _smooth, demo_document
from .render import draw_cairo


TOOLS = (
    ("selector", "Selector"),
    ("quill", "Quill"),
    ("sketch", "Sketch"),
    ("rectangle", "Rectangle"),
    ("rounded_rectangle", "Rounded rectangle"),
    ("ellipse", "Ellipse"),
    ("line", "Line"),
    ("text", "Text"),
)


def rgba_hex(color):
    return f"#{round(color.red * 255):02x}{round(color.green * 255):02x}{round(color.blue * 255):02x}"


class ArtlineCanvas(Gtk.DrawingArea):
    def __init__(self, document, status_changed):
        super().__init__()
        self.document = document
        self.status_changed = status_changed
        self.tool = "selector"
        self.selection = []
        self.zoom = 1.0
        self.grid = True
        self.grid_spacing = 20
        self.stroke = "#67e8f9"
        self.fill = "#101b2b"
        self.hollow = False
        self.line_width = 3.0
        self.drag_start = None
        self.last_point = None
        self.draft = []
        self.draft_kind = None
        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event", self.on_button)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("key-press-event", self.on_key)
        self.get_accessible().set_name("Zoe Artline drawing canvas")
        self.get_accessible().set_description(
            "Editable vector drawing. Selector, quill, sketch, rectangle, rounded rectangle, ellipse, line, and text tools. "
            "Shift-drag scales, Alt-drag rotates, right-click duplicates. Control-Z undoes."
        )

    def layout(self):
        width, height = max(1, self.get_allocated_width()), max(1, self.get_allocated_height())
        scale = min(width / CANVAS[0], height / CANVAS[1]) * self.zoom
        return scale, (width - CANVAS[0] * scale) / 2, (height - CANVAS[1] * scale) / 2

    def world_to_screen(self, point):
        scale, offset_x, offset_y = self.layout()
        return offset_x + point[0] * scale, offset_y + point[1] * scale

    def screen_to_world(self, x, y):
        scale, offset_x, offset_y = self.layout()
        return (x - offset_x) / scale, (y - offset_y) / scale

    def refresh(self):
        self.queue_draw()
        self.status_changed()

    def select(self, identifiers):
        self.selection = list(identifiers)
        self.refresh()

    def hit(self, point):
        for element in reversed(self.document.elements):
            if not self.document.layer(element["layer"])["visible"]:
                continue
            left, top, right, bottom = element_bounds(element)
            tolerance = max(4, element["width"] / 2 + 2)
            if left - tolerance <= point[0] <= right + tolerance and top - tolerance <= point[1] <= bottom + tolerance:
                return element["id"]
        return None

    def do_draw(self, context):
        scale, offset_x, offset_y = self.layout()
        context.save()
        context.translate(offset_x, offset_y)
        context.scale(scale, scale)
        draw_cairo(context, self.document.scene(), CANVAS[0], CANVAS[1], highlight_ids=self.selection)
        if self.grid:
            context.set_source_rgba(0.35, 0.5, 0.65, 0.18)
            context.set_line_width(1 / scale)
            for x in range(0, CANVAS[0] + 1, self.grid_spacing):
                context.move_to(x, 0)
                context.line_to(x, CANVAS[1])
            for y in range(0, CANVAS[1] + 1, self.grid_spacing):
                context.move_to(0, y)
                context.line_to(CANVAS[0], y)
            context.stroke()
        if self.drag_start is not None and self.last_point is not None:
            context.set_source_rgba(0.4, 0.85, 0.95, 0.85)
            context.set_line_width(max(1, 2 / scale))
            context.set_dash([8 / scale, 5 / scale])
            if self.draft_kind in {"rectangle", "rounded_rectangle", "ellipse"}:
                left, top = min(self.drag_start[0], self.last_point[0]), min(self.drag_start[1], self.last_point[1])
                width = abs(self.last_point[0] - self.drag_start[0])
                height = abs(self.last_point[1] - self.drag_start[1])
                if self.draft_kind == "ellipse":
                    context.save()
                    context.translate(left + width / 2, top + height / 2)
                    context.scale(max(0.001, width / 2), max(0.001, height / 2))
                    context.arc(0, 0, 1, 0, math.tau)
                    context.restore()
                else:
                    context.rectangle(left, top, width, height)
                context.stroke()
            elif self.draft_kind in {"line", "selector"}:
                context.move_to(*self.drag_start)
                context.line_to(*self.last_point)
                context.stroke()
            else:
                points = [*self.draft, self.last_point]
                if self.draft_kind in {"quill", "sketch"} and len(points) > 1:
                    if self.draft_kind == "sketch":
                        points = _smooth(points, False)
                    context.move_to(*points[0])
                    for point in points[1:]:
                        context.line_to(*point)
                    context.stroke()
            context.set_dash([])
        context.restore()
        return False

    def style(self):
        return {
            "stroke": self.stroke,
            "fill": "none" if self.hollow else self.fill,
            "width": self.line_width,
        }

    def on_button(self, _widget, event):
        if event.button not in {1, 3}:
            return False
        self.grab_focus()
        point = self.screen_to_world(event.x, event.y)
        if self.tool == "selector":
            identifier = self.hit(point)
            if identifier is None:
                self.select([])
                return True
            identifiers = self.document.grouped([identifier])
            if event.button == 3:
                try:
                    self.select(self.document.duplicate(identifiers))
                except ValueError as error:
                    self.status_changed(str(error))
                return True
            self.draft_kind = "scale" if event.state & Gdk.ModifierType.SHIFT_MASK else "rotate" if event.state & Gdk.ModifierType.MOD1_MASK else "move"
            self.selection = identifiers
            self.drag_start = point
            self.last_point = point
            self.refresh()
            return True
        if event.button == 3:
            return False
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and self.tool == "quill":
            self.finish_path()
            return True
        if self.tool == "text":
            self.get_toplevel().add_text(point)
            return True
        self.drag_start = point
        self.last_point = point
        self.draft_kind = self.tool
        if self.tool == "quill":
            if len(self.draft) >= 256:
                self.status_changed("Quill paths are limited to 256 anchor points")
                self.cancel_draft()
                return True
            self.draft.append(point)
        elif self.tool == "sketch":
            self.draft = [point]
        self.refresh()
        return True

    def on_motion(self, _widget, event):
        if self.drag_start is None:
            return False
        point = self.screen_to_world(event.x, event.y)
        if self.tool == "sketch" and math.hypot(point[0] - self.draft[-1][0], point[1] - self.draft[-1][1]) >= 2 and len(self.draft) < 256:
            self.draft.append(point)
        self.last_point = point
        self.queue_draw()
        return True

    def on_release(self, _widget, event):
        if self.drag_start is None:
            return False
        point = self.screen_to_world(event.x, event.y)
        if self.tool == "quill":
            self.drag_start = None
            self.last_point = None
            self.refresh()
            return True
        kind, start, selection = self.draft_kind, self.drag_start, list(self.selection)
        draft = list(self.draft)
        self.cancel_draft()
        try:
            if self.tool == "selector":
                if kind == "move":
                    self.document.transform(selection, dx=point[0] - start[0], dy=point[1] - start[1])
                elif kind == "scale":
                    center = self.selection_center()
                    first_distance = math.hypot(start[0] - center[0], start[1] - center[1])
                    last_distance = math.hypot(point[0] - center[0], point[1] - center[1])
                    if first_distance > 0 and last_distance > 0:
                        ratio = max(0.05, last_distance / first_distance)
                        self.document.transform(selection, scale=(ratio, ratio))
                elif kind == "rotate":
                    center = self.selection_center()
                    angle = math.atan2(point[1] - center[1], point[0] - center[0]) - math.atan2(start[1] - center[1], start[0] - center[0])
                    self.document.transform(selection, angle=angle)
            elif self.tool in {"rectangle", "rounded_rectangle", "ellipse"}:
                bounds = [min(start[0], point[0]), min(start[1], point[1]), max(start[0], point[0]), max(start[1], point[1])]
                if bounds[2] - bounds[0] >= 1 and bounds[3] - bounds[1] >= 1:
                    if self.tool == "ellipse":
                        self.document.add_element("ellipse", center=[(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2], radii=[(bounds[2] - bounds[0]) / 2, (bounds[3] - bounds[1]) / 2], **self.style())
                    else:
                        self.document.add_element(self.tool, bounds=bounds, **self.style())
            elif self.tool == "line":
                self.document.add_element("line", points=[start, point], **self.style())
            elif self.tool == "sketch" and len(draft) >= 2:
                self.document.add_element("path", points=draft, closed=not self.hollow and len(draft) >= 3, smooth=True, **self.style())
        except ValueError as error:
            self.status_changed(str(error))
        self.refresh()
        return True

    def cancel_draft(self):
        self.drag_start = None
        self.last_point = None
        self.draft_kind = None
        self.draft = []

    def finish_path(self):
        if len(self.draft) < 2:
            self.status_changed("Quill needs at least two anchor points")
            self.cancel_draft()
            return
        try:
            self.document.add_element("path", points=self.draft, closed=not self.hollow, smooth=True, **self.style())
        except ValueError as error:
            self.status_changed(str(error))
        self.cancel_draft()
        self.refresh()

    def selection_center(self):
        if not self.selection:
            return self.screen_to_world(self.get_allocated_width() / 2, self.get_allocated_height() / 2)
        bounds = [element_bounds(self.document.element(identifier)) for identifier in self.selection]
        return [
            (min(item[0] for item in bounds) + max(item[2] for item in bounds)) / 2,
            (min(item[1] for item in bounds) + max(item[3] for item in bounds)) / 2,
        ]

    def on_key(self, _widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            key = Gdk.keyval_name(event.keyval)
            if key == "z":
                self.get_toplevel().undo()
            elif key == "y":
                self.get_toplevel().redo()
            elif key == "d":
                if self.selection:
                    self.select(self.document.duplicate(self.selection))
            elif key == "g" and event.state & Gdk.ModifierType.SHIFT_MASK:
                self.get_toplevel().ungroup_selection()
            elif key == "g":
                self.get_toplevel().group_selection()
            elif key == "s":
                self.get_toplevel().save_dialog()
            elif key == "o":
                self.get_toplevel().open_dialog()
            elif key == "e":
                self.get_toplevel().export_dialog()
            else:
                return False
            return True
        key = Gdk.keyval_name(event.keyval)
        if key == "Delete" and self.selection:
            self.document.delete(self.selection)
            self.select([])
        elif key in {"plus", "equal", "KP_Add"}:
            self.get_toplevel().change_zoom(1.25)
        elif key in {"minus", "KP_Subtract"}:
            self.get_toplevel().change_zoom(0.8)
        elif key == "1":
            self.get_toplevel().set_zoom(1.0)
        elif key == "g":
            self.get_toplevel().toggle_grid()
        elif key == "Escape":
            self.cancel_draft()
            self.select([])
            self.refresh()
        else:
            return False
        return True


class ArtlineWindow(Gtk.Window):
    def __init__(self, document=None):
        super().__init__(title="Zoe Artline · original vector workbench")
        self.document = document or demo_document()
        self.path = None
        self.set_default_size(1400, 950)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", self.on_delete)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=10)
        self.add(outer)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        outer.pack_start(toolbar, False, False, 0)
        self.tool_selector = Gtk.ComboBoxText()
        for identifier, label in TOOLS:
            self.tool_selector.append(identifier, label)
        self.tool_selector.set_active_id("selector")
        self.tool_selector.connect("changed", self.on_tool_changed)
        toolbar.pack_start(self.tool_selector, False, False, 0)
        for label, callback in (
            ("Clone", self.duplicate_selection),
            ("Rotate 90°", self.rotate_selection),
            ("Flip", self.flip_selection),
            ("Front", lambda *_args: self.reorder_selection("front")),
            ("Back", lambda *_args: self.reorder_selection("back")),
            ("Group", self.group_selection),
            ("Ungroup", self.ungroup_selection),
            ("Undo", self.undo),
            ("Redo", self.redo),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            toolbar.pack_start(button, False, False, 0)
        self.new_button = Gtk.Button(label="New")
        self.new_button.connect("clicked", self.new_document)
        toolbar.pack_end(self.new_button, False, False, 0)
        self.open_button = Gtk.Button(label="Open")
        self.open_button.connect("clicked", self.open_dialog)
        toolbar.pack_end(self.open_button, False, False, 0)
        self.save_button = Gtk.Button(label="Save")
        self.save_button.connect("clicked", self.save_dialog)
        toolbar.pack_end(self.save_button, False, False, 0)
        self.export_button = Gtk.Button(label="Export")
        self.export_button.connect("clicked", self.export_dialog)
        toolbar.pack_end(self.export_button, False, False, 0)
        self.merge_button = Gtk.Button(label="Merge")
        self.merge_button.connect("clicked", self.merge_dialog)
        toolbar.pack_end(self.merge_button, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.set_position(1100)
        outer.pack_start(panes, True, True, 0)
        self.canvas = ArtlineCanvas(self.document, self.update_status)
        panes.pack1(self.canvas, True, True)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, border_width=8)
        side.set_size_request(260, -1)
        panes.pack2(side, False, True)
        style = self.canvas.style()
        side.pack_start(Gtk.Label(label="New element style", xalign=0), False, False, 0)
        self.stroke_button = Gtk.ColorButton()
        self.stroke_button.set_rgba(self.color(style["stroke"]))
        self.stroke_button.connect("color-set", self.on_stroke)
        side.pack_start(self.labeled("Stroke", self.stroke_button), False, False, 0)
        self.fill_button = Gtk.ColorButton()
        self.fill_button.set_rgba(self.color(style["fill"]))
        self.fill_button.connect("color-set", self.on_fill)
        side.pack_start(self.labeled("Fill", self.fill_button), False, False, 0)
        self.hollow_button = Gtk.CheckButton(label="Hollow (no fill)")
        self.hollow_button.connect("toggled", self.on_hollow)
        side.pack_start(self.hollow_button, False, False, 0)
        self.width_button = Gtk.SpinButton.new_with_range(0.5, 128, 0.5)
        self.width_button.set_value(style["width"])
        self.width_button.connect("value-changed", self.on_width)
        side.pack_start(self.labeled("Line width", self.width_button), False, False, 0)
        self.style_button = Gtk.Button(label="Apply style to selection")
        self.style_button.connect("clicked", self.apply_style)
        side.pack_start(self.style_button, False, False, 0)
        self.grid_button = Gtk.ToggleButton(label="Grid")
        self.grid_button.set_active(True)
        self.grid_button.connect("toggled", self.toggle_grid)
        side.pack_start(self.grid_button, False, False, 0)
        self.grid_spacing_button = Gtk.SpinButton.new_with_range(1, 256, 1)
        self.grid_spacing_button.set_value(20)
        self.grid_spacing_button.connect("value-changed", self.on_grid_spacing)
        side.pack_start(self.labeled("Grid spacing", self.grid_spacing_button), False, False, 0)
        self.snap_button = Gtk.Button(label="Align selection to grid")
        self.snap_button.connect("clicked", self.align_selection)
        side.pack_start(self.snap_button, False, False, 0)
        zoom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, callback in (("Zoom −", lambda *_args: self.change_zoom(0.8)), ("Zoom +", lambda *_args: self.change_zoom(1.25)), ("Fit", lambda *_args: self.set_zoom(1.0))):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            zoom.pack_start(button, True, True, 0)
        side.pack_start(zoom, False, False, 0)
        side.pack_start(Gtk.Label(label="Layers", xalign=0), False, False, 0)
        self.layer_store = Gtk.ListStore(bool, bool, str, str)
        self.layer_view = Gtk.TreeView(model=self.layer_store)
        self.layer_view.set_headers_visible(True)
        for index, title in enumerate(("Visible", "Locked", "Layer")):
            if index < 2:
                renderer = Gtk.CellRendererToggle()
                renderer.connect("toggled", self.on_layer_toggle, index)
                self.layer_view.insert_column(Gtk.TreeViewColumn(title, renderer, active=index), -1)
            else:
                self.layer_view.insert_column(Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=index), -1)
        self.layer_view.get_selection().connect("changed", self.on_layer_selected)
        side.pack_start(self.layer_view, True, True, 0)
        layer_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, callback in (("Add", self.add_layer), ("Remove", self.remove_layer)):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            layer_buttons.pack_start(button, True, True, 0)
        side.pack_start(layer_buttons, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        outer.pack_end(self.status, False, False, 0)
        self.refresh_layers()
        self.update_status()

    def labeled(self, text, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label=text, xalign=0)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)
        box.pack_end(widget, False, False, 0)
        return box

    def color(self, value):
        color = Gdk.RGBA()
        if not color.parse(value):
            raise ValueError(f"invalid color: {value}")
        return color

    def parent_window(self):
        return self

    def refresh_layers(self):
        selected = self.document.current_layer
        self.layer_store.clear()
        for layer in self.document.layers:
            self.layer_store.append([layer["visible"], layer["locked"], layer["name"] + (" · active" if layer["id"] == selected else ""), layer["id"]])
        self.canvas.refresh()

    def update_status(self, message=None):
        if message is not None:
            self.status.set_text(message)
        else:
            self.status.set_text(
                f"{len(self.document.elements)} elements · layer {self.document.current_layer} · "
                f"{len(self.selection_ids())} selected · {self.canvas.zoom:.2f}× · no automatic action"
            )

    def selection_ids(self):
        return self.canvas.selection

    def on_tool_changed(self, combo):
        self.canvas.tool = combo.get_active_id()
        self.canvas.cancel_draft()
        self.update_status(f"Tool: {self.canvas.tool}")

    def on_stroke(self, button):
        self.canvas.stroke = rgba_hex(button.get_rgba())

    def on_fill(self, button):
        self.canvas.fill = rgba_hex(button.get_rgba())

    def on_hollow(self, button):
        self.canvas.hollow = button.get_active()

    def on_width(self, button):
        self.canvas.line_width = button.get_value()

    def on_grid_spacing(self, button):
        self.canvas.grid_spacing = int(button.get_value())
        self.canvas.queue_draw()

    def apply_style(self, *_args):
        if not self.selection_ids():
            self.update_status("Select an element before applying a style")
            return
        self.document.restyle(self.selection_ids(), **self.canvas.style())
        self.canvas.refresh()

    def duplicate_selection(self, *_args):
        if self.selection_ids():
            self.canvas.select(self.document.duplicate(self.selection_ids()))

    def rotate_selection(self, *_args):
        if self.selection_ids():
            self.document.transform(self.selection_ids(), angle=math.pi / 2)

    def flip_selection(self, *_args):
        if self.selection_ids():
            self.document.transform(self.selection_ids(), flip="horizontal")

    def reorder_selection(self, direction):
        if self.selection_ids():
            self.document.reorder(self.selection_ids(), direction)
            self.canvas.refresh()

    def group_selection(self, *_args):
        if self.selection_ids():
            self.document.group(self.selection_ids())
            self.canvas.refresh()

    def ungroup_selection(self, *_args):
        if self.selection_ids():
            self.document.ungroup(self.selection_ids())
            self.canvas.refresh()

    def undo(self, *_args):
        try:
            self.document.undo()
            self.canvas.refresh()
        except ValueError as error:
            self.update_status(str(error))

    def redo(self, *_args):
        try:
            self.document.redo()
            self.canvas.refresh()
        except ValueError as error:
            self.update_status(str(error))

    def add_text(self, point):
        dialog = Gtk.Dialog(title="Create text element", transient_for=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Create", Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_border_width(12)
        entry = Gtk.Entry()
        entry.set_text("Zoe")
        entry.set_max_length(500)
        entry.set_activates_default(True)
        area.add(entry)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        try:
            if dialog.run() == Gtk.ResponseType.OK and entry.get_text():
                self.document.add_element("text", position=point, text=entry.get_text(), size=24, **self.canvas.style())
                self.canvas.refresh()
        finally:
            dialog.destroy()

    def add_layer(self, *_args):
        self.document.add_layer()
        self.refresh_layers()

    def remove_layer(self, *_args):
        try:
            self.document.remove_layer(self.document.current_layer)
            self.refresh_layers()
        except ValueError as error:
            self.update_status(str(error))

    def on_layer_toggle(self, _renderer, path, column):
        layer = self.document.layers[int(path)]
        if column == 0:
            self.document.set_layer_visible(layer["id"], not layer["visible"])
        else:
            self.document.set_layer_locked(layer["id"], not layer["locked"])
        self.refresh_layers()

    def on_layer_selected(self, selection):
        _model, tree_iter = selection.get_selected()
        if tree_iter is not None:
            self.document.set_layer(self.document.layers[self.layer_store.get_path(tree_iter).get_indices()[0]]["id"])
            self.refresh_layers()

    def align_selection(self, *_args):
        if self.selection_ids():
            try:
                self.document.align_to_grid(self.selection_ids(), self.canvas.grid_spacing)
                self.canvas.refresh()
            except ValueError as error:
                self.update_status(str(error))

    def change_zoom(self, factor):
        self.set_zoom(self.canvas.zoom * factor)

    def set_zoom(self, value):
        self.canvas.zoom = min(16, max(0.1, value))
        self.canvas.queue_draw()
        self.update_status()

    def toggle_grid(self, *_args):
        self.canvas.grid = not self.canvas.grid
        self.grid_button.set_active(self.canvas.grid)
        self.canvas.queue_draw()

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

    def confirm_replace(self):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL, text="Replace the current drawing?",
        )
        dialog.format_secondary_text("Unsaved changes in the current drawing will be replaced.")
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def new_document(self, *_args):
        if self.confirm_replace():
            self.document = ArtlineDocument()
            self.canvas.document = self.document
            self.canvas.select([])
            self.path = None
            self.refresh_layers()

    def open_dialog(self, *_args):
        path = self.choose_path("Open Artline JSON", Gtk.FileChooserAction.OPEN, "drawing.json")
        if path is None or not self.confirm_replace():
            return
        try:
            self.document = ArtlineDocument.load(path)
            self.canvas.document = self.document
            self.canvas.select([])
            self.path = path
            self.refresh_layers()
        except (OSError, ValueError) as error:
            self.update_status(f"Open failed: {error}")

    def merge_dialog(self, *_args):
        path = self.choose_path("Merge Artline JSON", Gtk.FileChooserAction.OPEN, "drawing.json")
        if path is not None:
            try:
                self.document.merge(ArtlineDocument.load(path))
                self.refresh_layers()
            except (OSError, ValueError) as error:
                self.update_status(f"Merge failed: {error}")

    def save_dialog(self, *_args):
        path = self.path or self.choose_path("Save Artline JSON", Gtk.FileChooserAction.SAVE, "drawing.json")
        if path is not None:
            try:
                self.document.save(path)
                self.path = path
                self.update_status(f"Saved {path}")
            except (OSError, ValueError) as error:
                self.update_status(f"Save failed: {error}")

    def export_dialog(self, *_args):
        path = self.choose_path("Export Artline", Gtk.FileChooserAction.SAVE, "zoe-artline.svg")
        if path is not None:
            try:
                self.document.export(path)
                self.update_status(f"Exported {path}")
            except (OSError, ValueError) as error:
                self.update_status(f"Export failed: {error}")

    def on_delete(self, *_args):
        return False


def launch_artline(document=None):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Artline requires a GTK display; use --output for headless export")
    window = ArtlineWindow(document)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="artline", description="Zoe Artline vector workbench")
    result.add_argument("input", nargs="?", help="Artline JSON document to load")
    result.add_argument("--empty", action="store_true", help="start with an empty drawing")
    result.add_argument("--output", help="export to a new .svg, .png, or .gem path instead of opening GTK")
    result.add_argument("--format", choices=("svg", "png", "gem"), help="default: infer from output suffix")
    result.add_argument("--width", type=int, default=1200, help="SVG/PNG width in pixels")
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        document = ArtlineDocument.load(arguments.input) if arguments.input else ArtlineDocument() if arguments.empty else demo_document()
        if arguments.output:
            output = document.export(arguments.output, arguments.format, arguments.width)
            print({"instrument": "zoe-artline", "elements": len(document.elements), "output": str(output), "bytes": output.stat().st_size})
            return 0
        launch_artline(document)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"artline: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
