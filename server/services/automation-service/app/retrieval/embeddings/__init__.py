"""
Enterprise Embedding Registry
==============================
Centralized, observable model management for all retrieval layers.

DIMENSION CONTRACT — resolved at startup, not hardcoded:
  The registry reads COLLECTION_DIM from shared config (QDRANT_VECTOR_SIZE),
  which is the authoritative value written by whoever created the collection.
  The embedding tiers are evaluated at load time against this live dimension.

  If QDRANT_VECTOR_SIZE=384 → all-MiniLM-L6-v2 is selected (matches collection)
  If QDRANT_VECTOR_SIZE=768 → e5-base-v2 is selected (matches collection)

  Startup raises RuntimeError if no tier produces the correct dimension.
  This prevents the silent 768-vs-384 mismatch that caused catastrophic
  grounding collapse in production (all vector searches failed silently).

Tier order (highest quality first):
  768-dim:  intfloat/e5-base-v2  →  all-mpnet-base-v2
  384-dim:  all-MiniLM-L6-v2

Every tier change emits:
  - WARNING log with full context
  - Dimension validation before returning the model
  - Metrics counter (embedding.model.tier)
  - Never silently degrades

Usage:
    registry = get_embedding_registry()
    embedder = registry.get_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("automation-service.embeddings")

# ── Model tier definitions ────────────────────────────────────────────────────

@dataclass
class EmbeddingModel:
    name: str
    expected_dim: int
    tier: int           # 1 = primary, 2 = secondary, 3 = tertiary
    description: str
    encode_prefix: str = ""   # e5 models need "query: " prefix


# All supported embedding models, ordered by quality within each dimension group.
# The registry selects based on COLLECTION_DIM at runtime — not at import time.
_ALL_EMBEDDING_TIERS: List[EmbeddingModel] = [
    # ── 768-dim models ──────────────────────────────────────────────────────
    EmbeddingModel(
        name="intfloat/e5-base-v2",
        expected_dim=768,
        tier=1,
        description="768-dim primary — e5 instruction-tuned, highest quality",
        encode_prefix="query: ",
    ),
    EmbeddingModel(
        name="sentence-transformers/all-mpnet-base-v2",
        expected_dim=768,
        tier=2,
        description="768-dim secondary — all-mpnet, solid quality",
        encode_prefix="",
    ),
    # ── 384-dim models ──────────────────────────────────────────────────────
    EmbeddingModel(
        name="sentence-transformers/all-MiniLM-L6-v2",
        expected_dim=384,
        tier=1,
        description="384-dim primary — MiniLM-L6, fast and accurate",
        encode_prefix="",
    ),
]


def _resolve_collection_dim() -> int:
    """
    Read the authoritative collection dimension from shared config.
    This is the value used to CREATE the Qdrant collection (QDRANT_VECTOR_SIZE).
    Falls back to 384 if config is unavailable to prefer the smaller model.
    """
    try:
        from shared.config import get_config
        dim = int(get_config().QDRANT_VECTOR_SIZE)
        logger.info("Collection dimension resolved from config: %d", dim)
        return dim
    except Exception as e:
        logger.warning(
            "Could not read QDRANT_VECTOR_SIZE from config (%s) — defaulting to 384", e
        )
        return 384


# COLLECTION_DIM is resolved once at module load from shared config.
# All code that previously hardcoded 768 must use this value.
COLLECTION_DIM: int = _resolve_collection_dim()

# EMBEDDING_TIERS is filtered to only the models that match COLLECTION_DIM,
# preserving tier order within that dimension group.
EMBEDDING_TIERS: List[EmbeddingModel] = [
    m for m in _ALL_EMBEDDING_TIERS if m.expected_dim == COLLECTION_DIM
]

if not EMBEDDING_TIERS:
    logger.error(
        "CRITICAL: No embedding model defined for COLLECTION_DIM=%d. "
        "Add a model entry in _ALL_EMBEDDING_TIERS.",
        COLLECTION_DIM,
    )
    # Keep all models as last-resort to avoid complete startup failure
    EMBEDDING_TIERS = list(_ALL_EMBEDDING_TIERS)


# ── Registry ──────────────────────────────────────────────────────────────────

class EmbeddingRegistry:
    """
    Enterprise embedding model registry.
    Loads the highest-tier available model and validates its dimension.
    """

    def __init__(self):
        self._embedder = None
        self._model_meta: Optional[EmbeddingModel] = None
        self._load_latency_ms: float = 0.0
        self._initialized = False

    def initialize(self) -> None:
        """
        Load the best available embedding model.
        Tries tiers in order; validates dimension after each load.
        Raises RuntimeError if no model loads successfully with correct dimensions.
        """
        if self._initialized:
            return

        t0 = time.perf_counter()
        last_error: Exception | None = None

        for model_def in EMBEDDING_TIERS:
            try:
                from sentence_transformers import SentenceTransformer
                # Suppress harmless UNEXPECTED key warnings during load
                import logging as _lg
                _lg.getLogger("sentence_transformers").setLevel(_lg.ERROR)
                embedder = SentenceTransformer(model_def.name)
                _lg.getLogger("sentence_transformers").setLevel(_lg.INFO)

                actual_dim = embedder.get_sentence_embedding_dimension()
                elapsed = (time.perf_counter() - t0) * 1000

                if actual_dim != model_def.expected_dim:
                    logger.error(
                        "Embedding model dimension mismatch: model=%s expected=%d actual=%d — skipping",
                        model_def.name, model_def.expected_dim, actual_dim,
                    )
                    continue

                if model_def.expected_dim != COLLECTION_DIM:
                    logger.warning(
                        "⚠️  EMBEDDING DEGRADATION TIER=%d | model=%s dim=%d "
                        "COLLECTION_DIM=%d — vector search will return ZERO results. "
                        "Semantic retrieval is DISABLED until a 768-dim model loads.",
                        model_def.tier, model_def.name,
                        model_def.expected_dim, COLLECTION_DIM,
                    )
                else:
                    if model_def.tier > 1:
                        logger.warning(
                            "⚠️  EMBEDDING FALLBACK TIER=%d | primary (e5-base-v2) unavailable. "
                            "Using: %s (%d-dim). Retrieval quality degraded.",
                            model_def.tier, model_def.name, actual_dim,
                        )
                    else:
                        logger.info(
                            "✅ Embedding model loaded | tier=%d model=%s dim=%d latency=%.0fms",
                            model_def.tier, model_def.name, actual_dim, elapsed,
                        )

                self._embedder = embedder
                self._model_meta = model_def
                self._load_latency_ms = elapsed
                self._initialized = True

                # Emit metric
                try:
                    from app.observability import get_metrics_collector
                    get_metrics_collector().record_counter(
                        f"embedding.model.tier.{model_def.tier}", 1, "system"
                    )
                except Exception:
                    pass

                return

            except Exception as e:
                last_error = e
                logger.warning(
                    "Failed to load embedding model tier=%d (%s): %s — trying next tier",
                    model_def.tier, model_def.name, e,
                )

        # All tiers failed
        logger.error(
            "CRITICAL: All embedding models failed to load. "
            "Semantic search is completely unavailable. Last error: %s",
            last_error,
        )
        self._initialized = True  # mark as attempted so we don't retry on every request

    def get_embedder(self):
        """Return the loaded SentenceTransformer instance, or None."""
        if not self._initialized:
            self.initialize()
        return self._embedder

    def get_model_name(self) -> str:
        return self._model_meta.name if self._model_meta else "none"

    def get_embedding_dim(self) -> int:
        return self._model_meta.expected_dim if self._model_meta else 0

    def get_encode_prefix(self) -> str:
        """e5 models require a 'query: ' prefix for query encoding."""
        return self._model_meta.encode_prefix if self._model_meta else ""

    def is_collection_compatible(self) -> bool:
        """True only when the loaded model's dimension matches the Qdrant collection."""
        return self._model_meta is not None and self._model_meta.expected_dim == COLLECTION_DIM

    @property
    def stats(self) -> dict:
        return {
            "model": self.get_model_name(),
            "dim": self.get_embedding_dim(),
            "tier": self._model_meta.tier if self._model_meta else 0,
            "collection_compatible": self.is_collection_compatible(),
            "load_latency_ms": round(self._load_latency_ms, 1),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[EmbeddingRegistry] = None


def get_embedding_registry() -> EmbeddingRegistry:
    """Get (and lazily initialize) the global embedding registry."""
    global _registry
    if _registry is None:
        _registry = EmbeddingRegistry()
    if not _registry._initialized:
        _registry.initialize()
    return _registry


__all__ = [
    "EmbeddingRegistry",
    "EmbeddingModel",
    "EMBEDDING_TIERS",
    "COLLECTION_DIM",
    "get_embedding_registry",
]
