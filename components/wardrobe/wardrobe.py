#!/usr/bin/env python3
"""
wardrobe — pick atoms from the NICE Framework library and assemble custom
role outfits. Every T/K/S/A/C atom is individually selectable. An outfit
is a saved YAML/JSON listing the atoms you wear and the proficiency rung
you wear them at.

Subcommands:
  browse     - list atoms (filter by type, text, role, competency)
  show       - detail one atom (text + which roles cite it + proficiency)
  try-on     - add an atom to the current outfit
  take-off   - remove an atom from the current outfit
  outfit     - show the current outfit
  save       - save the current outfit by name
  load       - load a saved outfit
  outfits    - list saved outfits
  render     - emit the outfit as prompt / markdown / json / checklist
  reset      - clear the current outfit

Storage: ~/wardrobe/outfits/<name>.json ; current outfit at ~/wardrobe/current.json
"""
import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path.home()/"wardrobe"
ATOMS_PATH = ROOT/"atoms.json"
OUTFITS_DIR = ROOT/"outfits"
CURRENT_PATH = ROOT/"current.json"
OUTFITS_DIR.mkdir(parents=True, exist_ok=True)

TYPE_LABEL = {"task":"T","knowledge":"K","skill":"S","ability":"A","competency":"C"}
LABEL_TYPE = {v:k for k,v in TYPE_LABEL.items()}

# ----- DB load -----
def load_atoms():
    if not ATOMS_PATH.exists():
        sys.exit(f"missing {ATOMS_PATH} — run extract_atoms.py first")
    return json.loads(ATOMS_PATH.read_text())

def index_by_code(atoms_db):
    idx = {}
    for bucket in atoms_db["atoms"].values():
        for a in bucket:
            idx[a["code"]] = a
    return idx

# ----- Outfit IO -----
def load_outfit(path):
    if not path.exists():
        return {"name": None, "items": [], "notes": ""}
    return json.loads(path.read_text())

def save_outfit(outfit, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(outfit, indent=2))

def current_outfit():
    return load_outfit(CURRENT_PATH)

def save_current(outfit):
    save_outfit(outfit, CURRENT_PATH)

# ----- Commands -----
def cmd_browse(args, db, idx):
    bucket_name = None
    if args.type:
        bucket_name = {"T":"tasks","K":"knowledge","S":"skills","A":"abilities","C":"competencies"}.get(args.type.upper())
    buckets = [bucket_name] if bucket_name else ["tasks","knowledge","skills","abilities","competencies"]
    needle = (args.text or "").lower()
    role = args.role
    fam = (args.competency or "").lower()
    n_shown = 0
    for b in buckets:
        for a in db["atoms"].get(b, []):
            if needle and needle not in a["text"].lower():
                continue
            if role and role not in a.get("source_roles", []):
                continue
            if fam and (a.get("competency_family") or "").lower() != fam:
                continue
            extras = []
            if a.get("competency_family"):
                extras.append(f"fam={a['competency_family'][:25]}")
            extras.append(f"roles={len(a.get('source_roles',[]))}")
            print(f"  {a['code']:<7} [{a['type'][:4]}]  {a['text'][:80]:<80}  {' '.join(extras)}")
            n_shown += 1
            if n_shown >= args.limit:
                print(f"  ... (limit {args.limit}, more matches; raise with -n)")
                return
    print(f"\n{n_shown} atoms")

def cmd_show(args, db, idx):
    a = idx.get(args.code.upper())
    if not a:
        sys.exit(f"no atom with code {args.code}")
    print(f"{a['code']}  [{a['type']}]")
    print(f"  {a['text']}\n")
    print(f"  source roles ({len(a.get('source_roles',[]))}): {', '.join(a.get('source_roles',[]))}")
    if a.get("competency_family"):
        print(f"  competency family: {a['competency_family']}")
    if a.get("importance_by_role"):
        print(f"  importance by role:")
        for r, imp in a["importance_by_role"].items():
            print(f"    {r}: {imp}")
    if a.get("proficiency_by_role"):
        print(f"  proficiency ladders:")
        for r, rungs in a["proficiency_by_role"].items():
            print(f"    [{r}]")
            for rung, txt in rungs.items():
                print(f"      {rung}: {txt[:160]}")

