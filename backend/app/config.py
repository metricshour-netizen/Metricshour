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
    comtrade_api_key: str = os.environ.get("COMTRADE_API_KEY", "")
    # Cloudflare
    cf_account_id: str = os.environ.get("CF_ACCOUNT_ID", "")
    cf_api_token: str = os.environ.get("CF_API_TOKEN", "")
    cf_kv_namespace_id: str = os.environ.get("CF_KV_NAMESPACE_ID", "")
    # R2
    r2_bucket_name: str = os.environ.get("R2_BUCKET_NAME", "metricshour-assets")
    r2_endpoint: str = os.environ.get("R2_ENDPOINT", "")
    r2_access_key_id: str = os.environ.get("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    r2_public_url: str = os.environ.get("R2_PUBLIC_URL", "")
    # Meilisearch
    meili_url: str = os.environ.get("MEILI_URL", "http://127.0.0.1:7700")
    meili_master_key: str = os.environ.get("MEILI_MASTER_KEY", "")
    # Sentry
    sentry_dsn: str = os.environ.get("SENTRY_DSN", "")
    # Google OAuth
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    # Google Indexing API (service account JSON key file path)
    google_indexing_key_file: str = os.environ.get("GOOGLE_INDEXING_KEY_FILE", "")
    frontend_url: str = os.environ.get("FRONTEND_URL", "https://metricshour.com")
    api_url: str = os.environ.get("API_URL", "https://api.metricshour.com")
    # Notifications
    telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_webhook_secret: str = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    resend_api_key: str = os.environ.get("RESEND_API_KEY", "")
    resend_from_email: str = os.environ.get("RESEND_FROM_EMAIL", "alerts@metricshour.com")
    # Unsplash (cover image auto-fetch)
    unsplash_access_key: str = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    # Tiingo financial data
    tiingo_api_key: str = os.environ.get("TIINGO_API_KEY", "")


settings = Settings()
