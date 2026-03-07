from sqlalchemy import String, Float, Date, Boolean, Integer, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date

from .base import Base


class Country(Base):
    """
    Static/rarely-changing facts about a country.
    Time-series data (GDP, population, inflation...) lives in CountryIndicator.
    """

    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identity
    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)    # ISO 3166-1 alpha-2: US, DE
    code3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)   # ISO 3166-1 alpha-3: USA, DEU
    numeric_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=True)  # UN M49: 840
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_official: Mapped[str] = mapped_column(String(200), nullable=True)       # United States of America
    capital_city: Mapped[str] = mapped_column(String(100), nullable=True)
    flag_emoji: Mapped[str] = mapped_column(String(10), nullable=True)           # 🇺🇸

    # Geography
    region: Mapped[str] = mapped_column(String(50), nullable=True)               # Americas, Asia, Europe
    subregion: Mapped[str] = mapped_column(String(50), nullable=True)            # Northern America, Eastern Asia
    area_km2: Mapped[float] = mapped_column(Float, nullable=True)
    coastline_km: Mapped[float] = mapped_column(Float, nullable=True)
    landlocked: Mapped[bool] = mapped_column(Boolean, nullable=True)
    island_nation: Mapped[bool] = mapped_column(Boolean, nullable=True)
    timezone_main: Mapped[str] = mapped_column(String(50), nullable=True)        # America/New_York
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    borders: Mapped[dict] = mapped_column(JSONB, nullable=True)                  # ["CA", "MX"] — neighbor codes

    # Political
    government_type: Mapped[str] = mapped_column(String(100), nullable=True)    # Federal republic, Monarchy
    independence_year: Mapped[int] = mapped_column(Integer, nullable=True)
    un_member: Mapped[bool] = mapped_column(Boolean, default=True)

    # Currency & monetary system
    currency_code: Mapped[str] = mapped_column(String(3), nullable=True)         # USD, EUR, CNY
    currency_name: Mapped[str] = mapped_column(String(50), nullable=True)        # US Dollar
    currency_symbol: Mapped[str] = mapped_column(String(5), nullable=True)       # $, €, ¥
    exchange_rate_regime: Mapped[str] = mapped_column(String(30), nullable=True)
    # float, managed_float, currency_board, dollarized, peg_usd, peg_eur

    # Country groupings — drives filtering and SEO page interlinking
    is_g7: Mapped[bool] = mapped_column(Boolean, default=False)
    is_g20: Mapped[bool] = mapped_column(Boolean, default=False)
    is_eu: Mapped[bool] = mapped_column(Boolean, default=False)
    is_eurozone: Mapped[bool] = mapped_column(Boolean, default=False)
    is_nato: Mapped[bool] = mapped_column(Boolean, default=False)
    is_opec: Mapped[bool] = mapped_column(Boolean, default=False)
    is_brics: Mapped[bool] = mapped_column(Boolean, default=False)
    is_asean: Mapped[bool] = mapped_column(Boolean, default=False)
    is_oecd: Mapped[bool] = mapped_column(Boolean, default=False)
    is_commonwealth: Mapped[bool] = mapped_column(Boolean, default=False)

    # Development classification
    income_level: Mapped[str] = mapped_column(String(20), nullable=True)
    # low, lower_middle, upper_middle, high  (World Bank classification)
    development_status: Mapped[str] = mapped_column(String(20), nullable=True)
    # developed, emerging, frontier

    # Credit ratings — often scattered across Bloomberg, S&P, Moody's sites
    credit_rating_sp: Mapped[str] = mapped_column(String(5), nullable=True)      # AAA, AA+, BB-
    credit_outlook_sp: Mapped[str] = mapped_column(String(10), nullable=True)    # stable, positive, negative
    credit_rating_moodys: Mapped[str] = mapped_column(String(5), nullable=True)  # Aaa, Aa1, Ba2
    credit_outlook_moodys: Mapped[str] = mapped_column(String(10), nullable=True)
    credit_rating_fitch: Mapped[str] = mapped_column(String(5), nullable=True)   # AAA, AA, BB+
    credit_outlook_fitch: Mapped[str] = mapped_column(String(10), nullable=True)
    credit_rating_updated: Mapped[date] = mapped_column(Date, nullable=True)

    # Natural resources — what the country actually produces
    major_exports: Mapped[list] = mapped_column(JSONB, nullable=True)
    # ["crude oil", "natural gas", "gold", "soybeans"]
    major_imports: Mapped[list] = mapped_column(JSONB, nullable=True)
    # ["electronics", "machinery", "vehicles"]
    natural_resources: Mapped[list] = mapped_column(JSONB, nullable=True)
    # ["oil", "coal", "copper", "timber", "arable land"]
    commodity_dependent: Mapped[bool] = mapped_column(Boolean, nullable=True)
    # True if >60% exports are primary commodities

    # Language
    official_languages: Mapped[list] = mapped_column(JSONB, nullable=True)       # ["English", "Spanish"]

    # Misc
    calling_code: Mapped[str] = mapped_column(String(10), nullable=True)         # +1, +44, +86
    tld: Mapped[str] = mapped_column(String(10), nullable=True)                  # .us, .de, .cn

    # SEO
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=True)   # united-states

    # Relationships
    indicators: Mapped[list["CountryIndicator"]] = relationship(back_populates="country")
    exports_to: Mapped[list["TradePair"]] = relationship(
        foreign_keys="TradePair.exporter_id", back_populates="exporter"
    )
    imports_from: Mapped[list["TradePair"]] = relationship(
        foreign_keys="TradePair.importer_id", back_populates="importer"
    )
    stock_exposures: Mapped[list["StockCountryRevenue"]] = relationship(back_populates="country")
    institutions: Mapped[list["CountryInstitution"]] = relationship(back_populates="country")


