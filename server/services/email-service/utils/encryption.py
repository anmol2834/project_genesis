"""
Encryption Utility
AES-256-GCM symmetric encryption for OAuth tokens and SMTP passwords.
Uses ENCRYPTION_KEY from shared config (base64-encoded 32-byte key).
"""

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared.config import get_config


def _get_key() -> bytes:
    """Decode the 32-byte AES key from config."""
    raw = get_config().ENCRYPTION_KEY
    return base64.b64decode(raw)


def encrypt(plaintext: str) -> str:
    """
    Encrypt a string with AES-256-GCM.
    Returns base64(nonce + ciphertext) safe for DB storage.
    """
    if not plaintext:
        return plaintext
    key   = _get_key()
    nonce = os.urandom(12)          # 96-bit nonce (GCM standard)
    ct    = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    """
    Decrypt a value produced by encrypt().
    Returns the original plaintext string.
    """
    if not token:
        return token
    key  = _get_key()
    raw  = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
