#!/bin/bash
# Frontend deploy: build → restart → purge CF cache.
# CF purge is mandatory: rebuilds change Nuxt chunk hashes, and stale HTML
# in CF will reference deleted chunk paths → 404s → broken hydration → ~3-5s LCP.
set -e

cd /root/metricshour/frontend
npm run build
systemctl restart metricshour-frontend
sleep 3
systemctl is-active metricshour-frontend

set -a
source /root/metricshour/backend/.env
set +a

curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $CF_CACHE_PURGE_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
echo
