"""
Password Hashing Utilities
Uses bcrypt directly for secure password hashing (avoids passlib/bcrypt version conflicts)
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a plain password using bcrypt.
    Bcrypt has a 72-byte limit — we pre-truncate to avoid ValueError.
    """
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a bcrypt hash.
    """
    try:
        password_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False
