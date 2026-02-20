"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # countries
    # -------------------------------------------------------------------------
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer, primary_key=True),
        # Identity
        sa.Column("code", sa.String(2), nullable=False),
        sa.Column("code3", sa.String(3), nullable=False),
        sa.Column("numeric_code", sa.String(3), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_official", sa.String(200), nullable=True),
        sa.Column("capital_city", sa.String(100), nullable=True),
        sa.Column("flag_emoji", sa.String(10), nullable=True),
        sa.Column("slug", sa.String(100), nullable=True),
        # Geography
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("subregion", sa.String(50), nullable=True),
        sa.Column("area_km2", sa.Float, nullable=True),
        sa.Column("coastline_km", sa.Float, nullable=True),
        sa.Column("landlocked", sa.Boolean, nullable=True),
        sa.Column("island_nation", sa.Boolean, nullable=True),
        sa.Column("timezone_main", sa.String(50), nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("borders", JSONB, nullable=True),
        # Political
        sa.Column("government_type", sa.String(100), nullable=True),
        sa.Column("independence_year", sa.Integer, nullable=True),
        sa.Column("un_member", sa.Boolean, default=True),
        # Currency
        sa.Column("currency_code", sa.String(3), nullable=True),
        sa.Column("currency_name", sa.String(50), nullable=True),
        sa.Column("currency_symbol", sa.String(5), nullable=True),
        sa.Column("exchange_rate_regime", sa.String(30), nullable=True),
        # Groupings
        sa.Column("is_g7", sa.Boolean, default=False),
        sa.Column("is_g20", sa.Boolean, default=False),
        sa.Column("is_eu", sa.Boolean, default=False),
        sa.Column("is_eurozone", sa.Boolean, default=False),
        sa.Column("is_nato", sa.Boolean, default=False),
        sa.Column("is_opec", sa.Boolean, default=False),
        sa.Column("is_brics", sa.Boolean, default=False),
        sa.Column("is_asean", sa.Boolean, default=False),
        sa.Column("is_oecd", sa.Boolean, default=False),
        sa.Column("is_commonwealth", sa.Boolean, default=False),
        # Development classification
        sa.Column("income_level", sa.String(20), nullable=True),
        sa.Column("development_status", sa.String(20), nullable=True),
        # Credit ratings
        sa.Column("credit_rating_sp", sa.String(5), nullable=True),
        sa.Column("credit_outlook_sp", sa.String(10), nullable=True),
        sa.Column("credit_rating_moodys", sa.String(5), nullable=True),
        sa.Column("credit_outlook_moodys", sa.String(10), nullable=True),
        sa.Column("credit_rating_fitch", sa.String(5), nullable=True),
        sa.Column("credit_outlook_fitch", sa.String(10), nullable=True),
        sa.Column("credit_rating_updated", sa.Date, nullable=True),
        # Resources
        sa.Column("major_exports", JSONB, nullable=True),
        sa.Column("major_imports", JSONB, nullable=True),
        sa.Column("natural_resources", JSONB, nullable=True),
        sa.Column("commodity_dependent", sa.Boolean, nullable=True),
        # Language / misc
        sa.Column("official_languages", JSONB, nullable=True),
        sa.Column("calling_code", sa.String(10), nullable=True),
        sa.Column("tld", sa.String(10), nullable=True),
        # Constraints
        sa.UniqueConstraint("code", name="uq_countries_code"),
        sa.UniqueConstraint("code3", name="uq_countries_code3"),
        sa.UniqueConstraint("numeric_code", name="uq_countries_numeric_code"),
        sa.UniqueConstraint("slug", name="uq_countries_slug"),
    )

    # -------------------------------------------------------------------------
    # country_indicators
    # -------------------------------------------------------------------------
    op.create_table(
        "country_indicators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("country_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("indicator", sa.String(60), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("period_date", sa.Date, nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),  # annual, quarterly, monthly
        sa.Column("source", sa.String(30), nullable=False),
        sa.UniqueConstraint(
            "country_id", "indicator", "period_date",
            name="uq_country_indicator_date",
        ),
    )
    op.create_index("ix_country_indicators_lookup", "country_indicators",
                    ["country_id", "indicator", "period_date"])
    op.create_index("ix_country_indicators_indicator", "country_indicators",
                    ["indicator", "period_date"])

    # -------------------------------------------------------------------------
    # trade_pairs
    # -------------------------------------------------------------------------
    op.create_table(
        "trade_pairs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("exporter_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("importer_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("trade_value_usd", sa.Float, nullable=False),
        sa.Column("exports_usd", sa.Float, nullable=True),
        sa.Column("imports_usd", sa.Float, nullable=True),
        sa.Column("balance_usd", sa.Float, nullable=True),
        sa.Column("top_export_products", JSONB, nullable=True),
        sa.Column("top_import_products", JSONB, nullable=True),
        sa.Column("exporter_gdp_share_pct", sa.Float, nullable=True),
        sa.Column("importer_gdp_share_pct", sa.Float, nullable=True),
        sa.UniqueConstraint("exporter_id", "importer_id", "year", name="uq_trade_pair_year"),
    )
    op.create_index("ix_trade_pairs_exporter", "trade_pairs", ["exporter_id", "year"])
    op.create_index("ix_trade_pairs_importer", "trade_pairs", ["importer_id", "year"])

    # -------------------------------------------------------------------------
    # assets
    # -------------------------------------------------------------------------
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_type", sa.String(10), nullable=False),  # stock, crypto, commodity, fx
        sa.Column("exchange", sa.String(20), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        # Stock-specific
        sa.Column("sector", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("country_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("market_cap_usd", sa.Float, nullable=True),
        # FX-specific
        sa.Column("base_currency", sa.String(3), nullable=True),
        sa.Column("quote_currency", sa.String(3), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.UniqueConstraint("symbol", "exchange", name="uq_asset_symbol_exchange"),
    )
    op.create_index("ix_assets_type", "assets", ["asset_type"])

    # -------------------------------------------------------------------------
    # prices
    # -------------------------------------------------------------------------
    op.create_table(
        "prices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),  # 1m, 15m, 1h, 1d
        sa.Column("open", sa.Float, nullable=True),
        sa.Column("high", sa.Float, nullable=True),
        sa.Column("low", sa.Float, nullable=True),
        sa.Column("close", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=True),
        sa.UniqueConstraint("asset_id", "timestamp", "interval", name="uq_price_asset_time_interval"),
    )
    op.create_index("ix_prices_asset_timestamp", "prices", ["asset_id", "timestamp"])

    # -------------------------------------------------------------------------
    # stock_country_revenues
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_country_revenues",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("country_id", sa.Integer, sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("revenue_pct", sa.Float, nullable=False),
        sa.Column("revenue_usd", sa.Float, nullable=True),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("fiscal_quarter", sa.Integer, nullable=True),
        sa.UniqueConstraint(
            "asset_id", "country_id", "fiscal_year", "fiscal_quarter",
            name="uq_stock_country_revenue",
        ),
    )
    op.create_index("ix_stock_country_revenue_asset", "stock_country_revenues",
                    ["asset_id", "fiscal_year"])
    op.create_index("ix_stock_country_revenue_country", "stock_country_revenues",
                    ["country_id", "fiscal_year"])

    # -------------------------------------------------------------------------
    # users
    # -------------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # -------------------------------------------------------------------------
    # price_alerts
    # -------------------------------------------------------------------------
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("condition", sa.String(5), nullable=False),  # above, below
        sa.Column("target_price", sa.Float, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -------------------------------------------------------------------------
    # feed_events
    # -------------------------------------------------------------------------
    op.create_table(
        "feed_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.String(5000), nullable=True),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("related_asset_ids", sa.String(200), nullable=True),
        sa.Column("related_country_ids", sa.String(200), nullable=True),
    )
    op.create_index("ix_feed_events_published_at", "feed_events", ["published_at"])


def downgrade() -> None:
    op.drop_table("feed_events")
    op.drop_table("price_alerts")
    op.drop_table("users")
    op.drop_table("stock_country_revenues")
    op.drop_table("prices")
    op.drop_table("assets")
    op.drop_table("trade_pairs")
    op.drop_table("country_indicators")
    op.drop_table("countries")
