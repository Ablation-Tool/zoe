"""Sequence encoders for semantic scoring (Stage 3).

Two encoder classes:

  ESM2Encoder         -- for protein sequences
                         Model: facebook/esm2_t6_8M_UR50D (8M params)
                         Trained on UniRef50 protein sequences

  NucleotideEncoder   -- for DNA and RNA sequences
                         Model: zhihan1996/DNABERT-2 (117M params)
                         Trained on multi-species genomic DNA; handles RNA
                         by accepting U as a valid token (equivalent to T
                         for embedding purposes)

Both encoders:
  - Lazy-load (model downloaded on first encode() call)
  - Mean-pool over the sequence dimension to produce one vector per sequence
  - L2-normalize output so dot product == cosine similarity
  - Truncate sequences longer than the model's positional limit

Using these encoders
--------------------
You do not need to use an encoder to run the pipeline. HomologFinder works
with encoder=None and uses Jaccard alone. Encoders add the Stage 3 semantic
tiebreak and improve recall for highly diverged sequences.

Model download happens automatically from HuggingFace Hub on first use.
Sizes: ESM2 8M ~32 MB, DNABERT-2 ~450 MB.
"""

from __future__ import annotations
from typing import Optional
import numpy as np

_ESM2_MAX_LEN   = 1022   # ESM2 positional limit minus BOS/EOS tokens
_DNABERT2_MAX   = 512    # DNABERT-2 max input length in base pairs


class ESM2Encoder:
    """Protein sequence encoder using ESM2.

    facebook/esm2_t6_8M_UR50D is the smallest ESM2 variant -- 8M parameters,
    480-dimensional embeddings, practical on CPU (~1-2 seconds per batch).
    Larger variants (35M, 150M, 650M) give better accuracy at higher cost.
    """
    _DEFAULT_MODEL = "facebook/esm2_t6_8M_UR50D"

    def __init__(self, model_id: Optional[str] = None, device: str = 'cpu'):
        self._model_id  = model_id or self._DEFAULT_MODEL
        self._device    = device
        self._model     = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from transformers import EsmTokenizer, EsmModel
        self._tokenizer = EsmTokenizer.from_pretrained(self._model_id)
        self._model     = EsmModel.from_pretrained(self._model_id)
        self._model.eval()

    def encode(self, sequences: list[str]) -> np.ndarray:
        """Return (N, D) float32 L2-normalized embeddings."""
        import torch
        self._load()
        truncated = [s[:_ESM2_MAX_LEN] for s in sequences]
        inputs = self._tokenizer(
            truncated, return_tensors='pt', padding=True,
            truncation=True, max_length=_ESM2_MAX_LEN + 2,
        )
        with torch.no_grad():
            out = self._model(**inputs)
        mask   = inputs['attention_mask'].unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
        vecs   = pooled.cpu().numpy().astype(np.float32)
        norms  = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms < 1e-9, 1.0, norms)

    def encode_one(self, sequence: str) -> np.ndarray:
        return self.encode([sequence])[0]


class NucleotideEncoder:
    """DNA/RNA sequence encoder using DNABERT-2.

    DNABERT-2 was pretrained on multi-species genomic sequences. It uses a
    Byte-Pair Encoding tokenizer, not fixed k-mer tokens, so it handles
    arbitrary sequences without preprocessing. RNA sequences (with U instead
    of T) are accepted; the model treats U identically to T for tokenization.

    For very long sequences (>512 bp), this encoder splits into non-overlapping
    windows and averages the embeddings. This loses positional context at window
    boundaries but preserves overall sequence composition.
    """
    _DEFAULT_MODEL = "zhihan1996/DNABERT-2"

    def __init__(self, model_id: Optional[str] = None, device: str = 'cpu'):
        self._model_id  = model_id or self._DEFAULT_MODEL
        self._device    = device
        self._model     = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModel
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_id, trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            self._model_id, trust_remote_code=True
        )
        self._model.eval()

    def _encode_single(self, sequence: str) -> np.ndarray:
        import torch
        # RNA -> DNA for tokenizer compatibility (U is not in DNABERT vocab)
        seq_dna = sequence.replace('U', 'T')

        if len(seq_dna) <= _DNABERT2_MAX:
            windows = [seq_dna]
        else:
            windows = [
                seq_dna[i:i+_DNABERT2_MAX]
                for i in range(0, len(seq_dna), _DNABERT2_MAX)
            ]

        window_vecs = []
        for w in windows:
            inputs = self._tokenizer(
                w, return_tensors='pt', padding=True,
                truncation=True, max_length=_DNABERT2_MAX,
            )
            with torch.no_grad():
                out = self._model(**inputs)
            mask   = inputs['attention_mask'].unsqueeze(-1).float()
            pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
            window_vecs.append(pooled.cpu().numpy().astype(np.float32))

        vec = np.mean(window_vecs, axis=0).squeeze()
        norm = np.linalg.norm(vec)
        return vec / (norm if norm > 1e-9 else 1.0)

    def encode(self, sequences: list[str]) -> np.ndarray:
        """Return (N, D) float32 L2-normalized embeddings."""
        self._load()
        return np.stack([self._encode_single(s) for s in sequences])

    def encode_one(self, sequence: str) -> np.ndarray:
        return self.encode([sequence])[0]
