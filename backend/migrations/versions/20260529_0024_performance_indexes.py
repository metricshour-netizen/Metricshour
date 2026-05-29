"""Add missing performance indexes for screener, lens, and geo revenue lookups.

Revision ID: 0024_performance_indexes
Revises: 0023_smart_money_alerts
Create Date: 2026-05-29
"""
from alembic import op

revision = '0024_performance_indexes'
down_revision = '0023_smart_money_alerts'  # 20260520_0023_smart_money_alerts.py
branch_labels = None
depends_on = None


def upgrade() -> None:
    # assets — sector and market_cap for screener filters/ordering
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_assets_sector
        ON assets(sector) WHERE sector IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_assets_market_cap
        ON assets(market_cap_usd DESC NULLS LAST) WHERE market_cap_usd IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_assets_type_active
        ON assets(asset_type, is_active) WHERE is_active = true
    """)

    # stock_country_revenues — compound for per-asset latest-year geo lookups
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scr_asset_year
        ON stock_country_revenues(asset_id, fiscal_year DESC)
    """)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scr_country_year
        ON stock_country_revenues(country_id, fiscal_year DESC)
    """)

    # prices — covering index for latest-price queries (asset + interval + timestamp)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_prices_asset_interval_ts
        ON prices(asset_id, interval, timestamp DESC)
    """)

    # macro_calendar_events — compound for Lens what_to_watch (date + country)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_macro_cal_date_country
        ON macro_calendar_events(event_date, country_code)
    """)

    # smart_money_holdings — compound for per-investor per-quarter lookups
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sm_holdings_investor_quarter
        ON smart_money_holdings(investor_id, quarter_label)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_assets_sector")
    op.execute("DROP INDEX IF EXISTS idx_assets_market_cap")
    op.execute("DROP INDEX IF EXISTS idx_assets_type_active")
    op.execute("DROP INDEX IF EXISTS idx_scr_asset_year")
    op.execute("DROP INDEX IF EXISTS idx_scr_country_year")
    op.execute("DROP INDEX IF EXISTS idx_prices_asset_interval_ts")
    op.execute("DROP INDEX IF EXISTS idx_macro_cal_date_country")
    op.execute("DROP INDEX IF EXISTS idx_sm_holdings_investor_quarter")
