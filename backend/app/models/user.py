"""User / authentication schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


def _lower_email(v: str) -> str:
    """Emails are case-insensitive identities: normalise so ``Admin@x.com`` == ``admin@x.com``."""
    return v.strip().lower()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    vpa: str = Field(..., pattern=r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")
    home_city: str = Field(default="Mumbai", max_length=120)

    _normalise_email = field_validator("email")(_lower_email)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    device_id: str = Field(default="web-default", max_length=120)

    _normalise_email = field_validator("email")(_lower_email)


class StepUpRequest(BaseModel):
    challenge_id: str
    otp: str = Field(..., min_length=4, max_length=8)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    vpa: str
    role: str
    home_city: str
    # True only for the governance council + the main admin.
    governance_access: bool = False


class LoginResponse(BaseModel):
    access_token: str | None = None
    user: UserPublic
    login_risk_score: int
    login_risk_tier: str
    step_up_required: bool
    challenge_id: str | None = None
    # Demo only: in production the OTP is delivered out-of-band (SMS/app), never returned.
    demo_otp: str | None = None
