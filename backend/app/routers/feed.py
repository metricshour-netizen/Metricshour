"""
Feed router — adaptive personalised financial feed.

Public endpoints (no auth):
  GET /api/feed               — ranked feed (anonymous = recency + importance only)

Authenticated endpoints (Bearer token required):
  POST /api/feed/{event_id}/interact   — record engagement signal
  GET  /api/follow                     — list what I follow
  POST /api/follow                     — follow an asset or country
  DELETE /api/follow/{entity_type}/{entity_id} — unfollow
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.country import Country
from app.models.feed import (
    FeedEvent,
    FollowEntityType,
    InteractionType,
    UserFollow,
    UserInteraction,
)
from app.models.user import User
from app.services.feed_ranker import rank_feed

router = APIRouter(prefix="/feed", tags=["feed"])

# Optional auth — does not raise 401 for anonymous users
_oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _optional_user(
    token: str | None = Depends(_oauth2_optional),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated User or None for anonymous requests."""
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()


def _require_user(
    token: str | None = Depends(_oauth2_optional),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated User or raise 401."""
    user = _optional_user.__wrapped__(token, db) if hasattr(_optional_user, "__wrapped__") else None
    # Inline the logic cleanly
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FeedEventOut(BaseModel):
    id: int
    title: str
    body: str | None
    event_type: str
    event_subtype: str | None
    source_url: str | None
    image_url: str | None
    published_at: datetime
    related_asset_ids: list[int] | None
    related_country_ids: list[int] | None
    event_data: dict | None
    importance_score: float | None

    class Config:
        from_attributes = True


class FeedPageOut(BaseModel):
    page: int
    page_size: int
    events: list[FeedEventOut]


class InteractIn(BaseModel):
    interaction_type: InteractionType
    dwell_seconds: int | None = None


class FollowIn(BaseModel):
    entity_type: FollowEntityType
    entity_id: int


class FollowOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    followed_at: datetime

    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=FeedPageOut)
def get_feed(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(_optional_user),
):
    """
    Return the ranked adaptive feed.

    Anonymous users get recency + importance + geo ranking.
    Authenticated users get personalised ranking based on follows + past interactions + geo.
    Geo signal comes from the Cloudflare CF-IPCountry header (2-letter ISO code).
    """
    user_id = current_user.id if current_user else None

    # Detect visitor's country from Cloudflare header (no extra API call needed)
    geo_country_id: int | None = None
    cf_country = request.headers.get("cf-ipcountry", "").strip().upper()
    if cf_country and cf_country not in ("", "T1", "XX"):  # T1=Tor, XX=unknown
        row = db.query(Country.id).filter(Country.code == cf_country).first()
        if row:
            geo_country_id = row[0]

    events = rank_feed(
        db,
        user_id=user_id,
        page=page,
        page_size=page_size,
        geo_country_id=geo_country_id,
    )
    return FeedPageOut(page=page, page_size=page_size, events=events)


@router.post("/{event_id}/interact", status_code=status.HTTP_204_NO_CONTENT)
def record_interaction(
    event_id: int,
    body: InteractIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_user),
):
    """
    Record a user interaction on a feed event.
    Upserts — only the most recent interaction per user per event is kept.
    """
    event = db.get(FeedEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Feed event not found")

    # Upsert — if a row exists for (user_id, feed_event_id), update it
    stmt = (
        pg_insert(UserInteraction)
        .values(
            user_id=current_user.id,
            feed_event_id=event_id,
            interaction_type=body.interaction_type,
            dwell_seconds=body.dwell_seconds,
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_user_interaction",
            set_={
                "interaction_type": body.interaction_type,
                "dwell_seconds": body.dwell_seconds,
                "created_at": datetime.now(timezone.utc),
            },
        )
    )
    db.execute(stmt)
    db.commit()


@router.get("/follows", response_model=list[FollowOut])
def list_follows(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_user),
):
    """Return everything the current user follows."""
    return (
        db.query(UserFollow)
        .filter(UserFollow.user_id == current_user.id)
        .order_by(UserFollow.followed_at.desc())
        .all()
    )


@router.post("/follows", response_model=FollowOut, status_code=status.HTTP_201_CREATED)
def add_follow(
    body: FollowIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_user),
):
    """Follow an asset or country."""
    existing = (
        db.query(UserFollow)
        .filter(
            UserFollow.user_id == current_user.id,
            UserFollow.entity_type == body.entity_type,
            UserFollow.entity_id == body.entity_id,
        )
        .first()
    )
    if existing:
        return existing  # idempotent

    follow = UserFollow(
        user_id=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        followed_at=datetime.now(timezone.utc),
    )
    db.add(follow)
    db.commit()
    db.refresh(follow)
    return follow


@router.delete(
    "/follows/{entity_type}/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_follow(
    entity_type: FollowEntityType,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_user),
):
    """Unfollow an asset or country."""
    follow = (
        db.query(UserFollow)
        .filter(
            UserFollow.user_id == current_user.id,
            UserFollow.entity_type == entity_type,
            UserFollow.entity_id == entity_id,
        )
        .first()
    )
    if follow is None:
        raise HTTPException(status_code=404, detail="Follow not found")
    db.delete(follow)
    db.commit()
