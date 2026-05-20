"""Macro calendar events: FRED US release dates + static central bank meeting schedules."""
import logging
from datetime import datetime, timezone, date
from typing import Optional

import requests
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.macro_calendar import MacroCalendarEvent

logger = logging.getLogger(__name__)

FRED_API_KEY = None  # loaded from env at runtime

# FRED release IDs → (event_name, event_type, country_code, impact)
FRED_RELEASES = {
    10:  ('Consumer Price Index (CPI)', 'cpi',        'US', 'high'),
    11:  ('Producer Price Index (PPI)', 'ppi',        'US', 'medium'),
    14:  ('Gross Domestic Product (GDP)', 'gdp',      'US', 'high'),
    50:  ('Employment Situation (NFP)', 'nfp',        'US', 'high'),
    22:  ('Advance Retail Sales', 'retail',           'US', 'high'),
    175: ('ISM Manufacturing PMI', 'pmi',             'US', 'medium'),
    20:  ('Industrial Production', 'industrial',      'US', 'medium'),
    18:  ('Housing Starts', 'housing',                'US', 'medium'),
    51:  ('Personal Income and Outlays (PCE)', 'pce', 'US', 'high'),
    32:  ('Trade Balance', 'trade',                   'US', 'medium'),
}

# Static 2026 central bank meeting dates (rate decision events)
CENTRAL_BANK_MEETINGS_2026 = [
    # Fed (FOMC) — 8 meetings/year
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 1, 29, 19, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 3, 19, 18, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 5, 7, 18, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 6, 18, 18, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 11, 5, 19, 0, tzinfo=timezone.utc)),
    ('US', 'Fed Rate Decision (FOMC)', 'rate_decision', 'high', 'Federal Reserve', datetime(2026, 12, 10, 19, 0, tzinfo=timezone.utc)),
    # ECB — 8 meetings/year
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 1, 30, 13, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 3, 6, 13, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 4, 17, 12, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 6, 5, 12, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 7, 24, 12, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 9, 11, 12, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 10, 23, 12, 15, tzinfo=timezone.utc)),
    ('EU', 'ECB Rate Decision', 'rate_decision', 'high', 'European Central Bank', datetime(2026, 12, 11, 13, 15, tzinfo=timezone.utc)),
    # BOE — 8 meetings/year
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 2, 6, 12, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 5, 8, 11, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 8, 6, 11, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)),
    ('GB', 'Bank of England Rate Decision', 'rate_decision', 'high', 'Bank of England', datetime(2026, 12, 18, 12, 0, tzinfo=timezone.utc)),
    # BOJ — 8 meetings/year
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 1, 24, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 3, 19, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 4, 30, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 6, 18, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 9, 19, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)),
    ('JP', 'Bank of Japan Rate Decision', 'rate_decision', 'high', 'Bank of Japan', datetime(2026, 12, 19, 3, 0, tzinfo=timezone.utc)),
    # RBA — 8 meetings/year
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 2, 18, 3, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 4, 7, 4, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 5, 19, 4, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 7, 7, 4, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 8, 4, 4, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 11, 3, 3, 30, tzinfo=timezone.utc)),
    ('AU', 'RBA Rate Decision', 'rate_decision', 'high', 'Reserve Bank of Australia', datetime(2026, 12, 8, 3, 30, tzinfo=timezone.utc)),
    # BOC — 8 meetings/year
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 1, 29, 15, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 3, 5, 15, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 4, 16, 14, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 9, 9, 14, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)),
    ('CA', 'Bank of Canada Rate Decision', 'rate_decision', 'high', 'Bank of Canada', datetime(2026, 12, 9, 15, 0, tzinfo=timezone.utc)),
    # OPEC meeting
    ('AE', 'OPEC+ Meeting', 'opec', 'high', 'OPEC', datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)),
    ('AE', 'OPEC+ Meeting', 'opec', 'high', 'OPEC', datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)),
    # G7 Summit
    ('CA', 'G7 Summit', 'g7', 'medium', 'G7', datetime(2026, 6, 13, 9, 0, tzinfo=timezone.utc)),
]

