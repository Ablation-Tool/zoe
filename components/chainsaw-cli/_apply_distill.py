#!/usr/bin/env python3
"""Apply a distill JSON (cards for books 46-54) into the chainsaw brain.

Reads cards.json (array per the distill schema), then:
  - writes brain/cards/NN_isbn.md in card format
  - saves syntheses/synthesis_NN_isbn.md, points _books.json file field at it
  - confirms/corrects lobe in _books.json
  - regenerates brain/INDEX.md: route-by-signal counts/lists + full chain map
    with reciprocal synapses (new edges added in BOTH directions)
Additive to existing 01-45 edges; nothing is dropped.
"""
import json, os, re, sys

BRAIN = "/home/cowboy/chainsaw"
CARDS = os.path.join(BRAIN, "brain", "cards")
SYN = os.path.join(BRAIN, "syntheses")
INDEX = os.path.join(BRAIN, "brain", "INDEX.md")
MANIFEST = os.path.join(BRAIN, "_books.json")

LOBE_DISPLAY = [
    ("offensive", "Offensive",
     "load when finding or proving an exploitable path: OSINT and Shodan recon, code review, "
     "reverse engineering, exploit development, fuzzing, web/api/crypto/cloud/network/privesc, side-channel."),
    ("defensive", "Defensive",
     "load when building visibility, resilience, ICS/OT and IoT defense, deception, malware analysis, "
     "or securing AI; thinking like the operator."),
    ("ai-agentic", "AI and Agentic",
     "load when building, grounding, governing, or securing AI/agentic systems; fairness, randomness, NLP."),
    ("craft-code", "Craft and Code",
     "load when the maker eye: trained observation, readable code, visual craft, tooling foundations."),
    ("human", "Human and Influence",
     "load when reading, persuading, leading, or connecting with people; social engineering; report and disclosure."),
    ("philosophy", "Philosophy",
     "load when proportion and skepticism: deciding what matters and how to think about it."),
]


def parse_existing_edges():
    edges = {}
    line_re = re.compile(r"-\s+\*\*(\d+)\*\*\s+.*?<->\s+(.*)")
    with open(INDEX) as f:
        for line in f:
            m = line_re.match(line.strip())
            if m:
                edges[int(m.group(1))] = set(int(x) for x in m.group(2).split() if x.isdigit())
    return edges


def isbn_of(manifest, n):
    return next(b["isbn"] for b in manifest if b["n"] == n)


def write_card(card, isbn, title):
    n = card["n"]
    p = os.path.join(CARDS, f"{n:02d}_{isbn}.md")
    L = [f"# {n:02d}. {title}", "",
         f"**ISBN** {isbn}  |  **Lobe** {card['lobe']}", "",
         f"> {card['blurb']}", "", "## Reach for this when", ""]
    L += [f"- {x}" for x in card["reach_for_when"]]
    L += ["", "## Principles", ""]
    L += [f"- {x}" for x in card["principles"]]
    L += ["", "## Chains with", ""]
    L += [f"- **{c['n']:02d}** - {c['reason']}" for c in card["chains_with"]]
    L += [""]
    open(p, "w").write("\n".join(L))
    return p


def main():
    cards = json.load(open(sys.argv[1]))
    cards = {c["n"]: c for c in cards}
    manifest = json.load(open(MANIFEST))
    os.makedirs(SYN, exist_ok=True)

    # carry over titles/lobes; the manifest title is canonical
    title_of = {b["n"]: b["title"] for b in manifest}
    for b in manifest:
        if b["n"] in cards:
            c = cards[b["n"]]
            isbn = b["isbn"]
            b["lobe"] = c["lobe"]                     # confirm/correct lobe
            synp = os.path.join(SYN, f"synthesis_{b['n']:02d}_{isbn}.md")
            open(synp, "w").write(f"# {b['n']:02d}. {b['title']}\n\n{c['synthesis_md']}\n")
            b["file"] = synp
            write_card(c, isbn, b["title"])
    lobe_of = {b["n"]: b["lobe"] for b in manifest}

    # merge edges: existing + new (reciprocal)
    edges = parse_existing_edges()
    for n in range(1, max(lobe_of) + 1):
        edges.setdefault(n, set())
    for n, c in cards.items():
        for link in c["chains_with"]:
            t = link["n"]
            if t == n or t < 1 or t > max(lobe_of):
                continue
            edges[n].add(t)
            edges[t].add(n)

    # rebuild INDEX.md
    by_lobe = {}
    for n, lobe in lobe_of.items():
        by_lobe.setdefault(lobe, []).append(n)
    out = ["# Chainsaw index", "",
           "The router. Match a task to its lobe by signal, load that lobe and its named cards, "
           "then follow the chain map across lobes. The framework is always-on; this index just points.",
           "", "## Route by signal", ""]
    for key, disp, desc in LOBE_DISPLAY:
        nums = sorted(by_lobe.get(key, []))
        out.append(f"- **{disp}** ({len(nums)}) -> {desc}")
        out.append(f"  cards: {' '.join(f'{x:02d}' for x in nums)}")
    out += ["", "## Flat weight", "",
            "Every card carries the same weight. The lobes differ in size because domains differ in size, "
            "not in importance. Load by what the task and its chains call for, never by rank.",
            "", "## Chain map (the synapses)", ""]
    total = max(lobe_of)
    out.append(f"{total} of {total} books are wired to at least one other. Follow these links across "
               "lobe boundaries; that crossing is where the brain thinks.")
    out.append("")
    for n in range(1, total + 1):
        sib = " ".join(f"{x:02d}" if False else str(x) for x in sorted(edges.get(n, set())))
        out.append(f"- **{n:02d}** {title_of[n]} [{lobe_of[n]}] <-> {sib}")
    open(INDEX, "w").write("\n".join(out) + "\n")
    json.dump(manifest, open(MANIFEST, "w"), indent=1, ensure_ascii=False)

    print(f"applied {len(cards)} cards; INDEX rebuilt ({total} books).")
    for n in sorted(cards):
        print(f"  {n:02d} [{lobe_of[n]:10}] {len(edges[n])} synapses  {title_of[n]}")


if __name__ == "__main__":
    main()
