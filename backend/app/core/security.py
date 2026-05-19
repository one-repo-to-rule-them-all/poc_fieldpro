"""Security utilities: JWT, password hashing, TOTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import secrets
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
import pyotp

from app.core.config import settings

# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches hashed_password."""
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #

def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = _utc_now() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a signed JWT refresh token with longer expiry."""
    to_encode = data.copy()
    expire = _utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(
        to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM
    )


def verify_token(token: str, secret: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises HTTPException 401 on any failure (expired, invalid signature, etc.).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
        return payload
    except JWTError as err:
        raise credentials_exception from err


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an access token and return its payload."""
    payload = verify_token(token, settings.SECRET_KEY)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Verify a refresh token and return its payload."""
    payload = verify_token(token, settings.REFRESH_SECRET_KEY)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# --------------------------------------------------------------------------- #
# Password-reset tokens (signed, short-lived)
# --------------------------------------------------------------------------- #

def create_password_reset_token(user_id: str) -> str:
    """Create a short-lived (1 hour) password reset token."""
    expire = _utc_now() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "password_reset"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_password_reset_token(token: str) -> str:
    """Return user_id from a valid password-reset token, else raise 400."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset":
            raise ValueError("Wrong token type")
        user_id: str = payload["sub"]
        return user_id
    except (JWTError, KeyError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        ) from err


# --------------------------------------------------------------------------- #
# TOTP (MFA)
# --------------------------------------------------------------------------- #

def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "FieldPro") -> str:
    """Build the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against the stored secret.

    Accepts codes from -1 / 0 / +1 windows to handle clock skew.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# --------------------------------------------------------------------------- #
# Misc helpers
# --------------------------------------------------------------------------- #

def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token string."""
    return secrets.token_urlsafe(nbytes)
