# R4 schema reconnaissance (read-only)

Purpose: identify tables/columns for dental charting, perio/BPE, clinical notes, and treatment planning in the live R4 DB (`sys2000`).

Run from the isolated tool container:

```bash
# Ensure env points at sys2000
sed -i 's/^R4_SQLSERVER_DB=.*/R4_SQLSERVER_DB=sys2000/' /home/amir/secrets/dental-pms-r4.env

cd ~/dental-pms
docker compose run --rm r4_import python -m app.scripts.r4_schema_recon > /tmp/r4_schema_recon_sys2000.txt
```

Do not commit output files; they may contain table/column names.
