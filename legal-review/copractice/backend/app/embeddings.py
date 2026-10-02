"""Local embeddings only. No text leaves the machine.

* SentenceTransformerEmbedder: bge-small-en-v1.5 (384 dims) loaded from a
  LOCAL directory (EMBED_MODEL_PATH). Hub downloads are disabled.
* DevHashEmbedder: feature hashing of word stems and bigrams into 384 dims.
  NOT semantic. For tests and for environments without the model weights;
  every search response names the embedder so this is never hidden.
"""

from __future__ import annotations

import hashlib
import os
import re

import numpy as np

DIM = 384
_WORD = re.compile(r"[a-z0-9]+")
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class DevHashEmbedder:
    name = "dev-hash (NOT semantic; test/dev only)"

    def _vec(self, text: str) -> np.ndarray:
        words = [w[:6] for w in _WORD.findall(text.lower()) if len(w) > 2]
        v = np.zeros(DIM, dtype=np.float32)
        for f in words + [a + "_" + b for a, b in zip(words, words[1:])]:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % DIM] += 1.0 if (h >> 63) else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, DIM), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class SentenceTransformerEmbedder:
    def __init__(self, path: str):
        if not path or not os.path.isdir(path):
            raise RuntimeError("EMBED_MODEL_PATH must point to a local model directory (no downloads)")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer  # optional dependency

        self._m = SentenceTransformer(path, device="cpu")
        if self._m.get_sentence_embedding_dimension() != DIM:
            raise RuntimeError(f"model must produce {DIM}-dim embeddings")
        self.name = "local:" + os.path.basename(path.rstrip("/"))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._m.encode(texts, normalize_embeddings=True, batch_size=32).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._m.encode([QUERY_PREFIX + text], normalize_embeddings=True)[0].astype(np.float32)


def from_settings(settings):
    if settings.embed_backend == "dev-hash":
        return DevHashEmbedder()
    return SentenceTransformerEmbedder(settings.embed_model_path or "")
