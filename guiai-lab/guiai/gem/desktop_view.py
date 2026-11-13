from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_foreign("cairo")
from gi.repository import GLib, Gtk

from .agent_bridge import AgentBridgeServer
from .agent_terminal import EmbeddedAgentPanel
from .desktop import DesktopProcesses
from .desktop_theme import CADENCE, PALETTE, PHI, SPACE, apply_theme
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .unified import ComponentRegistry, unified_scene
from .vdi import write_metafile


class ZoeDesktopWindow(Gtk.Window):
    def __init__(self, registry=None, processes=None, agent_command=None, agent=False, agent_layout="right"):
        super().__init__(title="Zoe OS · One ZOE. One GEM.")
        self.registry = registry or ComponentRegistry()
        self.processes = processes or DesktopProcesses(self.registry)
        self.selected_component = "zoe"
        self.selected_pid = None
        self.process_rows = {}
        self.process_signature = ()
        self.app_buttons = {}
        self.active_button = None
        self.agent_side = agent_layout if agent_layout in {"left", "right"} else "right"
        self.workspace_ratio = 1 / PHI
        self.timer = None
        apply_theme(self)
        self.set_default_size(1440, 900)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy", self.on_destroy)
        header = Gtk.HeaderBar(show_close_button=True)
        header.set_title("Zoe OS")
        header.set_subtitle("ONE ZOE · ONE GEM · ONE INSPECTABLE DESKTOP")
        self.set_titlebar(header)
        self.layout_selector = Gtk.ComboBoxText()
        self.layout_selector.append("right", "Agent right")
        self.layout_selector.append("left", "Agent left")
        self.layout_selector.set_active_id(self.agent_side)
        self.layout_selector.connect("changed", self.set_agent_side)
        self.layout_selector.set_no_show_all(True)
        header.pack_end(self.layout_selector)
        self.details_toggle = Gtk.ToggleButton(label="Details")
        self.details_toggle.set_active(True)
        self.details_toggle.get_style_context().add_class("zoe-action")
        self.details_toggle.connect("toggled", self.toggle_details)
        header.pack_end(self.details_toggle)
        self.agent_toggle = Gtk.ToggleButton(label="AI Agent")
        self.agent_toggle.get_style_context().add_class("zoe-action")
        self.agent_toggle.connect("toggled", self.toggle_agent)
        header.pack_end(self.agent_toggle)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE[2], border_width=SPACE[3])
        self.add(outer)
        title = Gtk.Label(xalign=0)
        title.set_markup(
            "<span size='xx-large' color='#67e8f9'>One ZOE. One GEM.</span>\n"
            "<span color='#9fb1c8'>Explicit applications · shared evidence · deterministic local instruments</span>"
        )
        outer.pack_start(title, False, False, 0)
        self.panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        self.panes.set_position(round(1440 / PHI))
        self.workspace_panes = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, wide_handle=True)
        self.workspace_panes.pack1(self.panes, True, True)
        self.workspace_panes.connect("notify::position", self.remember_position)
        outer.pack_start(self.workspace_panes, True, True, 0)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE[2])
        self.panes.pack1(left, True, True)
        filter_label = Gtk.Label(xalign=0, label="Applications · mathematical order, explicit action")
        filter_label.get_style_context().add_class("zoe-muted")
        left.pack_start(filter_label, False, False, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        left.pack_start(scrolled, True, True, 0)
        self.app_grid = Gtk.FlowBox()
        self.app_grid.set_max_children_per_line(3)
        self.app_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.app_grid.set_homogeneous(True)
        self.app_grid.set_column_spacing(SPACE[1])
        self.app_grid.set_row_spacing(SPACE[1])
        scrolled.add(self.app_grid)
        for index, component in enumerate(self.registry.manifest()["components"]):
            button = Gtk.Button()
            button.get_style_context().add_class("zoe-card")
            color = PALETTE[index % len(PALETTE)]
            title_text = GLib.markup_escape_text(component["title"])
            summary = GLib.markup_escape_text(component["summary"])
            label = Gtk.Label(xalign=0)
            label.set_markup(
                f"<span color='{color}' size='large'>{index + 1:02d} · {title_text}</span>\n"
                f"<span color='#d8e2ee' size='small'>{summary}</span>"
            )
            label.set_line_wrap(True)
            label.set_max_width_chars(31)
            button.add(label)
            button.set_size_request(278, 112)
            button.connect("clicked", self.select_component, component["identifier"])
            self.app_buttons[component["identifier"]] = button
            self.app_grid.add(button)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=SPACE[2], border_width=SPACE[1])
        right.set_size_request(430, -1)
        self.details_pane = right
        self.details_position = round(1440 / PHI)
        self.panes.pack2(right, False, True)
        self.details = Gtk.Label(xalign=0)
        self.details.set_line_wrap(True)
        self.details.set_selectable(True)
        self.details.get_style_context().add_class("zoe-panel")
        right.pack_start(self.details, False, False, 0)
        self.launch_button = Gtk.Button(label="Launch selected application")
        self.launch_button.get_style_context().add_class("zoe-action")
        self.launch_button.connect("clicked", self.launch_selected)
        right.pack_start(self.launch_button, False, False, 0)
        for label, callback in (
            ("Inspect source and boundaries", self.select_component),
            ("Record source context", self.record_source),
        ):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("zoe-action")
            button.connect("clicked", callback)
            right.pack_start(button, False, False, 0)
        for label, kind in (("Export component manifest", "manifest"), ("Export shared knowledge", "knowledge")):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("zoe-action")
            button.connect("clicked", self.export_document, kind)
            right.pack_start(button, False, False, 0)
        right.pack_start(Gtk.Separator(), False, False, SPACE[0])
        process_label = Gtk.Label(xalign=0, label="Processes started by this desktop")
        process_label.get_style_context().add_class("zoe-muted")
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
        self.stop_button.get_style_context().add_class("zoe-action")
        self.stop_button.connect("clicked", self.stop_selected)
        right.pack_start(self.stop_button, False, False, 0)
        command = agent_command or os.environ.get("ZOE_AGENT_COMMAND", "kimi")
        self.agent_bridge = AgentBridgeServer(self)
        self.agent_panel = EmbeddedAgentPanel(command, status_changed=self.agent_status, bridge=self.agent_bridge)
        self.agent_panel.set_size_request(420, 360)
        self.agent_panel.set_no_show_all(True)
        self.workspace_panes.pack2(self.agent_panel, True, True)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        self.status.get_style_context().add_class("zoe-status")
        outer.pack_end(self.status, False, False, 0)
        self.select_component()
        self.refresh_processes()
        self.timer = GLib.timeout_add(CADENCE[3], self.refresh_processes)
        if agent:
            self.agent_toggle.set_active(True)
            self.agent_panel.start()

    def toggle_details(self, *_args):
        if self.details_toggle.get_active():
            self.details_pane.set_no_show_all(False)
            self.details_pane.show_all()
            extent = max(1, self.panes.get_allocated_width())
            self.panes.set_position(min(self.details_position, extent))
        else:
            self.details_position = max(1, self.panes.get_position())
            self.details_pane.set_no_show_all(True)
            self.details_pane.hide()
            self.panes.set_position(max(1, self.panes.get_allocated_width()))
        return False

    def set_agent_side(self, *_args):
        self.agent_side = self.layout_selector.get_active_id() or "right"
        self.apply_layout()
        return False

    def remember_position(self, *_args):
        if not self.agent_toggle.get_active():
            return
        extent = self.workspace_panes.get_allocated_width()
        position = self.workspace_panes.get_position()
        if extent > 1 and position > 0:
            ratio = position / extent
            if self.agent_side == "left":
                ratio = 1 - ratio
            self.workspace_ratio = min(0.8, max(0.2, ratio))

    def apply_layout(self):
        extent = self.workspace_panes.get_allocated_width()
        if extent <= 1:
            extent = max(1, self.get_allocated_width())
        if extent <= 1:
            extent = 1440
        self.workspace_panes.remove(self.panes)
        self.workspace_panes.remove(self.agent_panel)
        if self.agent_side == "left":
            first, second = self.agent_panel, self.panes
            position = round(extent * (1 - self.workspace_ratio))
        else:
            first, second = self.panes, self.agent_panel
            position = round(extent * self.workspace_ratio)
        self.workspace_panes.pack1(first, True, True)
        self.workspace_panes.pack2(second, True, True)
        self.workspace_panes.set_position(position)

    def toggle_agent(self, *_args):
        if self.agent_toggle.get_active():
            self.layout_selector.set_no_show_all(False)
            self.layout_selector.show()
            self.agent_panel.set_no_show_all(False)
            self.apply_layout()
            self.workspace_panes.show_all()
            self.agent_panel.command_entry.grab_focus()
        else:
            self.layout_selector.hide()
            self.agent_panel.hide()
        return False

    def agent_status(self, text):
        if hasattr(self, "status"):
            self.status.set_text(text)

    def select_component(self, _widget=None, identifier=None):
        identifier = identifier or self.selected_component
        component = self.registry.component(identifier)
        self.selected_component = identifier
        if self.active_button is not None:
            self.active_button.get_style_context().remove_class("zoe-selected")
        self.active_button = self.app_buttons[identifier]
        self.active_button.get_style_context().add_class("zoe-selected")
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
        signature = tuple(sorted(self.processes.running))
        if signature == self.process_signature:
            return True
        self.process_signature = signature
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
        dialog = Gtk.FileChooserDialog(title=f"Export {kind}", transient_for=self, action=Gtk.FileChooserAction.SAVE)
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

    def agent_action(self, document):
        try:
            if not isinstance(document, dict) or not isinstance(document.get("action"), str):
                raise ValueError("agent action must be an object with an action string")
            action = document["action"]
            if action == "list":
                if set(document) != {"action"}:
                    raise ValueError("list accepts no additional fields")
                return {
                    "ok": True,
                    "selected": self.selected_component,
                    "components": [
                        {"identifier": row["identifier"], "title": row["title"], "summary": row["summary"]}
                        for row in self.registry.manifest()["components"]
                    ],
                    "processes": [
                        {"title": record["title"], "pid": pid}
                        for pid, record in sorted(self.processes.running.items())
                    ],
                }
            if action in {"select", "launch"}:
                allowed = {"action", "identifier"} | ({"arguments"} if action == "launch" else set())
                if set(document) - allowed or not isinstance(document.get("identifier"), str):
                    raise ValueError(f"{action} requires only an identifier and optional component arguments")
                identifier = document["identifier"]
                self.registry.component(identifier)
                arguments = document.get("arguments", [])
                if not isinstance(arguments, list) or len(arguments) > 128 or any(not isinstance(value, str) or not value or len(value) > 4096 for value in arguments):
                    raise ValueError("component arguments must contain at most 128 nonempty strings of at most 4096 characters")
                self.select_component(identifier=identifier)
                if action == "select":
                    return {"ok": True, "selected": identifier}
                record = self.processes.launch(identifier, arguments)
                self.refresh_processes()
                return {"ok": True, "selected": identifier, "pid": record["pid"], "readiness_verified": False}
            if action == "stop":
                if set(document) != {"action", "pid"} or isinstance(document.get("pid"), bool) or not isinstance(document.get("pid"), int):
                    raise ValueError("stop requires only an integer pid")
                record = self.processes.stop(document["pid"])
                self.refresh_processes()
                return {"ok": True, "pid": document["pid"], "exit_status": record["exit_status"]}
            if action == "layout":
                if set(document) != {"action", "side"} or document.get("side") not in {"left", "right"}:
                    raise ValueError("layout requires side left or right")
                self.layout_selector.set_active_id(document["side"])
                return {"ok": True, "side": self.agent_side}
            if action == "details":
                if set(document) != {"action", "visible"} or not isinstance(document.get("visible"), bool):
                    raise ValueError("details requires a boolean visible field")
                self.details_toggle.set_active(document["visible"])
                return {"ok": True, "visible": self.details_toggle.get_active()}
            if action == "export":
                if set(document) != {"action", "kind", "path"} or document.get("kind") not in {"manifest", "knowledge"}:
                    raise ValueError("export requires kind manifest or knowledge and a filename")
                filename = document.get("path")
                if not isinstance(filename, str) or not filename.endswith(".json") or Path(filename).name != filename:
                    raise ValueError("export path must be a JSON filename without directories")
                output = Path.cwd() / filename
                if output.exists():
                    raise FileExistsError(output)
                output = self.registry.write_manifest(output) if document["kind"] == "manifest" else self.registry.knowledge.save(output)
                return {"ok": True, "output": str(output), "bytes": output.stat().st_size}
            raise ValueError(f"unsupported agent action: {action}")
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
            return {"ok": False, "error": str(error)}

    def on_destroy(self, *_args):
        self.agent_panel.close()
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None


def launch_desktop(registry=None, agent_command=None, agent=False, agent_layout="right"):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe OS requires a GTK display; use --output or --list for headless operation")
    window = ZoeDesktopWindow(registry, agent_command=agent_command, agent=agent, agent_layout=agent_layout)
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
    result.add_argument("--agent", action="store_true", help="start the embedded interactive agent explicitly")
    result.add_argument("--agent-command", help="interactive local agent command used with --agent; the panel alone starts no process")
    result.add_argument("--agent-layout", choices=("left", "right"), default="right", help="place the agent beside the workspace with a draggable divider")
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
        launch_desktop(registry, agent_command=arguments.agent_command, agent=arguments.agent, agent_layout=arguments.agent_layout)
        return 0
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        print(f"zoe os: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
