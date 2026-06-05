"""
Shared e5-base-v2 model singleton.

Problem: column_mapper, classifier, and embedding_service each load
intfloat/e5-base-v2 independently. Each load takes ~10s and consumes
~1.5GB GPU memory. With 3 separate loads, startup takes 30s+ and
wastes GPU memory.

Solution: single module-level singleton shared across all ingestion modules.
All three modules import _get_shared_model() from here instead of loading
their own instance.

Thread safety: SentenceTransformer.encode() is thread-safe for inference.
The singleton is initialized once (on first call) and reused forever.
"""
import logging
import threading

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()


def get_shared_model():
    """
    Return the shared e5-base-v2 SentenceTransformer instance.
    Loads on first call, reuses on subsequent calls.
    Thread-safe via double-checked locking.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                import logging as _logging
                # Suppress the harmless 'embeddings.position_ids UNEXPECTED' warning
                _logging.getLogger("sentence_transformers").setLevel(_logging.ERROR)
                _model = SentenceTransformer("intfloat/e5-base-v2")
                _logging.getLogger("sentence_transformers").setLevel(_logging.INFO)
                logger.info("Shared e5-base-v2 model loaded (singleton)")
    return _model
