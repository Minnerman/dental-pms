from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


class ProbeJoinSource(R4SqlServerSource):
    def __init__(self, columns: dict[str, list[str]]):
        super().__init__(
            R4SqlServerConfig(
                enabled=False,
                host=None,
                port=1433,
                database=None,
                user=None,
                password=None,
                driver=None,
                encrypt=True,
                trust_cert=False,
                timeout_seconds=1,
            )
        )
        self._columns_cache = columns
        self.queries: list[str] = []
        self._first = True

    def _pick_column(self, table: str, candidates: list[str]):
        table_cols = self._columns_cache.get(table, [])
        for candidate in candidates:
            for col in table_cols:
                if col.lower() == candidate.lower():
                    return col
        return None

    def _query(self, sql: str, params=None):
        self.queries.append(sql)
        if self._first:
            self._first = False
            return [
                {
                    "trans_id": 10,
                    "tooth": 16,
                    "probing_point": 1,
                    "patient_code": 1000002,
                    "depth": 4,
                    "bleeding": 1,
                    "plaque": 0,
                    "recorded_at": None,
                }
            ]
        return []


def test_list_perio_probes_prefers_refid_with_transid_fallback_join_sql():
    source = ProbeJoinSource(
        {
            "PerioProbe": ["TransId", "Tooth", "ProbingPoint", "RefId"],
            "Transactions": ["RefId", "PatientCode"],
        }
    )

    rows = list(source.list_perio_probes(patients_from=1000000, patients_to=1000005, limit=1))

    assert len(rows) == 1
    assert rows[0].patient_code == 1000002
    sql = source.queries[0]
    assert "COALESCE(t_ref.patient_code, t_trans.patient_code)" in sql
    assert "t_ref.ref_id = pp.RefId" in sql
    assert "t_trans.ref_id = pp.TransId" in sql


def test_list_perio_probes_uses_transid_join_when_refid_missing():
    source = ProbeJoinSource(
        {
            "PerioProbe": ["TransId", "Tooth", "ProbingPoint"],
            "Transactions": ["RefId", "PatientCode"],
        }
    )

    rows = list(source.list_perio_probes(patients_from=1000000, patients_to=1000005, limit=1))

    assert len(rows) == 1
    sql = source.queries[0]
    assert "t_trans.ref_id = pp.TransId" in sql
    assert "COALESCE(t_ref.patient_code, t_trans.patient_code)" not in sql
