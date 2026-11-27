"""Zoe Zero-Token Engine — 100% free, zero-LLM-token symbolic math, local atlas, and open-science research.

Guarantees:
  - cloud_tokens_used = 0, llm_tokens_used = 0 ($0.00 forever)
  - Zero API keys, zero subscriptions, zero cloud LLM calls
  - Local SymPy symbolic math + Dorothy 3D Brain Encyclopedia + 6,130-chapter Local Library
  - Free public read-only science APIs (Europe PMC / PubMed, arXiv, Wikipedia) with extractive synthesis
  - Self-growing persistent offline SQLite FTS5 knowledge cache (~/.zoe/zoe_zero_token_cache.sqlite)
  - Strict epistemic honesty: clinical_action_authorized=False, cure_claim=False, sentience_claimed=False
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Sequence
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


DEFAULT_TAU = 0.08
DEFAULT_CACHE_PATH = Path.home() / ".zoe" / "zoe_zero_token_cache.sqlite"
USER_AGENT = "ZoeObservatory/1.0 (Zero-Token Open Science Research; non-clinical)"

_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "can", "could", "did", "do",
    "does", "for", "from", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "please", "should", "tell", "that", "the",
    "their", "them", "these", "they", "this", "those", "to", "us", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with", "would", "you", "your",
    "zoe", "explain", "define", "describe", "about", "role", "between", "work", "works",
})

_MECHANISM_CUES = frozenset({
    "inhibit", "inhibits", "inhibition", "mutation", "mutations", "pathway", "pathways",
    "receptor", "receptors", "mechanism", "mechanisms", "cortex", "cortical", "circuit",
    "circuits", "signal", "signaling", "protein", "proteins", "gene", "genes", "enzyme",
    "chromatin", "methylation", "histone", "neuron", "neurons", "synaptic", "glioma",
    "tumor", "tumors", "cell", "cells", "function", "functions", "regulates", "drives",
    "causes", "associated", "theorem", "entropy", "equation", "structure", "mni",
})

_CAVEAT_CUES = (
    "however", "unclear", "remains", "limitation", "limitations", "challenge",
    "challenges", "further study", "further research", "unknown", "resistance",
    "poor prognosis", "heterogeneity", "controversial",
)

_BIOMED_CUES = frozenset({
    "brain", "glioma", "tumor", "cancer", "cell", "cells", "gene", "genes", "mutation",
    "protein", "enzyme", "receptor", "neuron", "neurons", "synapse", "cortex", "hippocampus",
    "amygdala", "cerebellum", "brainstem", "pons", "thalamus", "mri", "fmri", "eeg",
    "clinical", "preclinical", "disease", "syndrome", "therapy", "drug", "kinase",
    "methylation", "histone", "prc2", "ezh2", "h3k27m", "neurology", "neuroscience",
    "pathology", "biomechanics", "anatomy", "artery", "nerve", "dopamine", "serotonin",
    "immunotherapy", "microglia", "astrocyte", "oligodendrocyte", "myelin", "axon",
})

_SYMPY_PREFIX_RE = re.compile(
    r"^(?:please\s+)?(?P<op>solve|diff|differentiate|derivative(?:\s+of)?|integrate|integral(?:\s+of)?|"
    r"factor|expand|simplify)\s+(?P<body>.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceHit:
    source: str
    title: str
    citation: str
    snippet: str
    score: float
    url: str = ""


@dataclass(frozen=True)
class ZeroTokenReport:
    query: str
    summary: str
    caveats: str
    hits: tuple[EvidenceHit, ...]
    a_tau: int
    tau: float = DEFAULT_TAU
    cached_count: int = 0
    cloud_tokens_used: int = 0
    llm_tokens_used: int = 0
    clinical_action_authorized: bool = False
    cure_claim: bool = False
    sentience_claimed: bool = False


def content_tokens(text: str) -> list[str]:
    """Extract normalized non-stopword alphanumeric tokens preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for tok in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", str(text or "").lower()):
        clean = tok.strip("-_")
        if len(clean) < 2 or clean in _STOPWORDS or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def strip_html(raw: str) -> str:
    """Strip HTML/XML markup and normalize whitespace cleanly."""
    text = re.sub(r"<[^>]+>", " ", str(raw or ""))
    return " ".join(unescape(text).split()).replace("—", ", ").replace(" — ", ", ")


