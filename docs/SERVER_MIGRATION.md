# Server Migration (Lift & Shift)

This guide is for moving the Dental PMS stack to a new Ubuntu server.

## 1) Install Docker + Compose
- Install Docker Engine and Docker Compose plugin on the new server.

## 2) Copy the repo
- Use git or rsync to copy `/home/amir/dental-pms` to the new server.

## 3) Copy environment file
- Copy `.env` to the new server (do not commit it).

## 4) Backup + restore Postgres volume
From the old server:
```bash
cd /home/amir/dental-pms
docker run --rm -v dental-pms_dental_pms_db_data:/v -v "$PWD":/b \
  busybox tar -czf /b/dbdata.tgz -C /v .
```

On the new server:
```bash
cd /home/amir/dental-pms
docker run --rm -v dental-pms_dental_pms_db_data:/v -v "$PWD":/b \
  busybox sh -c "rm -rf /v/* && tar -xzf /b/dbdata.tgz -C /v"
```

You can also use the helper scripts:
- `./ops/backup_db_volume.sh`
- `./ops/restore_db_volume.sh`

## 5) Start services
```bash
cd /home/amir/dental-pms
docker compose up -d --build
```

## 6) Run migrations
```bash
docker compose exec backend alembic upgrade head
```

If migrating an existing database that already has the tables/data, stamp the baseline once:
```bash
docker compose exec backend alembic stamp 0001_initial
docker compose exec backend alembic upgrade head
```
Then run upgrades on future releases with `alembic upgrade head`.

## 7) Verify
```bash
curl -fsS http://localhost:3100/api/health
./ops/health.sh
```

## DB migration strategy
- Alembic migrations live in `backend/alembic` and are applied with `alembic upgrade head`.
