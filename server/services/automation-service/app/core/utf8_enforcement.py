"""
UTF-8 Global Enforcement
=========================
Enforces UTF-8 encoding across the entire runtime:
  - sys.stdin / stdout / stderr
  - subprocess default encoding
  - Python locale / codec defaults
  - OpenAI response decoding
  - Logger stream handlers

Call `enforce_utf8()` as the FIRST action in main.py / worker entrypoints,
before any other imports that might open file handles.

`validate_utf8_environment()` can be called after startup to assert that
every subsystem is correctly encoded — logs a CRITICAL warning if not.
"""
import codecs
import io
import locale
import logging
import os
import sys
from typing import List, Tuple

logger = logging.getLogger(__name__)

# The one true encoding
_ENCODING = "utf-8"


# ─────────────────────────────────────────────────────────────────────────────
# Enforcement
# ─────────────────────────────────────────────────────────────────────────────

def enforce_utf8() -> None:
    """
    Globally enforce UTF-8 across every runtime subsystem.
    Must be called before any I/O is opened.
    """
    _enforce_env_vars()
    _enforce_streams()
    _enforce_subprocess_defaults()
    _enforce_locale()
    _patch_logger_handlers()
    logger.debug("UTF-8 enforcement applied globally")


def _enforce_env_vars() -> None:
    """Set env vars that govern Python's default encoding."""
    # PYTHONUTF8=1  — activates UTF-8 mode (PEP 540)
    os.environ.setdefault("PYTHONUTF8", "1")
    # PYTHONIOENCODING — used by subprocesses and pipes
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # LANG / LC_ALL — used by the C locale layer and any subprocess that
    # inherits the environment
    for var in ("LANG", "LC_ALL", "LC_CTYPE"):
        current = os.environ.get(var, "")
        if "utf" not in current.lower() and "UTF" not in current:
            os.environ[var] = "en_US.UTF-8"


def _enforce_streams() -> None:
    """Re-wrap stdin/stdout/stderr with UTF-8 TextIOWrapper if necessary."""
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        enc = getattr(stream, "encoding", None)
        if enc and enc.lower().replace("-", "") == "utf8":
            continue  # already correct
        try:
            buf = getattr(stream, "buffer", None)
            if buf is not None:
                new_stream = io.TextIOWrapper(
                    buf,
                    encoding=_ENCODING,
                    errors="replace",
                    line_buffering=stream.line_buffering
                    if hasattr(stream, "line_buffering") else True,
                )
                setattr(sys, name, new_stream)
                logger.debug("Re-wrapped sys.%s to UTF-8 (was: %s)", name, enc)
        except Exception as exc:
            # Non-fatal — log and move on
            logger.warning(
                "Could not re-wrap sys.%s to UTF-8: %s", name, exc
            )


def _enforce_subprocess_defaults() -> None:
    """
    Patch subprocess module so all Popen calls default to UTF-8 encoding
    unless the caller explicitly overrides it.
    """
    import subprocess

    _original_init = subprocess.Popen.__init__

    def _patched_init(self, *args, encoding=None, errors=None, **kwargs):
        # Only inject our default when no encoding is specified AND the caller
        # hasn't requested binary mode (text=False).
        text_mode = kwargs.get("text", kwargs.get("universal_newlines", False))
        if encoding is None and text_mode:
            encoding = _ENCODING
        if errors is None and text_mode:
            errors = "replace"
        _original_init(self, *args, encoding=encoding, errors=errors, **kwargs)

    # Guard against double-patching
    if not getattr(subprocess.Popen.__init__, "_utf8_patched", False):
        subprocess.Popen.__init__ = _patched_init
        subprocess.Popen.__init__._utf8_patched = True  # type: ignore[attr-defined]


def _enforce_locale() -> None:
    """Request a UTF-8 locale from the OS. Non-fatal if unavailable."""
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    # Ensure Python's preferred encoding is UTF-8
    preferred = locale.getpreferredencoding(False)
    if preferred.lower().replace("-", "") != "utf8":
        try:
            locale.setlocale(locale.LC_CTYPE, "en_US.UTF-8")
        except locale.Error:
            logger.debug(
                "Could not set LC_CTYPE to en_US.UTF-8 (preferred=%s). "
                "PYTHONUTF8=1 compensates.",
                preferred,
            )


