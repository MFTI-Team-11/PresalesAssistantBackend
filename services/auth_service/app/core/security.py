from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def token_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)


def refresh_token_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)


def create_access_token(user_id: UUID, email: str, session_id: UUID, expires_at: datetime) -> tuple[str, str]:
    token_jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "email": email,
        "sid": str(session_id),
        "jti": token_jti,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, token_jti


def create_refresh_token() -> str:
    return uuid4().hex + uuid4().hex


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
