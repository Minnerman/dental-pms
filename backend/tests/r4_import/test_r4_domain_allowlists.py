from app.scripts import r4_cohort_select, r4_import as r4_import_script, r4_parity_run


EXPECTED_ACTIVE_CHARTING_DOMAINS = (
    "appointment_notes",
    "bpe",
    "bpe_furcation",
    "chart_healing_actions",
    "completed_questionnaire_notes",
    "completed_treatment_findings",
    "old_patient_notes",
    "patient_notes",
    "perio_plaque",
    "perioprobe",
    "restorative_treatments",
    "temporary_notes",
    "treatment_notes",
    "treatment_plan_items",
    "treatment_plans",
)

REFERENCE_ONLY_CHARTING_DOMAINS = frozenset(
    {
        "fixed_note",
        "note_category",
        "tooth_surface",
        "tooth_system",
        "treatment_plan_review",
    }
)


def _sorted_domains(domains: set[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(domains))


def test_active_charting_domain_allowlists_match_documented_scope():
    expected = EXPECTED_ACTIVE_CHARTING_DOMAINS

    observed = {
        "r4_import._CHARTING_CANONICAL_DOMAINS": _sorted_domains(
            r4_import_script._CHARTING_CANONICAL_DOMAINS
        ),
        "r4_cohort_select.ALL_DOMAINS": _sorted_domains(r4_cohort_select.ALL_DOMAINS),
        "r4_parity_run.ALL_DOMAINS": _sorted_domains(r4_parity_run.ALL_DOMAINS),
    }

    assert len(expected) == 15
    assert not set(expected) & REFERENCE_ONLY_CHARTING_DOMAINS
    assert observed == {
        "r4_import._CHARTING_CANONICAL_DOMAINS": expected,
        "r4_cohort_select.ALL_DOMAINS": expected,
        "r4_parity_run.ALL_DOMAINS": expected,
    }
