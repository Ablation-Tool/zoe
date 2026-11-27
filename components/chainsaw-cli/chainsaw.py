#!/usr/bin/env python3
"""chainsaw - the collective brain as a thin tool.

Doctrine (FRAMEWORK.md / USAGE.md): the brain is full book texts. This tool is
plumbing around the brew, never a replacement for it. It routes a task to its
lobe and books, serves FULL TEXT (never a card in place of the book), logs what
fires, surfaces prune candidates, and slots new books in. The lift - book 07
reframing a recon problem - happens in the model holding several full texts at
once. The tool does not summarize. That is the one rule made executable.

Single file, stdlib only. Verbs:
  route "<task>"   lobe(s) + book numbers + full-text paths + one priming pick
  read <NN[-MM]>   cat the FULL TEXT of a book (territory, not map)
  list [lobe]      the manifest
  fire <NN..> --task T --lift L     append a USAGE.md fire-log row
  prune            books with zero fires past a fair-chance threshold
  add <pdf|txt> --lobe L --title T [--isbn I]   slot a new book (additive only)
"""
import json, os, re, sys, shutil, subprocess, argparse

BRAIN = os.path.dirname(os.path.abspath(__file__))
BOOKS = os.path.join(BRAIN, "books")
CARDS = os.path.join(BRAIN, "brain", "cards")
LOBES = os.path.join(BRAIN, "brain", "lobes")
INDEX = os.path.join(BRAIN, "brain", "INDEX.md")
MANIFEST = os.path.join(BRAIN, "_books.json")
USAGE = os.path.join(BRAIN, "USAGE.md")

# Lobe signal lexicon, distilled from INDEX.md "Route by signal". Keyword -> lobe.
LEXICON = {
    "offensive": "exploit reverse fuzz fuzzing web api crypto cloud network privesc "
                 "privilege injection sql xss kali payload shellcode rop overflow "
                 "vulnerability zero-day cve protocol pentest attack break "
                 "osint shodan censys dork recon reconnaissance fingerprint enumerate "
                 "enumeration attribution harvest banner exposed unauth unauthenticated "
                 "disassemble disassembly ida side-channel fault-injection glitch",
    "defensive": "defend detection honeypot deception resilience ics ot scada iot "
                 "industrial securing monitor visibility blue operator harden "
                 "incident forensic forensics malware rootkit defense triage",
    "ai-agentic": "ai agent agentic llm model fairness randomness nlp prompt mcp "
                  "embedding rag mistral inference governance ground tool-use",
    "craft-code": "code readable tool tooling observation drawing visual craft "
                  "photography pixel design refactor naming build maker",
    "human": "persuade lead leadership coach social engineering disclosure report "
             "influence conversation trust people humility connect",
    "philosophy": "proportion skepticism matters think philosophy ethic principle "
                  "framing assumption falsify",
}


def load_manifest():
    with open(MANIFEST) as f:
        return json.load(f)


def parse_chainmap():
    """INDEX.md lines: '- **NN** Title [lobe] <-> a b c' -> {n: [siblings]}."""
    edges, lobe_of, title_of = {}, {}, {}
    line_re = re.compile(r"-\s+\*\*(\d+)\*\*\s+(.*?)\s+\[(\w[\w-]*)\]\s+<->\s+(.*)")
    with open(INDEX) as f:
        for line in f:
            m = line_re.match(line.strip())
            if not m:
                continue
            n = int(m.group(1))
            title_of[n] = m.group(2).strip()
            lobe_of[n] = m.group(3).strip()
            edges[n] = [int(x) for x in m.group(4).split() if x.isdigit()]
    return edges, lobe_of, title_of


def card_path(n):
    for fn in os.listdir(CARDS):
        if fn.startswith(f"{n:02d}_"):
            return os.path.join(CARDS, fn)
    return None


def card_blurb(n):
    p = card_path(n)
    if not p:
        return ""
    txt = open(p, errors="ignore").read()
    m = re.search(r"^>\s+(.*)", txt, re.M)
    return m.group(1) if m else ""


def book_text_path(n):
    for fn in os.listdir(BOOKS):
        if fn.startswith(f"{n:02d}_"):
            return os.path.join(BOOKS, fn)
    return None


def score_lobes(task):
    t = task.lower()
    words = set(re.findall(r"[a-z][a-z-]+", t))
    out = {}
    for lobe, lex in LEXICON.items():
        keys = set(lex.split())
        out[lobe] = sum(1 for w in words if any(w == k or w.startswith(k) or k.startswith(w) for k in keys))
    return out


