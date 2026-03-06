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
