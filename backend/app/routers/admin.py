"""
Blog admin router — internal CRM for managing blog posts.

All endpoints require an authenticated user (any tier for now).
Lock to admin role once a role field is added to users.

GET    /api/admin/blogs           — list all posts (draft + published)
POST   /api/admin/blogs           — create draft
PUT    /api/admin/blogs/{id}      — update fields
POST   /api/admin/blogs/{id}/publish  — publish + auto-create FeedEvent
DELETE /api/admin/blogs/{id}      — delete (draft only)
POST   /api/admin/blogs/{id}/cover    — upload cover image to R2
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feed import BlogPost, BlogAuthor, BlogStatus, FeedEvent, BLOG_CATEGORIES
from app.routers.auth import get_admin_user, get_current_user
from app.models.user import User, LoginEvent, PageView
from app.storage import r2_public_url, r2_upload
from app.limiter import limiter
from app.utils.deep_links import inject_deep_links, detect_entities

router = APIRouter(prefix="/admin", tags=["admin"])

# ── Public blog endpoint (no auth required) ────────────────────────────────────

public_router = APIRouter(prefix="/blog", tags=["blog"])


class AuthorPublicOut(BaseModel):
    slug: str
    name: str
    title: str | None
    bio: str | None
    avatar_url: str | None
    twitter_handle: str | None

    class Config:
        from_attributes = True


class BlogPublicOut(BaseModel):
    id: int
    title: str
    slug: str
    body: str
    excerpt: str | None
    cover_image_url: str | None
    author_name: str
    author_slug: str | None
    author: AuthorPublicOut | None
    category: str | None
    importance_score: float
    published_at: datetime | None
    updated_at: datetime
    related_asset_ids: list[int] | None
    related_country_ids: list[int] | None

    class Config:
        from_attributes = True


class BlogListOut(BaseModel):
    """Lightweight blog list item — excludes body to avoid sending 10KB× N posts over the wire."""
    id: int
    title: str
    slug: str
    excerpt: str | None
    cover_image_url: str | None
    author_name: str
    author_slug: str | None
    category: str | None
    published_at: datetime | None

    class Config:
        from_attributes = True


@public_router.get("/categories", response_model=list[str])
def list_blog_categories():
    """Return the ordered list of valid blog categories."""
    return BLOG_CATEGORIES


@public_router.get("/authors/{author_slug}", response_model=AuthorPublicOut)
def get_blog_author(author_slug: str, db: Session = Depends(get_db)):
    author = db.get(BlogAuthor, author_slug)
    if author is None:
        raise HTTPException(status_code=404, detail="Author not found")
    return author


@public_router.get("/authors/{author_slug}/posts", response_model=list[BlogListOut])
def get_author_posts(author_slug: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    posts = db.execute(
        select(BlogPost)
        .where(BlogPost.author_slug == author_slug, BlogPost.status == BlogStatus.published)
        .order_by(BlogPost.published_at.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return posts


@public_router.get("", response_model=list[BlogListOut])
def list_blog_posts(
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Public blog listing — published posts only, newest first. Filter by ?category=macro etc."""
    q = select(BlogPost).where(BlogPost.status == BlogStatus.published)
    if category:
        q = q.where(BlogPost.category == category)
    posts = db.execute(
        q.order_by(BlogPost.published_at.desc()).offset(offset).limit(limit)
    ).scalars().all()
    return posts


@public_router.get("/{slug}", response_model=BlogPublicOut)
def get_blog_post(slug: str, db: Session = Depends(get_db)):
    """Public blog article endpoint — returns published posts only."""
    post = db.execute(
        select(BlogPost)
        .where(BlogPost.slug == slug, BlogPost.status == BlogStatus.published)
    ).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return post


# ── Schemas ───────────────────────────────────────────────────────────────────

class BlogIn(BaseModel):
    title: str
    body: str
    excerpt: str | None = None
    author_name: str = "MetricsHour Team"
    author_slug: str | None = "metricshour-team"
    category: str | None = None
    cover_image_url: str | None = None
    related_asset_ids: list[int] | None = None
    related_country_ids: list[int] | None = None
    importance_score: float = 5.0


class BlogUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    excerpt: str | None = None
    author_name: str | None = None
    author_slug: str | None = None
    category: str | None = None
    related_asset_ids: list[int] | None = None
    related_country_ids: list[int] | None = None
    importance_score: float | None = None
    cover_image_url: str | None = None


class BlogOut(BaseModel):
    id: int
    title: str
    slug: str
    excerpt: str | None
    cover_image_url: str | None
    author_name: str
    author_slug: str | None
    category: str | None
    status: str
    related_asset_ids: list[int] | None
    related_country_ids: list[int] | None
    importance_score: float
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    feed_event_id: int | None

    class Config:
        from_attributes = True


class AuthorIn(BaseModel):
    slug: str
    name: str
    title: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    twitter_handle: str | None = None


class AuthorUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    twitter_handle: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:280]


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    counter = 1
    while db.execute(select(BlogPost).where(BlogPost.slug == slug)).scalar_one_or_none():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _auto_excerpt(body: str, max_len: int = 280) -> str:
    """Extract a clean plaintext excerpt from markdown body."""
    import re as _re
    # Find first non-empty paragraph that isn't a heading/image/hr
    for para in body.split("\n\n"):
        line = para.strip()
        if not line or line.startswith("#") or line.startswith("!") or line.startswith("---"):
            continue
        # Strip inline markdown: bold, italic, code, links
        line = _re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)  # [text](url) → text
        line = _re.sub(r"`+([^`]+)`+", r"\1", line)             # `code` → code
        line = _re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", line)   # bold/italic → plain
        line = _re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", line)     # _italic_ → plain
        line = " ".join(line.split())                             # normalise whitespace
        if len(line) <= max_len:
            return line
        return line[:max_len].rsplit(" ", 1)[0] + "…"
    # Fallback: first max_len chars of body
    return body.strip()[:max_len].rsplit(" ", 1)[0] + "…"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/blogs", response_model=list[BlogOut])
def list_blogs(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    return db.execute(
        select(BlogPost).order_by(BlogPost.created_at.desc())
    ).scalars().all()


@router.post("/blogs", response_model=BlogOut, status_code=status.HTTP_201_CREATED)
def create_blog(
    body: BlogIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    now = datetime.now(timezone.utc)
    slug = _unique_slug(db, _slugify(body.title))
    excerpt = body.excerpt or _auto_excerpt(body.body)

    post = BlogPost(
        title=body.title,
        slug=slug,
        body=body.body,
        excerpt=excerpt,
        author_name=body.author_name,
        author_slug=body.author_slug,
        category=body.category,
        cover_image_url=body.cover_image_url,
        status=BlogStatus.draft,
        related_asset_ids=body.related_asset_ids,
        related_country_ids=body.related_country_ids,
        importance_score=body.importance_score,
        created_at=now,
        updated_at=now,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.put("/blogs/{post_id}", response_model=BlogOut)
def update_blog(
    post_id: int,
    body: BlogUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(post, field, value)

    # Auto-regenerate excerpt if body changed but no explicit excerpt provided
    if body.body and not body.excerpt:
        post.excerpt = _auto_excerpt(body.body)

    post.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)
    return post


@router.post("/blogs/{post_id}/publish", response_model=BlogOut)
def publish_blog(
    post_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """
    Publish a draft blog post.
    Auto-creates a FeedEvent so the article appears in the adaptive feed.
    """
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    if post.status == BlogStatus.published:
        raise HTTPException(status_code=409, detail="Post already published")

    now = datetime.now(timezone.utc)
    post.body = inject_deep_links(post.body or "")
    post.status = BlogStatus.published
    post.published_at = now
    post.updated_at = now

    # Auto-detect entity tags from body text and merge with any manually set IDs
    tickers_found, country_codes_found = detect_entities(post.body)

    if tickers_found:
        from app.models.asset import Asset as _Asset
        rows = db.execute(
            select(_Asset.id, _Asset.symbol).where(
                _Asset.symbol.in_(tickers_found), _Asset.is_active == True
            )
        ).all()
        detected_asset_ids = [r.id for r in rows]
        existing_asset_ids = list(post.related_asset_ids or [])
        merged = list(dict.fromkeys(existing_asset_ids + detected_asset_ids))  # deduped, order preserved
        post.related_asset_ids = merged

    if country_codes_found:
        from app.models.country import Country as _Country
        rows = db.execute(
            select(_Country.id).where(_Country.code.in_([c.upper() for c in country_codes_found]))
        ).all()
        detected_country_ids = [r.id for r in rows]
        existing_country_ids = list(post.related_country_ids or [])
        merged = list(dict.fromkeys(existing_country_ids + detected_country_ids))
        post.related_country_ids = merged

    # Auto-create FeedEvent
    event = FeedEvent(
        title=post.title,
        body=post.excerpt or _auto_excerpt(post.body),
        event_type="blog",
        event_subtype="article",
        source_url=f"/blog/{post.slug}/",
        image_url=post.cover_image_url,
        published_at=now,
        related_asset_ids=post.related_asset_ids,
        related_country_ids=post.related_country_ids,
        importance_score=post.importance_score,
        event_data={"slug": post.slug, "author": post.author_name},
    )
    db.add(event)
    db.flush()  # get event.id before committing

    post.feed_event_id = event.id
    db.commit()
    db.refresh(post)
    return post


@router.delete("/blogs/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blog(
    post_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    if post.status == BlogStatus.published and not force:
        raise HTTPException(status_code=409, detail="Cannot delete a published post. Use ?force=true to override.")
    # Clean up linked FeedEvent if present
    if post.feed_event_id:
        from app.models.feed import FeedEvent as _FeedEvent
        event = db.get(_FeedEvent, post.feed_event_id)
        if event:
            db.delete(event)
    db.delete(post)
    db.commit()


@router.post("/blogs/{post_id}/cover", response_model=dict)
async def upload_cover(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """Upload cover image to R2, update post.cover_image_url, return URL."""
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")

    _ALLOWED_TYPES = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP/GIF allowed")

    # Derive extension from content-type — never trust the user-supplied filename
    ext = _ALLOWED_TYPES[file.content_type]
    key = f"blog-covers/{post_id}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()

    _MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large — maximum 5 MB")

    r2_upload(key, data, content_type=file.content_type)

    url = r2_public_url(key)
    post.cover_image_url = url
    post.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"url": url, "key": key}


# ── Admin author management ───────────────────────────────────────────────────

@router.get("/authors", response_model=list[AuthorPublicOut])
def list_authors(db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    return db.execute(select(BlogAuthor)).scalars().all()


@router.post("/authors", response_model=AuthorPublicOut, status_code=status.HTTP_201_CREATED)
def create_author(body: AuthorIn, db: Session = Depends(get_db), _: User = Depends(get_admin_user)):
    if db.get(BlogAuthor, body.slug):
        raise HTTPException(status_code=409, detail="Author slug already exists")
    from datetime import timezone as _tz
    author = BlogAuthor(
        slug=body.slug,
        name=body.name,
        title=body.title,
        bio=body.bio,
        avatar_url=body.avatar_url,
        twitter_handle=body.twitter_handle,
        created_at=datetime.now(timezone.utc),
    )
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


@router.put("/authors/{author_slug}", response_model=AuthorPublicOut)
def update_author(
    author_slug: str,
    body: AuthorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    author = db.get(BlogAuthor, author_slug)
    if author is None:
        raise HTTPException(status_code=404, detail="Author not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(author, field, value)
    db.commit()
    db.refresh(author)
    return author


@router.post("/authors/{author_slug}/avatar", response_model=dict)
async def upload_author_avatar(
    author_slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    author = db.get(BlogAuthor, author_slug)
    if author is None:
        raise HTTPException(status_code=404, detail="Author not found")
    _ALLOWED_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP allowed")
    ext = _ALLOWED_TYPES[file.content_type]
    key = f"author-avatars/{author_slug}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large — maximum 2 MB")
    r2_upload(key, data, content_type=file.content_type)
    url = r2_public_url(key)
    author.avatar_url = url
    db.commit()
    return {"url": url}


# ── Admin stats dashboard ──────────────────────────────────────────────────────

@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    now = datetime.now(timezone.utc)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    total_users = db.execute(select(func.count(User.id))).scalar()
    new_7d = db.execute(select(func.count(User.id)).where(User.created_at >= d7)).scalar()
    new_30d = db.execute(select(func.count(User.id)).where(User.created_at >= d30)).scalar()
    pro_users = db.execute(select(func.count(User.id)).where(User.tier != "free")).scalar()

    logins_7d = db.execute(
        select(func.count(LoginEvent.id)).where(LoginEvent.created_at >= d7)
    ).scalar()

    recent_logins = db.execute(
        select(LoginEvent, User.email)
        .join(User, LoginEvent.user_id == User.id)
        .order_by(LoginEvent.created_at.desc())
        .limit(20)
    ).all()

    recent_signups = db.execute(
        select(User).order_by(User.created_at.desc()).limit(10)
    ).scalars().all()

    top_pages = db.execute(
        select(PageView.entity_type, PageView.entity_code, func.count(PageView.id).label("views"))
        .where(PageView.created_at >= d7)
        .group_by(PageView.entity_type, PageView.entity_code)
        .order_by(func.count(PageView.id).desc())
        .limit(20)
    ).all()

    return {
        "users": {
            "total": total_users,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "paid": pro_users,
        },
        "logins": {
            "total_7d": logins_7d,
            "recent": [
                {
                    "email": email,
                    "ip": e.ip_address,
                    "method": e.method,
                    "created_at": e.created_at.isoformat(),
                }
                for e, email in recent_logins
            ],
        },
        "signups": [
            {
                "id": u.id,
                "email": u.email,
                "tier": u.tier,
                "created_at": u.created_at.isoformat(),
            }
            for u in recent_signups
        ],
        "top_pages": [
            {"entity_type": et, "entity_code": ec, "views": v}
            for et, ec, v in top_pages
        ],
    }


# ── Page view tracker (fire-and-forget from frontend) ─────────────────────────

class TrackIn(BaseModel):
    entity_type: str   # 'country' | 'stock' | 'trade' | 'commodity'
    entity_code: str


_VALID_ENTITY_TYPES = {"country", "stock", "trade", "commodity"}

# Public router so any visitor's page views are counted (no auth required)
track_router = APIRouter(tags=["analytics"])


@track_router.post("/api/track", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("120/minute")
def track_page_view(
    request: Request,
    body: TrackIn,
    db: Session = Depends(get_db),
):
    if body.entity_type not in _VALID_ENTITY_TYPES:
        return  # silently ignore invalid types

    # Optionally associate with logged-in user (best-effort, no error if token missing)
    user_id = None
    try:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            from jose import jwt as _jwt
            from app.config import settings as _s
            payload = _jwt.decode(auth_header[7:], _s.jwt_secret, algorithms=[_s.jwt_algorithm])
            user_id = int(payload.get("sub", 0)) or None
    except Exception:
        pass

    db.add(PageView(
        entity_type=body.entity_type,
        entity_code=body.entity_code[:50],
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
