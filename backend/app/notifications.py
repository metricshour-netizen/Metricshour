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
N8N_WELCOME_WEBHOOK = os.environ.get(
    "N8N_WELCOME_WEBHOOK",
    "https://n8n.metricshour.com/webhook/welcome-email",
)
N8N_MACRO_ALERT_WEBHOOK = os.environ.get(
    "N8N_MACRO_ALERT_WEBHOOK",
    "https://n8n.metricshour.com/webhook/macro-alert",
)
N8N_NEWSLETTER_WEBHOOK = os.environ.get(
    "N8N_NEWSLETTER_WEBHOOK",
    "https://n8n.metricshour.com/webhook/newsletter-subscribe",
)


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


def send_welcome_email(to: str, name: str = "") -> str | None:
    """Send a welcome email to a new user via n8n webhook (tracked in n8n execution history)."""
    try:
        r = requests.post(
            N8N_WELCOME_WEBHOOK,
            json={"email": to, "name": name or to.split("@")[0]},
            timeout=10,
        )
        if r.status_code not in (200, 201):
            logger.warning("n8n welcome webhook %s: %s", r.status_code, r.text[:200])
            # Fall back to direct Resend if n8n is unreachable
            return _send_welcome_direct(to)
        return None
    except Exception:
        logger.warning("n8n welcome webhook unreachable, falling back to direct send")
        return _send_welcome_direct(to)


def send_macro_alert_via_n8n(
    user_email: str,
    telegram_chat_id: str | None,
    notify_telegram: bool,
    notify_email: bool,
    country_name: str,
    country_code: str,
    indicator_name: str,
    condition: str,
    threshold: float,
    current_value: float,
    context: str | None = None,
) -> str | None:
    """
    Send macro alert via n8n webhook (full execution history + retry built-in).
    n8n handles Telegram + email delivery.
    Falls back to direct delivery if n8n is unreachable.
    Returns None on success, error string on total failure.
    """
    label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
    payload = {
        "user_email": user_email,
        "telegram_chat_id": telegram_chat_id,
        "notify_telegram": notify_telegram,
        "notify_email": notify_email,
        "country_name": country_name,
        "country_code": country_code,
        "indicator_name": indicator_name,
        "indicator_label": label,
        "condition": condition,
        "threshold": threshold,
        "threshold_fmt": _fmt_macro(indicator_name, threshold),
        "current_value": current_value,
        "current_fmt": _fmt_macro(indicator_name, current_value),
        "context": context or "",
        "country_url": f"https://metricshour.com/countries/{country_code.lower()}",
    }
    try:
        r = requests.post(N8N_MACRO_ALERT_WEBHOOK, json=payload, timeout=10)
        if r.status_code not in (200, 201):
            logger.error("n8n macro alert webhook %s: %s", r.status_code, r.text[:200])
            return _send_macro_alert_direct(
                user_email, telegram_chat_id, notify_telegram, notify_email,
                country_name, country_code, indicator_name, condition,
                threshold, current_value, context,
            )
        return None
    except Exception as e:
        logger.error("n8n macro alert webhook unreachable: %s — falling back to direct", e)
        return _send_macro_alert_direct(
            user_email, telegram_chat_id, notify_telegram, notify_email,
            country_name, country_code, indicator_name, condition,
            threshold, current_value, context,
        )


def _send_macro_alert_direct(
    user_email: str,
    telegram_chat_id: str | None,
    notify_telegram: bool,
    notify_email: bool,
    country_name: str,
    country_code: str,
    indicator_name: str,
    condition: str,
    threshold: float,
    current_value: float,
    context: str | None = None,
) -> str | None:
    """Direct fallback — sends Telegram + email without n8n."""
    delivered = False
    if notify_telegram and telegram_chat_id:
        msg = build_macro_alert_telegram(
            country_name, country_code, indicator_name, condition,
            threshold, current_value, context=context,
        )
        err = send_telegram(telegram_chat_id, msg)
        if err:
            logger.error("Direct Telegram fallback failed: %s", err)
        else:
            delivered = True
    if notify_email and user_email:
        label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
        subject = f"📊 Macro Alert: {country_name} — {label} | MetricsHour"
        html = build_macro_alert_email(
            country_name, country_code, indicator_name, condition,
            threshold, current_value, context=context,
        )
        err = send_email(user_email, subject, html)
        if err:
            logger.error("Direct email fallback failed: %s", err)
        else:
            delivered = True
    return None if delivered else "all delivery channels failed"


def _send_welcome_direct(to: str) -> str | None:
    """Fallback: send welcome email directly via Resend (bypasses n8n)."""
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



