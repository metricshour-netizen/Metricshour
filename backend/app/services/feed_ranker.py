"""
Feed ranking algorithm — scores feed events per user.

Scoring model (additive):

  recency_score    → exponential decay, half-life = 6 hours, max 10 pts
  importance_score → 0–10, set by the feed generator based on market impact
  follow_boost     → +8 per matched followed asset, +6 per matched followed country
  interaction_adj  → save +5 | share +4 | click +3 | view +1 | skip −5

Cold-start (no follows, no history): score = recency + importance
  → best financial content surfaces first without personalisation.

Pagination happens AFTER scoring so the algorithm always sees the full
candidate pool for a user's context window (last 48 hours, max 200 events).
"""

import math
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models.feed import FeedEvent, UserFollow, UserInteraction, InteractionType


# ── Constants ─────────────────────────────────────────────────────────────────

RECENCY_HALF_LIFE_HOURS = 6   # score halves every 6 hours
RECENCY_MAX_SCORE = 10.0
FOLLOW_ASSET_BOOST = 8.0
FOLLOW_COUNTRY_BOOST = 6.0
INTERACTION_WEIGHTS: dict[str, float] = {
    InteractionType.save:  5.0,
    InteractionType.share: 4.0,
    InteractionType.click: 3.0,
    InteractionType.view:  1.0,
    InteractionType.skip: -5.0,
}
# Only surface events from the last 48 hours in the candidate pool
CANDIDATE_WINDOW_HOURS = 48
# Hard cap on events scored per request (avoids N+1 issues at scale)
MAX_CANDIDATE_EVENTS = 300


class ScoredEvent(NamedTuple):
    score: float
    event: FeedEvent


def rank_feed(
    db: Session,
    user_id: int | None,
    page: int = 1,
    page_size: int = 20,
) -> list[FeedEvent]:
    """
    Return a ranked, paginated list of feed events for a user.

    Args:
        db:        SQLAlchemy session
        user_id:   None for anonymous visitors → fallback to recency + importance
        page:      1-indexed page number
        page_size: events per page (max 50)

    Returns:
        Ordered list of FeedEvent ORM objects.
    """
    page_size = min(page_size, 50)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CANDIDATE_WINDOW_HOURS)

    events = (
        db.query(FeedEvent)
        .filter(FeedEvent.published_at >= cutoff)
        .order_by(FeedEvent.published_at.desc())
        .limit(MAX_CANDIDATE_EVENTS)
        .all()
    )

    if not events:
        return []

    # For anonymous visitors skip personalisation
    if user_id is None:
        scored = [ScoredEvent(_base_score(e), e) for e in events]
    else:
        follows = (
            db.query(UserFollow)
            .filter(UserFollow.user_id == user_id)
            .all()
        )
        interactions = (
            db.query(UserInteraction)
            .filter(UserInteraction.user_id == user_id)
            .all()
        )
        scored = _score_for_user(events, follows, interactions)

    scored.sort(key=lambda s: s.score, reverse=True)

    start = (page - 1) * page_size
    end = start + page_size
    return [s.event for s in scored[start:end]]


# ── Internal ──────────────────────────────────────────────────────────────────

def _base_score(event: FeedEvent) -> float:
    """Recency + importance — used for anonymous users and as the baseline."""
    return _recency(event.published_at) + float(event.importance_score or 0)


def _recency(published_at: datetime) -> float:
    """Exponential decay: score = MAX * 0.5^(age / half_life)."""
    now = datetime.now(timezone.utc)
    # Ensure timezone-aware comparison
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
    return RECENCY_MAX_SCORE * math.exp(-age_hours * math.log(2) / RECENCY_HALF_LIFE_HOURS)


def _score_for_user(
    events: list[FeedEvent],
    follows: list[UserFollow],
    interactions: list[UserInteraction],
) -> list[ScoredEvent]:
    """Apply full personalisation scoring."""
    followed_assets: set[int] = {
        f.entity_id for f in follows if f.entity_type == "asset"
    }
    followed_countries: set[int] = {
        f.entity_id for f in follows if f.entity_type == "country"
    }
    interaction_map: dict[int, UserInteraction] = {
        i.feed_event_id: i for i in interactions
    }

    scored = []
    for event in events:
        score = _base_score(event)

        # Follow boost — sum boosts for all matched entities
        event_assets: set[int] = set(event.related_asset_ids or [])
        event_countries: set[int] = set(event.related_country_ids or [])
        score += len(event_assets & followed_assets) * FOLLOW_ASSET_BOOST
        score += len(event_countries & followed_countries) * FOLLOW_COUNTRY_BOOST

        # Interaction adjustment
        interaction = interaction_map.get(event.id)
        if interaction:
            score += INTERACTION_WEIGHTS.get(interaction.interaction_type, 0)

        scored.append(ScoredEvent(score, event))

    return scored
