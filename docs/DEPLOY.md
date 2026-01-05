# Deploy

## Prereqs
- Docker
- Docker Compose

## Clone (SSH)
```bash
git clone git@github.com:Minnerman/dental-pms.git
cd dental-pms
```

## Configure
```bash
cp .env.example .env
```
Never commit `.env`.

## Start / stop / restart
```bash
docker compose up -d
docker compose down
docker compose restart
```

## Health check
```bash
./ops/health.sh
```

## URLs / ports
- Frontend: `http://<server-ip>:3100`
- Backend: `http://<server-ip>:8100`
- DB: host `5442` -> container `5432`

## Troubleshooting
```bash
docker compose ps
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f db
ss -lntp | egrep ':3100|:8100|:5442'
```
