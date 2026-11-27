"""Offline portfolio search, project matching, and resume generation."""

import argparse
import json
import re
import sys
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse


STOPWORDS = set("a an and are as at be for from help how i in is it me my of on or our the to we with you your".split())
ALIASES = {
    "agents": "agent", "apis": "api", "binaries": "binary",
    "llms": "llm", "vulnerabilities": "vulnerability", "permissions": "permission",
    "pentest": "penetration", "pentesting": "penetration", "auth": "authentication",
    "databases": "database", "tools": "tool", "models": "model",
}


def tokens(text):
    return {ALIASES.get(t, t) for t in re.findall(r"[a-z0-9]+", text.lower())} - STOPWORDS


def validate(data):
    """Validate the data contract; never infer verification from a URL."""
    errors = []
    if not isinstance(data, dict):
        return ["Portfolio must be a JSON object."]
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1.")
    for section, fields in {
        "person": ("name", "headline", "summary", "email", "website", "background"),
        "provenance": ("source", "status", "note"),
    }.items():
        obj = data.get(section)
        if not isinstance(obj, dict):
            errors.append(f"{section} must be an object.")
            continue
        for field in fields:
            if not isinstance(obj.get(field), str) or not obj[field].strip():
                errors.append(f"{section}.{field} must be a nonempty string.")
    person = data.get("person", {})
    if isinstance(person, dict):
        for field in ("languages", "services"):
            if not string_list(person.get(field)):
                errors.append(f"person.{field} must be a nonempty list of strings.")
    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        return errors + ["projects must be a nonempty array."]
    seen = set()
    for index, project in enumerate(projects):
        label = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{label} must be an object.")
            continue
        for field in ("id", "name", "category", "summary", "problem", "url", "evidence_status"):
            if not isinstance(project.get(field), str) or not project[field].strip():
                errors.append(f"{label}.{field} must be a nonempty string.")
        pid = project.get("id")
        if isinstance(pid, str):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", pid):
                errors.append(f"{label}.id must be a lowercase slug.")
            if pid in seen:
                errors.append(f"Duplicate project id: {pid}")
            seen.add(pid)
        for field in ("tags", "methods", "languages"):
            if not string_list(project.get(field)):
                errors.append(f"{label}.{field} must be a nonempty list of strings.")
        url = project.get("url", "")
        if isinstance(url, str):
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}.url must be an absolute HTTPS URL.")
        if project.get("evidence_status") not in ("owner-reported", "verified"):
            errors.append(f"{label}.evidence_status must be owner-reported or verified.")
        if project.get("evidence_status") == "verified":
            verification = project.get("verification", {})
            if not isinstance(verification, dict) or not all(
                isinstance(verification.get(key), str) and verification[key].strip()
                for key in ("source", "checked_on", "notes")
            ):
                errors.append(f"{label}: verified entries require source, checked_on, and notes.")
    return errors


