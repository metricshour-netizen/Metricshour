from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, countries, assets, trade, auth

app = FastAPI(
    title="MetricsHour API",
    description="Global financial intelligence — stocks, macro, trade, crypto, FX, commodities",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(countries.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"name": "MetricsHour API", "docs": "/docs"}
