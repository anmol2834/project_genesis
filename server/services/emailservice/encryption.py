"""
emailservice — AES-256-GCM encryption (standalone copy, no email-service dependency)
"""
import base64, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from shared.config import get_config

def _key() -> bytes:
    return base64.b64decode(get_config().ENCRYPTION_KEY)

def encrypt(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def decrypt(token: str) -> str:
    if not token:
        return token
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(_key()).decrypt(nonce, ct, None).decode()

encrypt_token = encrypt
decrypt_token = decrypt