def kloster_a_tau(scores: Sequence[float], tau: float = DEFAULT_TAU) -> int:
    """Compute Kloster A_tau(p) = |{i : p_i > tau}| over a normalized score simplex."""
    clipped = [max(0.0, float(s)) for s in scores]
    total = sum(clipped)
    if not clipped or total <= 1e-12:
        return 0
    return sum(1 for val in clipped if (val / total) > tau)


def try_symbolic_math(raw: str) -> str | None:
    """Evaluate exact symbolic algebra and calculus locally via SymPy (0 tokens)."""
    cleaned = " ".join(str(raw or "").split()).rstrip("?.!")
    if not cleaned or len(cleaned) > 160:
        return None
    match = _SYMPY_PREFIX_RE.match(cleaned)
    if not match:
        return None
    op = match.group("op").lower().split()[0]
    body = match.group("body").strip()
    body = re.sub(r"\s+with\s+respect\s+to\s+([a-zA-Z])\b", r" wrt \1", body, flags=re.IGNORECASE)
    var_name = "x"
    if " wrt " in body:
        body, var_part = body.rsplit(" wrt ", 1)
        if re.fullmatch(r"[a-zA-Z]", var_part.strip()):
            var_name = var_part.strip()
    if not re.fullmatch(r"[0-9a-zA-Z_+\-*/^()=.,\s]+", body):
        return None
    try:
        import sympy as sp
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except ImportError:
        return None

    trans = standard_transformations + (implicit_multiplication_application, convert_xor)
    allowed_names = {
        "x": sp.Symbol("x"), "y": sp.Symbol("y"), "z": sp.Symbol("z"), "t": sp.Symbol("t"),
        "n": sp.Symbol("n"), "pi": sp.pi, "e": sp.E, "sin": sp.sin, "cos": sp.cos,
        "tan": sp.tan, "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs,
    }
    sym = allowed_names.get(var_name, sp.Symbol(var_name))
    try:
        if op == "solve":
            if "=" in body:
                lhs_s, rhs_s = body.split("=", 1)
                expr = parse_expr(lhs_s, local_dict=allowed_names, transformations=trans) - parse_expr(
                    rhs_s, local_dict=allowed_names, transformations=trans
                )
            else:
                expr = parse_expr(body, local_dict=allowed_names, transformations=trans)
            free = sorted(expr.free_symbols, key=lambda s: s.name)
            target = sym if sym in free else (free[0] if free else sym)
            sols = sp.solve(expr, target)
            return f"SymPy exact solution for {target}: {sols}"
        expr = parse_expr(body, local_dict=allowed_names, transformations=trans)
        free = sorted(expr.free_symbols, key=lambda s: s.name)
        target = sym if sym in free else (free[0] if free else sym)
        if op in {"diff", "differentiate", "derivative"}:
            return f"d/d{target} ({expr}) = {sp.diff(expr, target)}"
        if op in {"integrate", "integral"}:
            return f"∫ ({expr}) d{target} = {sp.integrate(expr, target)} + C"
        if op == "factor":
            return f"factor({expr}) = {sp.factor(expr)}"
        if op == "expand":
            return f"expand({expr}) = {sp.expand(expr)}"
        return f"simplify({expr}) = {sp.simplify(expr)}"
    except Exception:
        return None


