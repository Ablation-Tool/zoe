from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import GLib, Gtk

from .desktop import DesktopProcesses
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .unified import ComponentRegistry, unified_scene
from .vdi import write_metafile


class ZoeDesktopWindow(Gtk.Window):
    def __init__(self, registry=None, processes=None):
        super().__init__(title="Zoe OS · One ZOE. One GEM.")
        self.registry = registry or ComponentRegistry()
        self.processes = processes or DesktopProcesses(self.registry)
        self.selected_component = "zoe"
        self.selected_pid = None
        self.process_rows = {}
        self.timer = None
        self.set_default_size(1400, 860)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, border_width=14)
        self.add(outer)
        title = Gtk.Label(xalign=0)
        title.set_markup(
            "<span size='xx-large' color='#67e8f9'>Zoe OS</span>\n"
            "<span color='#9fb1c8'>One ZOE. One GEM. One inspectable desktop.</span>"
        )
        outer.pack_start(title, False, False, 0)
        panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        panes.set_position(940)
        outer.pack_start(panes, True, True, 0)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panes.pack1(left, True, True)
        filter_label = Gtk.Label(xalign=0, label="Applications · select one to inspect or launch")
        left.pack_start(filter_label, False, False, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left.pack_start(scrolled, True, True, 0)
        self.app_grid = Gtk.FlowBox()
        self.app_grid.set_max_children_per_line(3)
        self.app_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.app_grid.set_homogeneous(True)
        scrolled.add(self.app_grid)
        for component in self.registry.manifest()["components"]:
            button = Gtk.Button()
            label = Gtk.Label(label=f"{component['title']}\n{component['summary']}", xalign=0)
            label.set_line_wrap(True)
            label.set_max_width_chars(30)
            button.add(label)
            button.set_size_request(280, 112)
            button.connect("clicked", self.select_component, component["identifier"])
            self.app_grid.add(button)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9, border_width=6)
        right.set_size_request(430, -1)
        panes.pack2(right, False, True)
        self.details = Gtk.Label(xalign=0)
        self.details.set_line_wrap(True)
        self.details.set_selectable(True)
        right.pack_start(self.details, False, False, 0)
        self.launch_button = Gtk.Button(label="Launch selected application")
        self.launch_button.connect("clicked", self.launch_selected)
        right.pack_start(self.launch_button, False, False, 0)
        inspect_button = Gtk.Button(label="Inspect source and boundaries")
        inspect_button.connect("clicked", self.select_component)
        right.pack_start(inspect_button, False, False, 0)
        record_button = Gtk.Button(label="Record source context")
        record_button.connect("clicked", self.record_source)
        right.pack_start(record_button, False, False, 0)
        for label, kind in (("Export component manifest", "manifest"), ("Export shared knowledge", "knowledge")):
            button = Gtk.Button(label=label)
            button.connect("clicked", self.export_document, kind)
            right.pack_start(button, False, False, 0)
        right.pack_start(Gtk.Separator(), False, False, 4)
        process_label = Gtk.Label(xalign=0, label="Processes started by this desktop")
        right.pack_start(process_label, False, False, 0)
        process_scroll = Gtk.ScrolledWindow()
        process_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        process_scroll.set_size_request(-1, 180)
        right.pack_start(process_scroll, True, True, 0)
        self.process_list = Gtk.ListBox()
        self.process_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.process_list.connect("row-selected", self.select_process)
        process_scroll.add(self.process_list)
        self.stop_button = Gtk.Button(label="Stop selected process")
        self.stop_button.connect("clicked", self.stop_selected)
        right.pack_start(self.stop_button, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        outer.pack_end(self.status, False, False, 0)
        self.select_component()
        self.refresh_processes()
        self.timer = GLib.timeout_add(500, self.refresh_processes)

    def select_component(self, _widget=None, identifier=None):
        identifier = identifier or self.selected_component
        component = self.registry.component(identifier)
        self.selected_component = identifier
        source = self.registry.source(identifier)
        mode = "content library; no process launch" if component.inspect_only else "explicit launch only"
        self.details.set_text(
            f"{component.title}\n\n{component.summary}\n\n"
            f"Source: {source['path']}\nMode: {source['mode']} · {mode}\n"
            f"Upstream: {component.repository}\n"
            "Source presence is not readiness, evidence transfer, or permission."
        )
        self.launch_button.set_sensitive(not component.inspect_only)
        return False

    def launch_selected(self, *_args):
        try:
            record = self.processes.launch(self.selected_component)
            self.status.set_text(f"Started {record['title']} with PID {record['pid']}; readiness is not inferred.")
        except (OSError, RuntimeError, ValueError) as error:
            self.status.set_text(str(error))
        self.refresh_processes()
        return False

    def record_source(self, *_args):
        try:
            observation = self.registry.record_source(self.selected_component)
            self.status.set_text(f"Recorded source observation {observation['id']}; no evidence or permission transferred.")
        except (OSError, RuntimeError, ValueError) as error:
            self.status.set_text(str(error))
        return False

    def select_process(self, _list, row):
        self.selected_pid = getattr(row, "pid", None) if row is not None else None

    def refresh_processes(self):
        self.processes.reap()
        selected = self.selected_pid
        for child in self.process_list.get_children():
            self.process_list.remove(child)
        self.process_rows = {}
        for pid, record in sorted(self.processes.running.items()):
            row = Gtk.ListBoxRow()
            row.pid = pid
            row.add(Gtk.Label(xalign=0, label=f"{record['title']} · PID {pid}"))
            self.process_list.add(row)
            self.process_rows[pid] = row
        self.process_list.show_all()
        if selected in self.process_rows:
            self.process_list.select_row(self.process_rows[selected])
        else:
            self.selected_pid = None
        return True

    def stop_selected(self, *_args):
        if self.selected_pid is None:
            self.status.set_text("Select a desktop-started process first.")
            return False
        try:
            record = self.processes.stop(self.selected_pid)
            self.status.set_text(f"Stopped {record['title']} with status {record['exit_status']}.")
        except (OSError, RuntimeError, ValueError) as error:
            self.status.set_text(str(error))
        self.refresh_processes()
        return False

    def export_document(self, _widget, kind):
        dialog = Gtk.FileChooserDialog(
            title=f"Export {kind}", transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Export", Gtk.ResponseType.OK)
        dialog.set_current_name(f"zoe-{kind}.json")
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                path = Path(dialog.get_filename())
                try:
                    output = self.registry.write_manifest(path) if kind == "manifest" else self.registry.knowledge.save(path)
                    self.status.set_text(f"Exported {output}")
                except (OSError, RuntimeError, ValueError) as error:
                    self.status.set_text(str(error))
        finally:
            dialog.destroy()

    def on_destroy(self, *_args):
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None


def launch_desktop(registry=None):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe OS requires a GTK display; use --output or --list for headless operation")
    window = ZoeDesktopWindow(registry)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def parser():
    result = argparse.ArgumentParser(prog="zoe os", description="One ZOE. One GEM. One inspectable desktop.")
    result.add_argument("--list", action="store_true", help="list applications without launching anything")
    result.add_argument("--output", help="export the unified desktop scene to .svg, .png, or .gem")
    result.add_argument("--format", choices=("svg", "png", "gem"))
    result.add_argument("--width", type=int, default=1400)
    return result


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        registry = ComponentRegistry()
        if arguments.list:
            for component in registry.manifest()["components"]:
                print(f"{component['identifier']:16} {component['title']} · {component['summary']}")
            return 0
        if arguments.output:
            output = Path(arguments.output)
            if output.exists():
                raise FileExistsError(output)
            kind = arguments.format or output.suffix.lower().lstrip(".")
            scene, report = unified_scene(registry)
            check = verify_vdi(scene) if kind == "gem" else verify(scene)
            if not check.passed:
                raise ValueError(check.text())
            if kind == "gem":
                write_metafile(scene, output)
            elif kind == "svg":
                write_svg(scene, output, arguments.width)
            elif kind == "png":
                write_png(scene, output, arguments.width)
            else:
                raise ValueError("desktop output must be svg, png, or gem")
            print(json.dumps({"instrument": "zoe-os", "components": report["entrypoint_count"], "output": str(output), "bytes": output.stat().st_size, "operating_system_claimed": False}, indent=2, sort_keys=True))
            return 0
        launch_desktop(registry)
        return 0
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        print(f"zoe os: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
