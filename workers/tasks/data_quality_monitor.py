"""
Data Quality Monitoring Task
Checks freshness and validity of all critical data sources.
Runs daily and sends alerts to Telegram if issues detected.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from celery import shared_task
from sqlalchemy import text
from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

@shared_task
def check_data_quality() -> Dict:
    """
    Check data quality across all critical tables.
    Returns dict with issues found.
    """
    issues = []
    warnings = []
    
    # 1. Check data freshness
    freshness_checks = [
        ("prices", "timestamp", "1 day", "Stock/crypto prices"),
        ("country_indicators", "period_date", "30 days", "Economic indicators"),
        ("countries", "credit_rating_updated", "90 days", "Country credit ratings"),
    ]
    
    for table, date_column, max_age, description in freshness_checks:
        try:
            with SessionLocal() as db:
                query = text(f"""
                    SELECT MAX({date_column}) as latest, COUNT(*) as count
                    FROM {table}
                    WHERE {date_column} IS NOT NULL
                """)
                result = db.execute(query).fetchone()
                
                if not result or not result.latest:
                    warnings.append(f"{description}: No data found")
                    continue
                    
                latest = result.latest
                count = result.count
                
                # Handle timezone-aware datetimes
                now_utc = datetime.now(timezone.utc)
                if isinstance(latest, datetime):
                    if latest.tzinfo is None:
                        # Make naive datetime timezone-aware (assume UTC)
                        latest = latest.replace(tzinfo=timezone.utc)
                    age = now_utc - latest
                else:
                    # Convert date to datetime for comparison
                    latest_dt = datetime.combine(latest, datetime.min.time()).replace(tzinfo=timezone.utc)
                    age = now_utc - latest_dt
                
                # Parse max_age string like "1 day", "30 days"
                if "day" in max_age:
                    days = int(max_age.split()[0])
                    max_timedelta = timedelta(days=days)
                else:
                    max_timedelta = timedelta(days=30)  # default
                
                if age > max_timedelta:
                    issues.append(f"{description}: Data is {age.days} days old (max: {days}d)")
                elif age > max_timedelta / 2:
                    warnings.append(f"{description}: Data is {age.days} days old")
                    
                logger.info(f"{table}: {count} rows, latest: {latest}, age: {age}")
                
        except Exception as e:
            warnings.append(f"{description}: Check failed - {str(e)}")
    
    # 2. Check data validity (basic sanity checks)
    validity_checks = [
        ("SELECT COUNT(*) FROM prices WHERE close <= 0", "prices", "Non-positive prices"),
        ("SELECT COUNT(*) FROM country_indicators WHERE value IS NULL", "country_indicators", "Null indicator values"),
        ("SELECT COUNT(*) FROM countries WHERE area_km2 IS NOT NULL AND area_km2 <= 0", "countries", "Non-positive area"),
    ]
    
    for query_str, table, description in validity_checks:
        try:
            with SessionLocal() as db:
                result = db.execute(text(query_str)).scalar()
                if result and result > 0:
                    warnings.append(f"{description}: {result} invalid rows in {table}")
        except Exception as e:
            logger.warning(f"Validity check failed for {table}: {e}")
    
    # 3. Check row counts (ensure data hasn't disappeared)
    count_checks = [
        ("countries", 100, "Country data"),
        ("country_indicators", 1000, "Indicator data"),
        ("prices", 10000, "Price data"),
        ("stock_country_revenues", 100, "Stock-country revenue data"),
    ]
    
    for table, min_rows, description in count_checks:
        try:
            with SessionLocal() as db:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                if result < min_rows:
                    issues.append(f"{description}: Only {result} rows (min: {min_rows})")
        except Exception as e:
            issues.append(f"{description}: Count check failed - {str(e)}")
    
    # 4. Compile report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "issues": issues,
        "warnings": warnings,
        "status": "OK" if not issues else "ISSUES",
        "summary": f"{len(issues)} issues, {len(warnings)} warnings"
    }
    
    # 5. Send alert if issues found
    if issues:
        send_alert(report)
    
    logger.info(f"Data quality check complete: {report['summary']}")
    return report

def send_alert(report: Dict) -> None:
    """Send alert to configured channel (Telegram)."""
    alert_msg = f"🚨 DATA QUALITY ALERT\n{report['summary']}\nIssues: {report['issues']}"
    logger.error(alert_msg)
    
    # Send to Telegram
    try:
        from app.notifications import send_telegram
        import os
        
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "7884960961")
        if telegram_chat_id:
            error = send_telegram(telegram_chat_id, alert_msg)
            if error:
                logger.warning(f"Failed to send Telegram alert: {error}")
            else:
                logger.info("Data quality alert sent to Telegram")
    except Exception as e:
        logger.warning(f"Could not send Telegram alert: {e}")

if __name__ == "__main__":
    # For manual testing
    result = check_data_quality()
    print(result)