def _parse_atlas_entries(data: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten structured Dorothy Observatory encyclopedia collections into searchable records."""
    records: list[dict[str, str]] = []
    for item in data.get("brodmann", []):
        ba = str(item.get("ba", ""))
        mni = item.get("mni", [])
        records.append({
            "title": f"Brodmann Area {ba} — {item.get('region', '')}",
            "citation": f"Dorothy Atlas · BA {ba} ({item.get('lobe', '')}, MNI {mni})",
            "text": f"Brodmann area {ba} ({item.get('region', '')}, {item.get('lobe', '')} lobe, MNI {mni}): {item.get('desc', '')}",
            "keys": f"ba {ba} brodmann {ba} {item.get('region', '')} {item.get('lobe', '')}",
        })
    for item in data.get("cranialNerves", []):
        cid = str(item.get("id", ""))
        name = str(item.get("name", ""))
        records.append({
            "title": f"{cid} ({name} Nerve)",
            "citation": f"Dorothy Atlas · {cid} ({name})",
            "text": f"{cid} {name}: modality {item.get('modality', '')}; origin {item.get('origin', '')}; foramen {item.get('foramen', '')}. {item.get('clinical', item.get('fn', ''))}",
            "keys": f"{cid} {name} cranial nerve {item.get('foramen', '')}",
        })
    for section, label in (
        ("tracts", "White-Matter Tract"),
        ("vascular", "Cerebral Vasculature"),
        ("neuromodulators", "Neuromodulator"),
        ("corticalLayers", "Cortical Layer"),
        ("eeg1020", "EEG 10-20 Electrode"),
        ("circuits", "Neural Circuit"),
        ("vascularTerritories", "Vascular Territory"),
    ):
        for item in data.get(section, []):
            name = str(item.get("name") or item.get("id") or item.get("layer") or label)
            desc = " ".join(f"{k}: {v}" for k, v in item.items() if k not in {"plates", "cam", "color"} and v)
            records.append({
                "title": f"{label}: {name}",
                "citation": f"Dorothy Atlas · {label} ({name})",
                "text": strip_html(desc)[:420],
                "keys": f"{label} {name} {item.get('id', '')} {item.get('ba', '')}",
            })
    return records


class DorothyEncyclopediaIndex:
    """Instant offline search across dorothy-brain-observatory/data/atlas_encyclopedia.js."""

    def __init__(self, zoe_root: Path):
        self.path = Path(zoe_root).resolve() / "dorothy-brain-observatory" / "data" / "atlas_encyclopedia.js"
        self.records: list[dict[str, str]] = self._load()

    def _load(self) -> list[dict[str, str]]:
        if not self.path.is_file():
            return []
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw[raw.index("{"):].rstrip(";\r\n "))
            return _parse_atlas_entries(data)
        except Exception:
            return []

    def search(self, query: str, limit: int = 3) -> list[EvidenceHit]:
        q_tokens = content_tokens(query)
        q_low = " ".join(str(query or "").lower().split())
        if not q_tokens or not self.records:
            return []
        scored: list[tuple[float, dict[str, str]]] = []
        for rec in self.records:
            hay = f"{rec['title']} {rec['keys']} {rec['text']}".lower()
            key_hay = f"{rec['title']} {rec['keys']}".lower()
            hits = sum(1 for t in q_tokens if re.search(rf"\b{re.escape(t)}\b", hay))
            key_hits = sum(1 for t in q_tokens if re.search(rf"\b{re.escape(t)}\b", key_hay))
            if hits == 0:
                continue
            score = (hits / len(q_tokens)) + (0.65 * key_hits / len(q_tokens))
            if rec["title"].lower() in q_low:
                score += 1.2
            if score >= 0.85:
                scored.append((score, rec))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            EvidenceHit(
                source="dorothy_atlas",
                title=rec["title"],
                citation=rec["citation"],
                snippet=rec["text"],
                score=round(sc, 3),
            )
            for sc, rec in scored[:limit]
        ]


class ZeroTokenKnowledgeCache:
    """Self-growing local SQLite FTS5 cache for verified zero-token open-science findings."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path or DEFAULT_CACHE_PATH).expanduser().resolve()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries (
                source TEXT NOT NULL,
                citation_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                stored_at TEXT NOT NULL,
                PRIMARY KEY (source, citation_id)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                source, citation_id, title, body, url,
                tokenize='porter unicode61'
            );
            """
        )
        return conn

    def count(self) -> int:
        if not self.db_path.is_file():
            return 0
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM entries").fetchone()
            return int(row["c"]) if row else 0
        except sqlite3.Error:
            return 0
        finally:
            conn.close()

    def upsert_hits(self, hits: Sequence[EvidenceHit]) -> int:
        persistable = [h for h in hits if h.source in {"pubmed", "arxiv", "wikipedia"} and h.snippet]
        if not persistable:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        saved = 0
        try:
            for hit in persistable:
                exists = conn.execute(
                    "SELECT 1 FROM entries WHERE source = ? AND citation_id = ?",
                    (hit.source, hit.citation),
                ).fetchone()
                conn.execute(
                    "INSERT OR REPLACE INTO entries(source, citation_id, title, body, url, stored_at) VALUES (?,?,?,?,?,?)",
                    (hit.source, hit.citation, hit.title, hit.snippet, hit.url, now),
                )
                if not exists:
                    conn.execute(
                        "INSERT INTO entries_fts(source, citation_id, title, body, url) VALUES (?,?,?,?,?)",
                        (hit.source, hit.citation, hit.title, hit.snippet, hit.url),
                    )
                    saved += 1
            conn.commit()
            return saved
        except sqlite3.Error:
            return saved
        finally:
            conn.close()

    def search(self, query: str, limit: int = 4) -> list[EvidenceHit]:
        if not self.db_path.is_file():
            return []
        tokens = content_tokens(query)[:8]
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in tokens)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT source, citation_id, title, body, url
                FROM entries_fts
                WHERE entries_fts MATCH ?
                ORDER BY bm25(entries_fts)
                LIMIT ?
                """,
                (fts_query, max(1, min(limit * 2, 12))),
            ).fetchall()
            out: list[EvidenceHit] = []
            for row in rows:
                hay = f"{row['title']} {row['body']}".lower()
                overlap = sum(1 for t in tokens if t in hay) / len(tokens)
                if overlap >= 0.45:
                    out.append(EvidenceHit(
                        source="cache",
                        title=str(row["title"]),
                        citation=f"Cached · {row['citation_id']}",
                        snippet=str(row["body"]),
                        score=round(0.8 + overlap, 3),
                        url=str(row["url"] or ""),
                    ))
            out.sort(key=lambda h: h.score, reverse=True)
            return out[:limit]
        except sqlite3.Error:
            return []
        finally:
            conn.close()


