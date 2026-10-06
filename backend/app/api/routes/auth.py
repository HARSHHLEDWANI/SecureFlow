"""Authentication endpoints with risk-based step-up.

Login is itself risk-scored: a LOW-risk attempt logs in directly, a MEDIUM-risk
attempt must clear a step-up OTP challenge, and a HIGH-risk attempt is blocked.

Security properties (see ``tests/test_security.py``):

* The login risk check fails *closed*: if neither Redis nor the database can say the
  device is known, the login is forced to step-up instead of silently scoring LOW.
* Only ``BOOTSTRAP_ADMIN_EMAIL`` is promoted to ADMIN on registration.
* The step-up OTP is only ever returned in the response outside production.
* Refresh tokens rotate on every use; reuse of a rotated token revokes the whole
  login family; logout revokes it (``app/core/refresh_tokens.py``).
* Failed logins are throttled per account as well as per IP.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import refresh_tokens as rt
from app.core.redis_client import redis_client
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database import Role, Transaction, User, get_db
from app.dependencies import RateLimiter, envelope, get_current_user
from app.models.user import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    StepUpRequest,
    UserPublic,
)
from app.utils.helpers import utcnow
from app.utils.logger import get_logger

logger = get_logger("auth")
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE = "sf_refresh"

_dummy_hash_value: Optional[str] = None


def _dummy_hash() -> str:
    """A throwaway bcrypt hash, so unknown emails cost the same time as wrong passwords."""
    global _dummy_hash_value
    if _dummy_hash_value is None:
        _dummy_hash_value = hash_password(secrets.token_hex(8))
    return _dummy_hash_value


def _cookie_attrs() -> dict:
    samesite = settings.refresh_cookie_samesite.lower()
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    return {"httponly": True, "samesite": samesite, "secure": settings.is_production or samesite == "none"}


def _clear_refresh_cookie(response: Response) -> None:
    # Browsers only delete a cookie when the attributes match the ones it was set with.
    response.delete_cookie(REFRESH_COOKIE, **_cookie_attrs())


def _require_allowed_origin(request: Request) -> None:
    """Cookie-authenticated endpoints reject browser requests from foreign origins (CSRF).

    Needed because ``SameSite=None`` (cross-site frontends) sends the cookie from any site.
    Requests without an ``Origin`` header (non-browser clients) are not CSRF-able.
    """
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")


def _public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        vpa=user.vpa,
        role=user.role.value,
        home_city=user.home_city,
    )


def _device_known(db: Session, user: User, device_id: str) -> Optional[bool]:
    """Is ``device_id`` a recognised device for ``user``?

    Redis first; if it cannot answer (``None``), fall back to the database - the same
    transaction-history check ``gather_signals`` uses. ``None`` only if *both* are down.
    """
    known = redis_client.is_known_device(user.id, device_id)
    if known is not None:
        return known
    try:
        seen = db.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id == user.id, Transaction.device_id == device_id)
        )
    except SQLAlchemyError:
        return None
    return (seen or 0) > 0


def _assess_login_risk(user: User, device_id: str, db: Session) -> tuple[int, str]:
    """Lightweight risk score (0-100) for a login attempt.

    An unrecognised device adds 45 (-> MEDIUM, step-up). An *unverifiable* device
    (Redis and DB both unavailable) is treated the same way: never trusted by default.
    """
    score = 0
    if _device_known(db, user, device_id) is not True:
        score += 45  # unrecognised, or unverifiable, device
    hour = utcnow().hour
    if hour < 6 or hour >= 23:
        score += 20  # unusual hour
    if device_id in ("", "web-default"):
        score += 10  # no real device fingerprint supplied

    if score <= 30:
        tier = "LOW"
    elif score <= 70:
        tier = "MEDIUM"
    else:
        tier = "HIGH"
    return min(score, 100), tier


def _issue_tokens(response: Response, user: User, family: Optional[str] = None) -> str:
    """Return an access token and set a rotating refresh cookie when it is verifiable.

    With Redis down the refresh token cannot be tracked, so none is issued: the session
    lasts only as long as the (short) access token.
    """
    access = create_token(user.id, "access", role=user.role.value, email=user.email)
    fid, jti = family or rt.new_family(), rt.new_jti()
    if rt.register(jti, fid, user.id):
        refresh = create_token(user.id, "refresh", jti=jti, fid=fid)
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=settings.refresh_token_expire_days * 86400,
            **_cookie_attrs(),
        )
    else:
        logger.warning("Refresh store unavailable - issuing access token only for %s", user.email)
        _clear_refresh_cookie(response)
    return access


def _account_key(email: str) -> str:
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]
    return f"ratelimit:acct:{digest}:login"


@router.post("/register", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(RateLimiter("register"))])
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    """Create a new user.

    Everyone registers as VIEWER except ``BOOTSTRAP_ADMIN_EMAIL``, which is promoted to
    ADMIN. There is no "first user wins": on a public URL that would hand the
    governance console to whoever arrives first.
    """
    exists = db.scalar(
        select(func.count()).select_from(User).where(func.lower(User.email) == req.email)
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    bootstrap = settings.bootstrap_admin_email.strip().lower()
    is_bootstrap = bool(bootstrap) and req.email == bootstrap  # req.email is already lower-cased
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        vpa=req.vpa,
        home_city=req.home_city,
        role=Role.ADMIN if is_bootstrap else Role.VIEWER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered user %s (role=%s)", user.email, user.role.value)
    return envelope(_public(user).model_dump())


@router.post("/login", dependencies=[Depends(RateLimiter("login"))])
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    """Authenticate, returning a token or a step-up challenge by risk tier."""
    acct_key = _account_key(req.email)
    if redis_client.counter_get(acct_key) >= settings.login_account_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed logins for this account. Try again later.",
        )

    user = db.execute(
        select(User).where(func.lower(User.email) == req.email).order_by(User.created_at)
    ).scalars().first()
    # Always run one bcrypt verify so response time does not reveal whether the email exists.
    password_ok = verify_password(req.password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok:
        redis_client.rate_limit_hit(acct_key, settings.login_account_window_seconds)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    redis_client.key_delete(acct_key)

    score, tier = _assess_login_risk(user, req.device_id, db)

    if tier == "HIGH":
        logger.warning("Blocked HIGH-risk login for %s", user.email)
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Login blocked: this attempt was flagged as high-risk.",
        )

    if tier == "MEDIUM":
        challenge_id = str(uuid.uuid4())
        otp = f"{secrets.randbelow(1_000_000):06d}"
        redis_client.set_session(
            f"stepup:{challenge_id}",
            {"user_id": user.id, "otp": otp, "device_id": req.device_id},
            ttl=300,
        )
        if settings.is_production:
            # Delivered out-of-band (SMS/app) in a real deployment; here it is logged so
            # an operator can complete the challenge. Never returned to the caller.
            logger.info("Step-up OTP for %s challenge=%s otp=%s", user.email, challenge_id, otp)
        return envelope(
            LoginResponse(
                user=_public(user),
                login_risk_score=score,
                login_risk_tier=tier,
                step_up_required=True,
                challenge_id=challenge_id,
                demo_otp=None if settings.is_production else otp,
            ).model_dump()
        )

    # LOW risk - log in directly.
    access = _issue_tokens(response, user)
    redis_client.add_device(user.id, req.device_id)
    return envelope(
        LoginResponse(
            access_token=access,
            user=_public(user),
            login_risk_score=score,
            login_risk_tier=tier,
            step_up_required=False,
        ).model_dump()
    )


@router.post("/verify-step-up", dependencies=[Depends(RateLimiter("stepup"))])
def verify_step_up(req: StepUpRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    """Complete a MEDIUM-risk login by verifying the OTP challenge."""
    session = redis_client.get_session(f"stepup:{req.challenge_id}")
    if session is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Challenge expired or invalid")
    if not secrets.compare_digest(str(session.get("otp")), req.otp):
        # A 6-digit OTP must not be brute-forceable: burn the challenge after a few misses.
        attempts = int(session.get("attempts", 0)) + 1
        if attempts >= settings.stepup_max_attempts:
            redis_client.delete_session(f"stepup:{req.challenge_id}")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Too many incorrect codes; log in again")
        redis_client.set_session(f"stepup:{req.challenge_id}", {**session, "attempts": attempts}, ttl=300)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect OTP")

    user = db.get(User, session["user_id"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

    redis_client.delete_session(f"stepup:{req.challenge_id}")
    access = _issue_tokens(response, user)
    redis_client.add_device(user.id, session.get("device_id", "web-default"))
    return envelope(
        LoginResponse(
            access_token=access,
            user=_public(user),
            login_risk_score=0,
            login_risk_tier="LOW",
            step_up_required=False,
        ).model_dump()
    )


@router.post("/refresh", dependencies=[Depends(RateLimiter("refresh", limit=30)), Depends(_require_allowed_origin)])
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    sf_refresh: str | None = Cookie(default=None),
) -> dict:
    """Rotate the refresh token and issue a new access token.

    The presented token is single-use. Presenting one that was already rotated is
    treated as theft: the whole login family is revoked.
    """
    if not sf_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    try:
        payload = decode_token(sf_refresh, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    ident = rt.identity_from_payload(payload)
    if ident is None:  # pre-rotation token (no jti/fid): cannot be tracked, so reject
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    state = rt.check(ident.jti, ident.fid)
    if state is rt.RefreshState.RACED:
        # Rotated a moment ago by a concurrent request that holds the successor cookie.
        raise HTTPException(status.HTTP_409_CONFLICT, "Refresh already in progress; retry")
    if state is rt.RefreshState.REUSED:
        rt.revoke_family(ident.fid)
        _clear_refresh_cookie(response)
        logger.warning("Refresh-token reuse detected for user %s - family revoked", payload.get("sub"))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected; log in again")
    if state is not rt.RefreshState.ACTIVE:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token is not valid; log in again")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

    rt.retire(ident.jti, ident.fid)
    access = _issue_tokens(response, user, family=ident.fid)
    return envelope({"accessToken": access})


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Return the currently-authenticated user (incl. governance access flag)."""
    from app.core.governance import has_governance_access

    pub = _public(user)
    pub.governance_access = has_governance_access(db, user)
    return envelope(pub.model_dump())


@router.post("/logout", dependencies=[Depends(_require_allowed_origin)])
def logout(response: Response, sf_refresh: str | None = Cookie(default=None)) -> dict:
    """Revoke the refresh-token family server-side and clear the cookie."""
    if sf_refresh:
        try:
            ident = rt.identity_from_payload(decode_token(sf_refresh, "refresh"))
        except jwt.PyJWTError:
            ident = None
        if ident is not None:
            rt.revoke_family(ident.fid)
    _clear_refresh_cookie(response)
    return envelope({"loggedOut": True})
