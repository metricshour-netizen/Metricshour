"""
Security monitor — hourly Celery task.
Checks SSH brute-force, nginx error spikes, fail2ban bans, UFW surges, open ports.
Sends Telegram alert if anomalies detected.
"""
import os
import subprocess
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

# Thresholds
SSH_FAIL_THRESHOLD = 50        # >50 SSH failures/hour
NGINX_5XX_THRESHOLD = 100      # >100 5xx/hour
NGINX_4XX_THRESHOLD = 1000     # >1000 4xx/hour (scans/fuzzing)
NGINX_TOTAL_THRESHOLD = 10000  # >10k requests/hour (DDoS)
UFW_BLOCK_THRESHOLD = 500      # >500 UFW blocks/hour
EXPECTED_PORTS = {22, 80, 443, 8000, 3000, 5432, 6379, 8090, 9100, 51820}


def _run(cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def _int(s: str) -> int:
    try:
        return int(s.strip().split()[0])
    except (ValueError, IndexError):
        return 0


def _send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("Telegram not configured")
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


@shared_task(name="tasks.security_monitor.run_security_checks", bind=True, max_retries=0)
def run_security_checks(self):
    """Hourly security scan — alert on anomalies."""
    alerts = []

    # --- 1. SSH brute-force ---
    ssh_count = _int(_run(
        "journalctl -u ssh --since='1 hour ago' --no-pager 2>/dev/null "
        "| grep -c 'Failed password\\|Invalid user\\|authentication failure' || echo 0"
    ))
    if ssh_count > SSH_FAIL_THRESHOLD:
        top = _run(
            "journalctl -u ssh --since='1 hour ago' --no-pager 2>/dev/null "
            "| grep -oE '[0-9]{1,3}(\\.[0-9]{1,3}){3}' | sort | uniq -c | sort -rn | head -5"
        )
        alerts.append(
            f"🚨 <b>SSH brute-force spike</b>: {ssh_count} failed attempts in 1h\n"
            f"<code>{top}</code>"
        )

    # --- 2. Nginx 5xx spike ---
    nx5 = _int(_run(
        "awk -v t=\"$(date -d '1 hour ago' +'%d/%b/%Y:%H:%M:%S')\" "
        "'$4>\"/\"t{print $9}' /var/log/nginx/access.log 2>/dev/null | grep -c '^5' || echo 0"
    ))
    nx4 = _int(_run(
        "awk -v t=\"$(date -d '1 hour ago' +'%d/%b/%Y:%H:%M:%S')\" "
        "'$4>\"/\"t{print $9}' /var/log/nginx/access.log 2>/dev/null | grep -c '^4' || echo 0"
    ))
    if nx5 > NGINX_5XX_THRESHOLD:
        top = _run(
            "awk -v t=\"$(date -d '1 hour ago' +'%d/%b/%Y:%H:%M:%S')\" "
            "'$4>\"/\"t && $9~/^5/{print $1}' /var/log/nginx/access.log 2>/dev/null "
            "| sort | uniq -c | sort -rn | head -5"
        )
        alerts.append(f"🚨 <b>Nginx 5xx spike</b>: {nx5} errors in 1h\n<code>{top}</code>")
    if nx4 > NGINX_4XX_THRESHOLD:
        alerts.append(f"⚠️ <b>Nginx 4xx spike</b>: {nx4} errors in 1h (possible scan/fuzzing)")

    # --- 3. fail2ban new bans ---
    new_bans = _int(_run(
        "grep 'Ban ' /var/log/fail2ban.log 2>/dev/null "
        "| awk -v t=\"$(date -d '1 hour ago' +'%Y-%m-%d %H:%M:%S')\" '$1\" \"$2>=t' | wc -l || echo 0"
    ))
    if new_bans > 10:
        top = _run(
            "grep 'Ban ' /var/log/fail2ban.log 2>/dev/null "
            "| awk -v t=\"$(date -d '1 hour ago' +'%Y-%m-%d %H:%M:%S')\" '$1\" \"$2>=t{print $NF}' "
            "| sort | uniq -c | sort -rn | head -5"
        )
        alerts.append(f"⚠️ <b>fail2ban</b>: {new_bans} new bans in 1h\n<code>{top}</code>")

    # --- 4. UFW block surge ---
    ufw_recent = _int(_run(
        "grep 'UFW BLOCK' /var/log/ufw.log 2>/dev/null "
        "| awk -v t=\"$(date -d '1 hour ago' +'%b %_d %H:%M:%S')\" '$0>=t' | wc -l || echo 0"
    ))
    if ufw_recent > UFW_BLOCK_THRESHOLD:
        top = _run(
            "grep 'UFW BLOCK' /var/log/ufw.log 2>/dev/null "
            "| awk -v t=\"$(date -d '1 hour ago' +'%b %_d %H:%M:%S')\" '$0>=t{print}' "
            "| grep -oE 'SRC=[0-9.]+' | sort | uniq -c | sort -rn | head -5"
        )
        alerts.append(
            f"⚠️ <b>UFW surge</b>: {ufw_recent} blocked packets in 1h\n<code>{top}</code>"
        )

    # --- 5. High total request volume (possible DDoS) ---
    nx_total = _int(_run(
        "awk -v t=\"$(date -d '1 hour ago' +'%d/%b/%Y:%H:%M:%S')\" "
        "'$4>\"/\"t' /var/log/nginx/access.log 2>/dev/null | wc -l || echo 0"
    ))
    if nx_total > NGINX_TOTAL_THRESHOLD:
        top_ips = _run(
            "awk -v t=\"$(date -d '1 hour ago' +'%d/%b/%Y:%H:%M:%S')\" "
            "'$4>\"/\"t{print $1}' /var/log/nginx/access.log 2>/dev/null "
            "| sort | uniq -c | sort -rn | head -5"
        )
        alerts.append(
            f"🚨 <b>Traffic spike (possible DDoS)</b>: {nx_total:,} requests in 1h\n<code>{top_ips}</code>"
        )

    # --- 6. Unexpected open ports ---
    ports_raw = _run("ss -tlnp | awk 'NR>1{print $4}' | grep -oE ':[0-9]+$' | tr -d ':'")
    open_ports = {int(p) for p in ports_raw.split() if p.isdigit()}
    unexpected = open_ports - EXPECTED_PORTS
    if unexpected:
        alerts.append(
            f"⚠️ <b>Unexpected port(s) open</b>: {', '.join(str(p) for p in sorted(unexpected))}\n"
            f"Run: <code>ss -tlnp</code>"
        )

    if alerts:
        msg = "🔐 <b>MetricsHour Security Monitor</b>\n\n" + "\n\n".join(alerts)
        _send_telegram(msg)
        logger.warning(f"Security: {len(alerts)} alert(s) sent")
    else:
        logger.info("Security check OK — no anomalies")

    return {"alerts_sent": len(alerts)}