def cmd_try_on(args, db, idx):
    out = current_outfit()
    for code in args.codes:
        code = code.upper()
        a = idx.get(code)
        if not a:
            print(f"  ! no atom {code}")
            continue
        item = {"code": code, "proficiency": args.proficiency, "note": args.note or ""}
        # Replace if already present
        out["items"] = [i for i in out["items"] if i["code"] != code]
        out["items"].append(item)
        print(f"  + {code}  [{a['type']}]  {a['text'][:80]}{'  ('+args.proficiency+')' if args.proficiency else ''}")
    save_current(out)
    print(f"\noutfit now has {len(out['items'])} pieces")

def cmd_take_off(args, db, idx):
    out = current_outfit()
    before = len(out["items"])
    codes = {c.upper() for c in args.codes}
    out["items"] = [i for i in out["items"] if i["code"] not in codes]
    save_current(out)
    print(f"  removed {before - len(out['items'])} piece(s); outfit now has {len(out['items'])}")

def cmd_outfit(args, db, idx):
    out = current_outfit()
    if not out["items"]:
        print("(empty outfit)")
        return
    name = out.get("name")
    suffix = f" — saved as {name}" if name else ""
    print(f"current outfit{suffix}")
    if out.get("notes"): print(f"  notes: {out['notes']}")
    for item in out["items"]:
        a = idx.get(item["code"]) or {}
        prof = item.get("proficiency") or ""
        prof_tag = f" [{prof}]" if prof else ""
        note = f"  // {item['note']}" if item.get("note") else ""
        print(f"  {item['code']:<7} [{a.get('type','?')[:4]}]{prof_tag}  {a.get('text','')[:80]}{note}")
    print(f"\n{len(out['items'])} pieces  (cross-role: {sorted({r for i in out['items'] for r in (idx.get(i['code']) or {}).get('source_roles',[])})})")

def cmd_save(args, db, idx):
    out = current_outfit()
    name = args.name
    out["name"] = name
    if args.notes:
        out["notes"] = args.notes
    p = OUTFITS_DIR / f"{name}.json"
    save_outfit(out, p)
    save_current(out)  # also update current with the name
    print(f"  saved outfit '{name}' -> {p}")

def cmd_load(args, db, idx):
    p = OUTFITS_DIR / f"{args.name}.json"
    if not p.exists():
        sys.exit(f"no outfit named {args.name}")
    out = load_outfit(p)
    save_current(out)
    print(f"  loaded '{args.name}' ({len(out['items'])} pieces)")

def cmd_outfits(args, db, idx):
    files = sorted(OUTFITS_DIR.glob("*.json"))
    if not files:
        print("(no saved outfits)")
        return
    for f in files:
        try:
            o = json.loads(f.read_text())
            print(f"  {f.stem:<25}  {len(o.get('items',[]))} pieces  {o.get('notes','')[:60]}")
        except Exception as e:
            print(f"  {f.stem} (parse fail: {e})")

def cmd_reset(args, db, idx):
    save_current({"name": None, "items": [], "notes": ""})
    print("  outfit cleared")

# ---- Renderers ----
def render_prompt(out, idx):
    """LLM system-prompt-style rendering."""
    lines = ["# Active Role Posture",
             "",
             "You are operating with the following posture, assembled as a custom",
             "role from the NICE Cybersecurity Workforce Framework. Lean on each",
             "piece as a thinking scaffold for the work in front of you."]
    if out.get("notes"):
        lines += ["", f"**Notes:** {out['notes']}"]
    by_type = {}
    for item in out["items"]:
        a = idx.get(item["code"]) or {}
        by_type.setdefault(a.get("type","?"), []).append((item, a))
    type_order = ["task","competency","knowledge","skill","ability"]
    type_heading = {"task":"## Tasks (what you do)",
                    "competency":"## Competencies (KSA bundles)",
                    "knowledge":"## Knowledge (what you know)",
                    "skill":"## Skills (what you can do)",
                    "ability":"## Abilities (what you can judge)"}
    for t in type_order:
        if t not in by_type: continue
        lines += ["", type_heading[t]]
        for item, a in by_type[t]:
            prof = item.get("proficiency")
            prof_tag = f"  _(at {prof} level)_" if prof else ""
            lines.append(f"- **{item['code']}** — {a.get('text','')}{prof_tag}")
            if item.get("note"):
                lines.append(f"  - _{item['note']}_")
            # If task with proficiency rung, surface the behavior text
            if t == "task" and prof and a.get("proficiency_by_role"):
                for role, rungs in a["proficiency_by_role"].items():
                    rung = rungs.get(prof.lower())
                    if rung:
                        lines.append(f"  - _{role}/{prof}:_ {rung[:200]}")
                        break
    lines += ["",
              "_Pieces from {} source role(s): {}_".format(
                  len({r for item in out['items'] for r in (idx.get(item['code']) or {}).get('source_roles',[])}),
                  ', '.join(sorted({r for item in out['items'] for r in (idx.get(item['code']) or {}).get('source_roles',[])}))
              )]
    return "\n".join(lines)