def cmd_route(args):
    task = " ".join(args.task)
    edges, lobe_of, title_of = parse_chainmap()
    by_lobe = {}
    for n, lobe in lobe_of.items():
        by_lobe.setdefault(lobe, []).append(n)
    scores = score_lobes(task)
    ranked_lobes = sorted(scores, key=scores.get, reverse=True)
    top_lobes = [l for l in ranked_lobes if scores[l] > 0][:2] or [ranked_lobes[0]]

    # rank candidate books inside the chosen lobes by task-word hits in title+blurb
    twords = set(re.findall(r"[a-z][a-z-]+", task.lower()))
    cands = []
    for lobe in top_lobes:
        for n in by_lobe.get(lobe, []):
            hay = (title_of.get(n, "") + " " + card_blurb(n)).lower()
            hits = sum(1 for w in twords if len(w) > 3 and w in hay)
            cands.append((hits, n))
    cands.sort(reverse=True)
    primary = [n for _, n in cands[:3]]
    # 1-hop synapses out of the primary set
    siblings = sorted({s for n in primary for s in edges.get(n, [])} - set(primary))
    # one distant priming book: in an unchosen lobe, NOT a 1-hop synapse of the
    # primary set, and the most isolated (fewest synapses) - the furthest reach
    # is where music-helps-programming priming pays off.
    distant_pool = [n for n, l in lobe_of.items()
                    if l not in top_lobes and n not in siblings and n not in primary]
    priming = min(distant_pool, key=lambda n: (len(edges.get(n, [])), n)) if distant_pool else None

    def line(n):
        bp = book_text_path(n)
        return f"  {n:02d} [{lobe_of[n]:10}] {title_of[n]}\n       full text: {bp}"

    print(f"TASK: {task}\n")
    print(f"LOBES (by signal): {', '.join(top_lobes)}   scores={ {k:v for k,v in scores.items() if v} }\n")
    print("PRIMARY books - load full text:")
    for n in primary:
        print(line(n))
    print("\nSYNAPSES (1-hop, pull if the task touches them):")
    for n in siblings[:8]:
        print(line(n))
    if priming:
        print("\nPRIMING (one distant book, the way music helps programming):")
        print(line(priming))
    print("\nThen: load the framework, read these full texts, let them brew, act. "
          "Log with: chainsaw fire " + " ".join(f"{n:02d}" for n in primary) + " --task ... --lift ...")


def cmd_read(args):
    spec = args.span
    if "-" in spec:
        a, b = spec.split("-"); rng = range(int(a), int(b) + 1)
    else:
        rng = [int(spec)]
    for n in rng:
        p = book_text_path(n)
        if not p:
            print(f"# {n:02d}: NO TEXT", file=sys.stderr); continue
        sys.stdout.write(f"\n===== BOOK {n:02d} :: {os.path.basename(p)} =====\n")
        sys.stdout.write(open(p, errors="ignore").read())


def cmd_list(args):
    edges, lobe_of, title_of = parse_chainmap()
    for b in load_manifest():
        n = b["n"]
        if args.lobe and b["lobe"] != args.lobe:
            continue
        print(f"  {n:02d} [{b['lobe']:10}] {b['title']}")


def cmd_fire(args):
    row = (f"| 2026-XX-XX | {args.task} | "
           f"{' '.join(f'{int(n):02d}' for n in args.books)} | {args.lift} | watch |\n")
    with open(USAGE, "a") as f:
        f.write(row)
    print("appended fire-log row (set the date):\n" + row)


def cmd_prune(args):
    # only the fire-log table counts; other tables (corpus growth) must not pollute it
    fired, in_log = set(), False
    for line in open(USAGE):
        s = line.strip()
        if s.startswith("## "):
            in_log = s.startswith("## The log")
            continue
        if in_log and s.startswith("|") and "books that fired" not in s and "---" not in s:
            cols = [c.strip() for c in s.split("|")]
            if len(cols) > 3:
                fired |= {int(x) for x in re.findall(r"\b\d{2}\b", cols[3])}
    alln = {b["n"] for b in load_manifest()}
    cold = sorted(alln - fired)
    print(f"FIRED so far: {len(fired)}/{len(alln)} books")
    print("COLD (zero fires - watch, do not prune yet unless fair chance given):")
    _, _, title_of = parse_chainmap()
    for n in cold:
        print(f"  {n:02d} {title_of.get(n,'?')}")


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:48]


def cmd_add(args):
    src = os.path.abspath(args.src)
    manifest = load_manifest()
    n = max(b["n"] for b in manifest) + 1
    isbn = args.isbn or f"x{n:013d}"
    slug = slugify(args.title)
    dest = os.path.join(BOOKS, f"{n:02d}_{isbn}_{slug}.txt")
    if src.endswith(".pdf"):
        subprocess.run(["pdftotext", "-q", src, dest], check=True)
    else:
        shutil.copyfile(src, dest)
    chars = os.path.getsize(dest)
    manifest.append({"n": n, "isbn": isbn, "lobe": args.lobe,
                     "file": f"PENDING_SYNTHESIS:{dest}", "title": args.title})
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    # stub card, synthesis pending - the synapse wiring is a distill job, not a guess
    cp = os.path.join(CARDS, f"{n:02d}_{isbn}.md")
    with open(cp, "w") as f:
        f.write(f"# {n:02d}. {args.title}\n\n**ISBN** {isbn}  |  **Lobe** {args.lobe}\n\n"
                f"> SYNTHESIS PENDING. Full text slotted ({chars:,} chars). Run the distill "
                f"pass to write the blurb, Reach-for-when, Principles, and Chains-with edges.\n")
    print(f"added book {n:02d} [{args.lobe}] {args.title}")
    print(f"  text: {dest} ({chars:,} chars)")
    print(f"  card: {cp} (stub - distill pending)")
    print(f"  NOTE: INDEX.md chain map NOT edited (synapses need real reading).")


def main():
    ap = argparse.ArgumentParser(prog="chainsaw")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route"); r.add_argument("task", nargs="+"); r.set_defaults(fn=cmd_route)
    rd = sub.add_parser("read"); rd.add_argument("span"); rd.set_defaults(fn=cmd_read)
    ls = sub.add_parser("list"); ls.add_argument("lobe", nargs="?"); ls.set_defaults(fn=cmd_list)
    fr = sub.add_parser("fire"); fr.add_argument("books", nargs="+")
    fr.add_argument("--task", required=True); fr.add_argument("--lift", required=True); fr.set_defaults(fn=cmd_fire)
    pr = sub.add_parser("prune"); pr.set_defaults(fn=cmd_prune)
    ad = sub.add_parser("add"); ad.add_argument("src")
    ad.add_argument("--lobe", required=True); ad.add_argument("--title", required=True)
    ad.add_argument("--isbn"); ad.set_defaults(fn=cmd_add)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