def _http_get_text(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_europe_pmc(query: str, limit: int = 4, timeout: int = 8) -> list[EvidenceHit]:
    """Fetch peer-reviewed biomedical abstracts from Europe PMC / PubMed (0 tokens, 0 API keys)."""
    q = urllib.parse.quote(query)
    url = (
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query={q}&format=json&pageSize={max(1, min(limit, 6))}&resultType=core"
    )
    try:
        payload = json.loads(_http_get_text(url, timeout=timeout))
    except Exception:
        return []
    hits: list[EvidenceHit] = []
    for item in (payload.get("resultList", {}).get("result") or []):
        title = strip_html(item.get("title", ""))
        abstract = strip_html(item.get("abstractText", ""))
        if not title or not abstract:
            continue
        pmid = str(item.get("pmid") or item.get("pmcid") or item.get("id") or "")
        year = str(item.get("pubYear") or "")
        journal = strip_html(item.get("journalTitle") or item.get("journalInfo", {}).get("journal", {}).get("title", ""))
        cite = f"PMID:{pmid}" if item.get("pmid") else (pmid or "EuropePMC")
        if journal or year:
            cite = f"{cite} · {journal} ({year})".strip()
        link = f"https://pubmed.ncbi.nlm.nih.gov/{item['pmid']}/" if item.get("pmid") else ""
        hits.append(EvidenceHit(
            source="pubmed",
            title=title,
            citation=cite,
            snippet=abstract[:1400],
            score=1.45,
            url=link,
        ))
    return hits[:limit]


def fetch_arxiv(query: str, limit: int = 3, timeout: int = 8) -> list[EvidenceHit]:
    """Fetch open-access math/CS/physics/bio abstracts from arXiv Atom API (0 tokens, 0 keys)."""
    tokens = content_tokens(query)[:6]
    search_expr = " AND ".join(f"all:{t}" for t in tokens) if tokens else f"all:{query}"
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query={urllib.parse.quote(search_expr)}&max_results={max(1, min(limit, 5))}"
    )
    try:
        root = ET.fromstring(_http_get_text(url, timeout=timeout))
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    hits: list[EvidenceHit] = []
    for entry in root.findall("a:entry", ns):
        title = strip_html(entry.findtext("a:title", "", ns))
        summary = strip_html(entry.findtext("a:summary", "", ns))
        entry_id = (entry.findtext("a:id", "", ns) or "").strip()
        published = (entry.findtext("a:published", "", ns) or "")[:4]
        arxiv_id = entry_id.rsplit("/", 1)[-1] if entry_id else "arXiv"
        if title and summary:
            hits.append(EvidenceHit(
                source="arxiv",
                title=title,
                citation=f"arXiv:{arxiv_id} ({published})" if published else f"arXiv:{arxiv_id}",
                snippet=summary[:1200],
                score=1.15,
                url=entry_id,
            ))
    return hits[:limit]


