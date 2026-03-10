"""
Notification delivery — Telegram Bot API + Resend (email).
Both functions return None on success, or an error string on failure.
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "alerts@metricshour.com")


def send_telegram(chat_id: str, text: str) -> str | None:
    """Send a Telegram message. Returns error string or None on success."""
    if not TELEGRAM_BOT_TOKEN:
        return "TELEGRAM_BOT_TOKEN not configured"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code != 200:
            return f"Telegram {r.status_code}: {r.text[:200]}"
        return None
    except Exception as e:
        return str(e)


def send_email(to: str, subject: str, html_body: str) -> str | None:
    """Send an email via Resend. Returns error string or None on success."""
    if not RESEND_API_KEY:
        return "RESEND_API_KEY not configured"
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM_EMAIL,
                "to": to,
                "subject": subject,
                "html": html_body,
            },
            timeout=10,
        )
        if r.status_code not in (200, 201):
            return f"Resend {r.status_code}: {r.text[:200]}"
        return None
    except Exception as e:
        return str(e)


def build_alert_email(symbol: str, name: str, condition: str, target: float, current: float) -> str:
    direction = "above" if condition == "above" else "below"
    color = "#10b981" if condition == "above" else "#f87171"
    arrow = "↑" if condition == "above" else "↓"
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#111827;border:1px solid #1f2937;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="background:#0d1117;padding:20px 28px;border-bottom:1px solid #1f2937;">
            <span style="font-size:13px;font-weight:700;color:#10b981;letter-spacing:2px;text-transform:uppercase;">MetricsHour</span>
            <span style="font-size:13px;color:#4b5563;margin-left:8px;">Price Alert Triggered</span>
          </td>
        </tr>
        <tr>
          <td style="padding:28px;">
            <p style="font-size:13px;color:#9ca3af;margin:0 0 6px 0;">Asset</p>
            <p style="font-size:24px;font-weight:800;color:#ffffff;margin:0 0 4px 0;">{symbol}</p>
            <p style="font-size:14px;color:#6b7280;margin:0 0 24px 0;">{name}</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>
                <td width="50%" style="padding-right:8px;">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:11px;color:#6b7280;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Current Price</p>
                    <p style="font-size:22px;font-weight:700;color:{color};margin:0;font-family:monospace;">${current:,.2f}</p>
                  </div>
                </td>
                <td width="50%" style="padding-left:8px;">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:11px;color:#6b7280;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Your Target</p>
                    <p style="font-size:22px;font-weight:700;color:#e5e7eb;margin:0;font-family:monospace;">{arrow} ${target:,.2f}</p>
                  </div>
                </td>
              </tr>
            </table>

            <p style="font-size:14px;color:#9ca3af;margin:0 0 24px 0;">
              <strong style="color:{color};">{symbol}</strong> has moved <strong style="color:{color};">{direction} ${target:,.2f}</strong> — your alert threshold.
            </p>

            <a href="https://metricshour.com/stocks/{symbol}" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:13px;padding:12px 24px;border-radius:8px;text-decoration:none;">View {symbol} →</a>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;border-top:1px solid #1f2937;">
            <p style="font-size:11px;color:#374151;margin:0;">
              You received this because you set a price alert on MetricsHour.
              <a href="https://metricshour.com/alerts" style="color:#4b5563;">Manage alerts →</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def send_welcome_email(to: str) -> str | None:
    """Send a welcome email to a new user."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#111827;border:1px solid #1f2937;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="background:#0d1117;padding:24px 28px;border-bottom:1px solid #1f2937;">
            <span style="font-size:20px;font-weight:800;color:#10b981;letter-spacing:1px;">METRICSHOUR</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 28px;">
            <p style="font-size:22px;font-weight:700;color:#ffffff;margin:0 0 8px 0;">Welcome aboard 👋</p>
            <p style="font-size:14px;color:#9ca3af;margin:0 0 28px 0;">You now have access to institutional-grade macro intelligence.</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td style="padding:0 6px 12px 0;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">🌍</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">196 Countries</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">GDP, inflation, trade, governance — 80+ indicators each</p>
                  </div>
                </td>
                <td style="padding:0 0 12px 6px;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">📈</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">Stock Exposure</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">See which countries drive every stock's revenue</p>
                  </div>
                </td>
              </tr>
              <tr>
                <td style="padding:0 6px 0 0;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">🔔</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">Price Alerts</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">Telegram + email when assets hit your targets</p>
                  </div>
                </td>
                <td style="padding:0 0 0 6px;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">⚡</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">Live Feed</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">Market-moving events personalised to your follows</p>
                  </div>
                </td>
              </tr>
            </table>

            <a href="https://metricshour.com" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:14px;padding:14px 28px;border-radius:8px;text-decoration:none;margin-bottom:24px;">Explore MetricsHour →</a>

            <p style="font-size:13px;color:#6b7280;margin:0;">
              Questions? Just reply to this email — I read every one.<br>
              <span style="color:#4b5563;">— The MetricsHour team</span>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;border-top:1px solid #1f2937;">
            <p style="font-size:11px;color:#374151;margin:0;">
              You're receiving this because you created an account at metricshour.com.
              <a href="https://metricshour.com" style="color:#4b5563;">Unsubscribe</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
    return send_email(to, "Welcome to MetricsHour 🌍", html)


