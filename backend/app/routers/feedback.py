from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.limiter import limiter

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    message: str
    page_url: str | None = None
    email: str | None = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        return v[:2000]  # hard cap

    @field_validator("page_url")
    @classmethod
    def validate_page_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()[:500]
        # Only allow relative paths or https metricshour.com URLs
        if v and not (v.startswith("/") or v.startswith("https://metricshour.com") or v.startswith("https://www.metricshour.com")):
            return None  # silently drop suspicious URLs
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()[:254]
        # Basic email format check
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            return None  # silently drop malformed emails
        return v


@router.post("")
@limiter.limit("5/minute;20/hour")
def submit_feedback(request: Request, body: FeedbackIn, db: Session = Depends(get_db)):
    if not body.message:
        raise HTTPException(status_code=422, detail="message is required")
    db.execute(
        text("INSERT INTO feedback (id, message, page_url, email) VALUES (gen_random_uuid(), :message, :page_url, :email)"),
        {"message": body.message, "page_url": body.page_url, "email": body.email}
    )
    db.commit()
    return {"ok": True}