def fetch_wikipedia(query: str, timeout: int = 6) -> list[EvidenceHit]:
    """Fetch a clean encyclopedic summary from Wikipedia REST API (0 tokens, 0 keys)."""
    tokens = content_tokens(query)
    search_term = " ".join(tokens[:5]) if tokens else query.strip()
    if not search_term:
        return []
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php?action=opensearch&limit=2&namespace=0&format=json&search="
            + urllib.parse.quote(search_term)
        )
        found = json.loads(_http_get_text(search_url, timeout=timeout))
        titles = found[1] if isinstance(found, list) and len(found) > 1 else []
        if not titles:
            return []
        title = str(titles[0])
        sum_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"))
        data = json.loads(_http_get_text(sum_url, timeout=timeout))
        extract = strip_html(data.get("extract", ""))
        if not extract or data.get("type") == "disambiguation":
            return []
        page_url = str(data.get("content_urls", {}).get("desktop", {}).get("page", ""))
        return [EvidenceHit(
            source="wikipedia",
            title=str(data.get("title", title)),
            citation=f"Wikipedia · {data.get('title', title)}",
            snippet=extract[:1100],
            score=1.1,
            url=page_url,
        )]
    except Exception:
        return []


def _split_sentences(text: str) -> list[str]:
    clean = strip_html(text)
    raw = re.split(r"(?<=[.!?])\s+", clean)
    return [s.strip() for s in raw if 38 <= len(s.strip()) <= 340]


