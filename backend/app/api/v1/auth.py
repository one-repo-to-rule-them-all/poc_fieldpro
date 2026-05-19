"""Authentication API router."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.audit import AuditService, get_audit_service
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_secure_token,
    generate_totp_secret,
    get_password_hash,
    get_totp_uri,
    verify_password,
    verify_password_reset_token,
    verify_refresh_token,
    verify_totp,
)
from app.models.tenant import Tenant
from app.models.user import RefreshToken, User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TenantRegisterRequest,
    TenantResponse,
    UpdateProfileRequest,
    UserResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _hash_token(token: str) -> str:
    """SHA-256 hash a token string for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _issue_token_pair(user: User) -> tuple[str, str]:
    """Create and return (access_token, refresh_token) for a user."""
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    return access_token, refresh_token


async def _store_refresh_token(
    db: AsyncSession,
    user: User,
    refresh_token: str,
    request: Request | None = None,
) -> None:
    """Persist a hashed refresh token record."""
    from datetime import timedelta

    from app.core.config import settings

    token_record = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash=_hash_token(refresh_token),
        expires_at=datetime.now(tz=UTC)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(token_record)


# --------------------------------------------------------------------------- #
# POST /login
# --------------------------------------------------------------------------- #

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


async def _get_refresh_token(
    request: Request,
    cookie_token: str | None = Cookie(default=None, alias="refresh_token"),
) -> str:
    """Resolve a refresh token from the JSON body (mobile) or httpOnly cookie (web)."""
    body_token: str | None = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            body_token = body.get("refresh_token") or None
    except Exception as exc:
        # No JSON body, or malformed JSON — fall back to cookie below
        logger.debug("refresh_token_body_parse_failed", error=str(exc))
    token = body_token or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )
    return token


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    client: str = Query(default="web"),
):
    """Authenticate with email + password; receive access + refresh tokens."""
    result = await db.execute(
        select(User).where(User.email == payload.email.lower())
    )
    user = result.scalar_one_or_none()

    # Constant-time-safe fail path — always run verify even on None
    pw_match = verify_password(
        payload.password,
        user.hashed_password if user else get_password_hash("dummy"),
    )

    if not user or not pw_match:
        # autonomous=True so the row survives the 401 rollback in get_db()
        await audit.record(
            action="login_failed",
            resource_type="auth",
            user_id=user.id if user else None,
            autonomous=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token, refresh_token = await _issue_token_pair(user)
    await _store_refresh_token(db, user, refresh_token, request)

    # Update last_login_at
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(tz=UTC))
    )

    await audit.record(
        action="login",
        resource_type="auth",
        resource_id=str(user.id),
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    logger.info("user_login", user_id=str(user.id), email=user.email)

    if client != "mobile":
        _set_refresh_cookie(response, refresh_token)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
    )


# --------------------------------------------------------------------------- #
# POST /logout
# --------------------------------------------------------------------------- #

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """Revoke a refresh token."""
    token_hash = _hash_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()
    if token_record:
        token_record.revoked_at = datetime.now(tz=UTC)
        await audit.record(
            action="logout",
            resource_type="auth",
            user_id=token_record.user_id,
            tenant_id=token_record.tenant_id,
        )
    # Return 204 regardless — do not reveal whether token existed


# --------------------------------------------------------------------------- #
# POST /refresh
# --------------------------------------------------------------------------- #

@router.post("/refresh", response_model=LoginResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    client: str = Query(default="web"),
    token: str = Depends(_get_refresh_token),
):
    """Rotate refresh token: revoke old token, issue new access + refresh pair.

    Mobile clients send the token in the JSON body; web clients send it via the
    httpOnly cookie set at login. The endpoint accepts both automatically.
    """
    # Verify JWT signature & expiry first
    jwt_payload = verify_refresh_token(token)
    user_id = uuid.UUID(jwt_payload["sub"])

    token_hash = _hash_token(token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()

    if token_record is None:
        # Token not found — could be a replay after deletion; treat as suspicious
        logger.warning("refresh_token_not_found", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if token_record.is_revoked:
        # Possible token reuse attack — revoke all tokens for this user
        logger.warning(
            "refresh_token_reuse_detected",
            user_id=str(user_id),
            token_id=str(token_record.id),
        )
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=UTC))
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been used — all sessions revoked",
        )

    if token_record.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired — please log in again",
        )

    # Revoke old token
    token_record.revoked_at = datetime.now(tz=UTC)

    # Load user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue new pair
    new_access, new_refresh = await _issue_token_pair(user)
    await _store_refresh_token(db, user, new_refresh, request)

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = tenant_result.scalar_one()

    if client != "mobile":
        _set_refresh_cookie(response, new_refresh)

    return LoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
    )


