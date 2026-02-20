#!/bin/bash
# MetricsHour deploy setup — run once on fresh server
# Usage: bash /root/metricshour/deploy/setup.sh

set -e

echo "=== Installing Nginx ==="
apt update && apt install -y nginx certbot python3-certbot-nginx

echo "=== Creating log directory ==="
mkdir -p /var/log/metricshour

echo "=== Copying systemd services ==="
cp /root/metricshour/deploy/metricshour-api.service    /etc/systemd/system/
cp /root/metricshour/deploy/metricshour-worker.service /etc/systemd/system/

echo "=== Enabling Nginx config ==="
cp /root/metricshour/deploy/nginx.conf /etc/nginx/sites-available/metricshour
ln -sf /etc/nginx/sites-available/metricshour /etc/nginx/sites-enabled/metricshour
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "=== Starting services ==="
systemctl daemon-reload
systemctl enable metricshour-api metricshour-worker
systemctl start metricshour-api metricshour-worker

echo ""
echo "=== Status ==="
systemctl status metricshour-api --no-pager
systemctl status metricshour-worker --no-pager

echo ""
echo "=== Next: SSL ==="
echo "Once DNS is pointed to this server (89.167.35.114), run:"
echo "  certbot --nginx -d api.metricshour.com"