def send_password_reset_email(to: str, token: str) -> str | None:
    """Send a password reset link via Resend."""
    frontend_url = os.environ.get("FRONTEND_URL", "https://metricshour.com")
    reset_url = f"{frontend_url}/auth/reset-password?token={token}"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#111827;border:1px solid #1f2937;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="background:#0d1117;padding:24px 28px;border-bottom:1px solid #1f2937;">
            <span style="font-size:20px;font-weight:800;color:#10b981;letter-spacing:1px;">METRICSHOUR</span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 28px;">
            <p style="font-size:22px;font-weight:700;color:#ffffff;margin:0 0 8px 0;">Reset your password</p>
            <p style="font-size:14px;color:#9ca3af;margin:0 0 28px 0;">Click the button below to set a new password. This link expires in 1 hour.</p>
            <a href="{reset_url}" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:14px;padding:14px 28px;border-radius:8px;text-decoration:none;margin-bottom:24px;">Reset Password →</a>
            <p style="font-size:12px;color:#6b7280;margin:0;">If you didn't request this, you can safely ignore this email.</p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;border-top:1px solid #1f2937;">
            <p style="font-size:11px;color:#374151;margin:0;">MetricsHour · metricshour.com</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return send_email(to, "Reset your MetricsHour password", html)


INDICATOR_LABELS: dict[str, tuple[str, str]] = {
    "gdp_growth_pct":                 ("GDP Growth",              "%"),
    "inflation_pct":                  ("Inflation Rate",          "%"),
    "unemployment_pct":               ("Unemployment Rate",       "%"),
    "government_debt_gdp_pct":        ("Govt Debt / GDP",         "%"),
    "budget_balance_gdp_pct":         ("Budget Balance / GDP",    "%"),
    "current_account_gdp_pct":        ("Current Account / GDP",   "%"),
    "interest_rate_pct":              ("Interest Rate",           "%"),
    "real_interest_rate_pct":         ("Real Interest Rate",      "%"),
    "money_supply_m2_gdp_pct":        ("M2 Supply / GDP",         "%"),
    "gdp_usd":                        ("GDP",                     "USD"),
    "gdp_per_capita_usd":             ("GDP per Capita",          "USD"),
    "exports_usd":                    ("Exports",                 "USD"),
    "imports_usd":                    ("Imports",                 "USD"),
    "fdi_inflows_usd":                ("FDI Inflows",             "USD"),
    "foreign_reserves_usd":           ("Foreign Reserves",        "USD"),
    "tax_revenue_gdp_pct":            ("Tax Revenue / GDP",       "%"),
    "military_spending_gdp_pct":      ("Military Spending / GDP", "%"),
    "gini_coefficient":               ("Gini Coefficient",        ""),
    "life_expectancy":                ("Life Expectancy",         "yrs"),
    "literacy_rate_pct":              ("Literacy Rate",           "%"),
    "internet_penetration_pct":       ("Internet Penetration",    "%"),
    "urban_population_pct":           ("Urban Population",        "%"),
    "control_of_corruption_index":    ("Corruption Control",      ""),
    "rule_of_law_index":              ("Rule of Law",             ""),
    "political_stability_index":      ("Political Stability",     ""),
    "government_effectiveness_index": ("Govt Effectiveness",      ""),
    "regulatory_quality_index":       ("Regulatory Quality",      ""),
    "voice_accountability_index":     ("Voice & Accountability",  ""),
}


def _fmt_macro(indicator_name: str, value: float) -> str:
    _, unit = INDICATOR_LABELS.get(indicator_name, ("", ""))
    if unit == "%":
        return f"{value:,.2f}%"
    if unit == "USD":
        if abs(value) >= 1_000_000_000_000:
            return f"${value / 1_000_000_000_000:.2f}T"
        if abs(value) >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        return f"${value:,.0f}"
    return f"{value:,.2f}"


