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
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feed import BlogPost, BlogStatus, FeedEvent
from app.routers.auth import get_current_user
from app.models.user import User
from app.storage import r2_public_url, r2_upload

router = APIRouter(prefix="/admin", tags=["admin"])

# ── Public blog endpoint (no auth required) ────────────────────────────────────

public_router = APIRouter(prefix="/blog", tags=["blog"])


class BlogPublicOut(BaseModel):
    id: int
    title: str
    slug: str
    body: str
    excerpt: str | None
    cover_image_url: str | None
    author_name: str
    importance_score: float
    published_at: datetime | None
    related_asset_ids: list[int] | None
    related_country_ids: list[int] | None

    class Config:
        from_attributes = True


@public_router.get("/{slug}", response_model=BlogPublicOut)
def get_blog_post(slug: str, db: Session = Depends(get_db)):
    """Public blog article endpoint — returns published posts only."""
    post = (
        db.query(BlogPost)
        .filter(BlogPost.slug == slug, BlogPost.status == BlogStatus.published)
        .first()
    )
    if post is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return post


# ── Schemas ───────────────────────────────────────────────────────────────────

class BlogIn(BaseModel):
    title: str
    body: str
    excerpt: str | None = None
    author_name: str = "MetricsHour Team"
    related_asset_ids: list[int] | None = None
    related_country_ids: list[int] | None = None
    importance_score: float = 5.0


class BlogUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    excerpt: str | None = None
    author_name: str | None = None
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
    while db.query(BlogPost).filter(BlogPost.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _auto_excerpt(body: str, max_len: int = 280) -> str:
    plain = body.strip()
    if len(plain) <= max_len:
        return plain
    return plain[:max_len].rsplit(" ", 1)[0] + "…"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/blogs", response_model=list[BlogOut])
def list_blogs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return (
        db.query(BlogPost)
        .order_by(BlogPost.created_at.desc())
        .all()
    )


@router.post("/blogs", response_model=BlogOut, status_code=status.HTTP_201_CREATED)
def create_blog(
    body: BlogIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
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
    _: User = Depends(get_current_user),
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
    post.status = BlogStatus.published
    post.published_at = now
    post.updated_at = now

    # Auto-create FeedEvent
    event = FeedEvent(
        title=post.title,
        body=post.excerpt or _auto_excerpt(post.body),
        event_type="blog",
        event_subtype="article",
        source_url=f"/blog/{post.slug}",
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")
    if post.status == BlogStatus.published:
        raise HTTPException(status_code=409, detail="Cannot delete a published post")
    db.delete(post)
    db.commit()


@router.post("/blogs/{post_id}/cover", response_model=dict)
async def upload_cover(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Upload cover image to R2, update post.cover_image_url, return URL."""
    post = db.get(BlogPost, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found")

    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP/GIF allowed")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    key = f"blog-covers/{post_id}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    r2_upload(key, data, content_type=file.content_type)

    url = r2_public_url(key)
    post.cover_image_url = url
    post.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"url": url, "key": key}
