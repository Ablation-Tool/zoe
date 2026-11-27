"""Runtime RAG over the bundled O'Reilly book corpus.

Pure-Python, dependency-free, offline, deterministic. Indexes the per-book
`_combined.md` extractions under `books/` with BM25 and answers passage queries.

Why BM25 and not embeddings: it needs no model download, no network, and no
third-party package, so `PromptArchitect` stays a self-contained import. The
`Retriever` protocol below lets an embedding backend (chromadb, sentence-
transformers, an API) be swapped in later without touching the architect.

Design grounding: lexical retrieval over a curated corpus is the baseline
retrieval-augmentation pattern (Pai, *Designing LLM Applications*, RAG chapters);
chunking with overlap preserves cross-paragraph context.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Union, runtime_checkable

from .models import Retrieved

# Small, deliberately conservative stopword set. Keeping it short avoids dropping
# domain terms that matter for prompt-engineering queries ("format", "output").
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in into is it its of on or
    that the their then there these this to was were will with we you your""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# BM25 tuning. k1 controls term-frequency saturation; b controls length
# normalization. 1.5 / 0.75 are the long-standing defaults.
_K1 = 1.5
_B = 0.75

# A book scope is one slug, an iterable of slugs, or None (corpus-wide).
BookScope = Union[str, Iterable[str], None]

_CACHE_VERSION = 3  # bump when chunking or index format changes (v3: pickle -> json)


def tokenize(text: str) -> List[str]:
    """Lowercase, split on word boundaries, drop stopwords and 1-char tokens."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in _STOPWORDS]


@runtime_checkable
class Retriever(Protocol):
    """Pluggable retrieval backend. Swap BM25 for embeddings by implementing this."""

    def search(self, query: str, k: int = 5, book: "BookScope" = None) -> List[Retrieved]:
        ...


class _Chunk:
    """One indexed passage. __slots__ keeps thousands of these lightweight."""

    __slots__ = ("book", "text", "tf", "length")

    def __init__(self, book: str, text: str, tf: Dict[str, int], length: int) -> None:
        self.book = book
        self.text = text
        self.tf = tf
        self.length = length