def send_newsletter_welcome(to: str, unsubscribe_token: str) -> str | None:
    """Send welcome email to new newsletter subscriber.

    Tries n8n webhook first (for automation/sequences); falls back to direct
    Resend if n8n is unreachable. Never silently fails — always returns None
    on success or an error string on failure.
    """
    unsubscribe_url = f"https://api.metricshour.com/api/newsletter/unsubscribe?token={unsubscribe_token}"

    # Try n8n first — lets us run welcome sequences, tagging, list management, etc.
    try:
        r = requests.post(
            N8N_NEWSLETTER_WEBHOOK,
            json={"email": to, "unsubscribe_url": unsubscribe_url, "unsubscribe_token": unsubscribe_token},
            timeout=8,
        )
        if r.status_code in (200, 201, 202):
            logger.info("Newsletter welcome sent via n8n for %s", to)
            return None
        logger.warning("n8n newsletter webhook returned %s — falling back to Resend", r.status_code)
    except Exception as exc:
        logger.warning("n8n newsletter webhook unreachable (%s) — falling back to Resend", exc)

    # Direct Resend fallback
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
            <p style="font-size:22px;font-weight:700;color:#ffffff;margin:0 0 8px 0;">You're in. Weekly macro intelligence incoming.</p>
            <p style="font-size:14px;color:#9ca3af;margin:0 0 24px 0;">Every week we send the most important macro moves — GDP shifts, trade flows, central bank decisions — explained in plain language.</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
              <tr>
                <td style="padding:0 6px 12px 0;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">🌍</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">196 Countries</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">GDP, inflation, trade — 80+ indicators each</p>
                  </div>
                </td>
                <td style="padding:0 0 12px 6px;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">📊</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">3,000+ Trade Pairs</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">Bilateral flows between every major economy</p>
                  </div>
                </td>
              </tr>
              <tr>
                <td style="padding:0 6px 0 0;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">📈</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">Stock Exposure</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">Which countries drive every stock's revenue</p>
                  </div>
                </td>
                <td style="padding:0 0 0 6px;" width="50%">
                  <div style="background:#0d1117;border:1px solid #1f2937;border-radius:8px;padding:16px;">
                    <p style="font-size:18px;margin:0 0 6px 0;">⚡</p>
                    <p style="font-size:13px;font-weight:700;color:#ffffff;margin:0 0 4px 0;">Live Feed</p>
                    <p style="font-size:11px;color:#6b7280;margin:0;">Market-moving events as they happen</p>
                  </div>
                </td>
              </tr>
            </table>

            <a href="https://metricshour.com" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:14px;padding:14px 28px;border-radius:8px;text-decoration:none;margin-bottom:24px;">Explore MetricsHour →</a>

            <p style="font-size:13px;color:#6b7280;margin:0;">
              Questions or story tips? Just reply — I read every one.<br>
              <span style="color:#4b5563;">— The MetricsHour team</span>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 28px;border-top:1px solid #1f2937;">
            <p style="font-size:11px;color:#374151;margin:0;">
              You subscribed at metricshour.com.
              <a href="{unsubscribe_url}" style="color:#4b5563;">Unsubscribe</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return send_email(to, "You're subscribed to MetricsHour Weekly", html)


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
    context: str | None = None,
) -> str:
    label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
    emoji = "🟢" if condition == "above" else "🔴"
    direction = "crossed above ↑" if condition == "above" else "dropped below ↓"
    parts = [
        f"{emoji} <b>Macro Alert — {country_name}</b>",
        f"<b>{label}</b> has {direction} your threshold\n",
        f"<b>Current:</b> <code>{_fmt_macro(indicator_name, current)}</code>",
        f"<b>Threshold:</b> <code>{_fmt_macro(indicator_name, threshold)}</code>",
    ]
    if context:
        parts.append(f"\n💡 {context}")
    parts.append(
        f"\n<a href=\"https://metricshour.com/countries/{country_code.lower()}\">"
        f"View {country_name} on MetricsHour →</a>"
    )
    return "\n".join(parts)


def build_macro_alert_email(
    country_name: str, country_code: str,
    indicator_name: str, condition: str,
    threshold: float, current: float,
    context: str | None = None,
) -> str:
    label, _ = INDICATOR_LABELS.get(indicator_name, (indicator_name, ""))
    color = "#10b981" if condition == "above" else "#f87171"
    arrow = "↑" if condition == "above" else "↓"
    direction = "above" if condition == "above" else "below"
    cur_fmt = _fmt_macro(indicator_name, current)
    thr_fmt = _fmt_macro(indicator_name, threshold)
    url = f"https://metricshour.com/countries/{country_code.lower()}"
    context_block = ""
    if context:
        context_block = f"""
        <div style="background:#0d1117;border-left:3px solid #10b981;border-radius:0 8px 8px 0;padding:16px 20px;margin-bottom:24px;">
          <p style="font-size:11px;font-weight:700;color:#10b981;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:1px;">💡 Analysis</p>
          <p style="font-size:13px;color:#d1d5db;margin:0;line-height:1.6;">{context}</p>
        </div>"""
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
                  <p style="font-size:11px;color:#6b7280;margin:0 0 6px 0;text-transform:uppercase;letter-spacing:1px;">Your Threshold</p>
                  <p style="font-size:22px;font-weight:700;color:#e5e7eb;margin:0;font-family:monospace;">{arrow} {thr_fmt}</p>
                </div>
              </td>
            </tr>
          </table>
          {context_block}
          <a href="{url}" style="display:inline-block;background:#10b981;color:#000000;font-weight:700;font-size:13px;padding:12px 24px;border-radius:8px;text-decoration:none;">View {country_name} on MetricsHour →</a>
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
