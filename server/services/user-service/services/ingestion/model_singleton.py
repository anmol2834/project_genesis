"""
Shared BAAI/bge-m3 model singleton.

Problem: column_mapper, classifier, and embedding_service each load
the model independently. Each load is expensive in time and memory.
With 3 separate loads, startup takes 30s+ and wastes memory.

Solution: single module-level singleton shared across all ingestion modules.
All three modules call get_shared_model() from here instead of loading
their own instance.

Model: BAAI/bge-m3
  - Output dimension : 1024
  - Distance metric  : Cosine
  - Prefix contract  : NO instruction prefixes (unlike e5-base-v2).
    Pass text as-is to .encode().

Cache: model weights are stored at <project_root>/server/.model_cache/
  This is a stable path relative to this file's location, which means
  the model is downloaded once and reused across all subsequent restarts.
  Without an explicit cache_folder, HuggingFace may resolve to a temp
  directory on Windows and re-download on every process start.

Thread safety: SentenceTransformer.encode() is thread-safe for inference.
The singleton is initialized once (on first call) and reused forever.
"""
import logging
import os
import threading

logger = logging.getLogger(__name__)

_model = None
_lock  = threading.Lock()

# Stable cache directory: <project_genesis>/server/.model_cache/
# Resolved relative to THIS file so it works regardless of cwd.
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))          # .../ingestion
_SVC_DIR    = os.path.dirname(os.path.dirname(_THIS_DIR))          # .../user-service
_SERVER_DIR = os.path.dirname(os.path.dirname(_SVC_DIR))           # .../server
_MODEL_CACHE_DIR = os.path.join(_SERVER_DIR, ".model_cache")
os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)


def get_shared_model():
    """
    Return the shared BAAI/bge-m3 SentenceTransformer instance.
    Loads on first call (downloading to _MODEL_CACHE_DIR if absent),
    reuses on subsequent calls without any network access.
    Thread-safe via double-checked locking.
    """
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                import logging as _logging
                _logging.getLogger("sentence_transformers").setLevel(_logging.ERROR)

                # Suppress HuggingFace progress bars (avoids safetensors conversion
                # noise printing to the terminal on every startup).
                os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

                # Check whether model weights are already on disk.
                # If any snapshot dir contains the weight file, load offline
                # to prevent HuggingFace from hitting the network on every start.
                _snapshot_root = os.path.join(
                    _MODEL_CACHE_DIR, "models--BAAI--bge-m3", "snapshots"
                )
                _cached = False
                if os.path.isdir(_snapshot_root):
                    for _snap in os.listdir(_snapshot_root):
                        _snap_path = os.path.join(_snapshot_root, _snap)
                        if not os.path.isdir(_snap_path):
                            continue
                        _files = os.listdir(_snap_path)
                        if "pytorch_model.bin" in _files or "model.safetensors" in _files:
                            _cached = True
                            break

                _model = SentenceTransformer(
                    "BAAI/bge-m3",
                    cache_folder=_MODEL_CACHE_DIR,
                    # local_files_only prevents any network check when weights exist
                    local_files_only=_cached,
                )
                _logging.getLogger("sentence_transformers").setLevel(_logging.INFO)
                logger.info(
                    "Shared BAAI/bge-m3 model loaded (singleton, 1024-dim) | "
                    "cache=%s | offline=%s",
                    _MODEL_CACHE_DIR,
                    _cached,
                )
    return _model