class BookCorpus:
    """BM25 index over the `books/*/_combined.md` extractions.

    Builds on first use, caches to disk (JSON) keyed on the source files' content
    hash plus the chunking parameters, and answers `search()` queries. Implements
    `Retriever`.
    """

    def __init__(
        self,
        books_dir: Optional[str] = None,
        chunk_words: int = 220,
        overlap: int = 40,
        cache: bool = True,
    ) -> None:
        # Guard the chunking geometry up front. overlap >= chunk_words collapses the
        # window step to 1 (see _chunk), which silently builds a near-quadratic,
        # massively duplicated index and skews the idf statistics. Fail loud instead.
        if chunk_words < 1:
            raise ValueError(f"chunk_words must be >= 1, got {chunk_words}")
        if overlap < 0 or overlap >= chunk_words:
            raise ValueError(
                f"overlap must satisfy 0 <= overlap < chunk_words; got overlap={overlap}, "
                f"chunk_words={chunk_words}"
            )
        self.books_dir = Path(books_dir) if books_dir else Path(__file__).parent / "books"
        self.chunk_words = chunk_words
        self.overlap = overlap
        self.cache = cache

        self._chunks: List[_Chunk] = []
        self._idf: Dict[str, float] = {}
        self._avgdl: float = 0.0
        self._built = False

    # ------------------------------------------------------------------ #
    # Index lifecycle
    # ------------------------------------------------------------------ #

    def build(self) -> "BookCorpus":
        """Build (or load from cache) the BM25 index. Idempotent."""
        if self._built:
            return self
        if not self.books_dir.is_dir():
            raise FileNotFoundError(f"books_dir not found: {self.books_dir}")

        combined = sorted(self.books_dir.glob("*/_combined.md"))
        if not combined:
            raise FileNotFoundError(
                f"no '*/_combined.md' files under {self.books_dir}; run colophon with -combined"
            )

        if self.cache and self._load_cache(combined):
            self._built = True
            return self

        self._index(combined)
        if self.cache:
            self._save_cache(combined)
        self._built = True
        return self

    def _index(self, combined: List[Path]) -> None:
        chunks: List[_Chunk] = []
        df: Dict[str, int] = {}
        for path in combined:
            book = path.parent.name
            text = path.read_text(encoding="utf-8", errors="replace")
            for passage in self._chunk(text):
                tokens = tokenize(passage)
                if not tokens:
                    continue
                tf: Dict[str, int] = {}
                for tok in tokens:
                    tf[tok] = tf.get(tok, 0) + 1
                chunks.append(_Chunk(book, passage, tf, len(tokens)))
                for term in tf:
                    df[term] = df.get(term, 0) + 1

        n = len(chunks)
        if n == 0:
            raise ValueError("corpus produced zero indexable chunks")
        # BM25+ idf: the `1 +` inside the log keeps idf strictly positive (classic
        # BM25 idf goes negative for terms in most documents), so very common terms
        # still contribute a small positive weight rather than zero or negative.
        self._idf = {
            term: math.log(1 + (n - d + 0.5) / (d + 0.5)) for term, d in df.items()
        }
        self._avgdl = sum(c.length for c in chunks) / n
        self._chunks = chunks

    def _chunk(self, text: str) -> List[str]:
        """Word-window chunks with overlap, split on blank-line paragraph runs.

        Markdown headings and short fragments are folded into the running window
        so each chunk carries enough context to be independently meaningful.
        """
        # Normalize whitespace within paragraphs; keep paragraph breaks.
        paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
        words: List[str] = []
        for p in paras:
            if p:
                words.extend(p.split(" "))
        chunks: List[str] = []
        # __init__ guarantees overlap < chunk_words, so step >= 1 without clamping.
        step = self.chunk_words - self.overlap
        for start in range(0, len(words), step):
            window = words[start : start + self.chunk_words]
            chunks.append(" ".join(window))
            if start + self.chunk_words >= len(words):
                break
        return chunks

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search(self, query: str, k: int = 5, book: "BookScope" = None) -> List[Retrieved]:
        """Return the top-k passages for `query`, optionally scoped to a book set.

        `book` may be a single slug, an iterable of slugs, or None (corpus-wide).
        An empty iterable means "no book matches" and yields no results, rather
        than silently widening to the whole corpus.
        """
        if not self._built:
            self.build()
        q_terms = tokenize(query)
        if not q_terms:
            return []
        # Pre-resolve idf for query terms once.
        q_idf = {t: self._idf.get(t, 0.0) for t in set(q_terms)}

        scope = self._normalize_scope(book)
        if scope is not None and not scope:
            return []

        scored: List[tuple] = []
        for cid, chunk in enumerate(self._chunks):
            if scope is not None and chunk.book not in scope:
                continue
            score = self._bm25(q_idf, chunk)
            if score > 0:
                scored.append((score, cid, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Retrieved] = []
        for score, cid, chunk in scored[:k]:
            results.append(
                Retrieved(
                    book=chunk.book,
                    chunk_id=cid,
                    score=round(float(score), 4),
                    text=chunk.text,
                )
            )
        return results

    @staticmethod
    def _normalize_scope(book: "BookScope") -> Optional[frozenset]:
        """Normalize a book scope to None (corpus-wide) or a frozenset of slugs.

        A bare string is one slug; any other iterable becomes a slug set. Returning
        an empty frozenset is meaningful: the caller asked for a set that matched no
        book, so search returns nothing instead of widening to the whole corpus.
        """
        if book is None:
            return None
        if isinstance(book, str):
            return frozenset((book,))
        return frozenset(book)

    def _bm25(self, q_idf: Dict[str, float], chunk: _Chunk) -> float:
        score = 0.0
        norm = _K1 * (1 - _B + _B * chunk.length / self._avgdl)
        tf = chunk.tf
        for term, idf in q_idf.items():
            if idf == 0.0:
                continue
            f = tf.get(term, 0)
            if f == 0:
                continue
            score += idf * (f * (_K1 + 1)) / (f + norm)
        return score

    # ------------------------------------------------------------------ #
    # Cache (JSON keyed on source content + params)
    # ------------------------------------------------------------------ #
    #
    # Deliberately JSON, not pickle. The cache lives at `books_dir/.rag_cache.json`,
    # a path that is writable by design (the program writes it) and user-suppliable
    # (BookCorpus(books_dir=...)), and it is .gitignored, so it is never a shipped or
    # trusted artifact - it is always created at runtime in a writable location. A
    # pickle there would let any co-located writer of that directory plant a payload
    # that executes during pickle.load on the next build() (CWE-502: deserialization
    # of untrusted data). JSON has no code-execution path on load: a hostile cache
    # file can at worst feed wrong numbers, which the content-hash signature rejects.

    def _cache_path(self) -> Path:
        return self.books_dir / ".rag_cache.json"

    def _signature(self, combined: List[Path]) -> str:
        # Key on book identity (the parent slug - every file's basename is the
        # identical "_combined.md") and a content hash, not just size+mtime. mtime in
        # whole seconds plus a shared basename made two different books with equal
        # (size, mtime-second) collide to the same signature and serve a stale index.
        parts = [str(_CACHE_VERSION), str(self.chunk_words), str(self.overlap)]
        for p in combined:
            st = p.stat()
            digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            parts.append(f"{p.parent.name}:{st.st_size}:{st.st_mtime_ns}:{digest}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _load_cache(self, combined: List[Path]) -> bool:
        path = self._cache_path()
        if not path.is_file():
            return False
        try:
            with path.open("r", encoding="utf-8") as fh:
                blob = json.load(fh)
            if blob.get("sig") != self._signature(combined):
                return False
            self._chunks = [
                _Chunk(c["book"], c["text"], c["tf"], c["length"]) for c in blob["chunks"]
            ]
            self._idf = blob["idf"]
            self._avgdl = blob["avgdl"]
            return True
        except (OSError, ValueError, KeyError, TypeError):
            # Expected corrupt/incompatible-cache modes (unreadable file, bad JSON,
            # missing/renamed key, wrong shape): rebuild silently. Anything outside
            # this set is a real bug and is left to propagate rather than be masked.
            return False

    def _save_cache(self, combined: List[Path]) -> None:
        blob = {
            "sig": self._signature(combined),
            "avgdl": self._avgdl,
            "idf": self._idf,
            "chunks": [
                {"book": c.book, "text": c.text, "tf": c.tf, "length": c.length}
                for c in self._chunks
            ],
        }
        try:
            tmp = self._cache_path().with_name(".rag_cache.json.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(blob, fh)
            os.replace(tmp, self._cache_path())
        except OSError:
            # Read-only books dir: skip caching, not fatal.
            pass

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    @property
    def num_chunks(self) -> int:
        if not self._built:
            self.build()
        return len(self._chunks)

    def books(self) -> List[str]:
        if not self._built:
            self.build()
        return sorted({c.book for c in self._chunks})


if __name__ == "__main__":
    corpus = BookCorpus().build()
    print(f"indexed {corpus.num_chunks} chunks across {len(corpus.books())} books")
    for q in ("output format guardrails json schema", "context window token limit",
              "few-shot examples improve output", "reduce hallucination uncertainty"):
        print(f"\n### {q}")
        for r in corpus.search(q, k=2):
            print(f"  [{r['score']:.2f}] {r['book']}")
            print("    " + r["text"][:160].replace("\n", " ") + "...")
