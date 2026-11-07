from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

from .field import _canonical
from .volume import measure_probabilities


TOKEN = re.compile(r"[a-z][a-z0-9_+./-]*|[0-9]+(?:\.[0-9]+)?|[^\w\s]", re.IGNORECASE)
SOURCE_SUFFIXES = {".html", ".htm", ".xhtml", ".txt", ".md", ".vhd", ".vhdl", ".v", ".sv", ".cpp", ".h", ".py"}
DOCUMENT_FIELDS = {"schema_version", "instrument", "model_type", "vocabulary", "counts", "unigram", "documents", "total_tokens", "digest"}
MAX_VOCABULARY = 2048


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def tokenize(text):
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("Cog text must be nonempty and at most 8 MiB")
    tokens = TOKEN.findall(text.lower())
    if not tokens or len(tokens) > 500000:
        raise ValueError("Cog text must contain 1-500000 tokens")
    return tokens


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text_from_html(text):
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return " ".join(parser.parts)


@dataclass
class Cog:
    vocabulary: list[str]
    counts: dict[str, dict[str, int]]
    unigram: dict[str, int]
    documents: list[dict]
    total_tokens: int
    _reverse: dict = field(default_factory=dict, init=False, repr=False)
    _reverse_unigram: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        if not isinstance(self.vocabulary, list) or any(not isinstance(token, str) or not 1 <= len(token) <= 256 for token in self.vocabulary):
            raise ValueError("Cog vocabulary must be bounded text")
        if len(self.vocabulary) < 4 or len(self.vocabulary) > MAX_VOCABULARY or len(set(self.vocabulary)) != len(self.vocabulary):
            raise ValueError("Cog vocabulary must contain 4-2048 unique tokens")
        if not {"<s>", "</s>", "<unk>"} <= set(self.vocabulary):
            raise ValueError("Cog vocabulary is missing boundary tokens")
        if isinstance(self.total_tokens, bool) or not isinstance(self.total_tokens, int) or not 1 <= self.total_tokens <= 500000:
            raise ValueError("Cog total token count is outside training bounds")
        if not isinstance(self.documents, list) or not self.documents or len(self.documents) > 16 or any(not isinstance(document, dict) for document in self.documents):
            raise ValueError("Cog requires 1-16 source documents")
        if not isinstance(self.unigram, dict) or set(self.unigram) != set(self.vocabulary):
            raise ValueError("Cog unigram and vocabulary disagree")
        if not isinstance(self.counts, dict):
            raise ValueError("Cog transitions must be a mapping")
        for previous, following in self.counts.items():
            if previous not in self.vocabulary or not isinstance(following, dict) or not following:
                raise ValueError("invalid Cog context")
            for token, count in following.items():
                if token not in self.vocabulary or isinstance(count, bool) or not isinstance(count, int) or count < 1:
                    raise ValueError("invalid Cog transition count")
        if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in self.unigram.values()):
            raise ValueError("invalid Cog unigram count")

    @classmethod
    def train(cls, documents, max_vocabulary=512):
        if isinstance(max_vocabulary, bool) or not isinstance(max_vocabulary, int) or not 16 <= max_vocabulary <= MAX_VOCABULARY:
            raise ValueError("Cog vocabulary limit must be between 16 and 2048")
        if not isinstance(documents, (list, tuple)) or not 1 <= len(documents) <= 16:
            raise ValueError("Cog training requires 1-16 documents")
        tokenized = []
        metadata = []
        for text, source in documents:
            tokens = tokenize(text)
            if not isinstance(source, str) or not 1 <= len(source) <= 4096:
                raise ValueError("Cog source label must contain 1-4096 characters")
            tokenized.append(tokens)
            metadata.append({"source": source, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "bytes": len(text.encode("utf-8")), "tokens": len(tokens)})
        if sum(len(tokens) for tokens in tokenized) > 500000:
            raise ValueError("Cog training corpus exceeds 500000 tokens")
        frequencies = Counter(token for tokens in tokenized for token in tokens)
        retained = sorted(frequencies, key=lambda token: (-frequencies[token], token))[:max_vocabulary - 3]
        vocabulary = ["<s>", "</s>", "<unk>", *retained]
        known = set(vocabulary)
        counts = {}
        unigram = Counter({token: 0 for token in vocabulary})
        for tokens in tokenized:
            mapped = [token if token in known else "<unk>" for token in tokens]
            unigram.update(mapped)
            for previous, current in zip(["<s>", *mapped], [*mapped, "</s>"]):
                counts.setdefault(previous, Counter())[current] += 1
        normalized = {previous: dict(sorted(following.items())) for previous, following in sorted(counts.items())}
        return cls(vocabulary, normalized, dict(unigram), metadata, sum(len(tokens) for tokens in tokenized))

    @classmethod
    def from_paths(cls, paths, max_vocabulary=512):
        if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= 16:
            raise ValueError("Cog requires 1-16 explicit text paths")
        documents = []
        sources = []
        for item in paths:
            path = Path(item)
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                raise ValueError("Cog input must be text, Markdown, HTML, HDL, C/C++, or Python")
            raw = path.read_bytes()
            if not raw or len(raw) > 2 * 1024 * 1024:
                raise ValueError(f"Cog source must contain 1 byte to 2 MiB: {path}")
            text = raw.decode("utf-8", errors="replace")
            if path.suffix.lower() in {".html", ".htm", ".xhtml"}:
                text = text_from_html(text)
            documents.append((text, str(path)))
            sources.append((raw, text))
        model = cls.train(documents, max_vocabulary)
        for record, (raw, text) in zip(model.documents, sources):
            record.update({"file_sha256": hashlib.sha256(raw).hexdigest(), "file_bytes": len(raw), "decode_replacements": text.count("\ufffd")})
        return model

    def _token(self, token):
        token = token.lower()
        return token if token in self.vocabulary else "<unk>"

    def _backward(self):
        if not self._reverse:
            reverse = {}
            unigram = Counter({token: 0 for token in self.vocabulary})
            for previous, following in self.counts.items():
                for token, count in following.items():
                    reverse.setdefault(token, Counter())[previous] += count
                    unigram[previous] += count
            self._reverse = {previous: dict(following) for previous, following in reverse.items()}
            self._reverse_unigram = dict(unigram)
        return self._reverse, self._reverse_unigram

    def distribution(self, token, reverse=False, alpha=0.1):
        if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not math.isfinite(alpha) or not 0 < alpha <= 10:
            raise ValueError("Cog smoothing must be in (0, 10]")
        counts, unigram = self._backward() if reverse else (self.counts, self.unigram)
        token = self._token(token)
        following = counts.get(token, {})
        total = sum(following.values())
        global_total = sum(unigram.values())
        probabilities = []
        for candidate in self.vocabulary:
            prior = unigram[candidate] / global_total if global_total else 0
            probability = (following.get(candidate, 0) + alpha * prior) / (total + alpha)
            probabilities.append(probability)
        normalization = sum(probabilities)
        probabilities = [probability / normalization for probability in probabilities]
        return [{"token": candidate, "probability": probability, "count": following.get(candidate, 0)} for candidate, probability in zip(self.vocabulary, probabilities)]

    def walk(self, text, steps=6, reverse=False, tau=0.05):
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 32:
            raise ValueError("Cog steps must be between 1 and 32")
        if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not math.isfinite(tau) or not 0 <= tau < 1:
            raise ValueError("Cog tau must be in [0, 1)")
        tokens = [self._token(token) for token in tokenize(text)]
        history = []
        for _ in range(steps):
            distribution = self.distribution(tokens[-1] if not reverse else tokens[0], reverse=reverse)
            chosen = min(distribution, key=lambda item: (-item["probability"], item["token"]))
            if reverse:
                tokens.insert(0, chosen["token"])
            else:
                tokens.append(chosen["token"])
            measurement = measure_probabilities([item["probability"] for item in distribution], thresholds=[tau])
            history.append({
                "context": tokens[1] if reverse else tokens[-2],
                "selected": chosen["token"],
                "top_candidates": sorted(distribution, key=lambda item: (-item["probability"], item["token"]))[:8],
                "vocabulary_size": len(distribution),
                "accessible_volume": measurement["threshold_sweep"][0]["accessible_volume"],
                "tau": tau,
                "distribution_sha256": _digest(distribution),
            })
            if chosen["token"] in {"<s>", "</s>"}:
                break
        visible = [token for token in tokens if token not in {"<s>", "</s>"}]
        return {
            "direction": "backward" if reverse else "forward",
            "tokens": tokens,
            "text": " ".join(visible),
            "steps": history,
            "review_required": True,
            "command_authorized": False,
            "fact_claimed": False,
        }

    def document(self):
        result = {
            "schema_version": 1,
            "instrument": "zoe-cog",
            "model_type": "bounded_interpolated_bigram",
            "vocabulary": self.vocabulary,
            "counts": self.counts,
            "unigram": self.unigram,
            "documents": self.documents,
            "total_tokens": self.total_tokens,
        }
        result["digest"] = _digest(result)
        return result

    def save(self, path):
        path = Path(path)
        if path.suffix.lower() != ".json":
            raise ValueError("Cog models must use a .json path")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(self.document()) + "\n")
        return path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Cog model exceeds 64 MiB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != DOCUMENT_FIELDS or data.get("schema_version") != 1 or data.get("instrument") != "zoe-cog" or data.get("model_type") != "bounded_interpolated_bigram":
            raise ValueError("unsupported Cog model")
        expected = _digest({key: value for key, value in data.items() if key != "digest"})
        if data["digest"] != expected:
            raise ValueError("Cog model digest mismatch")
        if isinstance(data["total_tokens"], bool) or not isinstance(data["total_tokens"], int) or not 1 <= data["total_tokens"] <= 500000:
            raise ValueError("Cog model token count exceeds training bounds")
        return cls(data["vocabulary"], data["counts"], data["unigram"], data["documents"], data["total_tokens"])


def demo_cog():
    return Cog.train([
        ("inspect the artifact before signing the update . verify the signature before testing the hardware .", "zoe-demo-inspect"),
        ("read the source before assigning a name . preserve uncertainty before proposing the next test .", "zoe-demo-evidence"),
        ("a small cog can turn a larger cog . a probability is not permission to act .", "zoe-demo-play"),
    ])


def demo_cog_report():
    model = demo_cog()
    forward = model.walk("inspect", steps=5)
    backward = model.walk("update", steps=5, reverse=True)
    return {
        "model_type": "bounded_interpolated_bigram",
        "vocabulary_size": len(model.vocabulary),
        "forward": forward,
        "backward": backward,
        "summary": f"Cog: {forward['text']}\nBackward: {backward['text']}\nToken forecasts are review-only; no command is generated.",
    }
