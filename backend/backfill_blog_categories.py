"""
Backfill category on existing blog posts using keyword matching on title + excerpt.

Run once after applying migration 0020:
  source /root/metricshour/workers/venv/bin/activate
  cd /root/metricshour/backend && python backfill_blog_categories.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.feed import BlogPost

# keyword → category (first match wins, order matters)
RULES: list[tuple[list[str], str]] = [
    # Crypto first — "bitcoin markets" should be crypto not markets
    (["bitcoin", "ethereum", "crypto", "btc", "eth", "defi", "blockchain", "digital asset",
      "web3", "altcoin", "stablecoin"], "crypto"),
    # FX
    (["currency", "forex", "exchange rate", "dollar strength", "euro zone", "yen", "pound",
      "usd ", "eur ", "gbp", "jpy", " fx ", "yuan", "renminbi", "rupee", "peso",
      "dollar index", "dxy"], "fx"),
    # Commodities
    (["oil price", "crude", "brent", "opec", "gold price", "silver", "copper", "wheat",
      "commodity", "commodities", "natural gas", "agriculture", "corn", "soybean",
      "lithium", "iron ore", "metals"], "commodities"),
    # Trade
    (["trade war", "tariff", "trade flow", "export", "import", "trade deficit",
      "trade surplus", "supply chain", "wto", "comtrade", "trade deal", "trade agreement",
      "trade balance", "bilateral trade"], "trade"),
    # Geopolitics
    (["sanction", "geopolit", "nato", "ukraine", "russia", "china risk", "taiwan",
      "middle east", "war ", "conflict", "election risk", "political risk",
      "energy security"], "geopolitics"),
    # Macro
    (["fed ", "federal reserve", "ecb", "boe", "boj", "boc", "rba", "imf",
      "interest rate", "rate hike", "rate cut", "inflation", "gdp", "recession",
      "central bank", "yield curve", "treasury yield", "monetary policy",
      "quantitative", "fiscal", "debt ceiling", "budget deficit"], "macro"),
    # Markets (equities)
    (["stock market", "s&p 500", "nasdaq", "earnings", "equity", "ipo", "valuation",
      "bull market", "bear market", "rally", "correction", "market crash",
      "dividend", "buyback", "hedge fund", "wall street"], "markets"),
    # Data / deep-dives
    (["data", "indicator", "statistics", "breakdown", "deep dive", "analysis",
      "report", "chart", "ranking", "comparison", "survey", "forecast"], "data"),
]


def infer_category(title: str, excerpt: str | None) -> str | None:
    text = (title + " " + (excerpt or "")).lower()
    for keywords, category in RULES:
        if any(kw in text for kw in keywords):
            return category
    return None


def main():
    db = SessionLocal()
    try:
        posts = db.query(BlogPost).filter(BlogPost.category.is_(None)).all()
        print(f"Posts without category: {len(posts)}")
        updated = 0
        for post in posts:
            cat = infer_category(post.title, post.excerpt)
            if cat:
                post.category = cat
                updated += 1
                print(f"  [{post.id}] {cat:15s} — {post.title[:70]}")
            else:
                print(f"  [{post.id}] {'(no match)':15s} — {post.title[:70]}")
        db.commit()
        print(f"\nUpdated {updated}/{len(posts)} posts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
