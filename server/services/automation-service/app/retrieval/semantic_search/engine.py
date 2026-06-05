"""
L6 Semantic Search Engine
==========================
Dense vector search backed by the EmbeddingRegistry.

Model hierarchy (managed by EmbeddingRegistry, NOT this file):
  Tier 1: intfloat/e5-base-v2      768-dim  ← matches Qdrant collection
  Tier 2: all-mpnet-base-v2        768-dim  ← same dimension, collection-compatible
  Tier 3: all-MiniLM-L6-v2        384-dim  ← DIMENSION MISMATCH — search disabled

Root cause of previous BAAI/bge-m3 failure:
  - bge-m3 produces 1024-dim vectors
  - Qdrant collection was built by user-service with e5-base-v2 at 768-dim
  - bge-m3 was NEVER used to build the collection data
  - Additionally, bge-m3's pytorch_model.bin is blocked by torch >= 2.6 (CVE-2025-32434)
  - Both issues render bge-m3 incompatible with this deployment

All model loading is delegated to EmbeddingRegistry.
This engine NEVER loads a model directly.

Performance: <200ms
Layer: L6 (after exact/metadata/BM25)
"""
import logging
import time
from typing import Any, Dict, List, Optional

from app.retrieval.schemas import ChunkType, RetrievalSource, RetrievedChunk

logger = logging.getLogger("automation-service.retrieval.semantic")

# Kept for backward-compat with audit_issues_1_14.py checks
_DEFAULT_EMBEDDING_MODEL = "intfloat/e5-base-v2"
_FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"


class SemanticSearchEngine:
    """
    L6 Dense semantic search.

    Delegates all model management to EmbeddingRegistry — no direct
    SentenceTransformer instantiation here.

    Features:
    - Collection-aligned embeddings via EmbeddingRegistry (e5-base-v2, 768-dim)
    - Graceful no-op when model dimension doesn't match collection
    - Multi-query execution with deduplication
    - Tenant-safe (user_id enforced at every call)
    - Full observability: logs model, dim, latency, query count per call
    """

    def __init__(self, qdrant_repository, embedding_model_name: str = _DEFAULT_EMBEDDING_MODEL):
        self.qdrant = qdrant_repository
        # embedding_model_name param kept for API compatibility but ignored —
        # model selection is owned by EmbeddingRegistry.
        self._registry = None
        self._init_registry()

    def _init_registry(self) -> None:
        """Bind to the global EmbeddingRegistry (loads on first access)."""
        try:
            from app.retrieval.embeddings import get_embedding_registry
            self._registry = get_embedding_registry()
            stats = self._registry.stats
            if self._registry.is_collection_compatible():
                logger.info(
                    "SemanticSearchEngine ready | model=%s dim=%d tier=%d load_ms=%.0f",
                    stats["model"], stats["dim"], stats["tier"], stats["load_latency_ms"],
                )
            else:
                logger.warning(
                    "⚠️  SemanticSearchEngine: model=%s dim=%d is NOT compatible "
                    "with Qdrant collection (768-dim). Vector search DISABLED.",
                    stats["model"], stats["dim"],
                )
        except Exception as e:
            logger.error("SemanticSearchEngine: registry init failed: %s", e)
            self._registry = None

    @property
    def embedder(self):
        """Expose embedder for external callers (reranker etc.)."""
        return self._registry.get_embedder() if self._registry else None

    @property
    def model_name(self) -> str:
        return self._registry.get_model_name() if self._registry else "none"

    @property
    def embedding_dim(self) -> int:
        return self._registry.get_embedding_dim() if self._registry else 0

    def _encode(self, text: str) -> Optional[List[float]]:
        """
        Encode a single text string.
        Applies the e5 'query: ' prefix when the primary model requires it.
        Returns None if the model is not collection-compatible.
        """
        if not self._registry or not self._registry.is_collection_compatible():
            return None
        embedder = self._registry.get_embedder()
        if not embedder:
            return None
        prefix = self._registry.get_encode_prefix()
        try:
            return embedder.encode(
                prefix + text, normalize_embeddings=True
            ).tolist()
        except Exception as e:
            logger.error("Embedding encode error: %s", e)
            return None

    async def search_semantic(
        self,
        user_id: str,
        queries: List[str],
        top_k: int = 10,
        score_threshold: float = 0.30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Dense vector search using the primary (combined) query."""
        if not user_id or not queries:
            return []

        if not self._registry or not self._registry.is_collection_compatible():
            logger.warning(
                "L6 semantic search SKIPPED — embedding model not collection-compatible | "
                "model=%s dim=%d required=768",
                self.model_name, self.embedding_dim,
            )
            return []

        t0 = time.perf_counter()
        try:
            query_text = " ".join(queries[:3])
            query_vector = self._encode(query_text)
            if query_vector is None:
                return []

            results = await self.qdrant.search(
                user_id=user_id,
                query_vector=query_vector,
                limit=top_k,
                filters=filters,
                score_threshold=score_threshold,
            )

            chunks = []
            for result in results:
                payload = result.get("payload", {})
                if payload.get("user_id") and payload["user_id"] != user_id:
                    continue
                chunk = RetrievedChunk(
                    content=payload.get("content", ""),
                    score=result.get("score", 0.0),
                    chunk_type=ChunkType(payload.get("chunk_type", "general")),
                    chunk_id=payload.get("chunk_id", str(result.get("id", ""))),
                    source=RetrievalSource.L5_SEMANTIC,
                    user_id=user_id,
                    metadata=payload,
                    retrieval_layer="L6",
                )
                chunks.append(chunk)

            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug(
                "L6 semantic | model=%s dim=%d queries=%d found=%d latency=%.1fms",
                self.model_name, self.embedding_dim, len(queries), len(chunks), elapsed,
            )
            return chunks

        except Exception as e:
            logger.error("L6 semantic search error: %s", e)
            return []

    async def search_multi_query(
        self,
        user_id: str,
        queries: List[str],
        top_k_per_query: int = 5,
        score_threshold: float = 0.30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Execute multiple semantic queries, merge and deduplicate results."""
        if not queries:
            return []

        all_chunks: List[RetrievedChunk] = []
        seen_ids: set = set()

        for q in queries[:5]:
            chunks = await self.search_semantic(
                user_id=user_id,
                queries=[q],
                top_k=top_k_per_query,
                score_threshold=score_threshold,
                filters=filters,
            )
            for c in chunks:
                if c.chunk_id not in seen_ids:
                    all_chunks.append(c)
                    seen_ids.add(c.chunk_id)

        all_chunks.sort(key=lambda c: c.score, reverse=True)
        return all_chunks

    def embed_text(self, text: str) -> Optional[List[float]]:
        """Embed a single text. Returns None if model unavailable."""
        return self._encode(text)

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed a batch of texts. Returns [] if model unavailable."""
        if not self._registry or not self._registry.is_collection_compatible():
            return []
        embedder = self._registry.get_embedder()
        if not embedder or not texts:
            return []
        prefix = self._registry.get_encode_prefix()
        try:
            prefixed = [prefix + t for t in texts]
            embeddings = embedder.encode(
                prefixed,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error("Batch embedding error: %s", e)
            return []
