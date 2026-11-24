#!/usr/bin/env python3
"""
extract_atoms — parse all 39 NICE career-pathway PDFs into one normalized
atom library. Each T/K/S/A/C code becomes a single entry with the roles
that cite it. The framework's implicit composability (KSAs reused across
roles) becomes explicit.
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PDF_DIR = Path.home()/"Documents"/"dod-cyber-pathways"
OUT = Path.home()/"wardrobe"/"atoms.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Map filename pattern to role ID (e.g. 541, 661)
ROLE_RE = re.compile(r"^(\d{3})[-_]")

# Atom code patterns
TASK_RE  = re.compile(r"\bT\d{4}\b")
KNOW_RE  = re.compile(r"\bK\d{4}\b")
SKILL_RE = re.compile(r"\bS\d{4}\b")
ABIL_RE  = re.compile(r"\bA\d{4}\b")
COMP_RE  = re.compile(r"\bC\d{3}\b")

ANY_CODE_RE = re.compile(r"\b([TKSA]\d{4}|C\d{3})\b")

# Proficiency rung detector
PROF_RE = re.compile(r"^\s*(As Written|Entry|Intermediate|Advanced)\b", re.I)

# Competency family detector (Table 3 has a Competency column, often
# right-aligned. We grab text following a known competency keyword.)
COMPETENCY_FAMILIES = {
    "Information Systems/Network Security",
    "Infrastructure Design",
    "Legal, Government, and Jurisprudence",
    "Risk Management",
    "Vulnerabilities Assessment",
    "Information Assurance",
    "Information Management",
    "Threat Analysis",
    "System Administration",
    "Systems Testing and Evaluation",
    "Computer Network Defense",
    "Computer Languages",
    "Computer Forensics",
    "Business Continuity",
    "Encryption",
    "Identity Management",
}

def role_id(pdf_path: Path) -> str:
    m = ROLE_RE.match(pdf_path.name)
    return m.group(1) if m else "???"

def pdf_to_text(pdf_path: Path) -> str:
    try:
        return subprocess.check_output(
            ["pdftotext", "-layout", "-q", str(pdf_path), "-"],
            text=True, timeout=60,
        )
    except Exception as e:
        print(f"  pdftotext fail on {pdf_path.name}: {e}", file=sys.stderr)
        return ""

def clean_text(s: str) -> str:
    """Collapse whitespace, strip page numbers and table headers."""
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def parse_role_atoms(text: str, role: str):
    """
    Walk the text line by line. Each line starting with a code introduces
    an atom whose statement is the trailing text on that line + any
    continuation lines until the next code-line or section boundary.
    """
    lines = text.splitlines()
    atoms_in_role = []  # list of (code, statement, raw_lines, surrounding_competency)
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = re.match(r"^\s*([TKSA]\d{4}|C\d{3})\b\s*(.*)$", stripped)
        if not m:
            i += 1
            continue
        code = m.group(1)
        first_chunk = m.group(2)
        chunks = [first_chunk] if first_chunk else []
        i += 1
        # Collect continuation lines
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                i += 1
                if i < len(lines) and not lines[i].strip():
                    break  # empty cluster ends a record
                continue
            # If next line is another code, stop
            if re.match(r"^\s*([TKSA]\d{4}|C\d{3})\b", nxt):
                break
            # Table headers stop continuation
            if re.match(r"^(Table \d+|Proficiency|KSA ID|Description|Competency|Task ID|Task Statement|Importance)\b", nxt, re.I):
                break
            if PROF_RE.match(nxt):
                break
            chunks.append(nxt)
            i += 1
        statement = clean_text(" ".join(chunks))
        # Strip trailing importance tag if present
        statement = re.sub(r"\s+(Core|Additional|Foundational to All Work Roles)\.?$", "", statement, flags=re.I)
        # Try to identify the competency family if mentioned in the statement
        comp_family = None
        for fam in COMPETENCY_FAMILIES:
            if fam in statement:
                comp_family = fam
                statement = statement.replace(fam, "").strip(" .")
                break
        # importance hint
        importance = None
        if re.search(r"\bCore\b", stripped): importance = "Core"
        elif re.search(r"\bAdditional\b", stripped): importance = "Additional"
        elif re.search(r"\bFoundational\b", stripped): importance = "Foundational"
        atoms_in_role.append({
            "code": code,
            "text": statement,
            "role": role,
            "competency_family": comp_family,
            "importance": importance,
        })
    return atoms_in_role

def parse_proficiency_ladders(text: str, role: str):
    """
    Find Task Analysis appendix tables. Each has rows like:
       As Written      <task statement>
       Entry           <entry-level behavior>
       Intermediate    <intermediate behavior>
       Advanced        <advanced behavior>
    Returns dict {task_code: {entry,intermediate,advanced,as_written}}
    """
    out = {}
    # Find table headers "Table N. T#### Task Analysis"
    for m in re.finditer(r"Table \d+\.\s*(T\d{4})\s+Task Analysis", text):
        code = m.group(1)
        # Grab the next ~80 lines as the table body
        start = m.end()
        body = text[start:start+5000]
        rungs = {}
        for r in ("As Written", "Entry", "Intermediate", "Advanced"):
            rm = re.search(
                rf"^\s*{r}\b\s+(.+?)(?=^\s*(?:As Written|Entry|Intermediate|Advanced|Table \d+|KSA ID)\b|\Z)",
                body, re.S | re.M | re.I,
            )
            if rm:
                rungs[r.lower().replace(" ", "_")] = clean_text(rm.group(1))
        if rungs:
            out[code] = rungs
    return out

def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    pdfs = [p for p in pdfs if ROLE_RE.match(p.name)]
    print(f"PDFs to parse: {len(pdfs)}")

    # Aggregate by code -> {text, source_roles, type, ...}
    by_code = {}
    proficiency_by_role_task = {}  # (role, task_code) -> rungs

    for pdf in pdfs:
        role = role_id(pdf)
        text = pdf_to_text(pdf)
        if not text:
            continue
        atoms = parse_role_atoms(text, role)
        for a in atoms:
            code = a["code"]
            if code not in by_code:
                by_code[code] = {
                    "code": code,
                    "type": {"T":"task","K":"knowledge","S":"skill","A":"ability","C":"competency"}[code[0]],
                    "text": a["text"],
                    "source_roles": [],
                    "competency_family": a.get("competency_family"),
                    "importance_by_role": {},
                }
            entry = by_code[code]
            if role not in entry["source_roles"]:
                entry["source_roles"].append(role)
            if a.get("importance"):
                entry["importance_by_role"][role] = a["importance"]
            # Prefer the longest text we've seen (most complete extraction)
            if a["text"] and len(a["text"]) > len(entry["text"]):
                entry["text"] = a["text"]
            if a.get("competency_family") and not entry.get("competency_family"):
                entry["competency_family"] = a["competency_family"]

        prof = parse_proficiency_ladders(text, role)
        for tcode, rungs in prof.items():
            proficiency_by_role_task[(role, tcode)] = rungs
        print(f"  {role}  {pdf.name[:60]:<60} {len(atoms):>4} atoms")

    # Bucket atoms by type
    bucketed = defaultdict(list)
    for a in by_code.values():
        bucketed[a["type"]].append(a)

    # Wire proficiency ladders into tasks
    for task in bucketed["task"]:
        proficiency = {}
        for role in task["source_roles"]:
            r = proficiency_by_role_task.get((role, task["code"]))
            if r:
                proficiency[role] = r
        if proficiency:
            task["proficiency_by_role"] = proficiency

    # Sort within each bucket
    for k in bucketed:
        bucketed[k].sort(key=lambda x: x["code"])

    out = {
        "version": "0.1",
        "extracted_at": "2026-06-07",
        "sources": [p.name for p in pdfs],
        "atoms": {
            "tasks":         bucketed["task"],
            "knowledge":     bucketed["knowledge"],
            "skills":        bucketed["skill"],
            "abilities":     bucketed["ability"],
            "competencies":  bucketed["competency"],
        },
        "counts": {k: len(v) for k, v in bucketed.items()},
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT}")
    print(f"  tasks:        {len(bucketed['task'])}")
    print(f"  knowledge:    {len(bucketed['knowledge'])}")
    print(f"  skills:       {len(bucketed['skill'])}")
    print(f"  abilities:    {len(bucketed['ability'])}")
    print(f"  competencies: {len(bucketed['competency'])}")

if __name__ == "__main__":
    main()