class CountryIndicator(Base):
    """
    All time-series data for a country. Uses a key-value pattern so we can add
    new indicators without schema migrations.

    Indicator codes (grouped by category):

    DEMOGRAPHICS
      population                  — total population
      population_growth_pct       — annual growth %
      urban_population_pct        — % living in urban areas
      median_age                  — years
      life_expectancy             — years at birth
      birth_rate                  — per 1,000 people
      death_rate                  — per 1,000 people
      fertility_rate              — births per woman
      net_migration               — net migrants per year
      dependency_ratio            — dependents per 100 working-age (often ignored, tells the fiscal story)
      population_density          — people per km²

    ECONOMY
      gdp_usd                     — nominal GDP in USD
      gdp_per_capita_usd          — nominal GDP per capita
      gdp_ppp_usd                 — PPP-adjusted GDP
      gdp_per_capita_ppp_usd      — PPP GDP per capita (better living standard comparison)
      gdp_growth_pct              — real GDP growth %
      gdp_agriculture_pct         — agriculture share of GDP
      gdp_industry_pct            — industry share of GDP
      gdp_services_pct            — services share of GDP
      gdp_manufacturing_pct       — manufacturing share of GDP

    MONETARY / INFLATION
      inflation_pct               — CPI inflation %
      core_inflation_pct          — ex-food & energy (often ignored vs headline)
      interest_rate_pct           — central bank policy rate
      money_supply_m2_usd         — M2 money supply
      real_interest_rate_pct      — nominal minus inflation (the real cost of money)

    EXTERNAL / FX
      foreign_reserves_usd        — total reserves
      foreign_reserves_months_imports  — reserves coverage ratio (critical risk indicator, rarely shown)
      current_account_usd         — current account balance
      current_account_gdp_pct     — CA balance as % of GDP
      fdi_inflows_usd             — foreign direct investment inflows
      fdi_outflows_usd            — FDI outflows
      external_debt_usd           — total external debt
      external_debt_gdp_pct       — debt/GDP (key vulnerability indicator)
      remittances_received_usd    — remittances in (massive for EM — often ignored)
      remittances_gdp_pct         — remittances as % of GDP
      sovereign_wealth_fund_usd   — SWF assets (Norway, UAE, Saudi — often not shown)

    TRADE
      exports_usd                 — total merchandise exports
      imports_usd                 — total merchandise imports
      trade_balance_usd           — exports minus imports
      services_exports_usd        — services exports (tourism, finance)
      services_imports_usd        — services imports
      trade_openness_pct          — (exports+imports)/GDP × 100

    FISCAL
      government_debt_gdp_pct     — total public debt / GDP
      budget_balance_gdp_pct      — surplus(+) or deficit(-) as % of GDP
      tax_revenue_gdp_pct         — total tax revenue / GDP
      government_spending_gdp_pct — total government expenditure / GDP
      military_spending_gdp_pct   — defense spending / GDP
      education_spending_gdp_pct  — public education spending / GDP
      healthcare_spending_gdp_pct — public health spending / GDP

    LABOR
      unemployment_pct            — official unemployment rate
      youth_unemployment_pct      — 15-24 age group (often 2-3× higher — rarely highlighted)
      labor_participation_pct     — working-age population in labor force
      female_labor_participation_pct  — gender gap indicator
      minimum_wage_usd            — monthly minimum wage in USD (for cross-country comparison)
      average_wage_usd            — average monthly wage

    SOCIAL / HUMAN DEVELOPMENT
      hdi                         — UNDP Human Development Index (0-1)
      gini_coefficient            — income inequality (0=perfect equality, 100=perfect inequality)
      poverty_rate_pct            — below $2.15/day (World Bank poverty line)
      literacy_rate_pct           — adult literacy
      internet_penetration_pct    — % of population online
      mobile_subscriptions_per_100 — mobile penetration (>100 = multiple SIMs)
      infant_mortality_per_1000   — deaths under age 1 per 1,000 births
      hospital_beds_per_1000      — healthcare capacity
      doctors_per_1000            — physician density

    GOVERNANCE / RISK (often ignored, huge for investors)
      corruption_perception_index — TI score 0-100 (100=very clean)
      rule_of_law_index           — World Bank -2.5 to +2.5
      political_stability_index   — World Bank -2.5 to +2.5
      government_effectiveness_index  — World Bank
      regulatory_quality_index    — World Bank
      economic_freedom_index      — Heritage Foundation 0-100
      press_freedom_index         — RSF score
      democracy_index             — EIU 0-10

    ENVIRONMENT
      co2_emissions_mt            — total CO₂ in megatons
      co2_per_capita_t            — CO₂ per person in tons
      renewable_energy_pct        — % of energy from renewables
      forest_cover_pct            — % of land area forested
      water_stress_index          — 0-5 (5=extremely high stress)
      air_quality_index           — annual average AQI

    INNOVATION
      global_innovation_index_rank  — WIPO ranking
      rd_spending_gdp_pct         — R&D as % of GDP
      patent_applications         — annual patent filings
      startup_ecosystem_rank      — Startup Genome ranking

    TOURISM
      tourist_arrivals            — international tourist arrivals per year
      tourism_revenue_usd         — tourism receipts in USD
      tourism_gdp_pct             — tourism contribution to GDP
    """

    __tablename__ = "country_indicators"
    __table_args__ = (
        UniqueConstraint("country_id", "indicator", "period_date", name="uq_country_indicator_date"),
        Index("ix_country_indicators_lookup", "country_id", "indicator", "period_date"),
        Index("ix_country_indicators_indicator", "indicator", "period_date"),  # cross-country comparisons
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)
    indicator: Mapped[str] = mapped_column(String(60), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)              # First day of the period
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)         # annual, quarterly, monthly
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    # world_bank, imf, fred, undp, oecd, ti, heritage, eiu, wipo, un_population

    country: Mapped["Country"] = relationship(back_populates="indicators")