def string_list(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def load(path=None):
    source = Path(path) if path else files("fieldwork").joinpath("data/portfolio.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        raise ValueError("\n".join(errors))
    return data


def rank(projects, query):
    """Explainable lexical retrieval, not an expertise or suitability score."""
    wanted = tokens(query)
    results = []
    for project in projects:
        weighted = [
            (4, " ".join(project["tags"])),
            (3, project["name"] + " " + project["category"]),
            (2, " ".join(project["methods"]) + " " + " ".join(project["languages"])),
            (1, project["summary"] + " " + project["problem"]),
        ]
        hits = set()
        score = 0
        for weight, text in weighted:
            overlap = wanted & tokens(text)
            hits |= overlap
            score += weight * len(overlap)
        if score:
            results.append({"project": project, "score": score, "matched_terms": sorted(hits)})
    return sorted(results, key=lambda r: (-r["score"], r["project"]["id"]))


def selected(data, focus=None):
    return [r["project"] for r in rank(data["projects"], focus)] if focus else data["projects"]


def resume(data, focus=None, limit=6):
    person = data["person"]
    projects = selected(data, focus)[:limit]
    lines = [f"# {person['name']}", "", person["headline"], "",
             f"{person['email']} | {person['website']}", "", person["summary"], "",
             "## Selected work", ""]
    if not projects:
        lines += ["No catalog projects matched this focus.", ""]
    for project in projects:
        lines += [f"### [{project['name']}]({project['url']})", "",
                  project["summary"], "", "Methods: " + ", ".join(project["methods"]) + ".", ""]
    lines += ["## Technical skills", "", ", ".join(person["languages"]), "",
              "## Background", "", person["background"], "",
              "## Contact", "", f"For project scope and availability: {person['email']}", "",
              "---", "", "Source: " + data["provenance"]["source"] + ".",
              data["provenance"]["note"], ""]
    return "\n".join(lines)


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--data", help="Use an alternative portfolio JSON file")
    commands = root.add_subparsers(dest="command", required=True)
    for name, help_text in (("profile", "Read the professional summary"),
                            ("projects", "Search and filter selected projects"),
                            ("show", "Read one project's evidence record"),
                            ("match", "Match a research problem to relevant work"),
                            ("resume", "Generate a Markdown resume"),
                            ("contact", "Show contact details and engagement areas"),
                            ("validate", "Check the portfolio data contract")):
        cmd = commands.add_parser(name, help=help_text)
        if name != "resume":
            cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
        if name == "projects":
            cmd.add_argument("--query", default="")
            cmd.add_argument("--language", help="Exact language, case-insensitive")
            cmd.add_argument("--category", help="Exact category, case-insensitive")
        if name == "show":
            cmd.add_argument("id")
        if name == "match":
            cmd.add_argument("query")
            cmd.add_argument("--limit", type=positive, default=5)
        if name == "resume":
            cmd.add_argument("--focus", help="Rank selected work for a topic or role")
            cmd.add_argument("--limit", type=positive, default=6)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        data = load(args.data)
    except (OSError, ValueError) as exc:
        print(f"fieldwork: {exc}", file=sys.stderr)
        return 2
    command = args.command
    if command == "resume":
        print(resume(data, args.focus, args.limit), end="")
        return 0
    if command == "profile":
        result = {"person": data["person"], "provenance": data["provenance"]}
        p = data["person"]
        output = f"{p['name']}\n{p['headline']}\n\n{p['summary']}\n\n{p['background']}\n\n{data['provenance']['note']}"
    elif command == "contact":
        p = data["person"]
        result = {k: p[k] for k in ("email", "website", "services")}
        output = f"{p['email']}\n{p['website']}\n\n" + "\n".join(p["services"]) + "\n\nAgree on scope, deliverables, and schedule before commissioning work."
    elif command == "validate":
        result = {"valid": True, "projects": len(data["projects"]), "external_evidence_checked": False}
        output = f"Valid portfolio: {len(data['projects'])} selected projects. External links and claims were not checked."
    elif command == "show":
        result = next((p for p in data["projects"] if p["id"] == args.id), None)
        if result is None:
            print(f"fieldwork: unknown project '{args.id}'. Use 'projects' to list IDs.", file=sys.stderr)
            return 1
        output = "\n".join([result["name"], result["summary"], "", "Problem: " + result["problem"],
                            "Methods: " + ", ".join(result["methods"]), result["url"],
                            "Evidence status: " + result["evidence_status"]])
        if "verification" in result:
            output += "\nVerification: " + json.dumps(result["verification"], ensure_ascii=False)
    elif command == "match":
        matches = rank(data["projects"], args.query)[:args.limit]
        result = {"query": args.query, "method": "weighted keyword overlap", "matches": matches,
                  "note": "Scores rank catalog relevance, not expertise or verified results."}
        output = "\n\n".join(
            f"{r['project']['name']} [{r['project']['id']}]\n{r['project']['summary']}\n"
            f"Matched: {', '.join(r['matched_terms'])}\n{r['project']['url']}"
            for r in matches
        ) or "No matching projects. Try a domain such as firmware, API, AI, or disclosure."
        output += "\n\n" + result["note"]
    else:
        projects = selected(data, args.query)
        if args.language:
            projects = [p for p in projects if args.language.casefold() in [v.casefold() for v in p["languages"]]]
        if args.category:
            projects = [p for p in projects if p["category"].casefold() == args.category.casefold()]
        result = {"projects": projects, "count": len(projects)}
        output = "\n\n".join(f"{p['id']} | {', '.join(p['languages'])} | {p['category']}\n{p['summary']}" for p in projects) or "No matching projects."
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else output)
    return 0
