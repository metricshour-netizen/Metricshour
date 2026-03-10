# Infrastructure

## Servers

| Server | IP | Role | Specs |
|--------|-----|------|-------|
| Netcup (main) | 159.195.29.136 | Core app | 12 CPU / 32GB / 1TB |
| Hetzner Finland | 89.167.35.114 | Services | 2 CPU / 4GB / 80GB |

## Network
- WireGuard tunnel: Netcup `10.0.0.1` ↔ Hetzner `10.0.0.2`
- Services on Hetzner connect to Postgres/DragonflyDB on Netcup via `10.0.0.1`

## Netcup Stack (systemd)
- PostgreSQL 17 + TimescaleDB
- DragonflyDB (Redis-compatible, 8GB)
- FastAPI + Gunicorn (8 workers)
- Celery Worker (8 concurrency, 3GB max)
- Celery Beat
- Nuxt SSR (Node, 1GB max)
- Nginx

## Hetzner Stack (Coolify → Docker)
- n8n (automation)
- Directus (CMS)
- Umami (analytics)
- Prometheus + Grafana (monitoring)

## Memory Budget (Netcup)
| Service | Allocation |
|---------|-----------|
| PostgreSQL shared_buffers | 8GB |
| DragonflyDB | 8GB |
| Gunicorn 8 workers | ~4GB |
| Celery 8 workers | 3GB max |
| Nuxt SSR | 1GB max |
| Docker | 1GB max |
| OS | ~2GB |
| **Free headroom** | **~5GB** |

## Deploy
```bash
# Netcup — deploy code changes
cd /root/metricshour
git pull
source workers/venv/bin/activate
cd backend && alembic upgrade head && cd ..
systemctl restart metricshour-api metricshour-worker metricshour-beat

# Rebuild frontend SSR
cd frontend && npm run build
systemctl restart metricshour-frontend
```

## WireGuard
See `wireguard/` for example configs. Never commit private keys.
```bash
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0
ping 10.0.0.2  # test tunnel from Netcup
```
