from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.storage import get_redis

router = APIRouter()


@router.api_route("/health", methods=["GET", "HEAD"])
def health_check() -> JSONResponse:
    """
    Liveness + readiness probe.
    Checks DB (SELECT 1) and Redis (PING). Returns 503 if either is unhealthy.
    """
    db_ok = False
    redis_ok = False
    errors: list[str] = []

    # Database check
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        errors.append(f"database: {exc}")

    # Redis check
    try:
        r = get_redis()
        r.ping()
        redis_ok = True
    except Exception as exc:
        errors.append(f"redis: {exc}")

    status_code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if status_code == 200 else "degraded",
            "database": "connected" if db_ok else "unavailable",
            "redis": "connected" if redis_ok else "unavailable",
            **({"errors": errors} if errors else {}),
        },
    )
