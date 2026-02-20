import pytest

from app.services.tooth_state_classification import classify_tooth_state_type


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Implant retained crown", "implant"),
        ("Titanium fixture placement", "implant"),
        ("Bridge pontic adjustment", "bridge"),
        ("Maryland bridge review", "bridge"),
        ("White Crown", "crown"),
        ("Gold Cap", "crown"),
        ("Porcelain Veneer", "veneer"),
        ("Ceramic Inlay", "inlay_onlay"),
        ("Composite onlay", "inlay_onlay"),
        ("Post and core build-up", "post"),
        ("Core restoration", "post"),
        ("Root canal therapy", "root_canal"),
        ("RCT extirpation", "root_canal"),
        ("Endodontic treatment", "root_canal"),
        ("Composite filling", "filling"),
        ("Amalgam restoration", "filling"),
        ("Glass ionomer", "filling"),
        ("GIC restoration", "filling"),
        ("Simple extraction", "extraction"),
        ("XLA UL6", "extraction"),
        ("Partial denture repair", "denture"),
        ("Full upper denture", "denture"),
    ],
)
def test_classify_tooth_state_type_keyword_buckets(label: str, expected: str):
    assert classify_tooth_state_type(label) == expected


def test_classify_tooth_state_type_rule_order_prefers_implant():
    assert classify_tooth_state_type("Implant Crown") == "implant"


@pytest.mark.parametrize("label", [None, "", "   "])
def test_classify_tooth_state_type_empty_to_other(label: str | None):
    assert classify_tooth_state_type(label) == "other"


def test_classify_tooth_state_type_unknown_to_other():
    assert classify_tooth_state_type("Hygiene Review") == "other"