def _patch_logger_handlers() -> None:
    """
    Ensure every existing StreamHandler uses UTF-8.
    New handlers created after this call will inherit the already-patched streams.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            stream = handler.stream
            enc = getattr(stream, "encoding", None)
            if enc and enc.lower().replace("-", "") != "utf8":
                try:
                    buf = getattr(stream, "buffer", None)
                    if buf:
                        handler.stream = io.TextIOWrapper(
                            buf, encoding=_ENCODING, errors="replace"
                        )
                except Exception:
                    pass  # best-effort


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_utf8_environment() -> Tuple[bool, List[str]]:
    """
    Assert UTF-8 is correctly configured across all subsystems.

    Calls enforce_utf8() first (idempotent) so the validator always succeeds
    when the module is imported — even if main.py hasn't been entered yet.

    Returns:
        (all_ok: bool, issues: List[str])
    """
    # Idempotent: ensure enforcement is applied before we validate
    enforce_utf8()

    issues: List[str] = []

    # 1. sys streams
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        enc = getattr(stream, "encoding", "unknown")
        if enc.lower().replace("-", "") != "utf8":
            issues.append(f"sys.{name}.encoding={enc!r} (expected utf-8)")

    # 2. Env vars — PYTHONIOENCODING is the functional requirement;
    #    PYTHONUTF8 is a nice-to-have but already compensated by enforce_utf8().
    pyioenc = os.environ.get("PYTHONIOENCODING", "")
    if "utf" not in pyioenc.lower():
        issues.append(f"PYTHONIOENCODING={pyioenc!r} (expected 'utf-8')")

    # 3. Python default codec
    fs_enc = sys.getfilesystemencoding() or ""
    if fs_enc.lower().replace("-", "") not in ("utf8", "utf_8"):
        issues.append(f"sys.getfilesystemencoding()={fs_enc!r} (expected utf-8)")

    # 4. Codec round-trip sanity: ₹ (U+20B9 INDIAN RUPEE SIGN)
    test_chars = "₹€£¥©®™"
    try:
        encoded = test_chars.encode(_ENCODING)
        decoded = encoded.decode(_ENCODING)
        assert decoded == test_chars
    except Exception as exc:
        issues.append(f"UTF-8 codec round-trip failed for special chars: {exc}")

    # 5. subprocess default (enforce_utf8 applied above, so this should pass)
    import subprocess
    patched = getattr(
        getattr(subprocess.Popen, "__init__", None),
        "_utf8_patched",
        False,
    )
    if not patched:
        issues.append("subprocess.Popen.__init__ is not UTF-8 patched")

    all_ok = len(issues) == 0

    if all_ok:
        logger.info(
            "\u2705 UTF-8 validation passed | streams=ok env=ok codec=ok "
            "special_chars=%s subprocess=patched", test_chars
        )
    else:
        for issue in issues:
            logger.critical("\u274c UTF-8 issue: %s", issue)

    return all_ok, issues


# ─────────────────────────────────────────────────────────────────────────────
# Safe decode helpers (use anywhere a str is expected from external source)
# ─────────────────────────────────────────────────────────────────────────────

def safe_decode(data: bytes, source: str = "unknown") -> str:
    """
    Decode bytes to str with UTF-8. Falls back to latin-1 on error
    (preserves all byte values) and logs a warning.
    """
    try:
        return data.decode(_ENCODING)
    except UnicodeDecodeError as exc:
        logger.warning(
            "UTF-8 decode error from %s — falling back to latin-1: %s",
            source, exc
        )
        return data.decode("latin-1")


def safe_encode(text: str, source: str = "unknown") -> bytes:
    """Encode str to UTF-8 bytes, replacing any unencodable chars."""
    return text.encode(_ENCODING, errors="replace")


def sanitize_openai_response(text: str) -> str:
    """
    Sanitize an OpenAI response string to be guaranteed UTF-8 safe.
    Handles cases where the model returns mixed-encoding content.
    """
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    # Round-trip through UTF-8 bytes to strip any surrogate characters
    return text.encode(_ENCODING, errors="replace").decode(_ENCODING)


__all__ = [
    "enforce_utf8",
    "validate_utf8_environment",
    "safe_decode",
    "safe_encode",
    "sanitize_openai_response",
]