# Static 2026 US economic release dates (BLS/BEA schedule — published in advance)
US_ECONOMIC_RELEASES_2026 = [
    # NFP — Employment Situation (first Friday of month, 8:30am ET = 13:30 UTC)
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026,  6,  5, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026,  7,  2, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026,  8,  7, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026,  9,  4, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026, 10,  2, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026, 11,  6, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Employment Situation (NFP)', 'nfp',    'high',   'Bureau of Labor Statistics', datetime(2026, 12,  4, 13, 30, tzinfo=timezone.utc)),
    # CPI — Consumer Price Index (~2nd Wednesday of month, 8:30am ET)
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026,  6, 11, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026,  7, 15, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026,  8, 12, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026,  9, 10, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026, 10, 14, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)),
    ('US', 'CPI Inflation (US)',            'cpi',    'high',   'Bureau of Labor Statistics', datetime(2026, 12,  9, 13, 30, tzinfo=timezone.utc)),
    # PCE — Personal Consumption Expenditures (~last Friday of month, 8:30am ET)
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026,  5, 29, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026,  6, 26, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026,  7, 31, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026,  8, 28, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026,  9, 25, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026, 10, 30, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026, 11, 25, 13, 30, tzinfo=timezone.utc)),
    ('US', 'PCE Inflation (US)',            'pce',    'high',   'Bureau of Economic Analysis', datetime(2026, 12, 18, 13, 30, tzinfo=timezone.utc)),
    # GDP Advance Estimate (quarterly — end of first month of each quarter)
    ('US', 'US GDP (Advance Estimate)',     'gdp',    'high',   'Bureau of Economic Analysis', datetime(2026,  7, 29, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US GDP (Advance Estimate)',     'gdp',    'high',   'Bureau of Economic Analysis', datetime(2026, 10, 28, 13, 30, tzinfo=timezone.utc)),
    # Retail Sales (~15th of month, 8:30am ET)
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026,  5, 15, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026,  6, 16, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026,  7, 16, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026,  8, 14, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026,  9, 15, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026, 11, 17, 13, 30, tzinfo=timezone.utc)),
    ('US', 'US Retail Sales',              'retail', 'high',   'US Census Bureau', datetime(2026, 12, 15, 13, 30, tzinfo=timezone.utc)),
    # ISM Manufacturing PMI (first business day of month)
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026,  6,  1, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026,  7,  1, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026,  8,  3, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026,  9,  1, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026, 10,  1, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026, 11,  2, 14,  0, tzinfo=timezone.utc)),
    ('US', 'ISM Manufacturing PMI',        'pmi',    'medium', 'Institute for Supply Management', datetime(2026, 12,  1, 14,  0, tzinfo=timezone.utc)),
]

# Static 2026 Eurozone/EU economic release dates (Eurostat schedule)
EU_ECONOMIC_RELEASES_2026 = [
    # Eurozone CPI Flash Estimate (first Wednesday of month, 10:00 CET = 09:00 UTC)
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026,  6,  3,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026,  7,  1,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026,  8,  5,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026,  9,  2,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026, 10,  7,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026, 11,  4,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone CPI Inflation (Flash)', 'cpi',  'high',   'Eurostat', datetime(2026, 12,  2,  9,  0, tzinfo=timezone.utc)),
    # Eurozone GDP (flash, quarterly — mid-month after quarter end)
    ('EU', 'Eurozone GDP (Flash Estimate)', 'gdp',   'high',   'Eurostat', datetime(2026,  7, 15,  9,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone GDP (Flash Estimate)', 'gdp',   'high',   'Eurostat', datetime(2026, 10, 14,  9,  0, tzinfo=timezone.utc)),
    # S&P Global Eurozone PMI (first business day of month)
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026,  6,  1,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026,  7,  1,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026,  8,  3,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026,  9,  1,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026, 10,  1,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026, 11,  2,  8,  0, tzinfo=timezone.utc)),
    ('EU', 'Eurozone Manufacturing PMI',   'pmi',    'medium', 'S&P Global', datetime(2026, 12,  1,  8,  0, tzinfo=timezone.utc)),
]

# Static 2026 UK economic release dates (ONS schedule)
UK_ECONOMIC_RELEASES_2026 = [
    # UK CPI (roughly 3rd Wednesday of month, 7:00am UTC)
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026,  5, 21,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026,  6, 18,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026,  7, 15,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026,  8, 19,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026,  9, 16,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026, 10, 21,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026, 11, 18,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK CPI Inflation',             'cpi',    'high',   'Office for National Statistics', datetime(2026, 12, 16,  7,  0, tzinfo=timezone.utc)),
    # UK GDP (monthly estimate, ~6 weeks after reference month)
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026,  6, 11,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026,  7, 10,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026,  8, 12,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026,  9, 10,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026, 10,  9,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026, 11, 12,  7,  0, tzinfo=timezone.utc)),
    ('GB', 'UK GDP Monthly Estimate',      'gdp',    'medium', 'Office for National Statistics', datetime(2026, 12, 10,  7,  0, tzinfo=timezone.utc)),
]

# Static 2026 China economic release dates (NBS schedule)
CN_ECONOMIC_RELEASES_2026 = [
    # China PMI Manufacturing (last day of month)
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026,  6, 30,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026,  7, 31,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026,  8, 31,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026,  9, 30,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026, 10, 31,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026, 11, 30,  1,  0, tzinfo=timezone.utc)),
    ('CN', 'China Manufacturing PMI (NBS)', 'pmi',   'high',   'National Bureau of Statistics', datetime(2026, 12, 31,  1,  0, tzinfo=timezone.utc)),
    # China CPI (~mid-month)
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026,  6, 10,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026,  7,  9,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026,  8, 10,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026,  9,  9,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026, 10, 13,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026, 11, 10,  1, 30, tzinfo=timezone.utc)),
    ('CN', 'China CPI Inflation',          'cpi',    'high',   'National Bureau of Statistics', datetime(2026, 12,  9,  1, 30, tzinfo=timezone.utc)),
]


