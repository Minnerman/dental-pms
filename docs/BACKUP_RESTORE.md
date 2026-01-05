# Backup & Restore (Postgres)

## Warnings
- Restore overwrites data. Double-check the target before proceeding.
- Keep backups off the server too (encrypted external drive or secure cloud storage).
- Do not store passwords inside scripts or backup files.

## Option A: Logical backup (recommended)
Creates a timestamped SQL dump in `./backups/`.

```bash
./ops/db_backup.sh
```

Output example:
```
backups/dental-pms-20260105-2100.sql
```

## Option B: Volume snapshot (advanced)
If you manage Docker volume snapshots at the host or storage level, you can snapshot the Postgres volume (`dental_pms_db_data`). Only use this if you are comfortable with volume-level restores.

## Restore (from SQL dump)
```bash
CONFIRM=YES ./ops/db_restore.sh ./backups/dental-pms-YYYYmmdd-HHMM.sql
```

Notes:
- Requires the database container to be running.
- If you need to restore into a fresh DB, ensure the DB exists and credentials are correct before restoring.
