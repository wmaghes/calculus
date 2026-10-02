"""Semantic embedding backends.

The backend is swappable (Embedder protocol). Two exist:

* LSAEmbedder (default, fully offline). A latent semantic analysis model
  (TF-IDF + truncated SVD) trained per case on that case's own chunks only.
  It needs no downloaded weights, so there is no model supply chain and no
  model shared across cases. It captures co-occurrence ("reefer" near
  "temperature") but is weaker than a neural model at paraphrase.
* A neural backend (e.g. bge-small via ONNX Runtime) is the intended upgrade.
  It is NOT included yet: its weights could not be fetched in the
  development environment, and weights must be provisioned offline and
  pinned by SHA-256 before use (SECURITY.md, open items).

The trained model and all vectors are serialized with numpy (no pickle),
then sealed with the case's vector key by the store.
"""

from __future__ import annotations

import io
import math
import re
from collections import Counter

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below between both
but by can could did do does doing down during each everything few find for from further had has have having he her here
hers him his how i if in into is it its itself just me more most my no nor not of off on once only or other
our out over own same she should so some such than that the their them then there these they this those
through to too under until up very was we were what when where which while who whom why will with would you
your show me list documents docs anything regarding related concerning involving
""".split())

MAX_VOCAB = 100_000
DIM = 200


def stem(t: str) -> str:
    """Deliberately light suffix stripping so "excursions"/"excursion" and
    "shipped"/"shipping" meet. (FTS5 uses the Porter stemmer separately.)"""
    if t.isdigit() or len(t) <= 4:
        return t
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if t.endswith(suf) and not t.endswith("ss") and len(t) - len(suf) >= 4:
            return t[: len(t) - len(suf)] + rep
    return t


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


def raw_terms(text: str) -> list[str]:
    """Unstemmed content words (for building FTS queries)."""
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


class LSAEmbedder:
    name = "lsa-v1"

    def __init__(self, vocab: dict[str, int], idf: np.ndarray, proj: np.ndarray):
        self.vocab, self.idf, self.proj = vocab, idf, proj

    @property
    def dim(self) -> int:
        return self.proj.shape[1]

    # -- training -----------------------------------------------------------
    @classmethod
    def train(cls, texts: list[str]) -> tuple["LSAEmbedder", np.ndarray]:
        """Returns the model and the (normalized) vectors for `texts`."""
        from scipy.sparse import csr_matrix
        from scipy.sparse.linalg import svds

        docs = [Counter(tokenize(t)) for t in texts]
        df = Counter()
        for d in docs:
            df.update(d.keys())
        terms = [t for t, _ in df.most_common(MAX_VOCAB)]
        vocab = {t: i for i, t in enumerate(sorted(terms))}
        n = len(texts)
        idf = np.zeros(len(vocab), dtype=np.float32)
        for t, i in vocab.items():
            idf[i] = math.log((1 + n) / (1 + df[t])) + 1.0
        rows, cols, vals = [], [], []
        for r, d in enumerate(docs):
            for t, c in d.items():
                i = vocab.get(t)
                if i is not None:
                    rows.append(r)
                    cols.append(i)
                    vals.append((1.0 + math.log(c)) * idf[i])
        x = csr_matrix((np.array(vals, dtype=np.float32), (rows, cols)), shape=(n, max(1, len(vocab))))
        x = _row_normalize_sparse(x)
        k = min(DIM, min(x.shape) - 1)
        if k >= 2:
            _, _, vt = svds(x, k=k, random_state=0)
            proj = np.ascontiguousarray(vt.T.astype(np.float32))
        else:  # tiny corpus: fall back to identity (pure TF-IDF space)
            proj = np.eye(x.shape[1], dtype=np.float32)
        model = cls(vocab, idf, proj)
        return model, _normalize(np.asarray(x @ proj, dtype=np.float32))

    # -- use ----------------------------------------------------------------
    def embed_query(self, text: str) -> np.ndarray | None:
        counts = Counter(tokenize(text))
        v = np.zeros(len(self.vocab) or 1, dtype=np.float32)
        hit = False
        for t, c in counts.items():
            i = self.vocab.get(t)
            if i is not None:
                v[i] = (1.0 + math.log(c)) * self.idf[i]
                hit = True
        if not hit:
            return None
        v /= np.linalg.norm(v) or 1.0
        return _normalize((v @ self.proj)[None, :])[0]

    def known_fraction(self, text: str) -> float:
        """Share of the query's distinct terms that this case's model knows.
        A query that is mostly out-of-vocabulary gets a vector built from one
        or two words, so its similarities are discounted accordingly."""
        terms = set(tokenize(text))
        return (sum(t in self.vocab for t in terms) / len(terms)) if terms else 0.0

    # -- serialization (no pickle) -------------------------------------------
    def to_arrays(self) -> dict[str, np.ndarray]:
        terms = sorted(self.vocab, key=self.vocab.get)
        return {"lsa_terms": np.array(terms, dtype=np.str_), "lsa_idf": self.idf, "lsa_proj": self.proj}

    @classmethod
    def from_arrays(cls, a) -> "LSAEmbedder":
        terms = [str(t) for t in a["lsa_terms"]]
        return cls({t: i for i, t in enumerate(terms)}, a["lsa_idf"], a["lsa_proj"])


def _row_normalize_sparse(x):
    from scipy.sparse import diags

    norms = np.sqrt(np.asarray(x.multiply(x).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    return diags(1.0 / norms) @ x


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class VectorIndex:
    """Exact (brute-force) cosine search. Exact on purpose: approximate
    nearest-neighbour indexes trade recall for speed, and missed documents
    are the costly error in review. ~1M chunks x 200 dims fits in ~800 MB
    (float32) and scores in well under a second on one core."""

    def __init__(self, model: LSAEmbedder, chunk_ids: np.ndarray, vectors: np.ndarray):
        self.model, self.chunk_ids, self.vectors = model, chunk_ids, vectors

    @classmethod
    def build(cls, rows: list[tuple[int, str]]) -> "VectorIndex":
        ids = np.array([r[0] for r in rows], dtype=np.int64)
        model, vecs = LSAEmbedder.train([r[1] for r in rows]) if rows else (LSAEmbedder({}, np.zeros(0, np.float32), np.zeros((1, 1), np.float32)), np.zeros((0, 1), np.float32))
        return cls(model, ids, vecs.astype(np.float32))

    def search(self, query: str, allowed: set[int], limit: int, min_score: float = 0.0) -> list[tuple[int, float]]:
        if len(self.chunk_ids) == 0:
            return []
        q = self.model.embed_query(query)
        if q is None:
            return []
        # Permission filter BEFORE ranking: disallowed chunks never compete.
        mask = np.fromiter((cid in allowed for cid in self.chunk_ids), dtype=bool, count=len(self.chunk_ids))
        if not mask.any():
            return []
        idx = np.nonzero(mask)[0]
        scores = (self.vectors[idx] @ q) * self.model.known_fraction(query)
        order = np.argsort(-scores)[:limit]
        return [(int(self.chunk_ids[idx[j]]), float(scores[j])) for j in order if scores[j] >= min_score]

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        np.savez(buf, backend=np.array(self.model.name), chunk_ids=self.chunk_ids, vectors=self.vectors,
                 **self.model.to_arrays())
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "VectorIndex":
        a = np.load(io.BytesIO(data), allow_pickle=False)
        if str(a["backend"]) != LSAEmbedder.name:
            raise ValueError("unknown_vector_backend")
        return cls(LSAEmbedder.from_arrays(a), a["chunk_ids"], a["vectors"])