def build_macro_alert_telegram(
    country_name: str, country_code: str,
    indicator_name: str, condition: str,
    threshold: float, current: float,
) -> str:
    label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
    emoji = "🟢" if condition == "above" else "🔴"
    direction = "crossed above ↑" if condition == "above" else "dropped below ↓"
    return (
        f"{emoji} <b>Macro Alert — {country_name}</b>\n"
        f"<b>{label}</b> has {direction} your threshold\n\n"
        f"<b>Current:</b> <code>{_fmt_macro(indicator_name, current)}</code>\n"
        f"<b>Threshold:</b> <code>{_fmt_macro(indicator_name, threshold)}</code>\n\n"
        f"<a href=\"https://metricshour.com/countries/{country_code.lower()}\">"
        f"View {country_name} on MetricsHour →</a>"
    )


def build_macro_alert_email(
    country_name: str, country_code: str,
    indicator_name: str, condition: str,
    threshold: float, current: float,
) -> str:
    label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
    color = "#10b981" if condition == "above" else "#f87171"
    arrow = "↑" if condition == "above" else "↓"
    direction = "above" if condition == "above" else "below"
    cur_fmt = _fmt_macro(indicator_name, current)
    thr_fmt = _fmt_macro(indicator_name, threshold)
    url = f"https://metricshour.com/countries/{country_code.lower()}"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0a0e1a;font-family:sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0e1a;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#111827;border:1px solid #1f2937;border-radius:12px;overflow:hidden;">
        <tr><td style="background:#0d1117;padding:20px 28px;border-bottom:1px solid #1f2937;">
          <span style="font-size:13px;font-weight:700;color:#10b981;letter-spacing:2px;text-transform:uppercase;">MetricsHour</span>
          <span style="font-size:13px;color:#4b5563;margin-left:8px;">Macro Alert</span>
        </td></tr>
        <tr><td style="padding:28px;">
          <p style="font-size:13px;color:#9ca3af;margin:0 0 4px 0;">Country</p>
          <p style="font-size:26px;font-weight:800;color:#ffffff;margin:0 0 4px 0;">{country_name}</p>
          <p style="font-size:14px;color:#6b7280;margin:0 0 24px 0;">{label}</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
            <tr>
              <td width="50%" style="padding-right:8px;">
                <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                  <p style="font-size:11px;color:#6b7280;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Current</p>
                  <p style="font-size:22px;font-weight:700;color:{color};margin:0;font-family:monospace;">{cur_fmt}</p>
                </div>
              </td>
              <td width="50%" style="padding-left:8px;">
                <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                  <p style="font-size:11px;color:#6b7280;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Threshold</p>
                  <p style="font-size:22px;font-weight:700;color:#e5e7eb;margin:0;font-family:monospace;">{arrow} {thr_fmt}</p>
                </div>
              </td>
            </tr>
          </table>
          <p style="font-size:14px;color:#9ca3af;margin:0 0 24px 0;">
            <strong style="color:{color};">{country_name}'s {label}</strong> is now
            <strong style="color:{color};">{direction} your {thr_fmt} threshold</strong>.
          </p>
          <a href="{url}" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:13px;padding:12px 24px;border-radius:8px;text-decoration:none;">View {country_name} →</a>
        </td></tr>
        <tr><td style="padding:16px 28px;border-top:1px solid #1f2937;">
          <p style="font-size:11px;color:#374151;margin:0;">You set this macro alert on MetricsHour.
            <a href="https://metricshour.com/alerts" style="color:#4b5563;">Manage alerts →</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def build_alert_telegram(symbol: str, name: str, condition: str, target: float, current: float) -> str:
    direction = "above ↑" if condition == "above" else "below ↓"
    emoji = "🟢" if condition == "above" else "🔴"
    diff_pct = abs(current - target) / target * 100
    return (
        f"{emoji} <b>Price Alert — {symbol}</b>\n"
        f"{name}\n\n"
        f"<b>Current:</b> <code>${current:,.2f}</code>\n"
        f"<b>Target:</b> {direction} <code>${target:,.2f}</code>\n"
        f"<b>Move:</b> {diff_pct:.1f}% from threshold\n\n"
        f"<a href=\"https://metricshour.com/stocks/{symbol}\">View {symbol} on MetricsHour →</a>"
    )
