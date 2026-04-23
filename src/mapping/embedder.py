import logging
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load and cache the embedding model (loaded once per process)."""
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    """Embed a single text string.

    Args:
        text: The text to embed.

    Returns:
        A 384-dimensional float list compatible with pgvector.
    """
    model = _get_model()
    vector: np.ndarray = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts more efficiently than calling embed_text in a loop.

    Args:
        texts: List of strings to embed.

    Returns:
        List of 384-dim float lists, one per input text.
    """
    if not texts:
        return []
    model = _get_model()
    vectors: np.ndarray = model.encode(
        texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=64, show_progress_bar=False
    )
    return [v.tolist() for v in vectors]
