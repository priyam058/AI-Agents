from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def hash_token(token: str) -> str:
    """Store refresh tokens as bcrypt hashes to prevent replay if DB is leaked."""
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


def verify_token_hash(token: str, hashed: str) -> bool:
    return bcrypt.checkpw(token.encode(), hashed.encode())


def create_access_token(user_id: UUID, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    import secrets
    return secrets.token_urlsafe(64)


def generate_reset_token() -> str:
    """Generate a cryptographically secure URL-safe password reset token."""
    import secrets
    return secrets.token_urlsafe(48)


def hash_reset_token(token: str) -> str:
    """SHA-256 hash for reset tokens — high-entropy input makes bcrypt unnecessary here."""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


def verify_reset_token_hash(token: str, token_hash: str) -> bool:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest() == token_hash


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
