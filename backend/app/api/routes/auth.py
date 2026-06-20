"""Authentication endpoints with risk-based step-up.

Login is itself risk-scored: a LOW-risk attempt logs in directly, a MEDIUM-risk
attempt must clear a step-up OTP challenge, and a HIGH-risk attempt is blocked.
"""
from __future__ import annotations

import secrets
import uuid

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.redis_client import redis_client
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database import Role, User, get_db
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


def _public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        vpa=user.vpa,
        role=user.role.value,
        home_city=user.home_city,
    )


def _assess_login_risk(user: User, device_id: str) -> tuple[int, str]:
    """Lightweight risk score (0–100) for a login attempt."""
    score = 0
    known = redis_client.is_known_device(user.id, device_id)
    if known is False:
        score += 45  # unrecognised device
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


def _issue_tokens(response: Response, user: User) -> str:
    access = create_token(user.id, "access", role=user.role.value, email=user.email)
    refresh = create_token(user.id, "refresh")
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.refresh_token_expire_days * 86400,
    )
    return access


@router.post("/register", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(RateLimiter("register"))])
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    """Create a new user. The first registered user becomes ADMIN."""
    exists = db.scalar(select(func.count()).select_from(User).where(User.email == req.email))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Seeded system accounts (lab demo users @secureflow.local + the governance
    # council @secureflow.io) are excluded so the first *real* registrant still
    # becomes ADMIN on a fresh deployment.
    real_users = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                ~User.email.like("%@secureflow.local"),
                ~User.email.like("%@secureflow.io"),
            )
        )
        or 0
    )
    is_first = real_users == 0
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        vpa=req.vpa,
        home_city=req.home_city,
        role=Role.ADMIN if is_first else Role.VIEWER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Registered user %s (role=%s)", user.email, user.role.value)
    return envelope(_public(user).model_dump())


@router.post("/login", dependencies=[Depends(RateLimiter("login"))])
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    """Authenticate, returning a token or a step-up challenge by risk tier."""
    user = db.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    score, tier = _assess_login_risk(user, req.device_id)

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
        return envelope(
            LoginResponse(
                user=_public(user),
                login_risk_score=score,
                login_risk_tier=tier,
                step_up_required=True,
                challenge_id=challenge_id,
                demo_otp=otp,
            ).model_dump()
        )

    # LOW risk — log in directly.
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


@router.post("/refresh")
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    sf_refresh: str | None = Cookie(default=None),
) -> dict:
    """Rotate the access token using the httpOnly refresh cookie."""
    if not sf_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    try:
        payload = decode_token(sf_refresh, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")

    access = _issue_tokens(response, user)
    return envelope({"accessToken": access})


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Return the currently-authenticated user (incl. governance access flag)."""
    from app.core.governance import has_governance_access

    pub = _public(user)
    pub.governance_access = has_governance_access(db, user)
    return envelope(pub.model_dump())


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the refresh cookie."""
    response.delete_cookie(REFRESH_COOKIE)
    return envelope({"loggedOut": True})