# --------------------------------------------------------------------------- #
# POST /register
# --------------------------------------------------------------------------- #

@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: TenantRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """Create a new tenant and its first admin user."""
    # Check slug uniqueness
    slug_exists = await db.execute(
        select(Tenant).where(Tenant.slug == payload.tenant_slug)
    )
    if slug_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A workspace with that slug already exists",
        )

    # Check email uniqueness (across all tenants for superadmin detection)
    # For regular tenants, email must be unique within the tenant
    tenant = Tenant(
        id=uuid.uuid4(),
        name=payload.tenant_name,
        slug=payload.tenant_slug,
        settings={},
    )
    db.add(tenant)
    await db.flush()  # Get the tenant.id before creating the user

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        role=UserRole.tenant_admin,
        is_active=True,
        is_verified=False,
    )
    db.add(user)

    access_token, refresh_token = await _issue_token_pair(user)
    await _store_refresh_token(db, user, refresh_token, request)

    await audit.record(
        action="tenant_registered",
        resource_type="Tenant",
        resource_id=str(tenant.id),
        user_id=user.id,
        tenant_id=tenant.id,
    )

    logger.info("tenant_registered", tenant_id=str(tenant.id), slug=tenant.slug)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
    )


# --------------------------------------------------------------------------- #
# POST /forgot-password
# --------------------------------------------------------------------------- #

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate password reset flow.

    Always returns 202 regardless of whether the email is found,
    to avoid user enumeration.
    """
    from app.core.security import create_password_reset_token

    result = await db.execute(
        select(User).where(User.email == payload.email.lower(), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if user:
        reset_token = create_password_reset_token(str(user.id))
        # Enqueue background job (import here to avoid circular deps)
        try:
            from app.workers.tasks import enqueue_task
            await enqueue_task(
                "send_password_reset_email",
                user_id=str(user.id),
                reset_token=reset_token,
            )
        except Exception:
            logger.warning("failed_to_enqueue_password_reset_email", user_id=str(user.id))

    return {"detail": "If that email exists, a reset link has been sent"}


# --------------------------------------------------------------------------- #
# POST /reset-password
# --------------------------------------------------------------------------- #

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
):
    """Validate reset token and update the user's password."""
    user_id_str = verify_password_reset_token(payload.token)

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id_str))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = get_password_hash(payload.new_password)

    # Invalidate all existing refresh tokens
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(tz=UTC))
    )

    await audit.record(
        action="password_reset",
        resource_type="User",
        resource_id=str(user.id),
        user_id=user.id,
        tenant_id=user.tenant_id,
    )

    return {"detail": "Password has been reset successfully"}


# --------------------------------------------------------------------------- #
# GET /me
# --------------------------------------------------------------------------- #

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# --------------------------------------------------------------------------- #
# PATCH /me — update profile
# --------------------------------------------------------------------------- #

@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Update the currently authenticated user's profile fields."""
    if payload.first_name is not None:
        current_user.first_name = payload.first_name
    if payload.last_name is not None:
        current_user.last_name = payload.last_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    await db.flush()
    logger.info("profile_updated", user_id=str(current_user.id))
    return UserResponse.model_validate(current_user)


# --------------------------------------------------------------------------- #
# POST /me/change-password
# --------------------------------------------------------------------------- #

@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Change password for the currently authenticated user."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    # Revoke all existing refresh tokens so other sessions are logged out
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(tz=UTC))
    )
    logger.info("password_changed", user_id=str(current_user.id))


# --------------------------------------------------------------------------- #
# POST /mfa/setup
# --------------------------------------------------------------------------- #

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate a TOTP secret and return QR code URI + backup codes."""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled for this account",
        )

    secret = generate_totp_secret()
    qr_code_url = get_totp_uri(secret, current_user.email)

    # Generate 8 one-time backup codes
    backup_codes = [generate_secure_token(10)[:10].upper() for _ in range(8)]

    # Temporarily store the secret; it becomes permanent only after /mfa/verify
    # In production you might store in Redis with TTL
    current_user.mfa_secret = secret

    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes,
    )


# --------------------------------------------------------------------------- #
# POST /mfa/verify
# --------------------------------------------------------------------------- #

@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def mfa_verify(
    payload: MFAVerifyRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Verify a TOTP code and permanently enable MFA on the account."""
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated — call /mfa/setup first",
        )

    if not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.mfa_enabled = True
    logger.info("mfa_enabled", user_id=str(current_user.id))

    return {"detail": "MFA has been enabled successfully"}
