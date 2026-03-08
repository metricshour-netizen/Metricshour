"""
Auth router — register, login, /me, Google OAuth.
POST /api/auth/register              — create account (returns token)
POST /api/auth/login                 — OAuth2 password flow (returns token)
GET  /api/auth/me                    — current user info (requires token)
GET  /api/auth/google/authorize      — redirect to Google OAuth consent
GET  /api/auth/google/callback       — handle Google OAuth callback
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests as http_requests
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserTier, LoginEvent
from app.notifications import send_welcome_email
from app.storage import redis_json_set, redis_json_get, redis_json_del

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://metricshour.com")

router = APIRouter(prefix="/auth", tags=["auth"])

_ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tier: str


class UserOut(BaseModel):
    id: int
    email: str
    tier: str
    is_admin: bool
    created_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_token(user_id: int, tier: str, is_admin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(
        {"sub": str(user_id), "tier": tier, "is_admin": is_admin, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _token_key(token: str) -> str:
    """Short Redis key derived from token hash — never stores the raw token."""
    return "auth:revoked:" + hashlib.sha256(token.encode()).hexdigest()[:32]


# ── Brute-force protection ────────────────────────────────────────────────────

_FAIL_MAX = 10       # lock after this many failures
_FAIL_WINDOW = 900   # seconds — 15 min lockout window


def _fail_key(email: str) -> str:
    return f"auth:fail:{email.lower()}"


def _check_brute_force(email: str) -> None:
    data = redis_json_get(_fail_key(email))
    if data and data.get("count", 0) >= _FAIL_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )


def _record_fail(email: str) -> None:
    data = redis_json_get(_fail_key(email)) or {"count": 0}
    data["count"] = data["count"] + 1
    redis_json_set(_fail_key(email), data, ttl_seconds=_FAIL_WINDOW)


def _clear_fails(email: str) -> None:
    redis_json_del(_fail_key(email))


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    # Check revocation list — logout stores the token hash here
    if redis_json_get(_token_key(token)) is not None:
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise credentials_error
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user = User(
        email=body.email,
        password_hash=_ph.hash(body.password),
        tier=UserTier.free,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Welcome email — fire and forget (don't fail registration if email fails)
    try:
        send_welcome_email(user.email)
    except Exception:
        pass

    return TokenOut(access_token=_make_token(user.id, user.tier, user.is_admin), tier=user.tier)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    _check_brute_force(form.username)

    user = db.query(User).filter(User.email == form.username, User.is_active == True).first()
    if not user:
        _record_fail(form.username)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        _ph.verify(user.password_hash, form.password)
    except VerifyMismatchError:
        _record_fail(form.username)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _clear_fails(form.username)
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    db.add(LoginEvent(
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:512],
        method="password",
        created_at=now,
    ))
    db.commit()

    return TokenOut(access_token=_make_token(user.id, user.tier, user.is_admin), tier=user.tier)


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        tier=current_user.tier,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
    )


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
def forgot_password(request: Request, body: ForgotIn, db: Session = Depends(get_db)):
    """Send a password reset link. Always returns 204 — never reveals if email exists."""
    user = db.query(User).filter(User.email == body.email, User.is_active == True).first()
    if user and user.password_hash != "__google__":
        token = secrets.token_urlsafe(32)
        redis_json_set(f"auth:reset:{token}", {"email": user.email}, ttl_seconds=3600)
        from app.notifications import send_password_reset_email
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            pass


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetIn, db: Session = Depends(get_db)):
    """Consume a reset token and update the user's password."""
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    data = redis_json_get(f"auth:reset:{body.token}")
    if not data:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    user = db.query(User).filter(User.email == data["email"], User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    user.password_hash = _ph.hash(body.password)
    db.commit()
    redis_json_del(f"auth:reset:{body.token}")  # one-time use


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(oauth2_scheme)):
    """Revoke the current JWT so it cannot be reused even before it expires."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        exp: int = payload.get("exp", 0)
        remaining_ttl = max(1, exp - int(datetime.now(timezone.utc).timestamp()))
    except JWTError:
        # Token already invalid — nothing to revoke
        return
    redis_json_set(_token_key(token), {"revoked": True}, ttl_seconds=remaining_ttl)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/authorize")
def google_authorize():
    """Redirect user to Google OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(16)
    redis_json_set(f"oauth:state:{state}", {"valid": True}, ttl_seconds=600)

    params = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.api_url}/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    })
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """Exchange Google code for user info, create/find user, return JWT."""
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")

    # Validate state (CSRF) — delete immediately after reading to prevent replay
    cached = redis_json_get(f"oauth:state:{state}")
    if not cached:
        return RedirectResponse(f"{_FRONTEND_URL}/auth/callback?error=invalid_state")
    redis_json_del(f"oauth:state:{state}")  # consume one-time state

    # Exchange code for tokens
    token_resp = http_requests.post(_GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": f"{settings.api_url}/api/auth/google/callback",
        "grant_type": "authorization_code",
    }, timeout=10)

    if token_resp.status_code != 200:
        return RedirectResponse(f"{_FRONTEND_URL}/auth/callback?error=token_exchange_failed")

    access_token = token_resp.json().get("access_token")

    # Get user info from Google
    userinfo_resp = http_requests.get(
        _GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        return RedirectResponse(f"{_FRONTEND_URL}/auth/callback?error=userinfo_failed")

    userinfo = userinfo_resp.json()
    email = userinfo.get("email", "").lower().strip()
    if not email:
        return RedirectResponse(f"{_FRONTEND_URL}/auth/callback?error=no_email")

    # Find or create user
    user = db.query(User).filter(User.email == email).first()
    is_new = user is None

    if is_new:
        user = User(
            email=email,
            password_hash="__google__",   # no password — Google-only account
            tier=UserTier.free,
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        try:
            send_welcome_email(user.email)
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    user.last_login_at = now
    db.add(LoginEvent(
        user_id=user.id,
        ip_address=None,   # Google OAuth — IP not easily available at callback
        user_agent=None,
        method="google",
        created_at=now,
    ))
    db.commit()

    jwt_token = _make_token(user.id, user.tier, user.is_admin)
    return RedirectResponse(
        f"{_FRONTEND_URL}/auth/callback?token={jwt_token}&tier={user.tier}&new={str(is_new).lower()}"
    )
