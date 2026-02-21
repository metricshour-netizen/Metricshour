import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.routers import health, countries, assets, trade, auth, search, feed, admin
from app.routers.admin import public_router as blog_router

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.2,   # 20% of requests traced (adjust up if needed)
        send_default_pii=False,
        environment="production" if not settings.debug else "development",
    )

app = FastAPI(
    title="MetricsHour API",
    description="Global financial intelligence — stocks, macro, trade, crypto, FX, commodities",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(countries.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(feed.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(blog_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"name": "MetricsHour API", "docs": "/docs"}