def _load_fred_key() -> Optional[str]:
    import os
    key = os.environ.get('FRED_API_KEY')
    if not key:
        try:
            from app.config import settings
            key = getattr(settings, 'fred_api_key', None)
        except Exception:
            pass
    return key


def _fetch_fred_release_dates(release_id: int, fred_key: str) -> list[datetime]:
    """Fetch future release dates for a FRED release ID."""
    today_str = date.today().isoformat()
    url = 'https://api.stlouisfed.org/fred/release/dates'
    params = {
        'release_id': release_id,
        'api_key': fred_key,
        'file_type': 'json',
        'realtime_start': today_str,
        'realtime_end': f'{date.today().year + 1}-12-31',
        'limit': 50,
        'sort_order': 'asc',
        'include_release_dates_with_no_data': 'true',
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        dates = []
        for rd in data.get('release_dates', []):
            d = rd.get('date')
            if d:
                dt = datetime.strptime(d, '%Y-%m-%d').replace(hour=13, minute=30, tzinfo=timezone.utc)
                dates.append(dt)
        return dates
    except Exception as exc:
        logger.warning('FRED release %d fetch failed: %s', release_id, exc)
        return []


@shared_task(
    name='tasks.macro_calendar.sync_macro_events',
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def sync_macro_events(self):
    """Sync macro calendar events: FRED US releases + static central bank meetings."""
    fred_key = _load_fred_key()
    events_to_upsert = []

    # 1. FRED release dates
    if fred_key:
        for release_id, (event_name, event_type, country_code, impact) in FRED_RELEASES.items():
            dates = _fetch_fred_release_dates(release_id, fred_key)
            for dt in dates:
                events_to_upsert.append({
                    'country_code': country_code,
                    'event_name': event_name,
                    'event_type': event_type,
                    'event_date': dt,
                    'impact': impact,
                    'source': 'FRED',
                    'source_url': f'https://fred.stlouisfed.org/release?release_id={release_id}',
                })
    else:
        logger.warning('FRED_API_KEY not set — skipping FRED release dates')

    # 2. Static central bank meetings
    for country_code, event_name, event_type, impact, source, dt in CENTRAL_BANK_MEETINGS_2026:
        events_to_upsert.append({
            'country_code': country_code,
            'event_name': event_name,
            'event_type': event_type,
            'event_date': dt,
            'impact': impact,
            'source': source,
            'source_url': None,
        })

    # 3. Static US economic data releases (BLS/BEA 2026 schedule)
    for country_code, event_name, event_type, impact, source, dt in US_ECONOMIC_RELEASES_2026:
        events_to_upsert.append({
            'country_code': country_code,
            'event_name': event_name,
            'event_type': event_type,
            'event_date': dt,
            'impact': impact,
            'source': source,
            'source_url': None,
        })

    # 4. Eurozone economic releases (Eurostat 2026 schedule)
    for country_code, event_name, event_type, impact, source, dt in EU_ECONOMIC_RELEASES_2026:
        events_to_upsert.append({
            'country_code': country_code,
            'event_name': event_name,
            'event_type': event_type,
            'event_date': dt,
            'impact': impact,
            'source': source,
            'source_url': None,
        })

    # 5. UK economic releases (ONS 2026 schedule)
    for country_code, event_name, event_type, impact, source, dt in UK_ECONOMIC_RELEASES_2026:
        events_to_upsert.append({
            'country_code': country_code,
            'event_name': event_name,
            'event_type': event_type,
            'event_date': dt,
            'impact': impact,
            'source': source,
            'source_url': None,
        })

    # 6. China economic releases (NBS 2026 schedule)
    for country_code, event_name, event_type, impact, source, dt in CN_ECONOMIC_RELEASES_2026:
        events_to_upsert.append({
            'country_code': country_code,
            'event_name': event_name,
            'event_type': event_type,
            'event_date': dt,
            'impact': impact,
            'source': source,
            'source_url': None,
        })

    if not events_to_upsert:
        logger.info('No macro calendar events to upsert')
        return {'upserted': 0}

    db = SessionLocal()
    try:
        stmt = pg_insert(MacroCalendarEvent).values(events_to_upsert)
        stmt = stmt.on_conflict_do_update(
            constraint='uq_macro_calendar_event',
            set_={
                'impact': stmt.excluded.impact,
                'source': stmt.excluded.source,
                'source_url': stmt.excluded.source_url,
                'updated_at': datetime.now(timezone.utc),
            },
        )
        db.execute(stmt)
        db.commit()
    finally:
        db.close()

    logger.info('Upserted %d macro calendar events', len(events_to_upsert))
    return {'upserted': len(events_to_upsert)}
