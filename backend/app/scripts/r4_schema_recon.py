import os
import pyodbc
from datetime import datetime

HOST = os.environ["R4_SQLSERVER_HOST"]
PORT = os.environ.get("R4_SQLSERVER_PORT", "1433")
DB = os.environ["R4_SQLSERVER_DB"]
USER = os.environ["R4_SQLSERVER_USER"]
PW = os.environ["R4_SQLSERVER_PASSWORD"]
DRIVER = os.environ.get("R4_SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server")

CONN_STR = (
    f"DRIVER={{{DRIVER}}};SERVER={HOST},{PORT};DATABASE={DB};UID={USER};PWD={PW};"
    "Encrypt=no;TrustServerCertificate=yes;"
)

KEYWORDS = [
    "chart",
    "tooth",
    "odont",
    "perio",
    "bpe",
    "pocket",
    "probe",
    "treatment",
    "tx",
    "plan",
    "procedure",
    "clinical",
    "note",
    "diag",
    "appointment",
    "appts",
    "patient",
    "patients",
]


def main() -> None:
    cn = pyodbc.connect(CONN_STR, timeout=10, autocommit=True)
    cur = cn.cursor()

    tables = cur.execute(
        """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE='BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
    ).fetchall()

    matches: list[tuple[str, str]] = []
    for sch, name in tables:
        low = f"{sch}.{name}".lower()
        if any(k in low for k in KEYWORDS):
            matches.append((sch, name))

    print(f"# R4 schema recon (read-only) {datetime.utcnow().isoformat()}Z")
    print(f"# server={HOST}:{PORT} db={DB}")
    print("\n## Keyword-matched tables")
    for sch, name in matches:
        print(f"- {sch}.{name}")

    print("\n## Columns for matched tables")
    for sch, name in matches:
        cols = cur.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
                   COALESCE(CAST(CHARACTER_MAXIMUM_LENGTH AS VARCHAR(20)), '')
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA=? AND TABLE_NAME=?
            ORDER BY ORDINAL_POSITION
            """,
            sch,
            name,
        ).fetchall()
        print(f"\n### {sch}.{name}")
        for col, dtype, nullable, maxlen in cols:
            extra = f"({maxlen})" if maxlen else ""
            print(f"- {col}: {dtype}{extra} nullable={nullable}")


if __name__ == "__main__":
    main()
