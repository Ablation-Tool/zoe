"""TOS GEM: native GTK3 workbench for github-tos-audit.

The deterministic scanner produces findings. The workbench verifies each
finding's clause quote against local GitHub policy documents and shows the
evidence side by side, so agent interpretations can be checked against source.
"""

import json
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from . import model, policies


class TosGemWindow(Gtk.Window):
    def __init__(self, repo: Path, agent_command: str = "auto", workspace: str = ""):
        super().__init__(title=f"TOS GEM: {repo}")
        self.repo = repo
        self.findings = []
        self.report = {}
        self.set_default_size(1280, 800)

        icon = Path(__file__).resolve().parent.parent / "assets" / "gem3ico.png"
        if icon.exists():
            self.set_icon_from_file(str(icon))
        self.set_wmclass("tos-gem", "TOS GEM")

        header = Gtk.HeaderBar(show_close_button=True)
        header.set_title("")
        self.set_titlebar(header)

        self.audit_button = Gtk.Button(label="Run Audit")
        self.audit_button.connect("clicked", lambda *_: self.run_audit())
        header.pack_start(self.audit_button)

        self.fetch_button = Gtk.Button(label="Fetch Policies")
        self.fetch_button.connect("clicked", lambda *_: self.fetch_policies())
        header.pack_start(self.fetch_button)

        self.export_button = Gtk.Button(label="Export Report")
        self.export_button.connect("clicked", lambda *_: self.export_report())
        header.pack_end(self.export_button)

        self.status = Gtk.Label(label="Ready", xalign=0)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add(outer)

        self.pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        outer.pack_start(self.pane, True, True, 0)
        outer.pack_start(self.status, False, False, 4)

        self.pane.pack1(self.build_lab(), False, False)
        self.pane.pack2(self.build_details(), True, False)
        self.pane.set_position(420)

        if agent_command != "none":
            from . import agent
            command = agent.detect_agent() if agent_command == "auto" else agent_command
            terminal = agent.build_terminal(repo, command, workspace)
            if terminal is None:
                terminal = Gtk.Label(label="VTE 2.91 unavailable: no embedded terminal.")
            split = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
            outer.remove(self.pane)
            outer.remove(self.status)
            split.pack1(self.pane, True, False)
            split.pack2(terminal, False, False)
            split.set_position(520)
            outer.pack_start(split, True, True, 0)
            outer.pack_start(self.status, False, False, 4)

        self.refresh_policies_view()

    def build_lab(self):
        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.LEFT)

        self.store = Gtk.TreeStore(str, int)
        self.tree = Gtk.TreeView(model=self.store)
        column = Gtk.TreeViewColumn("Findings", Gtk.CellRendererText(), text=0)
        self.tree.append_column(column)
        self.tree.set_headers_visible(False)
        self.tree.get_selection().connect("changed", self.on_select)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        notebook.append_page(scroll, Gtk.Label(label="Audit"))

        self.policy_store = Gtk.ListStore(str, str, str)
        policy_tree = Gtk.TreeView(model=self.policy_store)
        for i, title in enumerate(("Document", "Retrieved", "Source")):
            policy_tree.append_column(
                Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i))
        scroll = Gtk.ScrolledWindow()
        scroll.add(policy_tree)
        notebook.append_page(scroll, Gtk.Label(label="Policies"))
        return notebook

    def build_details(self):
        self.details = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD)
        self.details.set_left_margin(12)
        self.details.set_right_margin(12)
        self.details.set_top_margin(12)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.details)
        return scroll

    def set_status(self, text):
        self.status.set_text(text)

    def show_text(self, text):
        self.details.get_buffer().set_text(text)

    def run_audit(self):
        self.audit_button.set_sensitive(False)
        self.set_status("Running deterministic audit...")

        def work():
            try:
                report = model.run_audit(self.repo)
                findings = model.verified_findings(report)
                GLib.idle_add(self.audit_done, report, findings, None)
            except Exception as exc:
                GLib.idle_add(self.audit_done, {}, [], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def audit_done(self, report, findings, error):
        self.audit_button.set_sensitive(True)
        if error:
            self.set_status(f"Audit failed: {error}")
            return False
        self.report = report
        self.findings = findings
        self.store.clear()
        groups = {}
        suppressed = []
        for index, finding in enumerate(findings):
            if finding.get("suppress_reason"):
                suppressed.append((index, finding))
            else:
                groups.setdefault(finding["category"], []).append((index, finding))
        for category in sorted(groups):
            parent = self.store.append(None, [f"{category} ({len(groups[category])})", -1])
            for index, finding in groups[category]:
                label = self.finding_label(finding)
                self.store.append(parent, [label, index])
        if suppressed:
            parent = self.store.append(None, [f"suppressed ({len(suppressed)})", -1])
            for index, finding in suppressed:
                self.store.append(parent, [self.finding_label(finding), index])
        self.tree.expand_all()
        summary = report.get("summary", {})
        counts = summary.get("findings", {})
        self.set_status(
            f"Audit complete: {counts or 'no findings'}  "
            f"suppressed: {summary.get('suppressed', 0)}  "
            f"files scanned: {summary.get('files_scanned', 0)}"
        )
        return False

    @staticmethod
    def finding_label(finding):
        location = finding.get("file", "")
        if finding.get("line"):
            location += f":{finding['line']}"
        check = finding.get("policy_check", "")
        marker = {"verified": " [doc verified]", "mismatch": " [DOC MISMATCH]"}.get(check, "")
        return f"[{finding['severity']}] {finding['description']}  {location}{marker}"

    def on_select(self, selection):
        _, iterator = selection.get_selected()
        if iterator is None:
            return
        index = self.store[iterator][1]
        if index < 0:
            return
        self.show_text(self.finding_details(self.findings[index]))

    def finding_details(self, finding):
        lines = [
            f"{finding['severity']}  {finding['description']}",
            f"Status: {finding.get('verify_status', '')}",
            "",
        ]
        if finding.get("file"):
            location = finding["file"]
            if finding.get("line"):
                location += f":{finding['line']}"
            lines += [f"Repository location: {location}",
                      f"Full path: {self.repo / finding['file']}", ""]
        if finding.get("match"):
            lines += [f"Matched line:", finding["match"], ""]
        lines += [
            "GitHub policy clause",
            f"  {finding.get('clause_section', '')}",
            "",
            f"  \"{finding.get('clause_quote', '')}\"",
            "",
        ]
        if finding.get("clause_note"):
            lines += [f"Note: {finding['clause_note']}", ""]
        lines += [f"Clause URL: {finding.get('clause_url', '')}", ""]
        check = finding.get("policy_check", "")
        if check == "verified":
            lines += [
                f"LOCAL POLICY CHECK: VERIFIED against {finding.get('policy_document')}",
                f"Document retrieved: {finding.get('policy_retrieved')}",
                "",
                "Policy excerpt around the clause:",
                finding.get("policy_excerpt", ""),
            ]
        elif check == "mismatch":
            lines += [
                "LOCAL POLICY CHECK: MISMATCH. The clause quote was not found in the",
                "local policy text. The policy may have changed, or the clause registry",
                "may be stale. Run Fetch Policies and re-audit before trusting this finding.",
                "",
                finding.get("policy_excerpt", ""),
            ]
        elif check == "not-applicable":
            lines += ["Local policy check: not applicable (OPSEC finding, no ToS clause)."]
        else:
            lines += [f"Local policy check: unavailable ({finding.get('policy_error', '')})."]
        if finding.get("suppress_reason"):
            lines += ["", f"SUPPRESSED. Reason: {finding['suppress_reason']}"]
        return "\n".join(lines)

    def refresh_policies_view(self):
        self.policy_store.clear()
        directory = policies.policy_dir()
        meta = policies.load_meta(directory)
        source = "cache" if directory == policies.CACHE_DIR else "bundled snapshot"
        for key, info in policies.POLICIES.items():
            entry = meta.get(key, {})
            self.policy_store.append([
                info["title"], entry.get("retrieved", "not fetched"), source,
            ])

    def fetch_policies(self):
        self.fetch_button.set_sensitive(False)
        self.set_status("Fetching GitHub policy documents...")

        def work():
            results = policies.fetch_policies()
            GLib.idle_add(self.fetch_done, results)

        threading.Thread(target=work, daemon=True).start()

    def fetch_done(self, results):
        self.fetch_button.set_sensitive(True)
        self.refresh_policies_view()
        parts = [f"{r['key']}: {r['status']}" for r in results]
        self.set_status("Policy fetch: " + ", ".join(parts))
        errors = [r for r in results if r["status"] == "error"]
        if errors:
            self.show_text("\n".join(f"{r['title']}: {r['error']}" for r in errors))
        return False

    def export_report(self):
        if not self.report:
            self.set_status("Run an audit first.")
            return
        dialog = Gtk.FileChooserDialog(
            title="Export report", parent=self, action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Export", Gtk.ResponseType.OK)
        dialog.set_current_name("tos-audit-report.json")
        if dialog.run() == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())
            payload = dict(self.report)
            payload["verified_findings"] = self.findings
            path.write_text(json.dumps(payload, indent=2))
            self.set_status(f"Report exported: {path}")
        dialog.destroy()


def run(repo: Path, agent_command: str = "auto", workspace: str = ""):
    window = TosGemWindow(repo, agent_command, workspace)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