def _score_sentence(sent: str, q_tokens: Sequence[str], base_score: float) -> float:
    low = sent.lower()
    s_tokens = set(re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", low))
    matched = sum(1 for t in q_tokens if t in s_tokens or t in low)
    if q_tokens and matched == 0:
        return 0.0
    coverage = matched / max(1, len(q_tokens))
    mech = sum(1 for m in _MECHANISM_CUES if m in s_tokens)
    length_bonus = 0.25 if 65 <= len(sent) <= 240 else 0.0
    return base_score + (2.6 * coverage) + min(0.75, 0.18 * mech) + length_bonus


def _jaccard(a: str, b: str) -> float:
    sa = set(content_tokens(a))
    sb = set(content_tokens(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def synthesize_evidence(query: str, hits: Sequence[EvidenceHit], max_sentences: int = 3) -> tuple[str, str]:
    """Pure-Python extractive evidence synthesizer (0 LLM tokens, zero hallucinated claims)."""
    if not hits:
        return "No matching zero-token local or open-science records were found for that query.", ""
    q_tokens = content_tokens(query)
    scored: list[tuple[float, str, str]] = []
    caveat_candidates: list[tuple[float, str, str]] = []
    for hit in hits:
        for sent in _split_sentences(hit.snippet):
            sc = _score_sentence(sent, q_tokens, hit.score)
            if sc <= 0.0:
                continue
            low = sent.lower()
            if any(cue in low for cue in _CAVEAT_CUES):
                caveat_candidates.append((sc, sent, hit.citation))
            scored.append((sc, sent, hit.citation))
    scored.sort(key=lambda item: item[0], reverse=True)

    chosen: list[tuple[str, str]] = []
    for _sc, sent, cite in scored:
        if any(_jaccard(sent, prev) > 0.55 for prev, _ in chosen):
            continue
        chosen.append((sent, cite))
        if len(chosen) >= max_sentences:
            break

    if not chosen:
        top = hits[0]
        summary = f"{top.snippet[:320].rstrip('.')} [{top.citation}]."
    else:
        summary = " ".join(f"{s.rstrip('.')} [{c}]." for s, c in chosen)

    caveat_candidates.sort(key=lambda item: item[0], reverse=True)
    caveat = f"{caveat_candidates[0][1].rstrip('.')} [{caveat_candidates[0][2]}]." if caveat_candidates else ""
    return summary, caveat


def is_biomedical_query(query: str) -> bool:
    tokens = set(content_tokens(query))
    return bool(tokens & _BIOMED_CUES)


def is_research_question(raw: str) -> bool:
    """Return True when a plain chat turn looks like a substantive knowledge/research question."""
    low = " ".join(str(raw or "").lower().split())
    if not low or len(low) < 10:
        return False
    casual_prefixes = (
        "hi", "hello", "hey", "thanks", "thank you", "good morning", "good night",
        "how are you", "what do you think", "do you like", "i feel", "i am ", "what if ",
    )
    if low.startswith(casual_prefixes):
        return False
    tokens = content_tokens(low)
    if len(tokens) < 2:
        return False
    return low.endswith("?") or low.startswith((
        "what is ", "what are ", "what does ", "how does ", "how do ", "why does ", "why do ",
        "explain ", "define ", "describe ", "compare ", "mechanism of ", "role of ",
    )) or is_biomedical_query(low)


class ZeroTokenResearchEngine:
    """Unified 0-token local + open-science research engine with self-growing SQLite FTS5 cache."""

    def __init__(
        self,
        zoe_root: Path,
        *,
        dorothy_library: Any | None = None,
        evidence_index: Any | None = None,
        cache_path: Path | str | None = None,
        fetchers: dict[str, Callable[[str], list[EvidenceHit]]] | None = None,
    ):
        self.zoe_root = Path(zoe_root).resolve()
        self.encyclopedia = DorothyEncyclopediaIndex(self.zoe_root)
        self.dorothy_library = dorothy_library
        self.evidence_index = evidence_index
        self.cache = ZeroTokenKnowledgeCache(cache_path)
        self.fetchers: dict[str, Callable[[str], list[EvidenceHit]]] = fetchers or {
            "pubmed": lambda q: fetch_europe_pmc(q, limit=4),
            "arxiv": lambda q: fetch_arxiv(q, limit=3),
            "wikipedia": lambda q: fetch_wikipedia(q),
        }

    def search_local_library(self, query: str, limit: int = 3, min_overlap: float = 0.5) -> list[EvidenceHit]:
        """Query the 6,130-chapter local Dorothy Brain Library with strict token-overlap gating."""
        if self.dorothy_library is None:
            return []
        q_tokens = content_tokens(query)
        if not q_tokens:
            return []
        raw_hits = self.dorothy_library.search(query, limit=max(limit * 2, 6))
        out: list[EvidenceHit] = []
        for item in raw_hits:
            title = str(item.get("book_title", ""))
            chap = str(item.get("chapter_title", ""))
            excerpt = strip_html(item.get("excerpt", ""))
            hay = f"{title} {chap} {excerpt}".lower()
            matched = sum(1 for t in q_tokens if t in hay)
            overlap = matched / len(q_tokens)
            if len(q_tokens) >= 2 and matched < 2 and overlap < min_overlap:
                continue
            if overlap < min_overlap:
                continue
            out.append(EvidenceHit(
                source="dorothy_library",
                title=f"{title} :: {chap}",
                citation=f"Dorothy Library · {title} ({chap})",
                snippet=excerpt or f"{title} — {chap}",
                score=round(0.95 + overlap, 3),
            ))
        out.sort(key=lambda h: h.score, reverse=True)
        return out[:limit]

    def _collect_local_hits(self, query: str) -> list[EvidenceHit]:
        hits: list[EvidenceHit] = []
        hits.extend(self.encyclopedia.search(query, limit=2))
        hits.extend(self.search_local_library(query, limit=3, min_overlap=0.45))
        hits.extend(self.cache.search(query, limit=3))
        if self.evidence_index is not None:
            for item in self.evidence_index.search(query, limit=2):
                if float(item.get("score", 0.0)) >= 2.2:
                    chunk = item["chunk"]
                    hits.append(EvidenceHit(
                        source="monorepo",
                        title=chunk.citation,
                        citation=chunk.citation,
                        snippet=strip_html(chunk.content)[:420],
                        score=round(min(1.5, float(item["score"]) / 3.0), 3),
                    ))
        return hits

    def research(
        self,
        query: str,
        *,
        sources: Sequence[str] = ("local", "pubmed", "wikipedia", "arxiv"),
        allow_network: bool = True,
        medical_focus: bool = False,
    ) -> ZeroTokenReport:
        """Synthesize verified evidence across local vaults and free public science APIs (0 tokens)."""
        clean = " ".join(str(query or "").split())
        if not clean:
            raise ValueError("Provide a research question or topic.")
        hits: list[EvidenceHit] = []
        if "local" in sources:
            hits.extend(self._collect_local_hits(clean))

        remote_names = [s for s in sources if s in self.fetchers]
        if allow_network and remote_names:
            with ThreadPoolExecutor(max_workers=len(remote_names)) as pool:
                futs = [pool.submit(self.fetchers[name], clean) for name in remote_names]
                remote_hits: list[EvidenceHit] = []
                for fut in futs:
                    try:
                        remote_hits.extend(fut.result())
                    except Exception:
                        continue
            self.cache.upsert_hits(remote_hits)
            hits.extend(remote_hits)

        if medical_focus:
            hits.sort(key=lambda h: (h.source == "pubmed", h.score), reverse=True)
        else:
            hits.sort(key=lambda h: h.score, reverse=True)

        deduped: list[EvidenceHit] = []
        seen_keys: set[str] = set()
        for hit in hits:
            key = f"{hit.title.lower()[:70]}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(hit)
        top_hits = tuple(deduped[:6])
        summary, caveats = synthesize_evidence(clean, top_hits, max_sentences=4 if medical_focus else 3)
        a_tau = kloster_a_tau([h.score for h in top_hits], tau=DEFAULT_TAU)
        return ZeroTokenReport(
            query=clean,
            summary=summary,
            caveats=caveats,
            hits=top_hits,
            a_tau=a_tau,
            cached_count=self.cache.count(),
        )


def format_zero_token_report(report: ZeroTokenReport, *, heading: str = "Zoe Zero-Token Research") -> list[str]:
    """Render a ZeroTokenReport into clean terminal lines with citations and zero-token telemetry."""
    lines = [f"{heading} · {report.query}"]
    lines.append("")
    lines.append("[Synthesized Evidence · 0 LLM Tokens]")
    lines.append(report.summary)
    if report.caveats:
        lines.append("")
        lines.append("[Open Caveats / Uncertainties]")
        lines.append(report.caveats)
    if report.hits:
        lines.append("")
        lines.append(f"[Verified Sources · {len(report.hits)} matched · cache={report.cached_count}]")
        for hit in report.hits[:5]:
            link = f"  {hit.url}" if hit.url else ""
            lines.append(f"  • [{hit.source}] {hit.title[:96]} ({hit.citation}){link}")
    lines.append("")
    lines.append(
        f"tokens_used=0 ($0.00) · A_{report.tau:.2f}={report.a_tau}/{max(1, len(report.hits))} · "
        "clinical_action_authorized=False · cure_claim=False · sentience_claimed=False"
    )
    return lines
