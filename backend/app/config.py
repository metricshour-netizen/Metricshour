import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "")
    redis_url: str = os.environ.get("REDIS_URL", "")
    debug: bool = os.environ.get("DEBUG", "false").lower() == "true"
    allowed_origins: list[str] = os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000,https://metricshour.com"
    ).split(",")
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30
    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    marketstack_api_key: str = os.environ.get("MARKETSTACK_API_KEY", "")


settings = Settings()
