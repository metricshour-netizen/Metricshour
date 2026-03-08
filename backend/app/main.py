import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.routers import health, countries, assets, trade, auth, search, feed, admin, share, og, sitemap
from app.routers import alerts as alerts_router
from app.routers.admin import public_router as blog_router
from app.routers import intelligence
from app.routers import feedback

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
    # Disable interactive docs in production to avoid exposing the full API schema
    docs_url=None if not settings.debug else "/docs",
    redoc_url=None if not settings.debug else "/redoc",
    openapi_url=None if not settings.debug else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # HSTS — only sent over HTTPS (Nginx handles SSL, so this is safe)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(health.router)
app.include_router(countries.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(feed.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(blog_router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(feedback.router)
app.include_router(share.router)   # /s/{id} — social share OG preview (no prefix)
app.include_router(og.router)      # /og/feed/{id}.png, /og/countries/{code}.png, /og/stocks/{symbol}.png
app.include_router(sitemap.router) # /sitemap.xml — no Bot Fight Mode here
app.include_router(alerts_router.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"name": "MetricsHour API", "docs": "/docs"}
