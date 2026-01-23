from app.services.r4_import.sqlserver_source import R4SqlServerConfig, R4SqlServerSource


class FakeSqlServerSource(R4SqlServerSource):
    def __init__(self, columns, counts, samples):
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
        self._counts = counts
        self._samples = samples

    def _pick_column(self, table: str, candidates: list[str]):
        for candidate in candidates:
            if candidate in self._columns_cache.get(table, []):
                return candidate
        return None

    def _count_table(self, table: str, where_clause: str = "", params=None) -> int:
        key = table + ":" + where_clause.split("/*")[1].split("*/")[0] if "/*" in where_clause else table
        return self._counts.get(key, self._counts.get(table, 0))

    def _query(self, sql: str, params=None):
        for token, payload in self._samples.items():
            if token in sql:
                return payload
        return [{"count": self._counts.get(sql, 0)}]


def test_perio_probe_linkage_summary_ok():
    columns = {
        "PerioProbe": ["TransId"],
        "Transactions": ["RefId", "PatientCode"],
    }
    counts = {
        "PerioProbe": 10,
        "PerioProbe:perio_probe_with_transaction": 9,
        "PerioProbe:perio_probe_with_patient": 8,
        "/*perio_probe_ambiguous_count*/": 1,
    }
    samples = {
        "perio_probe_ambiguous_count": [{"count": 1}],
        "perio_probe_sample_ambiguous": [{"trans_id": 101}],
        "perio_probe_sample_unlinked_trans": [{"trans_id": 102}],
        "perio_probe_sample_unlinked_patient": [{"trans_id": 103}],
    }
    source = FakeSqlServerSource(columns, counts, samples)
    summary = source.perio_probe_linkage_summary()

    assert summary["status"] == "ok"
    assert summary["total_probes"] == 10
    assert summary["probes_with_transaction"] == 9
    assert summary["probes_with_patient"] == 8
    assert summary["ambiguous_trans_ids"] == 1
    assert summary["sample_ambiguous_trans_ids"] == [101]


def test_perio_probe_pipeline_summary_ok():
    columns = {
        "PerioProbe": ["TransId"],
        "Transactions": ["RefId", "PatientCode"],
    }
    counts = {
        "PerioProbe": 20,
        "PerioProbe:perio_probe_pipeline_with_transaction": 20,
        "PerioProbe:perio_probe_pipeline_with_patient": 18,
        "PerioProbe:perio_probe_pipeline_with_unique": 15,
    }
    samples = {
        "perio_probe_pipeline_after_filters": [{"count": 5}],
        "perio_probe_pipeline_sample_filtered": [
            {"trans_id": 2, "patient_code": 1000},
            {"trans_id": 3, "patient_code": 1000},
        ],
    }
    source = FakeSqlServerSource(columns, counts, samples)
    summary = source.perio_probe_pipeline_summary(patients_from=1000, patients_to=1000, limit=5)

    assert summary["status"] == "ok"
    assert summary["perio_probes_total_source"] == 20
    assert summary["perio_probes_after_join_transactions"] == 20
    assert summary["perio_probes_after_patient_link"] == 15
    assert summary["perio_probes_after_filters"] == 5
    assert summary["sample_filtered_trans_ids"] == [2, 3]


def test_perio_probe_patient_summary_ok():
    columns = {
        "PerioProbe": ["TransId", "Tooth", "ProbingPoint"],
        "Transactions": ["RefId", "PatientCode"],
    }
    samples = {
        "perio_probe_patient_total": [{"count": 12}],
        "perio_probe_patient_unique": [{"count": 10}],
    }
    source = FakeSqlServerSource(columns, counts={}, samples=samples)
    summary = source.perio_probe_patient_summary(patients_from=1000, patients_to=1000)

    assert summary["status"] == "ok"
    assert summary["total_rows"] == 12
    assert summary["unique_rows"] == 10
    assert summary["duplicate_rows"] == 2


def test_bpe_furcation_linkage_summary_unsupported():
    source = FakeSqlServerSource(columns={}, counts={}, samples={})
    summary = source.bpe_furcation_linkage_summary()
    assert summary["status"] == "unsupported"


def test_bpe_furcation_linkage_summary_refid_supported():
    columns = {
        "BPE": ["RefId", "PatientCode"],
        "BPEFurcation": ["BPEID"],
    }
    counts = {
        "BPEFurcation": 3,
        "BPEFurcation:bpe_furcation_with_bpe": 3,
        "BPEFurcation:bpe_furcation_with_patient": 3,
        "/*bpe_furcation_ambiguous_count*/": 0,
    }
    samples = {
        "bpe_furcation_sample_unlinked": [],
        "bpe_furcation_sample_ambiguous": [],
    }
    source = FakeSqlServerSource(columns, counts, samples)
    summary = source.bpe_furcation_linkage_summary()
    assert summary["status"] == "ok"
    assert summary["total_furcations"] == 3