class TradePair(Base):
    """
    Bilateral trade flows between two countries (UN Comtrade).
    Also stores top traded commodities between the pair — the part competitors miss.
    """

    __tablename__ = "trade_pairs"
    __table_args__ = (
        UniqueConstraint("exporter_id", "importer_id", "year", name="uq_trade_pair_year"),
        Index("ix_trade_pairs_exporter", "exporter_id", "year"),
        Index("ix_trade_pairs_importer", "importer_id", "year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exporter_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)
    importer_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Values
    trade_value_usd: Mapped[float] = mapped_column(Float, nullable=False)        # Total two-way trade
    exports_usd: Mapped[float] = mapped_column(Float, nullable=True)             # Exporter → Importer
    imports_usd: Mapped[float] = mapped_column(Float, nullable=True)             # Importer → Exporter
    balance_usd: Mapped[float] = mapped_column(Float, nullable=True)             # exports - imports

    # What they actually trade — often not shown alongside dollar figures
    top_export_products: Mapped[list] = mapped_column(JSONB, nullable=True)
    # [{"name": "crude oil", "value_usd": 45000000000, "share_pct": 38.2}, ...]
    top_import_products: Mapped[list] = mapped_column(JSONB, nullable=True)

    # Context
    exporter_gdp_share_pct: Mapped[float] = mapped_column(Float, nullable=True)
    # This trade as % of exporter's GDP — shows dependency
    importer_gdp_share_pct: Mapped[float] = mapped_column(Float, nullable=True)

    # Data provenance — shown on page for SEO credibility
    data_source: Mapped[str] = mapped_column(String(30), nullable=True)
    # e.g. "UN Comtrade 2022", "US Census Bureau 2023"

    exporter: Mapped["Country"] = relationship(foreign_keys=[exporter_id], back_populates="exports_to")
    importer: Mapped["Country"] = relationship(foreign_keys=[importer_id], back_populates="imports_from")


class CountryInstitution(Base):
    """
    Official institutional URLs for each country — government portal, central bank,
    stats office, ministry of finance, stock exchange, tax/customs/trade authorities.
    One row per country.
    """

    __tablename__ = "country_institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id", ondelete="CASCADE"),
                                             nullable=False, unique=True)

    # Government
    gov_portal_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # Central Bank
    central_bank_url: Mapped[str] = mapped_column(String(500), nullable=True)
    central_bank_name: Mapped[str] = mapped_column(String(200), nullable=True)

    # Statistics Office
    stats_office_url: Mapped[str] = mapped_column(String(500), nullable=True)
    stats_office_name: Mapped[str] = mapped_column(String(200), nullable=True)

    # Ministry of Finance
    min_finance_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # Stock Exchange
    stock_exchange_url: Mapped[str] = mapped_column(String(500), nullable=True)
    stock_exchange_name: Mapped[str] = mapped_column(String(200), nullable=True)

    # Revenue / Tax Authority
    revenue_authority_url: Mapped[str] = mapped_column(String(500), nullable=True)
    revenue_authority_name: Mapped[str] = mapped_column(String(200), nullable=True)

    # Customs
    customs_authority_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # Trade Ministry / Export Promotion
    trade_ministry_url: Mapped[str] = mapped_column(String(500), nullable=True)
    export_promotion_url: Mapped[str] = mapped_column(String(500), nullable=True)

    # Chamber of Commerce
    chamber_of_commerce_url: Mapped[str] = mapped_column(String(500), nullable=True)

    updated_at: Mapped[date] = mapped_column(Date, nullable=True)

    country: Mapped["Country"] = relationship(back_populates="institutions")
