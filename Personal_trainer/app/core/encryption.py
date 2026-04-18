"""AES-256-GCM field-level encryption for sensitive health data."""
import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_IV_LENGTH = 12  # 96-bit nonce, recommended for GCM
_TAG_LENGTH = 16  # 128-bit authentication tag (default for AESGCM)


def _get_key() -> bytes:
    if not settings.encryption_key:
        raise RuntimeError("ENCRYPTION_KEY environment variable is not set")
    key = base64.b64decode(settings.encryption_key)
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256)")
    return key


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return base64(iv + ciphertext_with_tag)."""
    key = _get_key()
    iv = os.urandom(_IV_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return base64.b64encode(iv + ciphertext_with_tag).decode("utf-8")


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64(iv + ciphertext_with_tag) string."""
    key = _get_key()
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:_IV_LENGTH]
    ciphertext_with_tag = raw[_IV_LENGTH:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
    return plaintext.decode("utf-8")


def encrypt_optional(value: Optional[str]) -> Optional[str]:
    return encrypt(value) if value is not None else None


def decrypt_optional(value: Optional[str]) -> Optional[str]:
    return decrypt(value) if value is not None else None
