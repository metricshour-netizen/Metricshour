"""
Seed assets: full S&P 500 stocks + international large-caps, 20 commodities,
10 crypto, 10 FX pairs, 18 indices, 21 ETFs, 12 bonds.
Hardcoded — no external API required. Idempotent.

Must run AFTER countries seeder (needs country IDs).

Run: python seed.py --only assets
"""

import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Asset, AssetType, Country

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# (symbol, name, exchange, sector, industry, hq_country_code, market_cap_usd)
STOCKS: list[tuple] = [
    # ── US Technology ──────────────────────────────────────────────────────────
    ("AAPL",  "Apple Inc.",                  "NASDAQ", "Technology",             "Consumer Electronics",  "US", 3_300_000_000_000),
    ("MSFT",  "Microsoft Corporation",       "NASDAQ", "Technology",             "Software",              "US", 2_900_000_000_000),
    ("NVDA",  "NVIDIA Corporation",          "NASDAQ", "Technology",             "Semiconductors",        "US", 3_000_000_000_000),
    ("GOOGL", "Alphabet Inc.",               "NASDAQ", "Technology",             "Internet Services",     "US", 2_100_000_000_000),
    ("META",  "Meta Platforms Inc.",         "NASDAQ", "Technology",             "Social Media",          "US", 1_600_000_000_000),
    ("AMZN",  "Amazon.com Inc.",             "NASDAQ", "Technology",             "E-Commerce",            "US", 2_200_000_000_000),
    ("TSLA",  "Tesla Inc.",                  "NASDAQ", "Consumer Discretionary", "Electric Vehicles",     "US",   700_000_000_000),
    ("AVGO",  "Broadcom Inc.",               "NASDAQ", "Technology",             "Semiconductors",        "US",   750_000_000_000),
    ("ORCL",  "Oracle Corporation",          "NYSE",   "Technology",             "Software",              "US",   430_000_000_000),
    ("AMD",   "Advanced Micro Devices",      "NASDAQ", "Technology",             "Semiconductors",        "US",   220_000_000_000),
    ("NFLX",  "Netflix Inc.",                "NASDAQ", "Technology",             "Streaming",             "US",   380_000_000_000),
    ("INTC",  "Intel Corporation",           "NASDAQ", "Technology",             "Semiconductors",        "US",   100_000_000_000),
    ("QCOM",  "Qualcomm Inc.",               "NASDAQ", "Technology",             "Semiconductors",        "US",   165_000_000_000),
    ("TXN",   "Texas Instruments",           "NASDAQ", "Technology",             "Semiconductors",        "US",   155_000_000_000),
    ("CSCO",  "Cisco Systems Inc.",          "NASDAQ", "Technology",             "Networking",            "US",   220_000_000_000),
    ("IBM",   "IBM Corporation",             "NYSE",   "Technology",             "IT Services",           "US",   200_000_000_000),
    ("ADBE",  "Adobe Inc.",                  "NASDAQ", "Technology",             "Software",              "US",   200_000_000_000),
    ("CRM",   "Salesforce Inc.",             "NYSE",   "Technology",             "Software",              "US",   280_000_000_000),
    ("AMAT",  "Applied Materials Inc.",      "NASDAQ", "Technology",             "Semiconductor Equipment","US",  180_000_000_000),
    ("MU",    "Micron Technology Inc.",      "NASDAQ", "Technology",             "Semiconductors",        "US",   120_000_000_000),
    # ── US Finance ────────────────────────────────────────────────────────────
    ("JPM",   "JPMorgan Chase & Co.",        "NYSE",   "Financials",             "Banking",               "US",   680_000_000_000),
    ("BAC",   "Bank of America Corp.",       "NYSE",   "Financials",             "Banking",               "US",   320_000_000_000),
    ("V",     "Visa Inc.",                   "NYSE",   "Financials",             "Payments",              "US",   550_000_000_000),
    ("MA",    "Mastercard Inc.",             "NYSE",   "Financials",             "Payments",              "US",   460_000_000_000),
    ("GS",    "Goldman Sachs Group",         "NYSE",   "Financials",             "Investment Banking",    "US",   185_000_000_000),
    ("MS",    "Morgan Stanley",              "NYSE",   "Financials",             "Investment Banking",    "US",   175_000_000_000),
    ("WFC",   "Wells Fargo & Company",       "NYSE",   "Financials",             "Banking",               "US",   210_000_000_000),
    ("AXP",   "American Express Company",    "NYSE",   "Financials",             "Payments",              "US",   180_000_000_000),
    ("BLK",   "BlackRock Inc.",              "NYSE",   "Financials",             "Asset Management",      "US",   150_000_000_000),
    ("C",     "Citigroup Inc.",              "NYSE",   "Financials",             "Banking",               "US",   140_000_000_000),
    # ── US Healthcare ─────────────────────────────────────────────────────────
    ("LLY",   "Eli Lilly and Company",       "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   750_000_000_000),
    ("JNJ",   "Johnson & Johnson",           "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   380_000_000_000),
    ("UNH",   "UnitedHealth Group",          "NYSE",   "Healthcare",             "Health Insurance",      "US",   480_000_000_000),
    ("ABBV",  "AbbVie Inc.",                 "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   310_000_000_000),
    ("MRK",   "Merck & Co. Inc.",            "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   260_000_000_000),
    ("PFE",   "Pfizer Inc.",                 "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   150_000_000_000),
    ("TMO",   "Thermo Fisher Scientific",    "NYSE",   "Healthcare",             "Life Sciences",         "US",   210_000_000_000),
    ("AMGN",  "Amgen Inc.",                  "NASDAQ", "Healthcare",             "Biotechnology",         "US",   155_000_000_000),
    ("BMY",   "Bristol-Myers Squibb",        "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   130_000_000_000),
    ("GILD",  "Gilead Sciences Inc.",        "NASDAQ", "Healthcare",             "Biotechnology",         "US",   115_000_000_000),
    # ── US Consumer ───────────────────────────────────────────────────────────
    ("WMT",   "Walmart Inc.",                "NYSE",   "Consumer Staples",       "Retail",                "US",   720_000_000_000),
    ("HD",    "The Home Depot Inc.",         "NYSE",   "Consumer Discretionary", "Home Improvement",      "US",   360_000_000_000),
    ("COST",  "Costco Wholesale",            "NASDAQ", "Consumer Staples",       "Retail",                "US",   370_000_000_000),
    ("PG",    "Procter & Gamble Co.",        "NYSE",   "Consumer Staples",       "Household Products",    "US",   350_000_000_000),
    ("KO",    "The Coca-Cola Company",       "NYSE",   "Consumer Staples",       "Beverages",             "US",   270_000_000_000),
    ("PEP",   "PepsiCo Inc.",                "NASDAQ", "Consumer Staples",       "Beverages",             "US",   210_000_000_000),
    ("MCD",   "McDonald's Corporation",      "NYSE",   "Consumer Discretionary", "Restaurants",           "US",   220_000_000_000),
    ("NKE",   "Nike Inc.",                   "NYSE",   "Consumer Discretionary", "Apparel",               "US",    85_000_000_000),
    ("SBUX",  "Starbucks Corporation",       "NASDAQ", "Consumer Discretionary", "Restaurants",           "US",    80_000_000_000),
    ("PM",    "Philip Morris International","NYSE",   "Consumer Staples",       "Tobacco",               "US",   185_000_000_000),
    # ── US Energy ─────────────────────────────────────────────────────────────
    ("XOM",   "ExxonMobil Corporation",      "NYSE",   "Energy",                 "Oil & Gas",             "US",   470_000_000_000),
    ("CVX",   "Chevron Corporation",         "NYSE",   "Energy",                 "Oil & Gas",             "US",   290_000_000_000),
    ("COP",   "ConocoPhillips",              "NYSE",   "Energy",                 "Oil & Gas",             "US",   140_000_000_000),
    ("SLB",   "SLB (Schlumberger)",          "NYSE",   "Energy",                 "Oil Field Services",    "US",    65_000_000_000),
    # ── US Industrials ────────────────────────────────────────────────────────
    ("RTX",   "RTX Corporation",             "NYSE",   "Industrials",            "Defense",               "US",   160_000_000_000),
    ("HON",   "Honeywell International",     "NASDAQ", "Industrials",            "Diversified Industrial","US",   140_000_000_000),
    ("BA",    "Boeing Company",              "NYSE",   "Industrials",            "Aerospace",             "US",   100_000_000_000),
    ("CAT",   "Caterpillar Inc.",            "NYSE",   "Industrials",            "Machinery",             "US",   155_000_000_000),
    ("GE",    "GE Aerospace",               "NYSE",   "Industrials",            "Aerospace",             "US",   180_000_000_000),
    ("UPS",   "United Parcel Service",       "NYSE",   "Industrials",            "Logistics",             "US",   120_000_000_000),
    ("DE",    "Deere & Company",             "NYSE",   "Industrials",            "Agricultural Machinery","US",   120_000_000_000),
    ("LMT",   "Lockheed Martin",             "NYSE",   "Industrials",            "Defense",               "US",   120_000_000_000),
    # ── US Telecom & Media ────────────────────────────────────────────────────
    ("T",     "AT&T Inc.",                   "NYSE",   "Communication Services", "Telecom",               "US",   150_000_000_000),
    ("VZ",    "Verizon Communications",      "NYSE",   "Communication Services", "Telecom",               "US",   170_000_000_000),
    ("DIS",   "The Walt Disney Company",     "NYSE",   "Communication Services", "Media & Entertainment", "US",   200_000_000_000),
    ("CMCSA", "Comcast Corporation",         "NASDAQ", "Communication Services", "Media & Telecom",       "US",   145_000_000_000),
    # ── International — UK ────────────────────────────────────────────────────
    ("SHEL",  "Shell plc",                   "NYSE",   "Energy",                 "Oil & Gas",             "GB",   220_000_000_000),
    ("AZN",   "AstraZeneca plc",             "NASDAQ", "Healthcare",             "Pharmaceuticals",       "GB",   230_000_000_000),
    ("BP",    "BP plc",                      "NYSE",   "Energy",                 "Oil & Gas",             "GB",   100_000_000_000),
    ("GSK",   "GSK plc",                     "NYSE",   "Healthcare",             "Pharmaceuticals",       "GB",    85_000_000_000),
    ("HSBC",  "HSBC Holdings plc",           "NYSE",   "Financials",             "Banking",               "GB",   175_000_000_000),
    ("ARM",   "Arm Holdings plc",            "NASDAQ", "Technology",             "Semiconductor IP",      "GB",   160_000_000_000),
    ("RIO",   "Rio Tinto plc",               "NYSE",   "Materials",              "Mining",                "GB",   100_000_000_000),
    # ── International — Europe ────────────────────────────────────────────────
    ("SAP",   "SAP SE",                      "NYSE",   "Technology",             "Software",              "DE",   260_000_000_000),
    ("TTE",   "TotalEnergies SE",            "NYSE",   "Energy",                 "Oil & Gas",             "FR",   150_000_000_000),
    ("NVO",   "Novo Nordisk A/S",            "NYSE",   "Healthcare",             "Pharmaceuticals",       "DK",   420_000_000_000),
    ("ASML",  "ASML Holding N.V.",           "NASDAQ", "Technology",             "Semiconductor Equipment","NL",  290_000_000_000),
    # ── International — Japan ─────────────────────────────────────────────────
    ("TM",    "Toyota Motor Corporation",    "NYSE",   "Consumer Discretionary", "Automobiles",           "JP",   220_000_000_000),
    ("SONY",  "Sony Group Corporation",      "NYSE",   "Consumer Discretionary", "Electronics",           "JP",   110_000_000_000),
    # ── International — Taiwan ────────────────────────────────────────────────
    ("TSM",   "Taiwan Semiconductor Mfg.",   "NYSE",   "Technology",             "Semiconductors",        "TW",   750_000_000_000),
    # ── International — China ─────────────────────────────────────────────────
    ("BABA",  "Alibaba Group Holding",       "NYSE",   "Technology",             "E-Commerce",            "CN",   210_000_000_000),
    ("BIDU",  "Baidu Inc.",                  "NASDAQ", "Technology",             "Internet Services",     "CN",    35_000_000_000),
    ("JD",    "JD.com Inc.",                 "NASDAQ", "Technology",             "E-Commerce",            "CN",    45_000_000_000),
    ("PDD",   "PDD Holdings Inc.",           "NASDAQ", "Technology",             "E-Commerce",            "CN",   170_000_000_000),
    # ── International — India ─────────────────────────────────────────────────
    ("INFY",  "Infosys Limited",             "NYSE",   "Technology",             "IT Services",           "IN",    75_000_000_000),
    ("HDB",   "HDFC Bank Limited",           "NYSE",   "Financials",             "Banking",               "IN",   130_000_000_000),
    # ── International — Brazil ────────────────────────────────────────────────
    ("VALE",  "Vale S.A.",                   "NYSE",   "Materials",              "Mining",                "BR",    65_000_000_000),
    ("PBR",   "Petróleo Brasileiro S.A.",    "NYSE",   "Energy",                 "Oil & Gas",             "BR",    80_000_000_000),
    # ── International — Australia ─────────────────────────────────────────────
    ("BHP",   "BHP Group Limited",           "NYSE",   "Materials",              "Mining",                "AU",   120_000_000_000),
    # ── International — South Korea (OTC/ADR) ─────────────────────────────────
    ("SSNLF", "Samsung Electronics",         "OTC",    "Technology",             "Semiconductors",        "KR",   260_000_000_000),

    # ══════════════════════════════════════════════════════════════════════════
    # S&P 500 EXPANSION — sectors below supplement the 90 above
    # ══════════════════════════════════════════════════════════════════════════

    # ── Communication Services ────────────────────────────────────────────────
    ("TMUS",  "T-Mobile US Inc.",             "NASDAQ", "Communication Services", "Telecom",               "US",   260_000_000_000),
    ("CHTR",  "Charter Communications",       "NASDAQ", "Communication Services", "Cable & Telecom",       "US",    45_000_000_000),
    ("WBD",   "Warner Bros. Discovery",       "NASDAQ", "Communication Services", "Media & Entertainment", "US",    25_000_000_000),
    ("FOXA",  "Fox Corporation (Class A)",    "NASDAQ", "Communication Services", "Media & Entertainment", "US",    22_000_000_000),
    ("FOX",   "Fox Corporation (Class B)",    "NASDAQ", "Communication Services", "Media & Entertainment", "US",    20_000_000_000),
    ("EA",    "Electronic Arts Inc.",         "NASDAQ", "Communication Services", "Video Games",           "US",    35_000_000_000),
    ("TTWO",  "Take-Two Interactive",         "NASDAQ", "Communication Services", "Video Games",           "US",    28_000_000_000),
    ("LYV",   "Live Nation Entertainment",    "NYSE",   "Communication Services", "Live Events",           "US",    22_000_000_000),
    ("IPG",   "Interpublic Group",            "NYSE",   "Communication Services", "Advertising",           "US",    10_000_000_000),
    ("OMC",   "Omnicom Group Inc.",           "NYSE",   "Communication Services", "Advertising",           "US",    16_000_000_000),
    ("MTCH",  "Match Group Inc.",             "NASDAQ", "Communication Services", "Internet Services",     "US",     8_000_000_000),
    ("PARA",  "Paramount Global",             "NASDAQ", "Communication Services", "Media & Entertainment", "US",     7_000_000_000),

    # ── Consumer Discretionary ────────────────────────────────────────────────
    ("LOW",   "Lowe's Companies Inc.",        "NYSE",   "Consumer Discretionary", "Home Improvement",      "US",   145_000_000_000),
    ("TJX",   "TJX Companies Inc.",           "NYSE",   "Consumer Discretionary", "Apparel Retail",        "US",   140_000_000_000),
    ("BKNG",  "Booking Holdings Inc.",        "NASDAQ", "Consumer Discretionary", "Online Travel",         "US",   165_000_000_000),
    ("ORLY",  "O'Reilly Automotive",          "NASDAQ", "Consumer Discretionary", "Auto Parts",            "US",    70_000_000_000),
    ("AZO",   "AutoZone Inc.",                "NYSE",   "Consumer Discretionary", "Auto Parts",            "US",    55_000_000_000),
    ("DG",    "Dollar General Corporation",   "NYSE",   "Consumer Discretionary", "Discount Retail",       "US",    28_000_000_000),
    ("DLTR",  "Dollar Tree Inc.",             "NASDAQ", "Consumer Discretionary", "Discount Retail",       "US",    20_000_000_000),
    ("ROST",  "Ross Stores Inc.",             "NASDAQ", "Consumer Discretionary", "Apparel Retail",        "US",    48_000_000_000),
    ("TGT",   "Target Corporation",           "NYSE",   "Consumer Discretionary", "General Merchandise",   "US",    50_000_000_000),
    ("F",     "Ford Motor Company",           "NYSE",   "Consumer Discretionary", "Automobiles",           "US",    45_000_000_000),
    ("GM",    "General Motors Company",       "NYSE",   "Consumer Discretionary", "Automobiles",           "US",    48_000_000_000),
    ("CMG",   "Chipotle Mexican Grill",       "NYSE",   "Consumer Discretionary", "Restaurants",           "US",    75_000_000_000),
    ("YUM",   "Yum! Brands Inc.",             "NYSE",   "Consumer Discretionary", "Restaurants",           "US",    32_000_000_000),
    ("QSR",   "Restaurant Brands Intl.",      "NYSE",   "Consumer Discretionary", "Restaurants",           "CA",    25_000_000_000),
    ("DRI",   "Darden Restaurants Inc.",      "NYSE",   "Consumer Discretionary", "Restaurants",           "US",    18_000_000_000),
    ("MAR",   "Marriott International",       "NASDAQ", "Consumer Discretionary", "Hotels",                "US",    68_000_000_000),
    ("HLT",   "Hilton Worldwide Holdings",    "NYSE",   "Consumer Discretionary", "Hotels",                "US",    55_000_000_000),
    ("RCL",   "Royal Caribbean Group",        "NYSE",   "Consumer Discretionary", "Cruise Lines",          "US",    55_000_000_000),
    ("CCL",   "Carnival Corporation",         "NYSE",   "Consumer Discretionary", "Cruise Lines",          "US",    22_000_000_000),
    ("ABNB",  "Airbnb Inc.",                  "NASDAQ", "Consumer Discretionary", "Online Travel",         "US",    90_000_000_000),
    ("EXPE",  "Expedia Group Inc.",           "NASDAQ", "Consumer Discretionary", "Online Travel",         "US",    20_000_000_000),
    ("LVS",   "Las Vegas Sands Corp.",        "NYSE",   "Consumer Discretionary", "Casinos & Gaming",      "US",    35_000_000_000),
    ("MGM",   "MGM Resorts International",    "NYSE",   "Consumer Discretionary", "Casinos & Gaming",      "US",    14_000_000_000),
    ("WYNN",  "Wynn Resorts Limited",         "NASDAQ", "Consumer Discretionary", "Casinos & Gaming",      "US",     9_000_000_000),
    ("PHM",   "PulteGroup Inc.",              "NYSE",   "Consumer Discretionary", "Homebuilding",          "US",    20_000_000_000),
    ("DHI",   "D.R. Horton Inc.",             "NYSE",   "Consumer Discretionary", "Homebuilding",          "US",    45_000_000_000),
    ("LEN",   "Lennar Corporation",           "NYSE",   "Consumer Discretionary", "Homebuilding",          "US",    40_000_000_000),
    ("NVR",   "NVR Inc.",                     "NYSE",   "Consumer Discretionary", "Homebuilding",          "US",    24_000_000_000),
    ("TOL",   "Toll Brothers Inc.",           "NYSE",   "Consumer Discretionary", "Homebuilding",          "US",    12_000_000_000),
    ("LULU",  "Lululemon Athletica",          "NASDAQ", "Consumer Discretionary", "Apparel",               "CA",    40_000_000_000),
    ("EBAY",  "eBay Inc.",                    "NASDAQ", "Consumer Discretionary", "E-Commerce",            "US",    25_000_000_000),
    ("ETSY",  "Etsy Inc.",                    "NASDAQ", "Consumer Discretionary", "E-Commerce",            "US",     7_000_000_000),
    ("UBER",  "Uber Technologies Inc.",       "NYSE",   "Consumer Discretionary", "Ride-Sharing",          "US",   165_000_000_000),
    ("BBY",   "Best Buy Co. Inc.",            "NYSE",   "Consumer Discretionary", "Electronics Retail",    "US",    14_000_000_000),
    ("RL",    "Ralph Lauren Corporation",     "NYSE",   "Consumer Discretionary", "Apparel",               "US",    14_000_000_000),
    ("TPR",   "Tapestry Inc.",                "NYSE",   "Consumer Discretionary", "Luxury Goods",          "US",     7_000_000_000),
    ("CPRI",  "Capri Holdings Limited",       "NYSE",   "Consumer Discretionary", "Luxury Goods",          "GB",     4_000_000_000),
    ("PVH",   "PVH Corp.",                    "NYSE",   "Consumer Discretionary", "Apparel",               "US",     6_000_000_000),
    ("HAS",   "Hasbro Inc.",                  "NASDAQ", "Consumer Discretionary", "Toys & Games",          "US",     8_000_000_000),
    ("GRMN",  "Garmin Ltd.",                  "NASDAQ", "Consumer Discretionary", "GPS & Wearables",       "CH",    35_000_000_000),
    ("DECK",  "Deckers Outdoor Corporation",  "NYSE",   "Consumer Discretionary", "Footwear",              "US",    19_000_000_000),
    ("POOL",  "Pool Corporation",             "NASDAQ", "Consumer Discretionary", "Swimming Pools",        "US",    14_000_000_000),
    ("WSM",   "Williams-Sonoma Inc.",         "NYSE",   "Consumer Discretionary", "Home Furnishings",      "US",    18_000_000_000),
    ("RH",    "RH (Restoration Hardware)",    "NYSE",   "Consumer Discretionary", "Home Furnishings",      "US",     6_000_000_000),
    ("BWA",   "BorgWarner Inc.",              "NYSE",   "Consumer Discretionary", "Auto Components",       "US",     7_000_000_000),
    ("LEA",   "Lear Corporation",             "NYSE",   "Consumer Discretionary", "Auto Components",       "US",     6_000_000_000),
    ("APTV",  "Aptiv PLC",                    "NYSE",   "Consumer Discretionary", "Auto Components",       "IE",    12_000_000_000),

    # ── Consumer Staples ──────────────────────────────────────────────────────
    ("CVS",   "CVS Health Corporation",       "NYSE",   "Consumer Staples",       "Drug Stores",           "US",    65_000_000_000),
    ("MO",    "Altria Group Inc.",            "NYSE",   "Consumer Staples",       "Tobacco",               "US",    95_000_000_000),
    ("CLX",   "Clorox Company",              "NYSE",   "Consumer Staples",       "Household Products",    "US",    18_000_000_000),
    ("CL",    "Colgate-Palmolive Company",   "NYSE",   "Consumer Staples",       "Personal Products",     "US",    60_000_000_000),
    ("KMB",   "Kimberly-Clark Corporation",  "NYSE",   "Consumer Staples",       "Household Products",    "US",    44_000_000_000),
    ("CHD",   "Church & Dwight Co.",         "NYSE",   "Consumer Staples",       "Household Products",    "US",    20_000_000_000),
    ("GIS",   "General Mills Inc.",          "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    33_000_000_000),
    ("K",     "Kellanova",                   "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    28_000_000_000),
    ("CPB",   "Campbell Soup Company",       "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    12_000_000_000),
    ("CAG",   "Conagra Brands Inc.",         "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    13_000_000_000),
    ("HRL",   "Hormel Foods Corporation",    "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    16_000_000_000),
    ("MKC",   "McCormick & Company",         "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    19_000_000_000),
    ("SJM",   "J.M. Smucker Company",        "NYSE",   "Consumer Staples",       "Packaged Foods",        "US",    11_000_000_000),
    ("TSN",   "Tyson Foods Inc.",            "NYSE",   "Consumer Staples",       "Meat Processing",       "US",    18_000_000_000),
    ("ADM",   "Archer-Daniels-Midland",      "NYSE",   "Consumer Staples",       "Agricultural Commodities","US",  28_000_000_000),
    ("BG",    "Bunge Global SA",             "NYSE",   "Consumer Staples",       "Agricultural Commodities","MO",  10_000_000_000),
    ("WBA",   "Walgreens Boots Alliance",    "NASDAQ", "Consumer Staples",       "Drug Stores",           "US",     6_000_000_000),
    ("MNST",  "Monster Beverage Corporation","NASDAQ", "Consumer Staples",       "Beverages",             "US",    55_000_000_000),
    ("STZ",   "Constellation Brands Inc.",   "NYSE",   "Consumer Staples",       "Beverages",             "US",    40_000_000_000),
    ("KDP",   "Keurig Dr Pepper Inc.",       "NASDAQ", "Consumer Staples",       "Beverages",             "US",    48_000_000_000),
    ("TAP",   "Molson Coors Beverage",       "NYSE",   "Consumer Staples",       "Beverages",             "US",    12_000_000_000),
    ("EL",    "Estée Lauder Companies",      "NYSE",   "Consumer Staples",       "Personal Products",     "US",    30_000_000_000),

    # ── Energy ────────────────────────────────────────────────────────────────
    ("EOG",   "EOG Resources Inc.",          "NYSE",   "Energy",                 "Oil & Gas",             "US",    70_000_000_000),
    ("OXY",   "Occidental Petroleum",        "NYSE",   "Energy",                 "Oil & Gas",             "US",    45_000_000_000),
    ("VLO",   "Valero Energy Corporation",   "NYSE",   "Energy",                 "Oil Refining",          "US",    45_000_000_000),
    ("PSX",   "Phillips 66",                 "NYSE",   "Energy",                 "Oil Refining",          "US",    50_000_000_000),
    ("MPC",   "Marathon Petroleum Corp.",    "NYSE",   "Energy",                 "Oil Refining",          "US",    55_000_000_000),
    ("HES",   "Hess Corporation",            "NYSE",   "Energy",                 "Oil & Gas",             "US",    40_000_000_000),
    ("DVN",   "Devon Energy Corporation",    "NYSE",   "Energy",                 "Oil & Gas",             "US",    18_000_000_000),
    ("FANG",  "Diamondback Energy Inc.",     "NASDAQ", "Energy",                 "Oil & Gas",             "US",    28_000_000_000),
    ("APA",   "APA Corporation",             "NASDAQ", "Energy",                 "Oil & Gas",             "US",     8_000_000_000),
    ("HAL",   "Halliburton Company",         "NYSE",   "Energy",                 "Oil Field Services",    "US",    28_000_000_000),
    ("BKR",   "Baker Hughes Company",        "NASDAQ", "Energy",                 "Oil Field Services",    "US",    35_000_000_000),
    ("CTRA",  "Coterra Energy Inc.",         "NYSE",   "Energy",                 "Oil & Gas",             "US",    18_000_000_000),
    ("EQT",   "EQT Corporation",            "NYSE",   "Energy",                 "Natural Gas",           "US",    16_000_000_000),
    ("KMI",   "Kinder Morgan Inc.",          "NYSE",   "Energy",                 "Pipelines",             "US",    24_000_000_000),
    ("WMB",   "Williams Companies Inc.",     "NYSE",   "Energy",                 "Pipelines",             "US",    55_000_000_000),
    ("OKE",   "ONEOK Inc.",                  "NYSE",   "Energy",                 "Pipelines",             "US",    50_000_000_000),
    ("TRGP",  "Targa Resources Corp.",       "NYSE",   "Energy",                 "Pipelines",             "US",    35_000_000_000),
    ("LNG",   "Cheniere Energy Inc.",        "NYSE",   "Energy",                 "LNG",                   "US",    42_000_000_000),
    ("MRO",   "Marathon Oil Corporation",    "NYSE",   "Energy",                 "Oil & Gas",             "US",    14_000_000_000),

    # ── Financials ────────────────────────────────────────────────────────────
    ("USB",   "U.S. Bancorp",                "NYSE",   "Financials",             "Banking",               "US",    70_000_000_000),
    ("PNC",   "PNC Financial Services",      "NYSE",   "Financials",             "Banking",               "US",    70_000_000_000),
    ("TFC",   "Truist Financial Corp.",      "NYSE",   "Financials",             "Banking",               "US",    55_000_000_000),
    ("COF",   "Capital One Financial",       "NYSE",   "Financials",             "Banking",               "US",    65_000_000_000),
    ("DFS",   "Discover Financial Services", "NYSE",   "Financials",             "Payments",              "US",    40_000_000_000),
    ("SYF",   "Synchrony Financial",         "NYSE",   "Financials",             "Payments",              "US",    18_000_000_000),
    ("FITB",  "Fifth Third Bancorp",         "NASDAQ", "Financials",             "Banking",               "US",    25_000_000_000),
    ("HBAN",  "Huntington Bancshares",       "NASDAQ", "Financials",             "Banking",               "US",    20_000_000_000),
    ("CFG",   "Citizens Financial Group",    "NYSE",   "Financials",             "Banking",               "US",    18_000_000_000),
    ("KEY",   "KeyCorp",                     "NYSE",   "Financials",             "Banking",               "US",    14_000_000_000),
    ("MTB",   "M&T Bank Corporation",        "NYSE",   "Financials",             "Banking",               "US",    30_000_000_000),
    ("RF",    "Regions Financial Corp.",     "NYSE",   "Financials",             "Banking",               "US",    20_000_000_000),
    ("NTRS",  "Northern Trust Corporation",  "NASDAQ", "Financials",             "Asset Management",      "US",    17_000_000_000),
    ("STT",   "State Street Corporation",    "NYSE",   "Financials",             "Asset Management",      "US",    24_000_000_000),
    ("BK",    "Bank of New York Mellon",     "NYSE",   "Financials",             "Asset Management",      "US",    50_000_000_000),
    ("SCHW",  "Charles Schwab Corporation",  "NYSE",   "Financials",             "Brokerage",             "US",   130_000_000_000),
    ("RJF",   "Raymond James Financial",     "NYSE",   "Financials",             "Investment Banking",    "US",    25_000_000_000),
    ("PRU",   "Prudential Financial Inc.",   "NYSE",   "Financials",             "Insurance",             "US",    38_000_000_000),
    ("MET",   "MetLife Inc.",                "NYSE",   "Financials",             "Insurance",             "US",    50_000_000_000),
    ("AFL",   "Aflac Incorporated",          "NYSE",   "Financials",             "Insurance",             "US",    55_000_000_000),
    ("ALL",   "Allstate Corporation",        "NYSE",   "Financials",             "Insurance",             "US",    50_000_000_000),
    ("TRV",   "Travelers Companies Inc.",    "NYSE",   "Financials",             "Insurance",             "US",    52_000_000_000),
    ("PGR",   "Progressive Corporation",     "NYSE",   "Financials",             "Insurance",             "US",   140_000_000_000),
    ("CB",    "Chubb Limited",               "NYSE",   "Financials",             "Insurance",             "CH",   105_000_000_000),
    ("AIG",   "American International Group","NYSE",   "Financials",             "Insurance",             "US",    50_000_000_000),
    ("HIG",   "Hartford Financial Services", "NYSE",   "Financials",             "Insurance",             "US",    24_000_000_000),
    ("TROW",  "T. Rowe Price Group",         "NASDAQ", "Financials",             "Asset Management",      "US",    22_000_000_000),
    ("IVZ",   "Invesco Ltd.",                "NYSE",   "Financials",             "Asset Management",      "US",     7_000_000_000),
    ("BEN",   "Franklin Resources Inc.",     "NYSE",   "Financials",             "Asset Management",      "US",    12_000_000_000),
    ("AMG",   "Affiliated Managers Group",   "NYSE",   "Financials",             "Asset Management",      "US",     6_000_000_000),
    ("FDS",   "FactSet Research Systems",    "NASDAQ", "Financials",             "Financial Data",        "US",    18_000_000_000),
    ("MSCI",  "MSCI Inc.",                   "NYSE",   "Financials",             "Financial Data",        "US",    44_000_000_000),
    ("ICE",   "Intercontinental Exchange",   "NYSE",   "Financials",             "Exchanges",             "US",    90_000_000_000),
    ("CME",   "CME Group Inc.",              "NASDAQ", "Financials",             "Exchanges",             "US",    80_000_000_000),
    ("NDAQ",  "Nasdaq Inc.",                 "NASDAQ", "Financials",             "Exchanges",             "US",    40_000_000_000),
    ("CBOE",  "Cboe Global Markets",         "CBOE",   "Financials",             "Exchanges",             "US",    22_000_000_000),
    ("MCO",   "Moody's Corporation",         "NYSE",   "Financials",             "Financial Data",        "US",    75_000_000_000),
    ("SPGI",  "S&P Global Inc.",             "NYSE",   "Financials",             "Financial Data",        "US",   145_000_000_000),
    ("AON",   "Aon plc",                     "NYSE",   "Financials",             "Insurance Brokerage",   "IE",    72_000_000_000),
    ("MMC",   "Marsh & McLennan Companies",  "NYSE",   "Financials",             "Insurance Brokerage",   "US",    95_000_000_000),
    ("WTW",   "Willis Towers Watson",        "NASDAQ", "Financials",             "Insurance Brokerage",   "IE",    28_000_000_000),
    ("AJG",   "Arthur J. Gallagher & Co.",   "NYSE",   "Financials",             "Insurance Brokerage",   "US",    60_000_000_000),
    ("PYPL",  "PayPal Holdings Inc.",        "NASDAQ", "Financials",             "Payments",              "US",    75_000_000_000),
    ("GPN",   "Global Payments Inc.",        "NYSE",   "Financials",             "Payments",              "US",    22_000_000_000),
    ("FIS",   "Fidelity National Info Svcs", "NYSE",   "Financials",             "Payments",              "US",    38_000_000_000),
    ("FISV",  "Fiserv Inc.",                 "NASDAQ", "Financials",             "Payments",              "US",    80_000_000_000),
    ("BR",    "Broadridge Financial Solns",  "NYSE",   "Financials",             "Financial Technology",  "US",    24_000_000_000),
    ("FNF",   "Fidelity National Financial", "NYSE",   "Financials",             "Title Insurance",       "US",    12_000_000_000),
    ("PFG",   "Principal Financial Group",   "NASDAQ", "Financials",             "Insurance",             "US",    18_000_000_000),
    ("VOYA",  "Voya Financial Inc.",         "NYSE",   "Financials",             "Insurance",             "US",     8_000_000_000),
    ("RE",    "Everest Group Ltd.",          "NYSE",   "Financials",             "Reinsurance",           "IE",    14_000_000_000),
    ("RGA",   "Reinsurance Group of America","NYSE",   "Financials",             "Reinsurance",           "US",    10_000_000_000),
    ("AIZ",   "Assurant Inc.",               "NYSE",   "Financials",             "Insurance",             "US",     9_000_000_000),
    ("L",     "Loews Corporation",           "NYSE",   "Financials",             "Conglomerates",         "US",    18_000_000_000),
    ("GL",    "Globe Life Inc.",             "NYSE",   "Financials",             "Insurance",             "US",    11_000_000_000),

    # ── Healthcare ────────────────────────────────────────────────────────────
    ("ABT",   "Abbott Laboratories",         "NYSE",   "Healthcare",             "Medical Devices",       "US",   220_000_000_000),
    ("MDT",   "Medtronic plc",               "NYSE",   "Healthcare",             "Medical Devices",       "IE",   100_000_000_000),
    ("SYK",   "Stryker Corporation",         "NYSE",   "Healthcare",             "Medical Devices",       "US",   130_000_000_000),
    ("BSX",   "Boston Scientific Corp.",     "NYSE",   "Healthcare",             "Medical Devices",       "US",   115_000_000_000),
    ("EW",    "Edwards Lifesciences",        "NYSE",   "Healthcare",             "Medical Devices",       "US",    40_000_000_000),
    ("ISRG",  "Intuitive Surgical Inc.",     "NASDAQ", "Healthcare",             "Medical Devices",       "US",   185_000_000_000),
    ("ZBH",   "Zimmer Biomet Holdings",      "NYSE",   "Healthcare",             "Medical Devices",       "US",    22_000_000_000),
    ("BDX",   "Becton Dickinson & Company",  "NYSE",   "Healthcare",             "Medical Devices",       "US",    62_000_000_000),
    ("BAX",   "Baxter International Inc.",   "NYSE",   "Healthcare",             "Medical Devices",       "US",    14_000_000_000),
    ("DHR",   "Danaher Corporation",         "NYSE",   "Healthcare",             "Life Sciences",         "US",   180_000_000_000),
    ("A",     "Agilent Technologies Inc.",   "NYSE",   "Healthcare",             "Life Sciences",         "US",    30_000_000_000),
    ("IQV",   "IQVIA Holdings Inc.",         "NYSE",   "Healthcare",             "Life Sciences",         "US",    40_000_000_000),
    ("LH",    "Labcorp",                     "NYSE",   "Healthcare",             "Lab Services",          "US",    20_000_000_000),
    ("DGX",   "Quest Diagnostics",           "NYSE",   "Healthcare",             "Lab Services",          "US",    17_000_000_000),
    ("CI",    "Cigna Group",                 "NYSE",   "Healthcare",             "Health Insurance",      "US",    85_000_000_000),
    ("HUM",   "Humana Inc.",                 "NYSE",   "Healthcare",             "Health Insurance",      "US",    45_000_000_000),
    ("ELV",   "Elevance Health Inc.",        "NYSE",   "Healthcare",             "Health Insurance",      "US",   110_000_000_000),
    ("CNC",   "Centene Corporation",         "NYSE",   "Healthcare",             "Health Insurance",      "US",    35_000_000_000),
    ("MOH",   "Molina Healthcare Inc.",      "NYSE",   "Healthcare",             "Health Insurance",      "US",    20_000_000_000),
    ("MCK",   "McKesson Corporation",        "NYSE",   "Healthcare",             "Drug Distribution",     "US",    80_000_000_000),
    ("CAH",   "Cardinal Health Inc.",        "NYSE",   "Healthcare",             "Drug Distribution",     "US",    30_000_000_000),
    ("COR",   "Cencora Inc.",                "NYSE",   "Healthcare",             "Drug Distribution",     "US",    48_000_000_000),
    ("VRTX",  "Vertex Pharmaceuticals",      "NASDAQ", "Healthcare",             "Biotechnology",         "US",   120_000_000_000),
    ("REGN",  "Regeneron Pharmaceuticals",   "NASDAQ", "Healthcare",             "Biotechnology",         "US",    80_000_000_000),
    ("BIIB",  "Biogen Inc.",                 "NASDAQ", "Healthcare",             "Biotechnology",         "US",    30_000_000_000),
    ("MRNA",  "Moderna Inc.",                "NASDAQ", "Healthcare",             "Biotechnology",         "US",    16_000_000_000),
    ("ALNY",  "Alnylam Pharmaceuticals",     "NASDAQ", "Healthcare",             "Biotechnology",         "US",    30_000_000_000),
    ("INCY",  "Incyte Corporation",          "NASDAQ", "Healthcare",             "Biotechnology",         "US",    14_000_000_000),
    ("ILMN",  "Illumina Inc.",               "NASDAQ", "Healthcare",             "Genomics",              "US",    22_000_000_000),
    ("DXCM",  "DexCom Inc.",                 "NASDAQ", "Healthcare",             "Medical Devices",       "US",    25_000_000_000),
    ("PODD",  "Insulet Corporation",         "NASDAQ", "Healthcare",             "Medical Devices",       "US",    14_000_000_000),
    ("ALGN",  "Align Technology Inc.",       "NASDAQ", "Healthcare",             "Medical Devices",       "US",    16_000_000_000),
    ("ZTS",   "Zoetis Inc.",                 "NYSE",   "Healthcare",             "Animal Health",         "US",    80_000_000_000),
    ("IDXX",  "IDEXX Laboratories",          "NASDAQ", "Healthcare",             "Animal Health",         "US",    36_000_000_000),
    ("VEEV",  "Veeva Systems Inc.",          "NYSE",   "Healthcare",             "Healthcare Software",   "US",    30_000_000_000),
    ("RMD",   "ResMed Inc.",                 "NYSE",   "Healthcare",             "Medical Devices",       "US",    35_000_000_000),
    ("HOLX",  "Hologic Inc.",                "NASDAQ", "Healthcare",             "Medical Devices",       "US",    18_000_000_000),
    ("HSIC",  "Henry Schein Inc.",           "NASDAQ", "Healthcare",             "Drug Distribution",     "US",    10_000_000_000),

    # ── Industrials ───────────────────────────────────────────────────────────
    ("NOC",   "Northrop Grumman Corp.",      "NYSE",   "Industrials",            "Defense",               "US",    70_000_000_000),
    ("GD",    "General Dynamics Corp.",      "NYSE",   "Industrials",            "Defense",               "US",    75_000_000_000),
    ("TDG",   "TransDigm Group Inc.",        "NYSE",   "Industrials",            "Aerospace",             "US",    70_000_000_000),
    ("HII",   "Huntington Ingalls Industries","NYSE",  "Industrials",            "Defense",               "US",    11_000_000_000),
    ("LDOS",  "Leidos Holdings Inc.",        "NYSE",   "Industrials",            "Defense IT",            "US",    22_000_000_000),
    ("SAIC",  "Science Applications Intl.", "NYSE",   "Industrials",            "Defense IT",            "US",     6_000_000_000),
    ("MMM",   "3M Company",                  "NYSE",   "Industrials",            "Diversified Industrial","US",    55_000_000_000),
    ("EMR",   "Emerson Electric Co.",        "NYSE",   "Industrials",            "Industrial Automation", "US",    65_000_000_000),
    ("ETN",   "Eaton Corporation plc",       "NYSE",   "Industrials",            "Electrical Equipment",  "IE",   130_000_000_000),
    ("ROK",   "Rockwell Automation",         "NYSE",   "Industrials",            "Industrial Automation", "US",    30_000_000_000),
    ("IR",    "Ingersoll Rand Inc.",         "NYSE",   "Industrials",            "Industrial Machinery",  "US",    35_000_000_000),
    ("AME",   "AMETEK Inc.",                 "NYSE",   "Industrials",            "Electronic Instruments","US",    38_000_000_000),
    ("XYL",   "Xylem Inc.",                  "NYSE",   "Industrials",            "Water Technology",      "US",    22_000_000_000),
    ("IEX",   "IDEX Corporation",            "NYSE",   "Industrials",            "Industrial Machinery",  "US",    16_000_000_000),
    ("ROP",   "Roper Technologies Inc.",     "NASDAQ", "Industrials",            "Diversified Industrial","US",    55_000_000_000),
    ("TT",    "Trane Technologies plc",      "NYSE",   "Industrials",            "HVAC",                  "IE",    80_000_000_000),
    ("CARR",  "Carrier Global Corporation",  "NYSE",   "Industrials",            "HVAC",                  "US",    60_000_000_000),
    ("OTIS",  "Otis Worldwide Corporation",  "NYSE",   "Industrials",            "Elevators",             "US",    35_000_000_000),
    ("ITW",   "Illinois Tool Works Inc.",    "NYSE",   "Industrials",            "Diversified Industrial","US",    70_000_000_000),
    ("PH",    "Parker Hannifin Corporation", "NYSE",   "Industrials",            "Industrial Machinery",  "US",    70_000_000_000),
    ("ADP",   "Automatic Data Processing",   "NASDAQ", "Industrials",            "HR & Payroll",          "US",   105_000_000_000),
    ("PAYX",  "Paychex Inc.",                "NASDAQ", "Industrials",            "HR & Payroll",          "US",    50_000_000_000),
    ("CTAS",  "Cintas Corporation",          "NASDAQ", "Industrials",            "Business Services",     "US",    80_000_000_000),
    ("FDX",   "FedEx Corporation",           "NYSE",   "Industrials",            "Logistics",             "US",    65_000_000_000),
    ("UNP",   "Union Pacific Corporation",   "NYSE",   "Industrials",            "Railroads",             "US",   135_000_000_000),
    ("CSX",   "CSX Corporation",             "NASDAQ", "Industrials",            "Railroads",             "US",    65_000_000_000),
    ("NSC",   "Norfolk Southern Corp.",      "NYSE",   "Industrials",            "Railroads",             "US",    55_000_000_000),
    ("DAL",   "Delta Air Lines Inc.",        "NYSE",   "Industrials",            "Airlines",              "US",    30_000_000_000),
    ("UAL",   "United Airlines Holdings",    "NASDAQ", "Industrials",            "Airlines",              "US",    22_000_000_000),
    ("AAL",   "American Airlines Group",     "NASDAQ", "Industrials",            "Airlines",              "US",     9_000_000_000),
    ("LUV",   "Southwest Airlines Co.",      "NYSE",   "Industrials",            "Airlines",              "US",    16_000_000_000),
    ("URI",   "United Rentals Inc.",         "NYSE",   "Industrials",            "Equipment Rental",      "US",    40_000_000_000),
    ("FAST",  "Fastenal Company",            "NASDAQ", "Industrials",            "Industrial Distribution","US",   40_000_000_000),
    ("GWW",   "W.W. Grainger Inc.",          "NYSE",   "Industrials",            "Industrial Distribution","US",   40_000_000_000),
    ("PWR",   "Quanta Services Inc.",        "NYSE",   "Industrials",            "Engineering & Construction","US",40_000_000_000),
    ("EXPD",  "Expeditors International",    "NASDAQ", "Industrials",            "Freight & Logistics",   "US",    16_000_000_000),
    ("CHRW",  "C.H. Robinson Worldwide",     "NASDAQ", "Industrials",            "Freight & Logistics",   "US",    12_000_000_000),
    ("JBHT",  "J.B. Hunt Transport Svcs",    "NASDAQ", "Industrials",            "Trucking",              "US",    16_000_000_000),
    ("ODFL",  "Old Dominion Freight Line",   "NASDAQ", "Industrials",            "Trucking",              "US",    40_000_000_000),
    ("XPO",   "XPO Inc.",                    "NYSE",   "Industrials",            "Trucking",              "US",    12_000_000_000),
    ("GXO",   "GXO Logistics Inc.",          "NYSE",   "Industrials",            "Freight & Logistics",   "US",     7_000_000_000),
    ("GNRC",  "Generac Holdings Inc.",       "NYSE",   "Industrials",            "Electrical Equipment",  "US",     8_000_000_000),
    ("NDSN",  "Nordson Corporation",         "NASDAQ", "Industrials",            "Industrial Machinery",  "US",    10_000_000_000),
    ("HUBB",  "Hubbell Incorporated",        "NYSE",   "Industrials",            "Electrical Equipment",  "US",    17_000_000_000),

    # ── Information Technology (additional) ───────────────────────────────────
    ("NOW",   "ServiceNow Inc.",             "NYSE",   "Technology",             "Software",              "US",   220_000_000_000),
    ("PANW",  "Palo Alto Networks Inc.",     "NASDAQ", "Technology",             "Cybersecurity",         "US",   110_000_000_000),
    ("CRWD",  "CrowdStrike Holdings Inc.",   "NASDAQ", "Technology",             "Cybersecurity",         "US",    90_000_000_000),
    ("FTNT",  "Fortinet Inc.",               "NASDAQ", "Technology",             "Cybersecurity",         "US",    70_000_000_000),
    ("DDOG",  "Datadog Inc.",                "NASDAQ", "Technology",             "Cloud Monitoring",      "US",    35_000_000_000),
    ("SNOW",  "Snowflake Inc.",              "NYSE",   "Technology",             "Cloud Data Platform",   "US",    45_000_000_000),
    ("PLTR",  "Palantir Technologies",       "NYSE",   "Technology",             "Data Analytics",        "US",   230_000_000_000),
    ("MDB",   "MongoDB Inc.",                "NASDAQ", "Technology",             "Database Software",     "US",    22_000_000_000),
    ("NET",   "Cloudflare Inc.",             "NYSE",   "Technology",             "Cloud Networking",      "US",    45_000_000_000),
    ("ZS",    "Zscaler Inc.",                "NASDAQ", "Technology",             "Cybersecurity",         "US",    30_000_000_000),
    ("OKTA",  "Okta Inc.",                   "NASDAQ", "Technology",             "Identity Security",     "US",    15_000_000_000),
    ("WDAY",  "Workday Inc.",                "NASDAQ", "Technology",             "Enterprise Software",   "US",    60_000_000_000),
    ("HUBS",  "HubSpot Inc.",                "NYSE",   "Technology",             "CRM Software",          "US",    22_000_000_000),
    ("KLAC",  "KLA Corporation",             "NASDAQ", "Technology",             "Semiconductor Equipment","US",   85_000_000_000),
    ("LRCX",  "Lam Research Corporation",   "NASDAQ", "Technology",             "Semiconductor Equipment","US",   85_000_000_000),
    ("MRVL",  "Marvell Technology Inc.",     "NASDAQ", "Technology",             "Semiconductors",        "US",    60_000_000_000),
    ("MCHP",  "Microchip Technology",        "NASDAQ", "Technology",             "Semiconductors",        "US",    40_000_000_000),
    ("ON",    "ON Semiconductor Corp.",      "NASDAQ", "Technology",             "Semiconductors",        "US",    25_000_000_000),
    ("SWKS",  "Skyworks Solutions Inc.",     "NASDAQ", "Technology",             "Semiconductors",        "US",    12_000_000_000),
    ("QRVO",  "Qorvo Inc.",                  "NASDAQ", "Technology",             "Semiconductors",        "US",     7_000_000_000),
    ("MPWR",  "Monolithic Power Systems",    "NASDAQ", "Technology",             "Semiconductors",        "US",    24_000_000_000),
    ("NXPI",  "NXP Semiconductors N.V.",     "NASDAQ", "Technology",             "Semiconductors",        "NL",    50_000_000_000),
    ("STX",   "Seagate Technology Holdings", "NASDAQ", "Technology",             "Data Storage",          "IE",    18_000_000_000),
    ("WDC",   "Western Digital Corporation", "NASDAQ", "Technology",             "Data Storage",          "US",    20_000_000_000),
    ("HPQ",   "HP Inc.",                     "NYSE",   "Technology",             "Personal Computers",    "US",    30_000_000_000),
    ("HPE",   "Hewlett Packard Enterprise",  "NYSE",   "Technology",             "IT Infrastructure",     "US",    25_000_000_000),
    ("DELL",  "Dell Technologies Inc.",      "NYSE",   "Technology",             "IT Infrastructure",     "US",    55_000_000_000),
    ("NTAP",  "NetApp Inc.",                 "NASDAQ", "Technology",             "Data Storage",          "US",    22_000_000_000),
    ("CDW",   "CDW Corporation",             "NASDAQ", "Technology",             "IT Distribution",       "US",    25_000_000_000),
    ("CTSH",  "Cognizant Technology Solns",  "NASDAQ", "Technology",             "IT Services",           "US",    35_000_000_000),
    ("ACN",   "Accenture plc",               "NYSE",   "Technology",             "IT Consulting",         "IE",   220_000_000_000),
    ("IT",    "Gartner Inc.",                "NYSE",   "Technology",             "Research & Advisory",   "US",    35_000_000_000),
    ("VRSK",  "Verisk Analytics Inc.",       "NASDAQ", "Technology",             "Data Analytics",        "US",    35_000_000_000),
    ("GDDY",  "GoDaddy Inc.",                "NYSE",   "Technology",             "Web Services",          "US",    22_000_000_000),
    ("AKAM",  "Akamai Technologies Inc.",    "NASDAQ", "Technology",             "Content Delivery",      "US",    15_000_000_000),
    ("JNPR",  "Juniper Networks Inc.",       "NYSE",   "Technology",             "Networking",            "US",    13_000_000_000),
    ("FFIV",  "F5 Inc.",                     "NASDAQ", "Technology",             "Networking",            "US",    11_000_000_000),
    ("KEYS",  "Keysight Technologies",       "NYSE",   "Technology",             "Electronic Instruments","US",    22_000_000_000),
    ("TEL",   "TE Connectivity Ltd.",        "NYSE",   "Technology",             "Electronic Components", "CH",    40_000_000_000),
    ("APH",   "Amphenol Corporation",        "NYSE",   "Technology",             "Electronic Components", "US",    80_000_000_000),
    ("GLW",   "Corning Incorporated",        "NYSE",   "Technology",             "Electronic Components", "US",    32_000_000_000),
    ("TTD",   "The Trade Desk Inc.",         "NASDAQ", "Technology",             "Ad Technology",         "US",    55_000_000_000),
    ("APP",   "AppLovin Corporation",        "NASDAQ", "Technology",             "Ad Technology",         "US",   100_000_000_000),
    ("EPAM",  "EPAM Systems Inc.",           "NYSE",   "Technology",             "IT Services",           "US",    12_000_000_000),
    ("PAYC",  "Paycom Software Inc.",        "NYSE",   "Technology",             "HR Software",           "US",    14_000_000_000),
    ("PCTY",  "Paylocity Holding Corp.",     "NASDAQ", "Technology",             "HR Software",           "US",     8_000_000_000),
    ("FOUR",  "Shift4 Payments Inc.",        "NYSE",   "Technology",             "Payments Technology",   "US",     7_000_000_000),

    # ── Materials ─────────────────────────────────────────────────────────────
    ("NEM",   "Newmont Corporation",         "NYSE",   "Materials",              "Gold Mining",           "US",    50_000_000_000),
    ("FCX",   "Freeport-McMoRan Inc.",       "NYSE",   "Materials",              "Copper Mining",         "US",    55_000_000_000),
    ("AA",    "Alcoa Corporation",           "NYSE",   "Materials",              "Aluminum",              "US",     8_000_000_000),
    ("NUE",   "Nucor Corporation",           "NYSE",   "Materials",              "Steel",                 "US",    18_000_000_000),
    ("STLD",  "Steel Dynamics Inc.",         "NASDAQ", "Materials",              "Steel",                 "US",    18_000_000_000),
    ("CLF",   "Cleveland-Cliffs Inc.",       "NYSE",   "Materials",              "Steel",                 "US",     5_000_000_000),
    ("CF",    "CF Industries Holdings",      "NYSE",   "Materials",              "Fertilizers",           "US",    12_000_000_000),
    ("MOS",   "Mosaic Company",              "NYSE",   "Materials",              "Fertilizers",           "US",     8_000_000_000),
    ("IFF",   "Intl Flavors & Fragrances",   "NYSE",   "Materials",              "Specialty Chemicals",   "US",    18_000_000_000),
    ("SHW",   "Sherwin-Williams Company",    "NYSE",   "Materials",              "Paints & Coatings",     "US",    85_000_000_000),
    ("PPG",   "PPG Industries Inc.",         "NYSE",   "Materials",              "Paints & Coatings",     "US",    28_000_000_000),
    ("RPM",   "RPM International Inc.",      "NYSE",   "Materials",              "Paints & Coatings",     "US",    12_000_000_000),
    ("ECL",   "Ecolab Inc.",                 "NYSE",   "Materials",              "Specialty Chemicals",   "US",    62_000_000_000),
    ("APD",   "Air Products and Chemicals",  "NYSE",   "Materials",              "Industrial Gases",      "US",    60_000_000_000),
    ("LIN",   "Linde plc",                   "NASDAQ", "Materials",              "Industrial Gases",      "IE",   210_000_000_000),
    ("DD",    "DuPont de Nemours Inc.",      "NYSE",   "Materials",              "Specialty Chemicals",   "US",    35_000_000_000),
    ("EMN",   "Eastman Chemical Company",    "NYSE",   "Materials",              "Specialty Chemicals",   "US",    12_000_000_000),
    ("LYB",   "LyondellBasell Industries",   "NYSE",   "Materials",              "Chemicals",             "NL",    20_000_000_000),
    ("PKG",   "Packaging Corp of America",   "NYSE",   "Materials",              "Paper & Packaging",     "US",    18_000_000_000),
    ("IP",    "International Paper Company", "NYSE",   "Materials",              "Paper & Packaging",     "US",    20_000_000_000),
    ("SEE",   "Sealed Air Corporation",      "NYSE",   "Materials",              "Paper & Packaging",     "US",     5_000_000_000),
    ("AMCR",  "Amcor plc",                   "NYSE",   "Materials",              "Paper & Packaging",     "AU",    14_000_000_000),
    ("BLL",   "Ball Corporation",            "NYSE",   "Materials",              "Metal Packaging",       "US",    14_000_000_000),
    ("AVY",   "Avery Dennison Corporation",  "NYSE",   "Materials",              "Paper & Packaging",     "US",    16_000_000_000),
    ("FMC",   "FMC Corporation",             "NYSE",   "Materials",              "Agricultural Chemicals","US",     6_000_000_000),
    ("ALB",   "Albemarle Corporation",       "NYSE",   "Materials",              "Lithium & Specialty",   "US",     9_000_000_000),
    ("CE",    "Celanese Corporation",        "NYSE",   "Materials",              "Specialty Chemicals",   "US",     8_000_000_000),
    ("WRK",   "WestRock Company",            "NYSE",   "Materials",              "Paper & Packaging",     "US",    10_000_000_000),

    # ── Real Estate ───────────────────────────────────────────────────────────
    ("PLD",   "Prologis Inc.",               "NYSE",   "Real Estate",            "Industrial REITs",      "US",   100_000_000_000),
    ("AMT",   "American Tower Corporation",  "NYSE",   "Real Estate",            "Cell Tower REITs",      "US",    85_000_000_000),
    ("EQIX",  "Equinix Inc.",                "NASDAQ", "Real Estate",            "Data Center REITs",     "US",    75_000_000_000),
    ("CCI",   "Crown Castle Inc.",           "NYSE",   "Real Estate",            "Cell Tower REITs",      "US",    45_000_000_000),
    ("SBAC",  "SBA Communications Corp.",    "NASDAQ", "Real Estate",            "Cell Tower REITs",      "US",    22_000_000_000),
    ("DLR",   "Digital Realty Trust Inc.",   "NYSE",   "Real Estate",            "Data Center REITs",     "US",    50_000_000_000),
    ("WELL",  "Welltower Inc.",              "NYSE",   "Real Estate",            "Healthcare REITs",      "US",    70_000_000_000),
    ("VTR",   "Ventas Inc.",                 "NYSE",   "Real Estate",            "Healthcare REITs",      "US",    22_000_000_000),
    ("VICI",  "VICI Properties Inc.",        "NYSE",   "Real Estate",            "Gaming REITs",          "US",    32_000_000_000),
    ("O",     "Realty Income Corporation",   "NYSE",   "Real Estate",            "Net Lease REITs",       "US",    50_000_000_000),
    ("SPG",   "Simon Property Group Inc.",   "NYSE",   "Real Estate",            "Retail REITs",          "US",    50_000_000_000),
    ("PSA",   "Public Storage",              "NYSE",   "Real Estate",            "Self-Storage REITs",    "US",    50_000_000_000),
    ("EXR",   "Extra Space Storage Inc.",    "NYSE",   "Real Estate",            "Self-Storage REITs",    "US",    32_000_000_000),
    ("AVB",   "AvalonBay Communities",       "NYSE",   "Real Estate",            "Residential REITs",     "US",    28_000_000_000),
    ("ESS",   "Essex Property Trust",        "NYSE",   "Real Estate",            "Residential REITs",     "US",    18_000_000_000),
    ("MAA",   "Mid-America Apartment Comm.", "NYSE",   "Real Estate",            "Residential REITs",     "US",    16_000_000_000),
    ("UDR",   "UDR Inc.",                    "NYSE",   "Real Estate",            "Residential REITs",     "US",    12_000_000_000),
    ("CPT",   "Camden Property Trust",       "NYSE",   "Real Estate",            "Residential REITs",     "US",    10_000_000_000),
    ("INVH",  "Invitation Homes Inc.",       "NYSE",   "Real Estate",            "Single-Family REITs",   "US",    20_000_000_000),
    ("SUI",   "Sun Communities Inc.",        "NYSE",   "Real Estate",            "Manufactured Housing",  "US",    16_000_000_000),
    ("ELS",   "Equity LifeStyle Properties","NYSE",   "Real Estate",            "Manufactured Housing",  "US",    12_000_000_000),
    ("NNN",   "NNN REIT Inc.",               "NYSE",   "Real Estate",            "Net Lease REITs",       "US",    10_000_000_000),
    ("STAG",  "STAG Industrial Inc.",        "NYSE",   "Real Estate",            "Industrial REITs",      "US",     6_000_000_000),
    ("ARE",   "Alexandria Real Estate Eq.",  "NYSE",   "Real Estate",            "Life Science REITs",    "US",    18_000_000_000),
    ("BXP",   "BXP Inc.",                    "NYSE",   "Real Estate",            "Office REITs",          "US",    10_000_000_000),
    ("KIM",   "Kimco Realty Corporation",    "NYSE",   "Real Estate",            "Retail REITs",          "US",    14_000_000_000),
    ("REG",   "Regency Centers Corporation", "NASDAQ", "Real Estate",            "Retail REITs",          "US",    12_000_000_000),
    ("FRT",   "Federal Realty Inv. Trust",   "NYSE",   "Real Estate",            "Retail REITs",          "US",     9_000_000_000),
    ("HST",   "Host Hotels & Resorts",       "NASDAQ", "Real Estate",            "Hotel REITs",           "US",    14_000_000_000),
    ("WY",    "Weyerhaeuser Company",        "NYSE",   "Real Estate",            "Timber REITs",          "US",    22_000_000_000),
    ("IRM",   "Iron Mountain Inc.",          "NYSE",   "Real Estate",            "Data Center REITs",     "US",    22_000_000_000),
    ("COLD",  "Americold Realty Trust",      "NYSE",   "Real Estate",            "Cold Storage REITs",    "US",     7_000_000_000),
    ("REXR",  "Rexford Industrial Realty",   "NYSE",   "Real Estate",            "Industrial REITs",      "US",     9_000_000_000),
    ("ADC",   "Agree Realty Corporation",    "NYSE",   "Real Estate",            "Net Lease REITs",       "US",     7_000_000_000),
    ("WPC",   "W. P. Carey Inc.",            "NYSE",   "Real Estate",            "Net Lease REITs",       "US",    13_000_000_000),

    # ── Utilities ─────────────────────────────────────────────────────────────
    ("NEE",   "NextEra Energy Inc.",         "NYSE",   "Utilities",              "Electric Utilities",    "US",   135_000_000_000),
    ("DUK",   "Duke Energy Corporation",     "NYSE",   "Utilities",              "Electric Utilities",    "US",    80_000_000_000),
    ("SO",    "Southern Company",            "NYSE",   "Utilities",              "Electric Utilities",    "US",    80_000_000_000),
    ("D",     "Dominion Energy Inc.",        "NYSE",   "Utilities",              "Electric Utilities",    "US",    40_000_000_000),
    ("AEP",   "American Electric Power",     "NASDAQ", "Utilities",              "Electric Utilities",    "US",    45_000_000_000),
    ("EXC",   "Exelon Corporation",          "NASDAQ", "Utilities",              "Electric Utilities",    "US",    40_000_000_000),
    ("SRE",   "Sempra",                      "NYSE",   "Utilities",              "Multi-Utilities",       "US",    45_000_000_000),
    ("PCG",   "PG&E Corporation",            "NYSE",   "Utilities",              "Electric Utilities",    "US",    35_000_000_000),
    ("XEL",   "Xcel Energy Inc.",            "NASDAQ", "Utilities",              "Electric Utilities",    "US",    30_000_000_000),
    ("WEC",   "WEC Energy Group Inc.",       "NYSE",   "Utilities",              "Electric Utilities",    "US",    28_000_000_000),
    ("ES",    "Eversource Energy",           "NYSE",   "Utilities",              "Electric Utilities",    "US",    20_000_000_000),
    ("AWK",   "American Water Works",        "NYSE",   "Utilities",              "Water Utilities",       "US",    25_000_000_000),
    ("PPL",   "PPL Corporation",             "NYSE",   "Utilities",              "Electric Utilities",    "US",    20_000_000_000),
    ("ETR",   "Entergy Corporation",         "NYSE",   "Utilities",              "Electric Utilities",    "US",    22_000_000_000),
    ("FE",    "FirstEnergy Corp.",           "NYSE",   "Utilities",              "Electric Utilities",    "US",    22_000_000_000),
    ("CNP",   "CenterPoint Energy Inc.",     "NYSE",   "Utilities",              "Multi-Utilities",       "US",    20_000_000_000),
    ("AES",   "AES Corporation",             "NYSE",   "Utilities",              "Electric Utilities",    "US",    12_000_000_000),
    ("LNT",   "Alliant Energy Corporation",  "NASDAQ", "Utilities",              "Electric Utilities",    "US",    14_000_000_000),
    ("EVRG",  "Evergy Inc.",                 "NASDAQ", "Utilities",              "Electric Utilities",    "US",    12_000_000_000),
    ("NRG",   "NRG Energy Inc.",             "NYSE",   "Utilities",              "Electric Utilities",    "US",    16_000_000_000),
    ("PNW",   "Pinnacle West Capital",       "NASDAQ", "Utilities",              "Electric Utilities",    "US",     8_000_000_000),
    ("AEE",   "Ameren Corporation",          "NYSE",   "Utilities",              "Multi-Utilities",       "US",    20_000_000_000),
    ("CMS",   "CMS Energy Corporation",      "NYSE",   "Utilities",              "Multi-Utilities",       "US",    18_000_000_000),
    ("NI",    "NiSource Inc.",               "NYSE",   "Utilities",              "Gas Utilities",         "US",    11_000_000_000),  # NYSE:NI (utility) — distinct from CME:NI (Nickel, disabled)
    ("OGE",   "OGE Energy Corp.",            "NYSE",   "Utilities",              "Electric Utilities",    "US",     3_500_000_000),
    ("POR",   "Portland General Electric",   "NYSE",   "Utilities",              "Electric Utilities",    "US",     4_000_000_000),
    ("IDA",   "IDACORP Inc.",                "NYSE",   "Utilities",              "Electric Utilities",    "US",     5_000_000_000),
    ("WTRG",  "Essential Utilities Inc.",    "NYSE",   "Utilities",              "Water Utilities",       "US",     9_000_000_000),
]

# (symbol, name, exchange, category)  — no country, no market cap
COMMODITIES: list[tuple] = [
    # Energy
    ("WTI",      "Crude Oil (WTI)",    "NYMEX", "Energy"),
    ("BRENT",    "Crude Oil (Brent)",  "ICE",   "Energy"),
    ("NG",       "Natural Gas",        "NYMEX", "Energy"),
    ("GASOLINE", "Gasoline",           "NYMEX", "Energy"),
    # ("COAL",     "Coal",               "CME",   "Energy"),   # No CME/NYMEX futures on yfinance — disabled
    # Metals
    ("XAUUSD",   "Gold",               "COMEX", "Metals"),
    ("XAGUSD",   "Silver",             "COMEX", "Metals"),
    ("XPTUSD",   "Platinum",           "NYMEX", "Metals"),
    ("HG",       "Copper",             "COMEX", "Metals"),
    ("ALI",      "Aluminum",           "CME",   "Metals"),    # ALI=F is CME contract (not LME)
    ("ZNC",      "Zinc",               "CME",   "Metals"),    # ZNC=F is CME contract
    # ("NI",       "Nickel",             "LME",   "Metals"),  # LME-only, no yfinance ticker — disabled
    # Agriculture
    ("ZW",       "Wheat",              "CBOT",  "Agriculture"),
    ("ZC",       "Corn",               "CBOT",  "Agriculture"),
    ("ZS",       "Soybeans",           "CBOT",  "Agriculture"),
    ("KC",       "Coffee",             "ICE",   "Agriculture"),
    ("SB",       "Sugar",              "ICE",   "Agriculture"),
    ("CT",       "Cotton",             "ICE",   "Agriculture"),
    ("CC",       "Cocoa",              "ICE",   "Agriculture"),
    ("LE",       "Live Cattle",        "CME",   "Agriculture"),
    ("PALM",     "Palm Oil",           "BMD",   "Agriculture"),   # Bursa Malaysia Derivatives (MYR/MT)
]

# (symbol, name, market_cap_usd)
CRYPTO: list[tuple] = [
    # ── Top 10 by market cap ──────────────────────────────────────────────────
    ("BTC",   "Bitcoin",              1_800_000_000_000),
    ("ETH",   "Ethereum",               400_000_000_000),
    ("BNB",   "BNB",                     90_000_000_000),
    ("SOL",   "Solana",                 100_000_000_000),
    ("XRP",   "XRP",                    140_000_000_000),
    ("DOGE",  "Dogecoin",                50_000_000_000),
    ("ADA",   "Cardano",                 30_000_000_000),
    ("AVAX",  "Avalanche",               20_000_000_000),
    ("DOT",   "Polkadot",                12_000_000_000),
    ("LINK",  "Chainlink",               20_000_000_000),
    # ── 11–30 ─────────────────────────────────────────────────────────────────
    ("LTC",   "Litecoin",                10_000_000_000),
    ("BCH",   "Bitcoin Cash",            10_000_000_000),
    ("UNI",   "Uniswap",                  6_000_000_000),
    ("ATOM",  "Cosmos",                   3_500_000_000),
    ("XLM",   "Stellar",                  4_500_000_000),
    ("NEAR",  "NEAR Protocol",            5_000_000_000),
    ("ICP",   "Internet Computer",        4_000_000_000),
    ("APT",   "Aptos",                    4_000_000_000),
    ("ARB",   "Arbitrum",                 3_000_000_000),
    ("OP",    "Optimism",                 2_500_000_000),
    ("FIL",   "Filecoin",                 3_000_000_000),
    ("VET",   "VeChain",                  2_500_000_000),
    ("HBAR",  "Hedera",                   4_000_000_000),
    ("MNT",   "Mantle",                   3_500_000_000),
    ("INJ",   "Injective",                2_000_000_000),
    ("ALGO",  "Algorand",                 1_500_000_000),
    ("EGLD",  "MultiversX",               1_800_000_000),
    ("THETA", "Theta Network",            1_500_000_000),
    ("FTM",   "Fantom",                   1_200_000_000),
    ("SAND",  "The Sandbox",              1_000_000_000),
    # ── 31–50 ─────────────────────────────────────────────────────────────────
    ("AXS",   "Axie Infinity",            1_200_000_000),
    ("MANA",  "Decentraland",               800_000_000),
    ("CHZ",   "Chiliz",                     800_000_000),
    ("EOS",   "EOS",                        900_000_000),
    ("ZEC",   "Zcash",                      700_000_000),
    ("DASH",  "Dash",                       600_000_000),
    ("XTZ",   "Tezos",                      800_000_000),
    ("ENJ",   "Enjin Coin",                 400_000_000),
    ("BAT",   "Basic Attention Token",      600_000_000),
    ("GRT",   "The Graph",               1_500_000_000),
    ("FLOW",  "Flow",                       900_000_000),
    ("KAVA",  "Kava",                       700_000_000),
    ("ZIL",   "Zilliqa",                    500_000_000),
    ("WAVES", "Waves",                      400_000_000),
    ("ONT",   "Ontology",                   300_000_000),
    ("ICX",   "ICON",                       300_000_000),
    ("QTUM",  "Qtum",                       400_000_000),
    ("CRV",   "Curve DAO Token",          1_000_000_000),
    ("LDO",   "Lido DAO",                 1_500_000_000),
    ("RUNE",  "THORChain",                  800_000_000),
]

# (symbol, name, exchange, region, market_cap_usd)
INDICES: list[tuple] = [
    # US
    ("SPX",    "S&P 500",                      "NYSE",    "US",          None),
    ("NDX",    "Nasdaq 100",                   "NASDAQ",  "US",          None),
    ("DJI",    "Dow Jones Industrial Average", "NYSE",    "US",          None),
    ("RUT",    "Russell 2000",                 "NYSE",    "US",          None),
    ("VIX",    "CBOE Volatility Index",        "CBOE",    "US",          None),
    # Europe
    ("UKX",    "FTSE 100",                     "LSE",     "Europe",      None),
    ("DAX",    "DAX 40",                       "XETRA",   "Europe",      None),
    ("CAC",    "CAC 40",                       "EURONEXT","Europe",      None),
    ("IBEX",   "IBEX 35",                      "BME",     "Europe",      None),
    ("SMI",    "Swiss Market Index",           "SIX",     "Europe",      None),
    # Asia-Pacific
    ("NKY",    "Nikkei 225",                   "TSE",     "Asia",        None),
    ("HSI",    "Hang Seng Index",              "HKEX",    "Asia",        None),
    ("SHCOMP", "Shanghai Composite",           "SSE",     "Asia",        None),
    ("KOSPI",  "KOSPI",                        "KRX",     "Asia",        None),
    ("SENSEX", "BSE Sensex",                   "BSE",     "Asia",        None),
    ("ASX200", "ASX 200",                      "ASX",     "Asia",        None),
    # Other
    ("MSCIW",  "MSCI World",                   "MSCI",    "Global",      None),
    ("MSCIEM", "MSCI Emerging Markets",        "MSCI",    "Global",      None),
]

# (symbol, name, exchange, sector, market_cap_usd)
ETFS: list[tuple] = [
    # ── US Broad Market ───────────────────────────────────────────────────────
    ("SPY",   "SPDR S&P 500 ETF Trust",               "NYSE",   "Broad Market",      500_000_000_000),
    ("QQQ",   "Invesco QQQ Trust",                    "NASDAQ", "Technology",        250_000_000_000),
    ("IWM",   "iShares Russell 2000 ETF",             "NYSE",   "Broad Market",       60_000_000_000),
    ("VTI",   "Vanguard Total Stock Market ETF",      "NYSE",   "Broad Market",      350_000_000_000),
    ("VOO",   "Vanguard S&P 500 ETF",                 "NYSE",   "Broad Market",      450_000_000_000),
    ("DIA",   "SPDR Dow Jones Industrial Average ETF","NYSE",   "Broad Market",       30_000_000_000),
    ("SCHB",  "Schwab U.S. Broad Market ETF",         "NYSE",   "Broad Market",       25_000_000_000),
    ("ITOT",  "iShares Core S&P Total US Stock",      "NYSE",   "Broad Market",       50_000_000_000),
    ("IVV",   "iShares Core S&P 500 ETF",             "NYSE",   "Broad Market",      450_000_000_000),
    ("RSP",   "Invesco S&P 500 Equal Weight ETF",     "NYSE",   "Broad Market",       50_000_000_000),
    # ── US Sectors (SPDR) ─────────────────────────────────────────────────────
    ("XLF",   "Financial Select Sector SPDR",         "NYSE",   "Financials",         40_000_000_000),
    ("XLK",   "Technology Select Sector SPDR",        "NYSE",   "Technology",         65_000_000_000),
    ("XLE",   "Energy Select Sector SPDR",            "NYSE",   "Energy",             30_000_000_000),
    ("XLV",   "Health Care Select Sector SPDR",       "NYSE",   "Healthcare",         40_000_000_000),
    ("XLI",   "Industrial Select Sector SPDR",        "NYSE",   "Industrials",        20_000_000_000),
    ("XLY",   "Consumer Discretionary Select SPDR",   "NYSE",   "Consumer Disc.",     20_000_000_000),
    ("XLP",   "Consumer Staples Select Sector SPDR",  "NYSE",   "Consumer Staples",   15_000_000_000),
    ("XLU",   "Utilities Select Sector SPDR",         "NYSE",   "Utilities",          12_000_000_000),
    ("XLB",   "Materials Select Sector SPDR",         "NYSE",   "Materials",           6_000_000_000),
    ("XLRE",  "Real Estate Select Sector SPDR",       "NYSE",   "Real Estate",        10_000_000_000),
    ("XLC",   "Communication Services Select SPDR",   "NYSE",   "Communication",      17_000_000_000),
    # ── US Growth & Value ─────────────────────────────────────────────────────
    ("VUG",   "Vanguard Growth ETF",                  "NYSE",   "Growth",            100_000_000_000),
    ("VTV",   "Vanguard Value ETF",                   "NYSE",   "Value",             100_000_000_000),
    ("IWF",   "iShares Russell 1000 Growth ETF",      "NYSE",   "Growth",             90_000_000_000),
    ("IWD",   "iShares Russell 1000 Value ETF",       "NYSE",   "Value",              55_000_000_000),
    ("MTUM",  "iShares MSCI USA Momentum Factor ETF", "NYSE",   "Factor",             10_000_000_000),
    # ── Thematic / Innovation ─────────────────────────────────────────────────
    ("ARKK",  "ARK Innovation ETF",                   "NYSE",   "Innovation",          7_000_000_000),
    ("SOXX",  "iShares Semiconductor ETF",            "NASDAQ", "Semiconductors",     13_000_000_000),
    ("IBB",   "iShares Biotechnology ETF",            "NASDAQ", "Biotechnology",      10_000_000_000),
    ("CIBR",  "First Trust Nasdaq Cybersecurity ETF", "NASDAQ", "Cybersecurity",       5_000_000_000),
    ("CLOU",  "Global X Cloud Computing ETF",         "NASDAQ", "Cloud",               2_000_000_000),
    ("ROBO",  "ROBO Global Robotics & Automation ETF","NYSE",   "Robotics",            2_000_000_000),
    ("DRIV",  "Global X Autonomous & EV ETF",         "NASDAQ", "Electric Vehicles",   1_500_000_000),
    ("ICLN",  "iShares Global Clean Energy ETF",      "NASDAQ", "Clean Energy",        3_000_000_000),
    ("LIT",   "Global X Lithium & Battery Tech ETF",  "NYSE",   "Lithium",             2_000_000_000),
    ("COPX",  "Global X Copper Miners ETF",           "NYSE",   "Copper Mining",       1_000_000_000),
    ("JETS",  "U.S. Global Jets ETF",                 "NYSE",   "Airlines",              800_000_000),
    # ── Dividends & Income ────────────────────────────────────────────────────
    ("VYM",   "Vanguard High Dividend Yield ETF",     "NYSE",   "Dividends",          50_000_000_000),
    ("DVY",   "iShares Select Dividend ETF",          "NASDAQ", "Dividends",          15_000_000_000),
    ("SCHD",  "Schwab U.S. Dividend Equity ETF",      "NYSE",   "Dividends",          50_000_000_000),
    ("NOBL",  "ProShares S&P 500 Dividend Aristocrats","BATS",  "Dividends",          10_000_000_000),
    # ── International ─────────────────────────────────────────────────────────
    ("EEM",   "iShares MSCI Emerging Markets ETF",    "NYSE",   "Emerging Markets",   25_000_000_000),
    ("EFA",   "iShares MSCI EAFE ETF",                "NYSE",   "International",      45_000_000_000),
    ("VEA",   "Vanguard FTSE Developed Markets",      "NYSE",   "International",      95_000_000_000),
    ("EWJ",   "iShares MSCI Japan ETF",               "NYSE",   "Japan",               8_000_000_000),
    ("FXI",   "iShares China Large-Cap ETF",          "NYSE",   "China",               6_000_000_000),
    ("EWZ",   "iShares MSCI Brazil ETF",              "NYSE",   "Brazil",              5_000_000_000),
    ("EWG",   "iShares MSCI Germany ETF",             "NYSE",   "Germany",             3_000_000_000),
    ("EWY",   "iShares MSCI South Korea ETF",         "NYSE",   "South Korea",         4_000_000_000),
    ("EWT",   "iShares MSCI Taiwan ETF",              "NYSE",   "Taiwan",              5_000_000_000),
    ("EWH",   "iShares MSCI Hong Kong ETF",           "NYSE",   "Hong Kong",           2_000_000_000),
    ("EWA",   "iShares MSCI Australia ETF",           "NYSE",   "Australia",           2_000_000_000),
    ("EWU",   "iShares MSCI United Kingdom ETF",      "NYSE",   "UK",                  2_000_000_000),
    ("EWC",   "iShares MSCI Canada ETF",              "NYSE",   "Canada",              3_000_000_000),
    ("EWI",   "iShares MSCI Italy ETF",               "NYSE",   "Italy",               1_000_000_000),
    ("VWO",   "Vanguard FTSE Emerging Markets ETF",   "NYSE",   "Emerging Markets",   60_000_000_000),
    ("MCHI",  "iShares MSCI China ETF",               "NYSE",   "China",               5_000_000_000),
    ("INDA",  "iShares MSCI India ETF",               "NYSE",   "India",              10_000_000_000),
    # ── Fixed Income ─────────────────────────────────────────────────────────
    ("AGG",   "iShares Core US Aggregate Bond",       "NYSE",   "Bonds",             100_000_000_000),
    ("BND",   "Vanguard Total Bond Market ETF",       "NYSE",   "Bonds",              95_000_000_000),
    ("TLT",   "iShares 20+ Year Treasury Bond",       "NYSE",   "Bonds",              40_000_000_000),
    ("SHY",   "iShares 1-3 Year Treasury Bond ETF",   "NYSE",   "Short-Term Bonds",   25_000_000_000),
    ("IEF",   "iShares 7-10 Year Treasury Bond ETF",  "NYSE",   "Bonds",              25_000_000_000),
    ("HYG",   "iShares iBoxx High Yield Corp Bond",   "NYSE",   "High Yield Bonds",   14_000_000_000),
    ("LQD",   "iShares iBoxx Invest Grade Corp Bond", "NYSE",   "Corp Bonds",         26_000_000_000),
    ("TIPS",  "iShares TIPS Bond ETF",                "NYSE",   "Inflation Bonds",    16_000_000_000),
    ("EMB",   "iShares J.P. Morgan USD EM Bond ETF",  "NYSE",   "EM Bonds",           12_000_000_000),
    ("MUB",   "iShares National Muni Bond ETF",       "NYSE",   "Municipal Bonds",    25_000_000_000),
    ("VCIT",  "Vanguard Intermediate-Term Corp Bond", "NYSE",   "Corp Bonds",         40_000_000_000),
    ("VCSH",  "Vanguard Short-Term Corp Bond ETF",    "NYSE",   "Corp Bonds",         35_000_000_000),
    # ── Commodities ───────────────────────────────────────────────────────────
    ("GLD",   "SPDR Gold Shares",                     "NYSE",   "Gold",               55_000_000_000),
    ("IAU",   "iShares Gold Trust",                   "NYSE",   "Gold",               30_000_000_000),
    ("SLV",   "iShares Silver Trust",                 "NYSE",   "Silver",              9_000_000_000),
    ("USO",   "United States Oil Fund",               "NYSE",   "Energy",              1_500_000_000),
    ("UNG",   "United States Natural Gas Fund",       "NYSE",   "Natural Gas",           500_000_000),
    ("PDBC",  "Invesco Optimum Yield Diversified Commodity","NYSE","Commodities",       5_000_000_000),
    ("DJP",   "iPath Bloomberg Commodity Index",      "NYSE",   "Commodities",         1_000_000_000),
    # ── Real Estate ───────────────────────────────────────────────────────────
    ("VNQ",   "Vanguard Real Estate ETF",             "NYSE",   "Real Estate",        30_000_000_000),
    ("IYR",   "iShares U.S. Real Estate ETF",         "NYSE",   "Real Estate",         4_000_000_000),
    ("REM",   "iShares Mortgage Real Estate ETF",     "NYSE",   "Mortgage REITs",      1_000_000_000),
    # ── Volatility / Inverse ─────────────────────────────────────────────────
    ("UVXY",  "ProShares Ultra VIX Short-Term Futures","NYSE",  "Volatility",          1_000_000_000),
    ("SQQQ",  "ProShares UltraPro Short QQQ",         "NASDAQ", "Inverse",             3_000_000_000),
    ("SPXU",  "ProShares UltraPro Short S&P 500",     "NYSE",   "Inverse",             1_000_000_000),
    ("SH",    "ProShares Short S&P 500",              "NYSE",   "Inverse",             2_000_000_000),
    ("PSQ",   "ProShares Short QQQ",                  "NYSE",   "Inverse",             1_000_000_000),
    # ── Leveraged ─────────────────────────────────────────────────────────────
    ("TQQQ",  "ProShares UltraPro QQQ",               "NASDAQ", "Leveraged",          18_000_000_000),
    ("UPRO",  "ProShares UltraPro S&P 500",           "NYSE",   "Leveraged",           3_000_000_000),
    ("SPXL",  "Direxion Daily S&P 500 Bull 3X",       "NYSE",   "Leveraged",           3_000_000_000),
    ("TNA",   "Direxion Daily Small Cap Bull 3X",     "NYSE",   "Leveraged",           1_200_000_000),
]

# (symbol, name, exchange, maturity, yield_pct)
BONDS: list[tuple] = [
    # US Treasuries — yfinance: ^FVX/^TNX/^TYX; FRED: DGS2/DGS5/DGS10/DGS30
    ("US02Y",  "US Treasury 2-Year Note",       "FRED",   "2Y",   None),
    ("US05Y",  "US Treasury 5-Year Note",       "CBOT",   "5Y",   None),
    ("US10Y",  "US Treasury 10-Year Note",      "CBOT",   "10Y",  None),
    ("US30Y",  "US Treasury 30-Year Bond",      "CBOT",   "30Y",  None),
    # European/Japanese sovereign 10Y yields — no accessible free source from server (inactive)
    ("DE10Y",  "Germany Bund 10-Year",          "ECB",    "10Y",  None),
    ("GB10Y",  "UK Gilt 10-Year",               "BoE",    "10Y",  None),
    ("FR10Y",  "France OAT 10-Year",            "ECB",    "10Y",  None),
    ("IT10Y",  "Italy BTP 10-Year",             "ECB",    "10Y",  None),
    ("JP10Y",  "Japan JGB 10-Year",             "BoJ",    "10Y",  None),
    # Note: HYG, LQD, EMB are seeded as ETFs in ETFS list above
]

# (symbol, name, base_currency, quote_currency)
FX: list[tuple] = [
    ("EURUSD", "Euro / US Dollar",         "EUR", "USD"),
    ("GBPUSD", "British Pound / US Dollar","GBP", "USD"),
    ("USDJPY", "US Dollar / Japanese Yen", "USD", "JPY"),
    ("USDCNY", "US Dollar / Chinese Yuan", "USD", "CNY"),
    ("USDCHF", "US Dollar / Swiss Franc",  "USD", "CHF"),
    ("AUDUSD", "Australian Dollar / USD",  "AUD", "USD"),
    ("USDCAD", "US Dollar / Canadian Dollar","USD","CAD"),
    ("USDMXN", "US Dollar / Mexican Peso", "USD", "MXN"),
    ("USDBRL", "US Dollar / Brazilian Real","USD","BRL"),
    ("USDINR", "US Dollar / Indian Rupee", "USD", "INR"),
]


def seed_assets(db: Session) -> int:
    # Build country code → id lookup
    country_rows = db.execute(select(Country.code, Country.id)).all()
    country_map: dict[str, int] = {row.code: row.id for row in country_rows}

    if not country_map:
        log.warning("No countries in DB — run countries seeder first. Skipping country_id linking.")

    rows: list[dict] = []

    for symbol, name, exchange, sector, industry, country_code, market_cap in STOCKS:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.stock,
            "exchange": exchange,
            "currency": "USD",
            "sector": sector,
            "industry": industry,
            "country_id": country_map.get(country_code) if country_code else None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    COMMODITY_CURRENCY = {"PALM": "MYR"}  # Bursa Malaysia futures quoted in MYR
    for symbol, name, exchange, _category in COMMODITIES:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.commodity,
            "exchange": exchange,
            "currency": COMMODITY_CURRENCY.get(symbol, "USD"),
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": None,
            "is_active": True,
        })

    for symbol, name, market_cap in CRYPTO:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.crypto,
            "exchange": "CRYPTO",
            "currency": "USD",
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    for symbol, name, base, quote in FX:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.fx,
            "exchange": "FOREX",
            "currency": quote,
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": None,
            "base_currency": base,
            "quote_currency": quote,
            "is_active": True,
        })

    for symbol, name, exchange, region, market_cap in INDICES:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.index,
            "exchange": exchange,
            "currency": "USD",
            "sector": region,
            "industry": "Market Index",
            "country_id": None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    for symbol, name, exchange, sector, market_cap in ETFS:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.etf,
            "exchange": exchange,
            "currency": "USD",
            "sector": sector,
            "industry": "ETF",
            "country_id": None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    for symbol, name, exchange, maturity, _yield in BONDS:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.bond,
            "exchange": exchange,
            "currency": "USD",
            "sector": maturity,
            "industry": "Government Bond" if any(x in symbol for x in ["US","DE","GB","FR","IT","JP"]) else "Corporate Bond",
            "country_id": None,
            "market_cap_usd": None,
            "is_active": True,
        })

    stmt = insert(Asset).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_symbol_exchange",
        set_={col: stmt.excluded[col] for col in rows[0].keys() if col not in ("symbol", "exchange")},
    )
    db.execute(stmt)

    # Explicitly deactivate assets with no live data source.
    # These remain in DB for history but are hidden from API/frontend (is_active=False).
    # Format: (symbol, exchange_or_None) — exchange=None means deactivate all rows for that symbol.
    NO_DATA_SOURCE: list[tuple[str, str | None]] = [
        ("COAL",  None),    # No CME/NYMEX futures on yfinance (ICE/SGX only)
        ("NI",    "CME"),   # Nickel LME-only, no yfinance ticker — NOTE: NYSE:NI (NiSource) stays active
        ("PALM",  None),    # FCPO=F (Bursa Malaysia) not available via yfinance from this server
        ("DE10Y", None),    # No accessible free source from server
        ("GB10Y", None),    # No accessible free source from server
        ("FR10Y", None),    # No accessible free source from server
        ("IT10Y", None),    # No accessible free source from server
        ("JP10Y", None),    # No accessible free source from server
    ]
    for sym, exchange in NO_DATA_SOURCE:
        q = Asset.__table__.update().where(Asset.symbol == sym)
        if exchange:
            q = q.where(Asset.exchange == exchange)
        db.execute(q.values(is_active=False))
        log.info(f"Deactivated asset with no data source: {sym} (exchange={exchange or 'all'})")

    # Deactivate orphan duplicates created when exchange labels changed between runs.
    # Only the canonical exchange should remain active per symbol.
    CANONICAL_EXCHANGE: dict[str, str] = {
        "US02Y": "FRED",  # Treasury.gov source; CBOT/Treasury labels were transitional
        "ALI":   "CME",   # LME label was incorrect; CME is the yfinance source
        "ZNC":   "CME",   # LME label was incorrect; CME is the yfinance source
        "PALM":  "BMD",   # MDEX label was old; BMD is correct (all deactivated anyway)
    }
    for sym, keep_exchange in CANONICAL_EXCHANGE.items():
        db.execute(
            Asset.__table__.update()
            .where(Asset.symbol == sym, Asset.exchange != keep_exchange)
            .values(is_active=False)
        )

    db.commit()

    log.info(f"Upserted {len(rows)} assets ({len(STOCKS)} stocks, {len(COMMODITIES)} commodities, {len(CRYPTO)} crypto, {len(FX)} FX, {len(INDICES)} indices, {len(ETFS)} ETFs, {len(BONDS)} bonds)")
    return len(rows)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_assets(db)
        log.info(f"Done. {total} assets in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
