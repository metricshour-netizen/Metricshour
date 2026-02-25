from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

class FeedbackIn(BaseModel):
    message: str
    page_url: str | None = None
    email: str | None = None

@router.post("")
def submit_feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    db.execute(
        text("INSERT INTO feedback (id, message, page_url, email) VALUES (gen_random_uuid(), :message, :page_url, :email)"),
        {"message": body.message[:2000], "page_url": body.page_url, "email": body.email}
    )
    db.commit()
    return {"ok": True}