def render_markdown(out, idx):
    """Human-readable role spec."""
    return render_prompt(out, idx)  # same template for now

def render_checklist(out, idx):
    """A checkable to-do for the human wearing the outfit."""
    name = out.get("name")
    head = f"# Outfit checklist: {name}" if name else "# Outfit checklist"
    lines = [head, ""]
    for item in out["items"]:
        a = idx.get(item["code"]) or {}
        prof = f" [{item['proficiency']}]" if item.get("proficiency") else ""
        lines.append(f"- [ ] {item['code']}{prof} — {a.get('text','')[:120]}")
    return "\n".join(lines)

def render_json(out, idx):
    """Full JSON serialization, including resolved atom text."""
    resolved = {"name": out.get("name"), "notes": out.get("notes"), "items": []}
    for item in out["items"]:
        a = idx.get(item["code"]) or {}
        resolved["items"].append({
            "code": item["code"],
            "type": a.get("type"),
            "text": a.get("text"),
            "proficiency": item.get("proficiency"),
            "note": item.get("note"),
            "source_roles": a.get("source_roles", []),
            "competency_family": a.get("competency_family"),
        })
    return json.dumps(resolved, indent=2)

def cmd_render(args, db, idx):
    out = current_outfit()
    if not out["items"]:
        sys.exit("(empty outfit; nothing to render)")
    if args.as_ == "prompt":     print(render_prompt(out, idx))
    elif args.as_ == "markdown": print(render_markdown(out, idx))
    elif args.as_ == "checklist": print(render_checklist(out, idx))
    elif args.as_ == "json":     print(render_json(out, idx))
    else:
        sys.exit(f"unknown render mode {args.as_}")

# ---- main ----
def main():
    p = argparse.ArgumentParser(prog="wardrobe")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("browse", help="list atoms (filterable)")
    s.add_argument("--type", help="T/K/S/A/C — restrict to one atom type")
    s.add_argument("--text", help="case-insensitive substring filter on the atom text")
    s.add_argument("--role", help="restrict to atoms cited by this role id (e.g. 541)")
    s.add_argument("--competency", help="restrict to a competency family name")
    s.add_argument("-n", "--limit", type=int, default=40)
    s.set_defaults(fn=cmd_browse)

    s = sub.add_parser("show", help="detail one atom")
    s.add_argument("code")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("try-on", help="add atom(s) to the current outfit")
    s.add_argument("codes", nargs="+")
    s.add_argument("--proficiency", choices=["Entry","Intermediate","Advanced"],
                   help="proficiency rung (tasks only)")
    s.add_argument("--note", help="freeform note on why this piece is in the outfit")
    s.set_defaults(fn=cmd_try_on)

    s = sub.add_parser("take-off", help="remove atom(s) from the current outfit")
    s.add_argument("codes", nargs="+")
    s.set_defaults(fn=cmd_take_off)

    s = sub.add_parser("outfit", help="show the current outfit")
    s.set_defaults(fn=cmd_outfit)

    s = sub.add_parser("save", help="save the current outfit by name")
    s.add_argument("name")
    s.add_argument("--notes", help="freeform notes describing the outfit")
    s.set_defaults(fn=cmd_save)

    s = sub.add_parser("load", help="load a saved outfit as the current one")
    s.add_argument("name")
    s.set_defaults(fn=cmd_load)

    s = sub.add_parser("outfits", help="list saved outfits")
    s.set_defaults(fn=cmd_outfits)

    s = sub.add_parser("reset", help="clear the current outfit")
    s.set_defaults(fn=cmd_reset)

    s = sub.add_parser("render", help="emit the outfit as prompt/markdown/checklist/json")
    s.add_argument("--as", dest="as_", default="prompt",
                   choices=["prompt","markdown","checklist","json"])
    s.set_defaults(fn=cmd_render)

    args = p.parse_args()
    db = load_atoms()
    idx = index_by_code(db)
    args.fn(args, db, idx)

if __name__ == "__main__":
    main()
